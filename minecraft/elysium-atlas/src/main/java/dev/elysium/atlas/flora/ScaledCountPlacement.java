package dev.elysium.atlas.flora;

import com.mojang.serialization.Codec;
import com.mojang.serialization.MapCodec;
import net.minecraft.core.BlockPos;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.levelgen.placement.PlacementModifierType;
import net.minecraft.world.level.levelgen.placement.RepeatingPlacement;

/**
 * elysium_atlas:scaled_count {factor}: repeats each position factor times on average (the fraction by chance).
 * Carries the extra attempts a layer in patches needs (NicheSelectorFeature thins them back outside the patches).
 * It is its own type so that Distant Horizons SeedGen, which multiplies only vanilla counts, sees the layer's true
 * mean density instead of the raised attempt count.
 */
public final class ScaledCountPlacement extends RepeatingPlacement {
    public static final MapCodec<ScaledCountPlacement> CODEC = Codec.FLOAT.fieldOf("factor").xmap(ScaledCountPlacement::new, p -> p.factor);
    public static PlacementModifierType<ScaledCountPlacement> TYPE;
    private final float factor;

    public ScaledCountPlacement(float factor) { this.factor = factor; }

    @Override
    protected int count(RandomSource r, BlockPos pos) {
        int n = (int) Math.floor(factor);
        return n + (r.nextFloat() < factor - n ? 1 : 0);
    }

    @Override
    public PlacementModifierType<?> type() { return TYPE; }
}
