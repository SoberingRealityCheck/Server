package dev.elysium.flora.mixin.client;

import com.llamalad7.mixinextras.injector.wrapmethod.WrapMethod;
import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import dev.elysium.flora.LeafTone;
import dev.elysium.flora.client.ToneSource;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import net.minecraft.client.color.block.BlockColors;
import net.minecraft.client.color.block.BlockTintSource;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.LeavesBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.Property;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * Leaf tones on top of every other tint. @WrapMethod wraps getTintSources with all other mods' injections inside
 * it (the atlas's leaf tints cancel at HEAD), so the tone applies to the final colour whichever mod set it.
 * getTintSource(state, i) and every renderer go through getTintSources.
 */
@Mixin(BlockColors.class)
public abstract class BlockColorsMixin {
    @WrapMethod(method = "getTintSources")
    private List<BlockTintSource> elysiumFlora$tones(BlockState state, Operation<List<BlockTintSource>> original) {
        List<BlockTintSource> sources = original.call(state);
        if (!state.hasProperty(LeafTone.TONE)) return sources;
        return ToneSource.wrap(sources, state.getValue(LeafTone.TONE));
    }

    /** Tone changes the colour, so states that differ only in tone must not share a colour group. */
    @Inject(method = "getColoringProperties", at = @At("RETURN"), cancellable = true)
    private void elysiumFlora$toneProperty(Block block, CallbackInfoReturnable<Set<Property<?>>> cir) {
        Set<Property<?>> props = cir.getReturnValue();
        if (!(block instanceof LeavesBlock) || props.isEmpty() || props.contains(LeafTone.TONE)) return;
        Set<Property<?>> s = new HashSet<>(props);
        s.add(LeafTone.TONE);
        cir.setReturnValue(s);
    }
}
