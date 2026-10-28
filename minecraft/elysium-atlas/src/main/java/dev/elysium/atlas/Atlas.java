package dev.elysium.atlas;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import net.fabricmc.loader.api.FabricLoader;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.io.Reader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/**
 * The baked atlas: manifest plus a stack of levels, finest first.
 * Read from config/elysium_atlas/ (or -Delysium.atlas.dir=...). Server only.
 */
public final class Atlas {
    public static final Logger LOG = LoggerFactory.getLogger("elysium_atlas");
    private static volatile Atlas instance;

    public final Path dir;
    public final String version;
    /** Scale profile the atlas was baked with (atlas.json "profile"); null hash for atlases baked before profiles. */
    public final String profileName, profileHash;
    /** Top of the world the profile was designed for (blocks), or 0 if not given. */
    public final int profileMaxY;
    public final double metresPerBlock;
    public final int seaLevelY;
    public final double lon0, radius;
    public final double xMin, xMax, zMin, zMax;
    public final List<String> palette = new ArrayList<>();
    public final int spawnX, spawnZ;
    /** Finest first. */
    public final List<AtlasLevel> levels = new ArrayList<>();
    /** Rivers and lakes, or null for an atlas baked without water. */
    public final Water water;
    /** Region layer that picks biome variants, or null. */
    public final Regions regions;
    /** Per-biome local relief, or null for an atlas baked without a detail table. */
    public final Detail detail;
    /** Vertical transfer of the bake (atlas.json "vertical"): broad-scale metres per metre, and the soft cap on height. */
    private final double eLow, topKnee, topSpan;

    private Atlas(Path dir) throws IOException {
        this.dir = dir;
        JsonObject m;
        try (Reader r = Files.newBufferedReader(dir.resolve("atlas.json"))) {
            m = JsonParser.parseReader(r).getAsJsonObject();
        }
        if (m.get("format").getAsInt() != 1) throw new IOException("unsupported atlas format " + m.get("format"));
        version = m.get("atlas_version").getAsString();
        JsonObject pr = m.has("profile") ? m.getAsJsonObject("profile") : null;
        profileName = pr != null ? pr.get("name").getAsString() : "none";
        profileHash = pr != null ? pr.get("hash").getAsString() : null;
        profileMaxY = pr != null && pr.has("max_y") ? pr.get("max_y").getAsInt() : 0;
        metresPerBlock = m.get("metres_per_block").getAsDouble();
        seaLevelY = m.get("sea_level_y").getAsInt();
        JsonObject proj = m.getAsJsonObject("projection");
        lon0 = proj.get("lon0").getAsDouble();
        radius = proj.get("radius_m").getAsDouble();
        JsonObject b = m.getAsJsonObject("bounds_blocks");
        xMin = b.get("xmin").getAsDouble(); xMax = b.get("xmax").getAsDouble();
        zMin = b.get("zmin").getAsDouble(); zMax = b.get("zmax").getAsDouble();
        for (JsonElement e : m.getAsJsonArray("biome_palette")) palette.add(e.getAsString());
        JsonObject s = m.getAsJsonObject("spawn");
        spawnX = s.get("x").getAsInt(); spawnZ = s.get("z").getAsInt();
        int tile = m.get("tile_size").getAsInt();
        JsonArray lv = m.getAsJsonArray("levels");
        for (int i = lv.size() - 1; i >= 0; i--) {
            JsonObject l = lv.get(i).getAsJsonObject();
            levels.add(new AtlasLevel(l.get("name").getAsString(), dir.resolve(l.get("dir").getAsString()), l.get("cell").getAsInt(), tile));
        }
        levels.sort((a, c) -> Integer.compare(a.cell, c.cell));
        water = m.has("water") ? new Water(dir.resolve(m.getAsJsonObject("water").get("file").getAsString())) : null;
        if (m.has("regions")) {
            JsonObject rg = m.getAsJsonObject("regions");
            List<String> names = new ArrayList<>();
            for (JsonElement e : rg.getAsJsonArray("names")) names.add(e.getAsString());
            regions = new Regions(dir.resolve(rg.get("file").getAsString()), names);
        } else regions = null;
        detail = m.has("detail") ? new Detail(m.getAsJsonObject("detail"), palette) : null;
        JsonObject v = m.has("vertical") ? m.getAsJsonObject("vertical") : new JsonObject();
        eLow = v.has("e_low") ? v.get("e_low").getAsDouble() : 8.0;
        topKnee = v.has("top_knee") ? v.get("top_knee").getAsDouble() : 400.0;
        topSpan = v.has("top_span") ? v.get("top_span").getAsDouble() : 120.0;
        LOG.info("Atlas {} (profile {}) loaded from {}: {} levels, {} biomes, {} regions, {} m/block", version, profileName, dir, levels.size(), palette.size(), regions == null ? 0 : regions.names.size(), metresPerBlock);
    }

    private static volatile boolean active;

    /** True while the running server's overworld uses the atlas biome source (set on server start). */
    public static boolean active() { return active; }

