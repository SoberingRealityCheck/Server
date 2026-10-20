package dev.elysium.atlas;

import com.mojang.serialization.Codec;
import com.mojang.serialization.MapCodec;
import com.mojang.serialization.codecs.RecordCodecBuilder;
import net.minecraft.util.KeyDispatchDataCodec;
import net.minecraft.util.StringRepresentable;
import net.minecraft.world.level.levelgen.DensityFunction;

/**
 * elysium_atlas:sample. A 2D atlas lookup, meant to be wrapped in flat_cache / cache_2d.
 * On worlds that do not use the atlas world preset it returns "fallback" instead, so the
 * Lithostitched wraps leave Tectonic unchanged there.
 *
 * Channels:
 *   offset       terrain offset for Tectonic's depth function: depth = 1 - y/128 + offset, so the surface sits at the atlas height
 *   height       atlas surface Y in blocks
 *   continents   continentalness in Tectonic's raw_continents range (-0.45 deep sea .. ~0.35 high inland)
 *   relief       local relief in kilometres (8 km window)
 *   calm         0 on rivers and lakes, rising to 1 away from them: scales Tectonic's own noise so it cannot fill a channel
 */
public record AtlasDensityFunction(Channel channel, DensityFunction fallback) implements DensityFunction {
    public enum Channel implements StringRepresentable {
        OFFSET("offset", -1.5, 4.0), HEIGHT("height", -64, 640), CONTINENTS("continents", -0.45, 0.35), RELIEF("relief", 0, 5.1), CALM("calm", 0, 1);

        public static final Codec<Channel> CODEC = StringRepresentable.fromEnum(Channel::values);
        final String id; final double min, max;
        Channel(String id, double min, double max) { this.id = id; this.min = min; this.max = max; }
        @Override public String getSerializedName() { return id; }
    }

    public static final MapCodec<AtlasDensityFunction> MAP_CODEC = RecordCodecBuilder.mapCodec(i -> i.group(
            Channel.CODEC.fieldOf("channel").forGetter(AtlasDensityFunction::channel),
            DensityFunction.CODEC.fieldOf("fallback").forGetter(AtlasDensityFunction::fallback)
    ).apply(i, AtlasDensityFunction::new));
    public static final KeyDispatchDataCodec<AtlasDensityFunction> CODEC = KeyDispatchDataCodec.of(MAP_CODEC);

    @Override
    public double compute(FunctionContext ctx) {
        if (!Atlas.active()) return fallback.compute(ctx);
        Atlas a = Atlas.get();
        int x = ctx.blockX(), z = ctx.blockZ();
        return switch (channel) {
            case OFFSET -> a.column(x, z).height() / 128.0 - 1.0;
            case HEIGHT -> a.column(x, z).height();
            case CONTINENTS -> continents(a.heightOrOcean(x, z) - (a.seaLevelY + 0.5));
            case RELIEF -> a.relief(x, z) / 1000.0;
            case CALM -> a.column(x, z).calm();
        };
    }

    @Override
    public void fillArray(double[] out, ContextProvider ctx) {
        if (!Atlas.active()) fallback.fillArray(out, ctx);
        else ctx.fillAllDirectly(out, this);
    }

    @Override
    public DensityFunction mapChildren(Visitor visitor) {
        return new AtlasDensityFunction(channel, visitor.apply(fallback));
    }

    /** Sea: -0.2 at the shore down to -0.45 offshore. Land: -0.15 at the shore up to 0.35 inland and high. */
    static double continents(double h) {
        return h < 0 ? -0.2 - 0.25 * Math.tanh(-h / 16.0) : -0.15 + 0.5 * Math.tanh(h / 40.0);
    }

    @Override public double minValue() { return Math.min(channel.min, fallback.minValue()); }
    @Override public double maxValue() { return Math.max(channel.max, fallback.maxValue()); }
    @Override public KeyDispatchDataCodec<? extends DensityFunction> codec() { return CODEC; }
}
