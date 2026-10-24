package dev.elysium.atlas;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import net.minecraft.world.level.levelgen.LegacyRandomSource;
import net.minecraft.world.level.levelgen.synth.SimplexNoise;

import java.util.List;

/**
 * Local relief per biome: the small terms on top of the atlas height (the large terms).
 * Each biome has an amplitude (standard deviation of the offset, blocks), a base wavelength (blocks) and a style; the table comes from atlas.json
 * "detail" (bake/bake_detail.py, tuned there). Amplitude, wavelength and style are averaged over a 5-point
 * stencil so biome borders do not step. Three octaves of 2D simplex noise; wavelengths stay below the atlas's
 * own resolution, so the noise never moves a mountain, only the ground on it.
 */
public final class Detail {
    static final int ROLLING = 0, RIDGED = 1, TERRACE = 2;
    private static final int REACH = 24;               // stencil radius, blocks
    private final float[] amp, wave; private final int[] style;
    private final SimplexNoise[] noise = new SimplexNoise[3];
    private final double fineLevelFactor;
    private final double fSd, rMean, rSd;              // fbm and ridged statistics, so amplitude is a standard deviation

    Detail(JsonObject d, List<String> palette) {
        int n = palette.size(); amp = new float[n]; wave = new float[n]; style = new int[n];
        JsonObject t = d.getAsJsonObject("biomes");
        for (int i = 0; i < n; i++) {
            JsonElement e = t.get(palette.get(i));
            if (e == null) { wave[i] = 64; continue; }
            var a = e.getAsJsonArray();
            amp[i] = a.get(0).getAsFloat(); wave[i] = Math.max(8, a.get(1).getAsFloat());
            style[i] = switch (a.get(2).getAsString()) { case "ridged" -> RIDGED; case "terrace" -> TERRACE; default -> ROLLING; };
        }
        fineLevelFactor = d.has("fine_level_factor") ? d.get("fine_level_factor").getAsDouble() : 0.35;
        LegacyRandomSource r = new LegacyRandomSource(d.has("seed") ? d.get("seed").getAsLong() : 0x6C79_7369L);
        for (int i = 0; i < noise.length; i++) noise[i] = new SimplexNoise(r);
        // measure the noise once: 4096 samples on a scattered grid, at unit wavelength
        double sf = 0, sf2 = 0, sr = 0, sr2 = 0; int cnt = 0;
        for (int i = 0; i < 64; i++) for (int j = 0; j < 64; j++) {
            double[] v = fbm(i * 3.37 + 0.11, j * 2.91 + 0.53, 1.0);
            sf += v[0]; sf2 += v[0] * v[0]; sr += v[1]; sr2 += v[1] * v[1]; cnt++;
        }
        fSd = Math.sqrt(Math.max(1e-6, sf2 / cnt - (sf / cnt) * (sf / cnt)));
        rMean = sr / cnt; rSd = Math.sqrt(Math.max(1e-6, sr2 / cnt - rMean * rMean));
    }

    /** fbm and ridged noise at a point: octaves at W, W/2.3, W/5.3 with weights 1, 0.45, 0.2 (normalised). */
    private double[] fbm(double x, double z, double W) {
        double f = 0, rid = 0, sum = 0, wl = W, w = 1;
        for (SimplexNoise s : noise) {
            double v = s.getValue(x / wl, z / wl);
            f += w * v; rid += w * (1 - 2 * Math.abs(v)); sum += w;
            wl /= 2.3; w *= 0.45;
        }
        return new double[]{f / sum, rid / sum};
    }

    /** Height offset in blocks at a column; 0 on water (calm) and fading to 0 at the sea shore. */
    double blocks(Atlas a, int x, int z, double calm, double height, boolean fineLevel) {
        double sa = 0, sw = 0, wr = 0, wt = 0; int k = 0;
        int[][] pts = {{0, 0}, {REACH, 0}, {-REACH, 0}, {0, REACH}, {0, -REACH}};
        for (int[] p : pts) {
            int b = a.biome(x + p[0], z + p[1]);
            if (b < 0 || b >= amp.length) continue;
            sa += amp[b]; sw += wave[b]; k++;
            if (style[b] == RIDGED) wr++; else if (style[b] == TERRACE) wt++;
        }
        if (k == 0 || sa <= 0) return 0;
        double A = sa / k, W = sw / k; wr /= k; wt /= k;
        double shore = Math.max(0, Math.min(1, (height - (a.seaLevelY + 0.5)) / 3.0));
        A *= calm * shore * (fineLevel ? fineLevelFactor : 1.0);
        if (A <= 0) return 0;
        double[] v = fbm(x, z, W);
        double f = v[0] / fSd, rid = (v[1] - rMean) / rSd;   // both zero-mean, unit standard deviation
        double ter = terrace(f * A, 3.0);
        return (1 - wr - wt) * f * A + wr * rid * A + wt * ter;
    }

    /** Soft steps of the given height: flat treads, short risers. */
    private static double terrace(double h, double step) {
        double q = Math.floor(h / step), t = h / step - q;
        t = t < 0.7 ? 0 : (t - 0.7) / 0.3;
        return (q + t * t * (3 - 2 * t)) * step;
    }
}
