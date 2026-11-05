package dev.elysium.flora.mixin;

import dev.elysium.flora.LeafTone;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.LeavesBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.StateDefinition;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Adds LeafTone.TONE to every leaf block, vanilla and modded (they all build their states through
 * LeavesBlock.createBlockStateDefinition). Four times the states per leaf block (28 -> 112). Default 0, so placed
 * leaves, saved worlds and blockstate files that don't name `tone` are unchanged.
 */
@Mixin(LeavesBlock.class)
public abstract class LeavesBlockMixin {
    @Inject(method = "createBlockStateDefinition", at = @At("TAIL"))
    private void elysiumFlora$tone(StateDefinition.Builder<Block, BlockState> builder, CallbackInfo ci) {
        builder.add(LeafTone.TONE);
    }
}
