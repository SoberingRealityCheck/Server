package dev.elysium.atlas;

import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.Aquifer;
import net.minecraft.world.level.levelgen.NoiseGeneratorSettings;

/** Global fluid picker with atlas rivers and lakes on top of the original (see NoiseBasedChunkGeneratorMixin). */
public record AtlasFluidPicker(Aquifer.FluidPicker base, NoiseGeneratorSettings settings) implements Aquifer.FluidPicker {
    /** Below this the original picker decides (lava floor, deep aquifers). */
    private static final int MIN_Y = -32;

    /** The settings of the overworld that uses the atlas; set on server start. */
    static volatile NoiseGeneratorSettings atlasSettings;

    /** Water filling down from a river or lake surface to just under its bed. */
    private static final int BELOW_BED = 6;

    @Override
    public Aquifer.FluidStatus computeFluid(int x, int y, int z) {
        if (Atlas.active() && settings == atlasSettings && y > MIN_Y) {
            int level = Atlas.get().column(x, z).fluid();
            if (level != Water.NO_FLUID && y < level) return new Aquifer.FluidStatus(level, Blocks.WATER.defaultBlockState());
        }
        return base.computeFluid(x, y, z);
    }

    /** Water for an open (non-solid) block of an atlas river or lake, or null to let the aquifer decide. */
    public BlockState atlasWater(int x, int y, int z) {
        if (!Atlas.active() || settings != atlasSettings) return null;
        Water.Column c = Atlas.get().column(x, z);
        return c.fluid() != Water.NO_FLUID && y < c.fluid() && y >= c.height() - BELOW_BED ? Blocks.WATER.defaultBlockState() : null;
    }
}
