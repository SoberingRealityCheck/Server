package dev.elysium.atlas.client.mixin;

import dev.elysium.atlas.client.LeafTints;
import net.minecraft.client.color.block.BlockColors;
import net.minecraft.client.color.block.BlockTintSource;
import net.minecraft.world.level.block.state.BlockState;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

import java.util.List;

/** Leaf tints win over whatever vanilla or another mod registered (getTintSource goes through getTintSources). */
@Mixin(BlockColors.class)
public class BlockColorsMixin {
    @Inject(method = "getTintSources", at = @At("HEAD"), cancellable = true)
    private void elysium$leafTints(BlockState state, CallbackInfoReturnable<List<BlockTintSource>> cir) {
        List<BlockTintSource> s = LeafTints.of(state.getBlock());
        if (s != null) cir.setReturnValue(s);
    }

    /** Grass colours from the regions' explicit season palettes, over vanilla's (and Serene Seasons') grass colour. */
    @Inject(method = "getTintSources", at = @At("RETURN"), cancellable = true)
    private void elysium$grassSeasons(BlockState state, CallbackInfoReturnable<List<BlockTintSource>> cir) {
        List<BlockTintSource> s = LeafTints.grass(state.getBlock(), cir.getReturnValue());
        if (s != null) cir.setReturnValue(s);
    }
}