    static void setActive(boolean on) {
        if (on) get();   // load now so a missing atlas fails at startup, not mid-generation
        active = on;
        LOG.info("Atlas worldgen {}", on ? "active for this world" : "inactive");
    }

    public static Path defaultDir() {
        String p = System.getProperty("elysium.atlas.dir");
        return p != null ? Path.of(p) : FabricLoader.getInstance().getConfigDir().resolve("elysium_atlas");
    }

    public static Atlas get() {
        Atlas a = instance;
        if (a == null) {
            synchronized (Atlas.class) {
                a = instance;
                if (a == null) {
                    Path d = defaultDir();
                    try {
                        instance = a = new Atlas(d);
                    } catch (IOException e) {
                        throw new IllegalStateException("Elysium atlas missing or unreadable at " + d + " (copy the baked atlas folder there)", e);
                    }
                }
            }
        }
        return a;
    }

    /** Surface height in blocks (fractional), or NaN outside every level. */
    public double height(double x, double z) {
        for (AtlasLevel l : levels) {
            double h = l.height(x, z);
            if (!Double.isNaN(h)) return h;
        }
        return Double.NaN;
    }

    /** Surface height with a deep-ocean fallback outside the globe. */
    public double heightOrOcean(double x, double z) {
        double h = height(x, z);
        return Double.isNaN(h) ? seaLevelY - 48 : h;
    }

    /** Palette index of the biome at a block column, or -1. */
    public int biome(double x, double z) {
        for (AtlasLevel l : levels) {
            int b = l.biome(x, z);
            if (b >= 0) return b;
        }
        return -1;
    }

    private static final int CACHE = 1024;
    private record Cached(int x, int z, Water.Column c) {}
    private final ThreadLocal<Cached[]> columns = ThreadLocal.withInitial(() -> new Cached[CACHE]);

    /** Terrain after rivers and lakes are cut in, per block column. Cached per thread: the density functions, fluid picker and biome source all ask for the same columns. */
    public Water.Column column(int x, int z) {
        Cached[] cache = columns.get();
        int slot = ((x & 31) | (z & 31) << 5) & (CACHE - 1);
        Cached c = cache[slot];
        if (c != null && c.x == x && c.z == z) return c.c;
        double h = heightOrOcean(x, z);
        Water.Column col = water != null ? water.column(x + 0.5, z + 0.5, h) : new Water.Column(h, Water.NO_FLUID, 1, false, false);
        cache[slot] = new Cached(x, z, col);
        return col;
    }

    /** Blocks from the column to the nearest river or stream channel edge (negative inside), or +inf. */
    public double channelEdge(int x, int z) {
        return water != null ? water.channelEdge(x + 0.5, z + 0.5) : Double.POSITIVE_INFINITY;
    }

    /** How far coast surface rules look for the sea, in blocks. */
    public static final int SEA_REACH = 40;
    private static final int SEA_STEP = 4;
    private final java.util.concurrent.ConcurrentHashMap<Long, float[]> seaCache = new java.util.concurrent.ConcurrentHashMap<>();

    /**
     * Horizontal distance in blocks from a column to the nearest sea, capped at SEA_REACH. Sea is a 4-block lattice
     * point where the generator's final density leaves both Y sea-2 and Y sea+2 open: the water the game actually
     * builds, not the atlas estimate (which misplaces flat and steep shores by up to a cell) or the preliminary surface
     * (which reads flat coastal plains as sea). Lattice points are shared between chunks and cached; chunks with no low
     * atlas ground within reach skip the fine pass.
     */
    public float seaDistance(int x, int z, net.minecraft.world.level.levelgen.RandomState rs) {
        int cx = x >> 4, cz = z >> 4;
        long k = (long) cx << 32 ^ (cz & 0xffffffffL);
        float[] d = seaCache.get(k);
        if (d == null) {
            d = seaChunk(cx << 4, cz << 4, rs);
            if (seaCache.size() > 16384) seaCache.clear();
            seaCache.put(k, d);
        }
        return d[(z & 15) << 4 | (x & 15)];
    }

    private final java.util.concurrent.ConcurrentHashMap<Long, Boolean> seaPoints = new java.util.concurrent.ConcurrentHashMap<>();

    private boolean seaPoint(int px, int pz, net.minecraft.world.level.levelgen.DensityFunction f) {
        long k = (long) (px >> 2) << 32 ^ ((pz >> 2) & 0xffffffffL);
        Boolean v = seaPoints.get(k);
        if (v == null) {
            int sea = (int) Math.floor(seaLevelY);
            v = heightOrOcean(px + 0.5, pz + 0.5) < seaLevelY + 4
                    && f.compute(new net.minecraft.world.level.levelgen.DensityFunction.SinglePointContext(px, sea - 2, pz)) <= 0
                    && f.compute(new net.minecraft.world.level.levelgen.DensityFunction.SinglePointContext(px, sea + 2, pz)) <= 0;
            if (seaPoints.size() > 262144) seaPoints.clear();
            seaPoints.put(k, v);
        }
        return v;
    }

