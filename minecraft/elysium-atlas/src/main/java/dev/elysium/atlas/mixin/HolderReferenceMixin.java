package dev.elysium.atlas.mixin;

import com.llamalad7.mixinextras.injector.ModifyReturnValue;
import dev.elysium.atlas.Variants;
import net.minecraft.core.Holder;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** A biome variant answers key checks for its parent too, so code that tests for a specific biome by key treats it as the parent. */
@Mixin(Holder.Reference.class)
abstract class HolderReferenceMixin<T> implements Variants.VariantHolder {
    @Unique private Holder<?> elysium$parent;

    @Override public Holder<?> elysium$parent() { return elysium$parent; }
    @Override public void elysium$setParent(Holder<?> parent) { elysium$parent = parent; }

    @SuppressWarnings("unchecked")
    @ModifyReturnValue(method = "is(Lnet/minecraft/resources/ResourceKey;)Z", at = @At("RETURN"))
    private boolean elysium_atlas$parentKey(boolean is, ResourceKey<T> key) {
        return is || elysium$parent != null && ((Holder<T>) elysium$parent).is(key);
    }

    @Shadow public abstract boolean is(ResourceKey<T> key);

    /** Vanilla asks the other holder (other.is(this.key)), which would make a parent "be" its variant. Ask this one instead. */
    @Inject(method = "is(Lnet/minecraft/core/Holder;)Z", at = @At("HEAD"), cancellable = true)
    private void elysium_atlas$holder(Holder<T> other, CallbackInfoReturnable<Boolean> cir) {
        if (other instanceof Holder.Reference<T> r) cir.setReturnValue(this.is(r.key()));
    }

    @ModifyReturnValue(method = "is(Lnet/minecraft/resources/Identifier;)Z", at = @At("RETURN"))
    private boolean elysium_atlas$parentId(boolean is, Identifier id) {
        return is || elysium$parent != null && elysium$parent.is(id);
    }
}
