package dev.elysium.atlas.mixin;

import net.minecraft.world.level.chunk.ChunkAccess;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Accessor;

/** Column and block position of the surface rule context, for the atlas surface conditions. */
@Mixin(targets = "net.minecraft.world.level.levelgen.SurfaceRules$Context")
public interface SurfaceContextAccessor {
    @Accessor("blockX") int elysium$blockX();
    @Accessor("blockZ") int elysium$blockZ();
    @Accessor("blockY") int elysium$blockY();
    @Accessor("chunk") ChunkAccess elysium$chunk();
    @Accessor("randomState") net.minecraft.world.level.levelgen.RandomState elysium$randomState();
}
