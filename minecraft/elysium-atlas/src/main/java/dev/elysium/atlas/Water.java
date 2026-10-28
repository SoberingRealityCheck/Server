package dev.elysium.atlas;

import java.io.DataInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;
import java.util.zip.GZIPInputStream;

/**
 * Rivers and lakes (bake_water.py, tiled by tile_water.py). Vector data, evaluated per block column:
 * river channels are carved to a bed below the river's water level with a levee at the edge, lakes get a
 * bed that deepens away from the shore, and both report the fluid level the generator should fill to. Format 3 keeps
 * the data in tiles of 4096 blocks, each holding everything that reaches into it, loaded on first use and dropped
 * least recently used first past elysium_atlas.waterCacheMB (default 96); formats 1 and 2 are one file loaded whole.
 */
public final class Water {
    public static final int NO_FLUID = Integer.MIN_VALUE;
    private static final int SEG = 9;           // x0 z0 x1 z1 level0 level1 halfWidth0 halfWidth1 depth
    private static final double BANK_MIN = 8;   // blocks of bank beyond the channel edge
    private static final double CALM_EXTRA = 16;

    /**
     * Carved surface height, fluid level (water below this Y) or NO_FLUID, how much Tectonic noise to keep (0..1),
     * whether the column is open water, and whether that water is a river or lake (streams keep the land biome).
     */
    public record Column(double height, int fluid, double calm, boolean wet, boolean river) {}

    private final int bucket, lakeReach, tileBlocks;
    private int[] lakeLevel;
    private float[] lakeDepth;
    /** The whole water set (formats 1 and 2), or null when it is tiled (format 3). */
    private final Part whole;
    private final Path dir;
    private final java.util.Set<Long> present = new java.util.HashSet<>();
    private final java.util.concurrent.ConcurrentHashMap<Long, Slot> tiles = new java.util.concurrent.ConcurrentHashMap<>();
    private final java.util.concurrent.atomic.AtomicLong clock = new java.util.concurrent.atomic.AtomicLong(), held = new java.util.concurrent.atomic.AtomicLong();
    private final java.util.concurrent.atomic.AtomicBoolean evicting = new java.util.concurrent.atomic.AtomicBoolean();
    private final long capBytes = Long.getLong("elysium_atlas.waterCacheMB", 96) << 20;
    private final ThreadLocal<Part> last = new ThreadLocal<>();
    private static final Part NONE = new Part();

    /** Segments, lake shore edges and lake-interior buckets of one tile (or of the whole atlas), with their index. */
    private static final class Part {
        final long key;
        final int riverCount;
        final float[] seg, edge;
        final int[] edgeLake;
        final Index riverIdx, edgeIdx;
        final Map<Long, Integer> interior = new HashMap<>();
        final long bytes;

        private Part() {
            key = Long.MIN_VALUE; riverCount = 0; seg = edge = new float[0]; edgeLake = new int[0];
            riverIdx = edgeIdx = new Index(new long[0], 0); bytes = 64;
        }

        /** seg and riverCount already read; b is at the shore edges. */
        Part(long key, float[] seg, int riverCount, ByteBuffer b, Water w) {
            this.key = key; this.seg = seg; this.riverCount = riverCount;
            int ne = b.getInt();
            edge = new float[ne * 4]; edgeLake = new int[ne];
            b.asFloatBuffer().get(edge); b.position(b.position() + edge.length * 4);
            b.asIntBuffer().get(edgeLake); b.position(b.position() + ne * 4);
            int ni = b.getInt();
            for (int i = 0; i < ni; i++) interior.put(Water.key(b.getInt(), b.getInt()), b.getInt());
            Index.Builder ri = new Index.Builder(), ei = new Index.Builder();
            for (int s = 0; s < seg.length / SEG; s++) {
                int o = s * SEG;
                double r = 2 * Math.max(seg[o + 6], seg[o + 7]) + BANK_MIN + CALM_EXTRA;
                w.index(ri, seg[o], seg[o + 1], seg[o + 2], seg[o + 3], r, s);
            }
            for (int e = 0; e < ne; e++) w.index(ei, edge[e * 4], edge[e * 4 + 1], edge[e * 4 + 2], edge[e * 4 + 3], w.lakeReach, e);
            riverIdx = ri.build(); edgeIdx = ei.build();
            bytes = 4L * (seg.length + edge.length + edgeLake.length) + riverIdx.bytes() + edgeIdx.bytes() + 80L * ni + 256;
        }
    }

