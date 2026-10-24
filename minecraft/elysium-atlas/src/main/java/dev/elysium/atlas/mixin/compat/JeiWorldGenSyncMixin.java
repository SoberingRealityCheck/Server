package dev.elysium.atlas.mixin.compat;

import dev.elysium.atlas.Variants;
import java.util.LinkedHashMap;
import java.util.Map;
import net.minecraft.core.HolderSet;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyVariable;

/**
 * JEI WorldGen sends ore data for every biome to the client in one login query. The packet holds at most
 * 1 MiB, so with a few hundred regional variants it overflows and the client disconnects while joining
 * ("Failed to decode packet 'clientbound/minecraft:custom_query'"). A variant's ores are its parent's, so
 * drop variants from that data; JEI lists the parent biome. Optional: skipped when JEI WorldGen is absent.
 */
@Pseudo
@Mixin(targets = "de.larsensmods.jeiworldgen.util.OreGenDataBuilder", remap = false)
abstract class JeiWorldGenSyncMixin {
    @ModifyVariable(method = "fromRaw", at = @At("HEAD"), argsOnly = true, ordinal = 0, require = 0)
    private static Map<ResourceKey<Biome>, HolderSet<PlacedFeature>> elysium_atlas$dropVariants0(Map<ResourceKey<Biome>, HolderSet<PlacedFeature>> features) {
        return withoutVariants(features);
    }

    @ModifyVariable(method = "fromRaw", at = @At("HEAD"), argsOnly = true, ordinal = 1, require = 0)
    private static Map<ResourceKey<Biome>, HolderSet<PlacedFeature>> elysium_atlas$dropVariants1(Map<ResourceKey<Biome>, HolderSet<PlacedFeature>> features) {
        return withoutVariants(features);
    }

    private static Map<ResourceKey<Biome>, HolderSet<PlacedFeature>> withoutVariants(Map<ResourceKey<Biome>, HolderSet<PlacedFeature>> features) {
        if (features == null) return null;
        Map<ResourceKey<Biome>, HolderSet<PlacedFeature>> out = new LinkedHashMap<>();
        features.forEach((k, v) -> { if (!Variants.DEFS.containsKey(k.identifier())) out.put(k, v); });
        return out;
    }
}
