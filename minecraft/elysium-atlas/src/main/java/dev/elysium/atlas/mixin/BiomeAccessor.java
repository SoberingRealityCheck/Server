package dev.elysium.atlas.mixin;

import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.BiomeGenerationSettings;
import net.minecraft.world.level.biome.MobSpawnSettings;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Mutable;
import org.spongepowered.asm.mixin.gen.Accessor;

/** Lets Variants give a variant its parent's final generation and spawn settings. */
@Mixin(Biome.class)
public interface BiomeAccessor {
    @Mutable @Accessor("generationSettings") void elysium$setGenerationSettings(BiomeGenerationSettings s);
    @Mutable @Accessor("mobSettings") void elysium$setMobSettings(MobSpawnSettings s);
}