    private static final class Slot {
        final Part part;
        volatile long used;
        Slot(Part p, long used) { part = p; this.used = used; }
    }

    private static float[] floats(ByteBuffer b, int n) {
        float[] f = new float[n];
        b.asFloatBuffer().get(f); b.position(b.position() + n * 4);
        return f;
    }

    /** atlas.json's "water": a format 1 or 2 file loaded whole, or a format 3 directory of tiles loaded on use. */
    Water(Path file) throws IOException {
        if (Files.isDirectory(file)) {
            ByteBuffer b = ByteBuffer.wrap(Files.readAllBytes(file.resolve("index.bin"))).order(ByteOrder.LITTLE_ENDIAN);
            if (b.getInt() != 0x49545745 /* "EWTI" */) throw new IOException("bad water index header");
            int format = b.getShort();
            if (format != 3) throw new IOException("unknown water index format " + format);
            bucket = b.getShort(); lakeReach = b.getInt(); tileBlocks = b.getInt();
            readLakes(b);
            int nt = b.getInt();
            for (int i = 0; i < nt; i++) present.add(key(b.getInt(), b.getInt()));
            dir = file; whole = null;
            Atlas.LOG.info("Water: {} tiles of {} blocks, {} lakes; tiles load on use (cache {} MB)", nt, tileBlocks, lakeLevel.length, capBytes >> 20);
            return;
        }
        byte[] raw;
        try (InputStream in = new GZIPInputStream(Files.newInputStream(file), 1 << 16)) {
            raw = new DataInputStream(in).readAllBytes();
        }
        ByteBuffer b = ByteBuffer.wrap(raw).order(ByteOrder.LITTLE_ENDIAN);
        if (b.getInt() != 0x54415745 /* "EWAT" */) throw new IOException("bad water header");
        int format = b.getShort();
        if (format != 1 && format != 2) throw new IOException("unknown water format " + format);
        bucket = b.getShort(); lakeReach = b.getInt(); tileBlocks = 0; dir = null;
        int ns = b.getInt();
        int rc = format >= 2 ? b.getInt() : ns;   // segments past the river count are streams
        float[] seg = floats(b, ns * SEG);
        readLakes(b);
        whole = new Part(0, seg, rc, b, this);
        Atlas.LOG.info("Water: {} river and {} stream segments, {} lakes, {} shore edges, loaded whole", rc, ns - rc, lakeLevel.length, whole.edge.length / 4);
    }

    private void readLakes(ByteBuffer b) {
        int nl = b.getInt();
        lakeLevel = new int[nl]; lakeDepth = new float[nl];
        for (int i = 0; i < nl; i++) { lakeLevel[i] = b.getInt(); lakeDepth[i] = b.getFloat(); }
    }

    /** Tiles held now and their estimated bytes (for /atlas). */
    public String cacheInfo() { return whole != null ? "whole" : tiles.size() + " tiles, " + (held.get() >> 20) + " MB"; }

    /** The part holding a column: the whole set, or its tile (loaded on first use, least recently used dropped past the cap). */
    private Part part(double x, double z) {
        if (whole != null) return whole;
        int tx = Math.floorDiv((int) Math.floor(x), tileBlocks), tz = Math.floorDiv((int) Math.floor(z), tileBlocks);
        long k = key(tx, tz);
        Part p = last.get();
        if (p != null && p.key == k) return p;
        if (!present.contains(k)) { p = NONE; last.set(p); return p; }
        long now = clock.incrementAndGet();
        Slot s = tiles.computeIfAbsent(k, kk -> {
            Slot n = new Slot(load(tx, tz, kk), now);
            held.addAndGet(n.part.bytes);
            return n;
        });
        s.used = now;
        if (held.get() > capBytes) evict();
        last.set(s.part);
        return s.part;
    }

    private Part load(int tx, int tz, long k) {
        Path f = dir.resolve(tx + "_" + tz + ".bin.gz");
        try (InputStream in = new GZIPInputStream(Files.newInputStream(f), 1 << 16)) {
            ByteBuffer b = ByteBuffer.wrap(new DataInputStream(in).readAllBytes()).order(ByteOrder.LITTLE_ENDIAN);
            if (b.getInt() != 0x54545745 /* "EWTT" */) throw new IOException("bad water tile header");
            int ns = b.getInt(), rc = b.getInt();
            return new Part(k, floats(b, ns * SEG), rc, b, this);
        } catch (IOException e) {
            Atlas.LOG.error("Water tile {} unreadable, treating as dry", f, e);
            return new Part();
        }
    }

