package dev.elysium.atlas.flora;

import com.mojang.serialization.Codec;
import com.mojang.serialization.codecs.RecordCodecBuilder;

import java.util.Arrays;
import java.util.Random;

/**
 * Patches on the ground (variants/db: a species' "clump", an ecoregion layer's "patches").
 *   size     typical patch width in blocks
 *   share    fraction of the ground inside patches
 *   outside  relative amount outside patches (0 = only in patches, 1 = no patches)
 *   key      names the noise, so each species or layer has its own pattern
 * membership() is 0 outside a patch and 1 inside, with a soft edge. The noise is two octaves of smoothed value noise
 * seeded from the world seed and the key; its quantiles are measured once, so `share` holds for any size.
 */
public record Clump(float size, float share, float outside, String key) {
    public static final Codec<Clump> CODEC = RecordCodecBuilder.create(i -> i.group(
            Codec.FLOAT.fieldOf("size").forGetter(Clump::size),
            Codec.FLOAT.fieldOf("share").forGetter(Clump::share),
            Codec.FLOAT.optionalFieldOf("outside", 0.1f).forGetter(Clump::outside),
            Codec.STRING.fieldOf("key").forGetter(Clump::key)).apply(i, Clump::new));

    static final double EDGE = 0.04;     // soft edge, in noise units (the noise spans about 0..1)
    private static final double[] QUANTILES = quantiles();

    /** 0 outside a patch, 1 inside. */
    public double membership(long worldSeed, int x, int z) {
        double v = noise(worldSeed ^ mix(key.hashCode()), x / (double) size, z / (double) size);
        double t = QUANTILES[(int) Math.round(Math.max(0, Math.min(1, 1 - share)) * (QUANTILES.length - 1))];
        return NicheSelectorFeature.smooth((v - t) / EDGE + 0.5);
    }

    /** Presence at a spot: `outside` between patches, 1 inside. */
    public double presence(long worldSeed, int x, int z) {
        return outside + (1 - outside) * membership(worldSeed, x, z);
    }

    /** Mean presence over the ground; dividing presence by it keeps a species' total abundance. */
    public double mean() { return outside + (1 - outside) * share; }

    static double noise(long seed, double x, double z) {
        return 0.65 * value(seed, x, z) + 0.35 * value(seed ^ 0x5DEECE66DL, x * 2.2 + 17.3, z * 2.2 - 41.9);
    }

    static double value(long seed, double x, double z) {
        int x0 = (int) Math.floor(x), z0 = (int) Math.floor(z);
        double fx = fade(x - x0), fz = fade(z - z0);
        double a = corner(seed, x0, z0), b = corner(seed, x0 + 1, z0), c = corner(seed, x0, z0 + 1), d = corner(seed, x0 + 1, z0 + 1);
        return (a + (b - a) * fx) + ((c + (d - c) * fx) - (a + (b - a) * fx)) * fz;
    }

    static double fade(double t) { return t * t * t * (t * (t * 6 - 15) + 10); }

    static double corner(long seed, int x, int z) {
        long h = mix(seed + x * 0x9E3779B97F4A7C15L + z * 0xC2B2AE3D27D4EB4FL);
        return (h >>> 11) * 0x1.0p-53;
    }

    static long mix(long z) {
        z = (z ^ (z >>> 30)) * 0xBF58476D1CE4E5B9L;
        z = (z ^ (z >>> 27)) * 0x94D049BB133111EBL;
        return z ^ (z >>> 31);
    }

    private static double[] quantiles() {
        Random r = new Random(1);
        double[] v = new double[100000];
        for (int i = 0; i < v.length; i++) v[i] = noise(r.nextLong(), r.nextDouble() * 1000, r.nextDouble() * 1000);
        Arrays.sort(v);
        double[] q = new double[201];
        for (int i = 0; i < q.length; i++) q[i] = v[Math.min(v.length - 1, (int) ((long) i * v.length / (q.length - 1)))];
        return q;
    }
}