    private float[] seaChunk(int x0, int z0, net.minecraft.world.level.levelgen.RandomState rs) {
        float[] out = new float[256];
        java.util.Arrays.fill(out, SEA_REACH);
        double sea = seaLevelY;
        // coarse pass (8 blocks): nothing near sea level within reach means no sea worth a fine pass
        boolean near = false;
        for (int dz = -SEA_REACH; dz <= 16 + SEA_REACH && !near; dz += 8)
            for (int dx = -SEA_REACH; dx <= 16 + SEA_REACH; dx += 8)
                if (heightOrOcean(x0 + dx, z0 + dz) < sea + 6) { near = true; break; }
        if (!near) return out;
        net.minecraft.world.level.levelgen.DensityFunction f = rs.router().finalDensity();
        int n = (16 + 2 * SEA_REACH) / SEA_STEP + 1;
        int[] sx = new int[n * n], sz = new int[n * n]; int m = 0;
        for (int j = 0; j < n; j++)
            for (int i = 0; i < n; i++) {
                int px = x0 - SEA_REACH + i * SEA_STEP, pz = z0 - SEA_REACH + j * SEA_STEP;
                if (seaPoint(px, pz, f)) { sx[m] = px; sz[m] = pz; m++; }
            }
        if (m == 0) return out;
        for (int c = 0; c < 256; c++) {
            int x = x0 + (c & 15), z = z0 + (c >> 4); long best = (long) SEA_REACH * SEA_REACH;
            for (int q = 0; q < m; q++) {
                long ddx = sx[q] - x, ddz = sz[q] - z, dd = ddx * ddx + ddz * ddz;
                if (dd < best) best = dd;
            }
            out[c] = (float) Math.max(0, Math.sqrt(best) - 1.5);   // samples stand for 4-block cells
        }
        return out;
    }

    /** Per-biome local relief in blocks at a column (Detail), or 0. Finer levels carry real relief there, so it is damped. */
    public double hills(int x, int z) {
        if (detail == null) return 0;
        Water.Column c = column(x, z);
        boolean fine = levels.size() > 1 && levels.get(0).biome(x, z) >= 0;
        return detail.blocks(this, x, z, c.calm(), c.height(), fine);
    }

    /**
     * Real-world elevation (metres above the atlas sea) estimated from an atlas height in blocks: the bake's vertical
     * transfer inverted for its broad band. Peaks are amplified less than plains in the bake, so this reads the
     * regional elevation, not the exact height of a summit; that is what treelines and elevation belts follow.
     */
    public double elevationMetres(double y) {
        double yl = y;
        if (yl > topKnee) yl = topKnee + topSpan * atanh(Math.min(0.999, (yl - topKnee) / topSpan));
        return Math.max(0, (yl - seaLevelY - 0.5) * metresPerBlock / eLow);
    }

    private static double atanh(double t) { return 0.5 * Math.log((1 + t) / (1 - t)); }

    /** Local relief in metres (8 km window), or 0. */
    public double relief(double x, double z) {
        for (AtlasLevel l : levels) {
            double r = l.relief(x, z);
            if (!Double.isNaN(r)) return r;
        }
        return 0;
    }

    // ---- Equal Earth, identical to bake_atlas.py
    private static final double A1 = 1.340264, A2 = -0.081106, A3 = 0.000893, A4 = 0.003796, M = Math.sqrt(3) / 2;

    /** Block position for a longitude and latitude. */
    public double[] toBlock(double lon, double lat) {
        double lam = Math.toRadians(((lon - lon0 + 180) % 360 + 360) % 360 - 180);
        double th = Math.asin(M * Math.sin(Math.toRadians(lat))), t2 = th * th, t6 = t2 * t2 * t2;
        double x = 2 * Math.sqrt(3) * lam * Math.cos(th) / (3 * (9 * A4 * t6 * t2 + 7 * A3 * t6 + 3 * A2 * t2 + A1));
        double y = th * (A4 * t6 * t2 + A3 * t6 + A2 * t2 + A1);
        return new double[]{radius * x / metresPerBlock, -radius * y / metresPerBlock};
    }

    /** Longitude and latitude for a block position (NaN outside the globe). */
    public double[] toLonLat(double bx, double bz) {
        double x = bx * metresPerBlock / radius, y = -bz * metresPerBlock / radius, th = y;
        for (int i = 0; i < 12; i++) {
            double t2 = th * th, t6 = t2 * t2 * t2;
            th -= (th * (A4 * t6 * t2 + A3 * t6 + A2 * t2 + A1) - y) / (9 * A4 * t6 * t2 + 7 * A3 * t6 + 3 * A2 * t2 + A1);
        }
        double t2 = th * th, t6 = t2 * t2 * t2, d = 9 * A4 * t6 * t2 + 7 * A3 * t6 + 3 * A2 * t2 + A1;
        double lam = 3 * x * d / (2 * Math.sqrt(3) * Math.cos(th)), lon = Math.toDegrees(lam);
        if (Math.abs(lon) > 180 || Double.isNaN(th)) return new double[]{Double.NaN, Double.NaN};
        return new double[]{((lon + lon0 + 180) % 360 + 360) % 360 - 180, Math.toDegrees(Math.asin(Math.max(-1, Math.min(1, Math.sin(th) / M))))};
    }
}