    /** Drops the least recently used tiles down to three quarters of the cap; one thread at a time. */
    private void evict() {
        if (!evicting.compareAndSet(false, true)) return;
        try {
            Slot[] all = tiles.values().toArray(new Slot[0]);
            java.util.Arrays.sort(all, java.util.Comparator.comparingLong(sl -> sl.used));
            for (Slot sl : all) {
                if (held.get() <= capBytes * 3 / 4 || tiles.size() <= 4) break;
                if (tiles.remove(sl.part.key, sl)) held.addAndGet(-sl.part.bytes);
            }
        } finally {
            evicting.set(false);
        }
    }

    private static long key(int bx, int bz) { return ((long) bx << 32) ^ (bz & 0xffffffffL); }

    private void index(Index.Builder m, double x0, double z0, double x1, double z1, double r, int id) {
        int a0 = (int) Math.floor((Math.min(x0, x1) - r) / bucket), a1 = (int) Math.floor((Math.max(x0, x1) + r) / bucket);
        int c0 = (int) Math.floor((Math.min(z0, z1) - r) / bucket), c1 = (int) Math.floor((Math.max(z0, z1) + r) / bucket);
        for (int a = a0; a <= a1; a++) for (int c = c0; c <= c1; c++) m.add(Index.key(a, c), id);
    }

    /**
     * Bucket -> ids as sorted keys with offsets into one id array. Streams put millions of ids in buckets,
     * which as a map of boxed lists would cost hundreds of MB.
     */
    private static final class Index {
        private final int[] keys, start, ids;

        /** Bucket coordinates fit 16 bits each: the globe is under 2^21 blocks across. */
        static int key(int bx, int bz) { return bx << 16 | (bz & 0xffff); }

        Index(long[] pairs, int n) {
            java.util.Arrays.sort(pairs, 0, n);
            int buckets = 0;
            for (int i = 0; i < n; i++) if (i == 0 || (int) (pairs[i] >> 32) != (int) (pairs[i - 1] >> 32)) buckets++;
            keys = new int[buckets]; start = new int[buckets + 1]; ids = new int[n];
            for (int i = 0, k = -1; i < n; i++) {
                int key = (int) (pairs[i] >> 32);
                if (k < 0 || key != keys[k]) { keys[++k] = key; start[k] = i; }
                ids[i] = (int) pairs[i];
            }
            start[buckets] = n;
        }

        long bytes() { return 4L * (keys.length + start.length + ids.length); }

        /** Index range [from, to) in ids for a bucket, packed as from << 32 | to; 0 if absent. */
        long range(int key) {
            int k = java.util.Arrays.binarySearch(keys, key);
            return k < 0 ? 0 : (long) start[k] << 32 | start[k + 1];
        }

        static final class Builder {
            private long[] pairs = new long[1 << 16];
            private int n;

            void add(int key, int id) {
                if (n == pairs.length) pairs = java.util.Arrays.copyOf(pairs, n * 2);
                pairs[n++] = (long) key << 32 | id;
            }

            Index build() { return new Index(pairs, n); }
        }
    }

    private static double smooth(double t) {
        t = Math.max(0, Math.min(1, t));
        return t * t * (3 - 2 * t);
    }

    /** Distance from (x, z) to the edge of the nearest river or stream channel in its bucket, negative inside; +inf if none. */
    public double channelEdge(double x, double z) {
        Part p = part(x, z);
        float[] seg = p.seg;
        Index riverIdx = p.riverIdx;
        int k = Index.key(Math.floorDiv((int) Math.floor(x), bucket), Math.floorDiv((int) Math.floor(z), bucket));
        long rr = riverIdx.range(k);
        double best = Double.POSITIVE_INFINITY;
        if (rr == 0) return best;
        for (int n = (int) (rr >>> 32), end = (int) rr; n < end; n++) {
            int o = riverIdx.ids[n] * SEG;
            double ax = seg[o], az = seg[o + 1], dx = seg[o + 2] - ax, dz = seg[o + 3] - az;
            double len2 = dx * dx + dz * dz;
            double t = len2 > 0 ? Math.max(0, Math.min(1, ((x - ax) * dx + (z - az) * dz) / len2)) : 0;
            double hw = seg[o + 6] + t * (seg[o + 7] - seg[o + 6]);
            best = Math.min(best, Math.hypot(x - ax - t * dx, z - az - t * dz) - hw);
        }
        return best;
    }

