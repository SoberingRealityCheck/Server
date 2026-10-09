package elysium.seasonalspawns.mixin;

import elysium.seasonalspawns.SeasonalSpawns;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.RandomSource;
import net.minecraft.world.entity.MobCategory;
import net.minecraft.world.level.NaturalSpawner;
import net.minecraft.world.level.StructureManager;
import net.minecraft.world.level.biome.MobSpawnSettings;
import net.minecraft.world.level.chunk.ChunkGenerator;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

import java.util.Optional;

/**
 * One hook. After the game picks which animal to spawn, ask SeasonalSpawns
 * if it may go ahead. If not, say nothing was picked. The game then ends
 * that spawn attempt and tries again on a later tick.
 *
 * Only land animals (MobCategory.CREATURE). Monsters, fish and ambient
 * mobs never reach the rules.
 *
 * Hack: this targets a private method by name. A Minecraft update that
 * renames or reshapes getRandomSpawnMobAt breaks the mod at startup
 * (defaultRequire = 1 in the mixin config makes it loud, not silent).
 */
@Mixin(NaturalSpawner.class)
abstract class NaturalSpawnerMixin {

    @Inject(method = "getRandomSpawnMobAt", at = @At("RETURN"), cancellable = true)
    private static void elysium$seasonalVeto(
            ServerLevel level, StructureManager structures, ChunkGenerator generator,
            MobCategory category, RandomSource random, BlockPos pos,
            CallbackInfoReturnable<Optional<MobSpawnSettings.SpawnerData>> cir) {
        if (category != MobCategory.CREATURE) {
            return;
        }
        Optional<MobSpawnSettings.SpawnerData> picked = cir.getReturnValue();
        if (picked.isPresent() && !SeasonalSpawns.allows(level, pos, picked.get().type(), random)) {
            cir.setReturnValue(Optional.empty());
        }
    }
}
