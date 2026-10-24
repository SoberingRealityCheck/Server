package dev.elysium.atlas.mixin;

import dev.elysium.atlas.AtlasFluidPicker;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.Aquifer;
import net.minecraft.world.level.levelgen.DensityFunction;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * Below the chunk's highest surface the aquifer decides fluids from a coarse grid of samples, which
 * misses a river a few blocks wide. Atlas water is decided per block before that.
 */
@Mixin(targets = "net.minecraft.world.level.levelgen.Aquifer$NoiseBasedAquifer")
abstract class NoiseBasedAquiferMixin {
    @Shadow @Final private Aquifer.FluidPicker globalFluidPicker;
    @Shadow private boolean shouldScheduleFluidUpdate;

    @Inject(method = "computeSubstance", at = @At("HEAD"), cancellable = true)
    private void elysium_atlas$water(DensityFunction.FunctionContext ctx, double density, CallbackInfoReturnable<BlockState> cir) {
        if (density > 0 || !(globalFluidPicker instanceof AtlasFluidPicker p)) return;
        BlockState s = p.atlasWater(ctx.blockX(), ctx.blockY(), ctx.blockZ());
        if (s != null) {
            shouldScheduleFluidUpdate = false;
            cir.setReturnValue(s);
        }
    }
}
