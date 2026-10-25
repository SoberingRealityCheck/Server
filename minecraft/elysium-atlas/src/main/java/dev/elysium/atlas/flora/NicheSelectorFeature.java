package dev.elysium.atlas.flora;

import com.mojang.serialization.Codec;
import com.mojang.serialization.codecs.RecordCodecBuilder;
import dev.elysium.atlas.Atlas;
import dev.elysium.atlas.Water;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.levelgen.feature.ConfiguredFeature;
import net.minecraft.world.level.levelgen.feature.Feature;
import net.minecraft.world.level.levelgen.feature.FeaturePlaceContext;
import net.minecraft.world.level.levelgen.feature.configurations.FeatureConfiguration;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;

import java.util.List;
import java.util.Optional;
import java.util.stream.Stream;

/**
 * Picks one species for a spot, weighted by how well the spot suits it (variants/db: a species' "niche").
 * Each entry has a base weight (its share in the ecoregion) and an optional niche:
 *   elevation  [low, high] metres, soft edges of EDGE_M (Atlas.elevationMetres of the ground height, so treelines follow the actual terrain)
 *   water      riparian (near rivers and lakes), wet (riparian or waterlogged ground), dry (away from water)
 *   slope      flat or steep (terrain slope around the spot)
 * Weight at a spot = base weight x suitability. The plant count scales with the best suitability of any entry, so the
 * species that fit share the full density and a spot that suits none gets nothing (treelines, bare ridges). Without the atlas every niche counts as fully suitable.
 */
public class NicheSelectorFeature extends Feature<NicheSelectorFeature.Config> {
    static final double EDGE_M = 150;

    public record Niche(Optional<List<Double>> elevation, Optional<String> water, Optional<String> slope) {
        public static final Codec<Niche> CODEC = RecordCodecBuilder.create(i -> i.group(
                Codec.DOUBLE.listOf().optionalFieldOf("elevation").forGetter(Niche::elevation),
                Codec.STRING.optionalFieldOf("water").forGetter(Niche::water),
                Codec.STRING.optionalFieldOf("slope").forGetter(Niche::slope)).apply(i, Niche::new));
        static final Niche ANY = new Niche(Optional.empty(), Optional.empty(), Optional.empty());

        double suit(Spot s) {
            double f = 1;
            if (elevation.isPresent() && s.elevation >= 0) {
                List<Double> e = elevation.get();
                f *= smooth((s.elevation - e.get(0) + EDGE_M) / (2 * EDGE_M)) * (1 - smooth((s.elevation - e.get(1) + EDGE_M) / (2 * EDGE_M)));
            }
            if (water.isPresent() && s.calm >= 0) {
                double near = 1 - s.calm;                      // 1 at the bank, 0 beyond ~25 blocks
                f *= switch (water.get()) {
                    case "riparian" -> 0.03 + 0.97 * near;
                    case "wet" -> s.wet ? 1 : 0.03 + 0.97 * near;
                    case "dry" -> 0.15 + 0.85 * s.calm;
                    default -> 1;
                };
            }
            if (slope.isPresent()) {
                double st = smooth((s.slope - 0.35) / 0.65);  // 0 below 0.35 blocks per block, 1 above 1
                f *= switch (slope.get()) {
                    case "steep" -> 0.1 + 0.9 * st;
                    case "flat" -> 1 - 0.9 * st;
                    default -> 1;
                };
            }
            return f;
        }
    }

    public record Entry(Holder<PlacedFeature> feature, float weight, Niche niche) {
        public static final Codec<Entry> CODEC = RecordCodecBuilder.create(i -> i.group(
                PlacedFeature.CODEC.fieldOf("feature").forGetter(Entry::feature),
                Codec.FLOAT.fieldOf("weight").forGetter(Entry::weight),
                Niche.CODEC.optionalFieldOf("niche", Niche.ANY).forGetter(Entry::niche)).apply(i, Entry::new));
    }

    public record Config(List<Entry> entries) implements FeatureConfiguration {
        public static final Codec<Config> CODEC = RecordCodecBuilder.create(i -> i.group(
                Entry.CODEC.listOf().fieldOf("entries").forGetter(Config::entries)).apply(i, Config::new));

        @Override
        public Stream<Holder<ConfiguredFeature<?, ?>>> getSubFeatures() {
            return entries.stream().map(e -> e.feature().value().feature());
        }
    }

    /** What the niches look at, for one spot. Negative values mean unknown. */
    record Spot(double elevation, double calm, boolean wet, double slope) {}

    public NicheSelectorFeature(Codec<Config> codec) { super(codec); }

    static Spot spot(WorldGenLevel level, BlockPos p) {
        int h0 = level.getHeight(Heightmap.Types.WORLD_SURFACE_WG, p.getX(), p.getZ());
        int hx = level.getHeight(Heightmap.Types.WORLD_SURFACE_WG, p.getX() + 3, p.getZ()) - level.getHeight(Heightmap.Types.WORLD_SURFACE_WG, p.getX() - 3, p.getZ());
        int hz = level.getHeight(Heightmap.Types.WORLD_SURFACE_WG, p.getX(), p.getZ() + 3) - level.getHeight(Heightmap.Types.WORLD_SURFACE_WG, p.getX(), p.getZ() - 3);
        double slope = Math.hypot(hx, hz) / 6.0;
        Atlas a = Atlas.active() ? Atlas.get() : null;
        if (a == null) return new Spot(-1, -1, false, slope);
        Water.Column c = a.column(p.getX(), p.getZ());
        return new Spot(a.elevationMetres(h0), c.calm(), c.wet() || c.fluid() != Water.NO_FLUID && c.fluid() >= h0 - 1, slope);
    }

    @Override
    public boolean place(FeaturePlaceContext<Config> ctx) {
        List<Entry> es = ctx.config().entries();
        if (es.isEmpty()) return false;
        Spot s = spot(ctx.level(), ctx.origin());
        double[] w = new double[es.size()];
        double tot = 0, best = 0;
        for (int i = 0; i < w.length; i++) {
            double f = es.get(i).niche().suit(s);
            w[i] = es.get(i).weight() * f; tot += w[i]; best = Math.max(best, f);
        }
        // the plant count follows the best-suited species: where any listed species fits fully, density is full
        // (the others give way); where none fits (above the treeline, a bare ridge) it fades to nothing
        RandomSource r = ctx.random();
        if (tot <= 0 || r.nextDouble() > best) return false;
        double pick = r.nextDouble() * tot;
        for (int i = 0; i < w.length; i++) {
            pick -= w[i];
            if (pick <= 0) return es.get(i).feature().value().place(ctx.level(), ctx.chunkGenerator(), r, ctx.origin());
        }
        return es.get(w.length - 1).feature().value().place(ctx.level(), ctx.chunkGenerator(), r, ctx.origin());
    }

    static double smooth(double t) { t = Math.max(0, Math.min(1, t)); return t * t * (3 - 2 * t); }
}
