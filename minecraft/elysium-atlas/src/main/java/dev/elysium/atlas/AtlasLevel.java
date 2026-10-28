package dev.elysium.atlas;

import java.io.DataInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.NoSuchFileException;
import java.nio.file.Path;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;
import java.util.zip.GZIPInputStream;

/**
 * One resolution level of the atlas: square tiles of cells, loaded on first use and dropped least recently used
 * first once the level holds more than its cap (system property elysium_atlas.tileCacheMB, default 256, per level;
 * a tile is 256 KB). Tile layout matches bake_atlas.py write_tiles().
 */
public final class AtlasLevel {
    private static final short NO_HEIGHT = Short.MIN_VALUE;

    public final String name;
    public final Path dir;
    public final int cell, tileSize;
    private final ConcurrentHashMap<Long, Slot> tiles = new ConcurrentHashMap<>();
    private final int cap;
    private final AtomicLong clock = new AtomicLong();
    private final AtomicBoolean evicting = new AtomicBoolean();

    private static final class Slot {
        final Tile tile;
        volatile long used;
        Slot(Tile t, long used) { tile = t; this.used = used; }
    }

    record Tile(int tx, int tz, short[] h, byte[] relief, byte[] biome) {
        static final Tile EMPTY = new Tile(Integer.MIN_VALUE, Integer.MIN_VALUE, null, null, null);
    }

    private final ThreadLocal<Tile> last = ThreadLocal.withInitial(() -> Tile.EMPTY);

    AtlasLevel(String name, Path dir, int cell, int tileSize) {
        this.name = name; this.dir = dir; this.cell = cell; this.tileSize = tileSize;
        long mb = Long.getLong("elysium_atlas.tileCacheMB", 256);
        cap = (int) Math.max(8, mb * 1024 * 1024 / Math.max(1, (long) tileSize * tileSize * 4));
    }

    /** Tiles held now (for /atlas and tests). */
    public int cachedTiles() { return tiles.size(); }

    private Tile tile(int tx, int tz) {
        Tile t = last.get();
        if (t.tx == tx && t.tz == tz) return t;
        long key = ((long) tx << 32) ^ (tz & 0xffffffffL), now = clock.incrementAndGet();
        Slot slot = tiles.computeIfAbsent(key, k -> new Slot(load(tx, tz), now));
        slot.used = now;
        t = slot.tile;
        if (tiles.size() > cap) evict();
        // EMPTY keeps its sentinel coordinates, so remember the miss under this key instead
        last.set(t == Tile.EMPTY ? new Tile(tx, tz, null, null, null) : t);
        return t;
    }

    /** Drops the least recently used eighth of the cap; one thread at a time, the others carry on. */
    private void evict() {
        if (!evicting.compareAndSet(false, true)) return;
        try {
            int drop = tiles.size() - cap + cap / 8;
            if (drop <= 0) return;
            long[] stamps = tiles.values().stream().mapToLong(sl -> sl.used).sorted().toArray();
            long cut = stamps[Math.min(drop, stamps.length) - 1];
            tiles.values().removeIf(sl -> sl.used <= cut);
        } finally {
            evicting.set(false);
        }
    }

