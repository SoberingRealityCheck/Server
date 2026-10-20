package dev.elysium.atlas.mixin;

import com.google.common.base.Suppliers;
import com.llamalad7.mixinextras.injector.ModifyExpressionValue;
import dev.elysium.atlas.AtlasFluidPicker;
import net.minecraft.core.Holder;
import net.minecraft.world.level.levelgen.Aquifer;
import net.minecraft.world.level.levelgen.NoiseBasedChunkGenerator;
import net.minecraft.world.level.levelgen.NoiseGeneratorSettings;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;

import java.util.function.Supplier;

/**
 * Wraps the generator's global fluid picker (sea water above, lava at the bottom) where it is read, so
 * atlas rivers and lakes fill with water above sea level. Tectonic replaces the picker in the constructor,
 * so wrapping at the read sees whatever picker is installed. The wrapper passes through unless the atlas
 * is active and the settings are the overworld's.
 */
@Mixin(NoiseBasedChunkGenerator.class)
abstract class NoiseBasedChunkGeneratorMixin {
    @Shadow @Final private Holder<NoiseGeneratorSettings> settings;

    @Unique
    private record Wrapped(Supplier<Aquifer.FluidPicker> from, Supplier<Aquifer.FluidPicker> to) {}

    @Unique
    private volatile Wrapped elysium_atlas$wrapped;

    @ModifyExpressionValue(method = {"createNoiseChunk", "getInterpolatedNoiseValue", "iterateNoiseColumn"},
            at = @At(value = "FIELD", target = "Lnet/minecraft/world/level/levelgen/NoiseBasedChunkGenerator;globalFluidPicker:Ljava/util/function/Supplier;"))
    private Supplier<Aquifer.FluidPicker> elysium_atlas$water(Supplier<Aquifer.FluidPicker> original) {
        Wrapped w = elysium_atlas$wrapped;
        if (w == null || w.from() != original) {
            NoiseGeneratorSettings s = settings.value();
            w = new Wrapped(original, Suppliers.memoize(() -> new AtlasFluidPicker(original.get(), s)));
            elysium_atlas$wrapped = w;
        }
        return w.to();
    }
}
