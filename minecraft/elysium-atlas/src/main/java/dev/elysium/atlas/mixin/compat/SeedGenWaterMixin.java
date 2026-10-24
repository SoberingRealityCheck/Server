package dev.elysium.atlas.mixin.compat;

import com.llamalad7.mixinextras.sugar.Local;
import dev.elysium.atlas.Atlas;
import dev.elysium.atlas.Water;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyVariable;

/**
 * Distant Horizons SeedGen fills each LOD column with water up to sea level only, so atlas lakes, rivers
 * and streams above sea level show as dry beds at a distance. Raise the column's water level to the atlas
 * fluid level. SeedGen fills Y below the level it is given, the same convention as {@link Water.Column#fluid()}.
 * Optional: skipped when SeedGen is absent or its method changes. Only applies where the atlas is loaded
 * (singleplayer, or a server that runs SeedGen); a client joining a server has no atlas and keeps sea level.
 */
@Pseudo
@Mixin(targets = "mobius.seedrenderer.dh.SeedWorldGenerator", remap = false)
abstract class SeedGenWaterMixin {
    @ModifyVariable(method = "buildColumn", at = @At("HEAD"), argsOnly = true, ordinal = 2, require = 0)
    private int elysium_atlas$waterLevel(int waterLevel, @Local(argsOnly = true, ordinal = 0) int blockX, @Local(argsOnly = true, ordinal = 1) int blockZ) {
        if (!Atlas.active()) return waterLevel;
        int fluid = Atlas.get().column(blockX, blockZ).fluid();
        return fluid != Water.NO_FLUID && fluid > waterLevel ? fluid : waterLevel;
    }
}
