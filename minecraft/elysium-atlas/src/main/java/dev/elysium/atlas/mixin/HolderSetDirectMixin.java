package dev.elysium.atlas.mixin;

import com.llamalad7.mixinextras.injector.ModifyReturnValue;
import dev.elysium.atlas.Variants;
import net.minecraft.core.Holder;
import net.minecraft.core.HolderSet;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;

/**
 * Explicit biome lists (surface rules, loot conditions, structure and feature biome lists written as ids)
 * contain a variant when they contain its parent. Tag-backed sets need nothing: variants join the tags.
 */
@Mixin(HolderSet.Direct.class)
abstract class HolderSetDirectMixin<T> {
    @SuppressWarnings("unchecked")
    @ModifyReturnValue(method = "contains", at = @At("RETURN"))
    private boolean elysium_atlas$parent(boolean contains, Holder<T> holder) {
        if (contains || !(holder instanceof Variants.VariantHolder v) || v.elysium$parent() == null) return contains;
        return ((HolderSet<T>) (Object) this).contains((Holder<T>) v.elysium$parent());
    }
}
