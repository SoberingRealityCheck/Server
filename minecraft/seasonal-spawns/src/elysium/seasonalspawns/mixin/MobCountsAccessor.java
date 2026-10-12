package elysium.seasonalspawns.mixin;

import it.unimi.dsi.fastutil.objects.Object2IntMap;
import net.minecraft.world.entity.MobCategory;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Accessor;

/**
 * Reads how many animals of each kind are counted near one player. The game keeps
 * that in a package-private class (LocalMobCapCalculator$MobCounts), so it is
 * named by string. LocalMobCapCalculatorMixin uses it to compare the count with
 * a cap of its own instead of the game's.
 */
@Mixin(targets = "net.minecraft.world.level.LocalMobCapCalculator$MobCounts")
public interface MobCountsAccessor {

    @Accessor("counts")
    Object2IntMap<MobCategory> elysium$counts();
}
