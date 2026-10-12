package elysium.seasonalspawns.mixin;

import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.RandomSource;
import net.minecraft.world.entity.MobCategory;
import net.minecraft.world.level.NaturalSpawner;
import net.minecraft.world.level.StructureManager;
import net.minecraft.world.level.biome.MobSpawnSettings;
import net.minecraft.world.level.chunk.ChunkGenerator;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Invoker;

import java.util.Optional;

/**
 * Lets /seasonalspawns sample call the game's own "pick an animal to spawn
 * here" method. That is the same method NaturalSpawnerMixin hooks, so a
 * sample goes through the real rules. It exists only for that command.
 */
@Mixin(NaturalSpawner.class)
public interface NaturalSpawnerAccessor {

    @Invoker("getRandomSpawnMobAt")
    static Optional<MobSpawnSettings.SpawnerData> elysium$pick(
            ServerLevel level, StructureManager structures, ChunkGenerator generator,
            MobCategory category, RandomSource random, BlockPos pos) {
        throw new AssertionError("replaced by Mixin");
    }
}