    private Tile load(int tx, int tz) {
        Path p = dir.resolve(tx + "_" + tz + ".bin.gz");
        try (InputStream in = new GZIPInputStream(Files.newInputStream(p), 1 << 16)) {
            int n = tileSize * tileSize;
            byte[] raw = new DataInputStream(in).readNBytes(8 + n * 4);
            ByteBuffer bb = ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN);
            if (raw.length != 8 + n * 4 || bb.getInt(0) != 0x4C544145 /* "EATL" */ || bb.getShort(6) != tileSize)
                throw new IOException("bad tile header or size");
            short[] h = new short[n];
            bb.position(8); bb.asShortBuffer().get(h);
            byte[] r = new byte[n], b = new byte[n];
            System.arraycopy(raw, 8 + 2 * n, r, 0, n);
            System.arraycopy(raw, 8 + 3 * n, b, 0, n);
            return new Tile(tx, tz, h, r, b);
        } catch (NoSuchFileException e) {
            return Tile.EMPTY;
        } catch (IOException e) {
            Atlas.LOG.error("Atlas tile {} unreadable, treating as missing", p, e);
            return Tile.EMPTY;
        }
    }

    /** Raw height (Y * 8) of cell (i, j), or NO_HEIGHT. */
    private short h(int i, int j) {
        Tile t = tile(Math.floorDiv(i, tileSize), Math.floorDiv(j, tileSize));
        if (t.h == null) return NO_HEIGHT;
        return t.h[Math.floorMod(j, tileSize) * tileSize + Math.floorMod(i, tileSize)];
    }

    private static void weights(double t, double[] w) {
        double t2 = t * t, t3 = t2 * t;
        w[0] = (-t3 + 2 * t2 - t) / 2; w[1] = (3 * t3 - 5 * t2 + 2) / 2; w[2] = (-3 * t3 + 4 * t2 + t) / 2; w[3] = (t3 - t2) / 2;
    }

    /** Catmull-Rom surface height in blocks at a block position, or NaN if any of the 4x4 cells is missing. */
    public double height(double x, double z) {
        double u = x / cell - 0.5, v = z / cell - 0.5;
        int iu = (int) Math.floor(u), iv = (int) Math.floor(v);
        double[] wu = new double[4], wv = new double[4];
        weights(u - iu, wu); weights(v - iv, wv);
        double sum = 0;
        for (int b = 0; b < 4; b++) {
            double row = 0;
            for (int a = 0; a < 4; a++) {
                short s = h(iu + a - 1, iv + b - 1);
                if (s == NO_HEIGHT) return Double.NaN;
                row += wu[a] * s;
            }
            sum += wv[b] * row;
        }
        return sum / 8.0;
    }

    /** Relief (metres) of the nearest cell, or NaN. */
    public double relief(double x, double z) {
        int i = (int) Math.floor(x / cell), j = (int) Math.floor(z / cell);
        Tile t = tile(Math.floorDiv(i, tileSize), Math.floorDiv(j, tileSize));
        if (t.h == null) return Double.NaN;
        int k = Math.floorMod(j, tileSize) * tileSize + Math.floorMod(i, tileSize);
        return t.h[k] == NO_HEIGHT ? Double.NaN : (t.relief[k] & 0xff) * 20.0;
    }

    /** Palette index of the nearest cell, jittered on coarse levels so cell edges do not show; -1 if none. */
    public int biome(double x, double z) {
        if (cell >= 16) {
            double s = cell * 0.45;
            x += (noise(x / (cell * 1.5), z / (cell * 1.5), 0x51ED) - 0.5) * 2 * s;
            z += (noise(x / (cell * 1.5), z / (cell * 1.5), 0x2C7B) - 0.5) * 2 * s;
        }
        int i = (int) Math.floor(x / cell), j = (int) Math.floor(z / cell);
        Tile t = tile(Math.floorDiv(i, tileSize), Math.floorDiv(j, tileSize));
        if (t.biome == null) return -1;
        int b = t.biome[Math.floorMod(j, tileSize) * tileSize + Math.floorMod(i, tileSize)] & 0xff;
        return b == 255 ? -1 : b;
    }

    /** Smooth value noise in [0, 1). */
    static double noise(double x, double z, int seed) {
        int ix = (int) Math.floor(x), iz = (int) Math.floor(z);
        double fx = x - ix, fz = z - iz, sx = fx * fx * (3 - 2 * fx), sz = fz * fz * (3 - 2 * fz);
        return hash(ix, iz, seed) * (1 - sx) * (1 - sz) + hash(ix + 1, iz, seed) * sx * (1 - sz)
                + hash(ix, iz + 1, seed) * (1 - sx) * sz + hash(ix + 1, iz + 1, seed) * sx * sz;
    }

    private static double hash(int x, int z, int seed) {
        int h = x * 0x27d4eb2d ^ z * 0x165667b1 ^ seed;
        h = (h ^ (h >>> 15)) * 0x2c1b3c6d;
        h = (h ^ (h >>> 12)) * 0x297a2d39;
        h ^= h >>> 15;
        return (h & 0xffffff) / (double) 0x1000000;
    }
}
