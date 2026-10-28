package net.minecraft.world.level.levelgen;

import com.mojang.serialization.Codec;
import com.mojang.serialization.MapCodec;
import com.mojang.serialization.codecs.RecordCodecBuilder;
import dev.elysium.atlas.Atlas;
import dev.elysium.atlas.mixin.SurfaceContextAccessor;
import net.minecraft.world.level.chunk.ChunkAccess;

/**
 * Surface rule conditions of elysium_atlas. SurfaceRules.Condition is package-private, so the conditions live in its
 * package (Fabric loads the game and mods with one class loader, so this is the same runtime package).
 * <ul>
 * <li>{@code elysium_atlas:rise} {min, max}: the largest height step to the four neighbouring columns
 *     (WORLD_SURFACE_WG, inside the chunk, as vanilla {@code steep}) is within [min, max]. 1..1 finds ledges that
 *     {@code steep} misses.</li>
 * <li>{@code elysium_atlas:y_band} {period, from, to}: (Y mod period) is within [from, to]: rows of bedded rock.</li>
 * <li>{@code elysium_atlas:near_channel} {distance}: within that many blocks of an atlas river or stream channel
 *     (inside it counts): river beds and banks.</li>
 * </ul>
 */
public final class ElysiumSurfaceConditions {
    private ElysiumSurfaceConditions() {}

    private static SurfaceContextAccessor at(SurfaceRules.Context c) { return (SurfaceContextAccessor) (Object) c; }

    /** A per-column test, computed once per column (the vanilla lazy conditions are private). */
    private abstract static class PerColumn implements SurfaceRules.Condition {
        final SurfaceContextAccessor a;
        private long last = Long.MIN_VALUE;
        private boolean result;

        PerColumn(SurfaceRules.Context ctx) { a = at(ctx); }

        abstract boolean compute(int x, int z);

        @Override public boolean test() {
            int x = a.elysium$blockX(), z = a.elysium$blockZ();
            long k = (long) x << 32 ^ (z & 0xffffffffL);
            if (k != last) { result = compute(x, z); last = k; }
            return result;
        }
    }

    public record Rise(int min, int max) implements SurfaceRules.ConditionSource {
        public static final MapCodec<Rise> CODEC = RecordCodecBuilder.mapCodec(i -> i.group(
                Codec.INT.fieldOf("min").forGetter(Rise::min), Codec.INT.fieldOf("max").forGetter(Rise::max)).apply(i, Rise::new));

        @Override public MapCodec<Rise> codec() { return CODEC; }

        @Override public SurfaceRules.Condition apply(SurfaceRules.Context ctx) {
            return new PerColumn(ctx) {
                @Override boolean compute(int x, int z) {
                    ChunkAccess ch = a.elysium$chunk();
                    int x0 = ch.getPos().getMinBlockX(), z0 = ch.getPos().getMinBlockZ();
                    Heightmap.Types t = Heightmap.Types.WORLD_SURFACE_WG;
                    int h = ch.getHeight(t, x & 15, z & 15);
                    int step = 0;
                    if (x > x0) step = Math.max(step, Math.abs(ch.getHeight(t, (x - 1) & 15, z & 15) - h));
                    if (x < x0 + 15) step = Math.max(step, Math.abs(ch.getHeight(t, (x + 1) & 15, z & 15) - h));
                    if (z > z0) step = Math.max(step, Math.abs(ch.getHeight(t, x & 15, (z - 1) & 15) - h));
                    if (z < z0 + 15) step = Math.max(step, Math.abs(ch.getHeight(t, x & 15, (z + 1) & 15) - h));
                    return step >= min && step <= max;
                }
            };
        }
    }

    public record YBand(int period, int from, int to) implements SurfaceRules.ConditionSource {
        public static final MapCodec<YBand> CODEC = RecordCodecBuilder.mapCodec(i -> i.group(
                Codec.intRange(1, 256).fieldOf("period").forGetter(YBand::period), Codec.INT.fieldOf("from").forGetter(YBand::from),
                Codec.INT.fieldOf("to").forGetter(YBand::to)).apply(i, YBand::new));

        @Override public MapCodec<YBand> codec() { return CODEC; }

        @Override public SurfaceRules.Condition apply(SurfaceRules.Context ctx) {
            SurfaceContextAccessor a = at(ctx);
            return () -> {
                int r = Math.floorMod(a.elysium$blockY(), period);
                return r >= from && r <= to;
            };
        }
    }

    public record NearChannel(double distance) implements SurfaceRules.ConditionSource {
        public static final MapCodec<NearChannel> CODEC = Codec.DOUBLE.fieldOf("distance").xmap(NearChannel::new, NearChannel::distance);

        @Override public MapCodec<NearChannel> codec() { return CODEC; }

        @Override public SurfaceRules.Condition apply(SurfaceRules.Context ctx) {
            return new PerColumn(ctx) {
                @Override boolean compute(int x, int z) {
                    return Atlas.active() && Atlas.get().channelEdge(x, z) <= distance;
                }
            };
        }
    }
}
