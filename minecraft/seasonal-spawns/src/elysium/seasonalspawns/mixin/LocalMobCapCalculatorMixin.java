package elysium.seasonalspawns.mixin;

import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import com.llamalad7.mixinextras.injector.wrapoperation.WrapOperation;
import com.llamalad7.mixinextras.sugar.Local;
import elysium.seasonalspawns.SeasonalSpawns;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.MobCategory;
import net.minecraft.world.level.LocalMobCapCalculator;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Coerce;

/**
 * Gives each player their own animal cap.
 *
 * The game asks "is there room for another animal?" by looping over the players
 * near a chunk. For each one it compares that player's count with a single fixed
 * number (Respawning Animals sets it to 15). Here we wrap that comparison for
 * land animals only. We compare the same count with a cap that depends on the
 * biomes around that player and the season. See Capacity and SeasonalSpawns.capFor.
 *
 * The game still decides the rest: any one nearby player with room is enough.
 *
 * Hack: this targets a method call inside canSpawn by its signature, and
 * captures the loop's player variable by type. A Minecraft update that reshapes
 * canSpawn stops the server at startup, loudly (defaultRequire = 1).
 */
@Mixin(LocalMobCapCalculator.class)
abstract class LocalMobCapCalculatorMixin {

    @WrapOperation(
            method = "canSpawn",
            at = @At(value = "INVOKE",
                    target = "Lnet/minecraft/world/level/LocalMobCapCalculator$MobCounts;canSpawn(Lnet/minecraft/world/entity/MobCategory;)Z"))
    private boolean elysium$playerCap(
            @Coerce Object counts, MobCategory category, Operation<Boolean> original, @Local ServerPlayer player) {
        if (category != MobCategory.CREATURE) {
            return original.call(counts, category);
        }
        double cap = SeasonalSpawns.capFor(player);
        if (cap < 0) {
            return original.call(counts, category); // feature off, or no seasons here
        }
        int count = ((MobCountsAccessor) counts).elysium$counts().getOrDefault(category, 0);
        return count < cap;
    }
}
