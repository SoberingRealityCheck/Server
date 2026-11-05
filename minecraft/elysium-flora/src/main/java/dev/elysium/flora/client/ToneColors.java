package dev.elysium.flora.client;

import java.util.concurrent.ConcurrentHashMap;

/**
 * Tone shifts in CIE Lab, with a contrast floor: each tone lands at least FLOOR (dE76) from the base colour as
 * seen on a leaf face (tint x the texture's mean grey, FACE_GREY). Where the shift clips at the sRGB gamut the
 * offset grows in steps until the floor is met. Tuned in tree-studies/tone (tone.py, same numbers): worst case
 * over vanilla, autumn and winter bases is about 20. A base that is already near black can't get a darker shade.
 */
public final class ToneColors {
    static final double FACE_GREY = 0.62;
    static final double FLOOR = 24.0;
    /** dL, da, db, chroma scale, per tone 1..3 (sun, shade, pale). */
    private static final double[][] SHIFT = {
            null,
            {14, -4, 22, 1.0},
            {-22, 0, -4, 0.9},
            {26, 0, 0, 0.30},
    };
    private static final double[] STEPS = {1.0, 1.4, 1.9, 2.6, 3.5};
    @SuppressWarnings("unchecked")
    private static final ConcurrentHashMap<Integer, Integer>[] CACHE = new ConcurrentHashMap[]{
            null, new ConcurrentHashMap<>(), new ConcurrentHashMap<>(), new ConcurrentHashMap<>()};

    private ToneColors() {
    }

    /** rgb (0xRRGGBB, alpha kept) shifted by tone 1..3; tone 0 returns rgb. */
    public static int shift(int argb, int tone) {
        if (tone <= 0 || tone > 3) return argb;
        int rgb = argb & 0xFFFFFF;
        ConcurrentHashMap<Integer, Integer> cache = CACHE[tone];
        Integer hit = cache.get(rgb);
        if (hit == null) {
            if (cache.size() > 8192) cache.clear(); // biome blending and season drift make many inputs; keep it bounded
            hit = compute(rgb, SHIFT[tone]);
            cache.put(rgb, hit);
        }
        return (argb & 0xFF000000) | hit;
    }

    static int compute(int rgb, double[] s) {
        double[] base = lab(r(rgb), g(rgb), b(rgb));
        double[] face = lab(r(rgb) * FACE_GREY, g(rgb) * FACE_GREY, b(rgb) * FACE_GREY);
        int out = rgb;
        for (double k : STEPS) {
            double keep = 1 - (1 - s[3]) * Math.min(k, 1);
            double[] c = srgb(base[0] + s[0] * k, base[1] * keep + s[1] * k, base[2] * keep + s[2] * k);
            out = ((int) c[0] << 16) | ((int) c[1] << 8) | (int) c[2];
            double[] f = lab(c[0] * FACE_GREY, c[1] * FACE_GREY, c[2] * FACE_GREY);
            double dl = f[0] - face[0], da = f[1] - face[1], db = f[2] - face[2];
            if (Math.sqrt(dl * dl + da * da + db * db) >= FLOOR) break;
        }
        return out;
    }

    private static double r(int c) { return (c >> 16) & 255; }
    private static double g(int c) { return (c >> 8) & 255; }
    private static double b(int c) { return c & 255; }

    private static double lin(double c) {
        c /= 255.0;
        return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    }

    private static double gam(double c) {
        c = Math.max(0, Math.min(1, c));
        return Math.round(255 * (c <= 0.0031308 ? c * 12.92 : 1.055 * Math.pow(c, 1 / 2.4) - 0.055));
    }

    private static final double WX = 0.95047, WZ = 1.08883, E = 216.0 / 24389, K = 24389.0 / 27;

    private static double f(double t) { return t > E ? Math.cbrt(t) : (K * t + 16) / 116; }
    private static double fi(double t) { return t * t * t > E ? t * t * t : (116 * t - 16) / K; }

    static double[] lab(double r8, double g8, double b8) {
        double r = lin(r8), g = lin(g8), b = lin(b8);
        double x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / WX;
        double y = 0.2126 * r + 0.7152 * g + 0.0722 * b;
        double z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / WZ;
        double fx = f(x), fy = f(y), fz = f(z);
        return new double[]{116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)};
    }

    static double[] srgb(double L, double a, double bb) {
        double fy = (L + 16) / 116, fx = fy + a / 500, fz = fy - bb / 200;
        double x = fi(fx) * WX, y = fi(fy), z = fi(fz) * WZ;
        // inverse of the matrix in lab()
        double r = 3.2406255 * x - 1.5372080 * y - 0.4986286 * z;
        double g = -0.9689307 * x + 1.8757561 * y + 0.0415175 * z;
        double b = 0.0557101 * x - 0.2040211 * y + 1.0569959 * z;
        return new double[]{gam(r), gam(g), gam(b)};
    }
}