    /** Applies rivers and lakes to the terrain height H at a column. */
    public Column column(double x, double z, double H) {
        Part p = part(x, z);
        float[] seg = p.seg, edge = p.edge;
        int[] edgeLake = p.edgeLake;
        Index riverIdx = p.riverIdx, edgeIdx = p.edgeIdx;
        int riverCount = p.riverCount;
        int bx = Math.floorDiv((int) Math.floor(x), bucket), bz = Math.floorDiv((int) Math.floor(z), bucket);
        int k = Index.key(bx, bz);
        double h = H, calm = 1;
        int fluid = NO_FLUID;
        boolean wet = false, river = false;

        // rivers and streams: the lowest carve of every segment whose bank reaches here
        long rr = riverIdx.range(k);
        if (rr != 0) {
            double carved = Double.POSITIVE_INFINITY;
            for (int n = (int) (rr >>> 32), end = (int) rr; n < end; n++) {
                int s = riverIdx.ids[n], o = s * SEG;
                double ax = seg[o], az = seg[o + 1], dx = seg[o + 2] - ax, dz = seg[o + 3] - az;
                double len2 = dx * dx + dz * dz;
                double t = len2 > 0 ? Math.max(0, Math.min(1, ((x - ax) * dx + (z - az) * dz) / len2)) : 0;
                double d = Math.hypot(x - ax - t * dx, z - az - t * dz);
                double hw = seg[o + 6] + t * (seg[o + 7] - seg[o + 6]);
                double bank = Math.max(BANK_MIN, hw);
                calm = Math.min(calm, smooth((d - hw) / (bank + CALM_EXTRA)));
                if (d >= hw + bank) continue;
                double L = seg[o + 4] + t * (seg[o + 5] - seg[o + 4]);
                double hi;
                if (d < hw) {
                    double f = d / hw;
                    hi = Math.min(H, L - 1 - seg[o + 8] * (1 - f * f));
                    fluid = Math.max(fluid, (int) Math.floor(L));
                    wet = true;
                    river |= s < riverCount;
                } else {
                    // levee just above the water, then a slope back up to the terrain
                    double cut = Math.max(Math.min(H, L + 1.2 + 0.6 * (d - hw)), L + 1.2);
                    double u = (d - hw) / bank;
                    hi = cut + (H - cut) * smooth((u - 0.5) / 0.5);
                }
                carved = Math.min(carved, hi);
            }
            if (carved != Double.POSITIVE_INFINITY) h = carved;
        }

        // lakes: signed distance to the nearest shore edge (positive inside)
        long er = edgeIdx.range(k);
        int lake = -1;
        double sd = 0;
        if (er != 0) {
            double best = Double.POSITIVE_INFINITY, bestFacing = -1;
            for (int n = (int) (er >>> 32), end = (int) er; n < end; n++) {
                int e = edgeIdx.ids[n], o = e * 4;
                double ax = edge[o], az = edge[o + 1], dx = edge[o + 2] - ax, dz = edge[o + 3] - az;
                double len2 = dx * dx + dz * dz;
                double t = len2 > 0 ? Math.max(0, Math.min(1, ((x - ax) * dx + (z - az) * dz) / len2)) : 0;
                double d = Math.hypot(x - ax - t * dx, z - az - t * dz);
                double cross = len2 > 0 ? (dx * (z - az) - dz * (x - ax)) / Math.sqrt(len2) : 0;
                // at a shared vertex two edges tie; the one facing the point more squarely decides the side
                if (d < best - 1e-6 || (d < best + 1e-6 && Math.abs(cross) > bestFacing)) {
                    best = Math.min(best, d); bestFacing = Math.abs(cross);
                    lake = edgeLake[e]; sd = cross >= 0 ? d : -d;
                }
            }
            if (best > lakeReach) lake = -1;
        }
        if (lake < 0) {
            Integer in = p.interior.get(key(bx, bz));
            if (in != null) { lake = in; sd = lakeReach; }
        }
        if (lake >= 0) {
            int lv = lakeLevel[lake];
            if (sd > 0) {
                h = Math.min(h, lv - Math.min(lakeDepth[lake], 1 + 0.3 * sd));
                fluid = Math.max(fluid, lv);
                wet = river = true;
                calm = 0;
            } else {
                double out = -sd, levee = lv + 1.2;
                if (!wet && out < 8 && h < levee) h += (levee - h) * (1 - smooth((out - 3) / 5));
                calm = Math.min(calm, smooth(out / 24));
            }
        }
        return new Column(h, fluid, calm, wet, river);
    }
}
