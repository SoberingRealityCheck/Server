package elysium.dhemissive.mixin;

import com.llamalad7.mixinextras.sugar.Local;
import com.seibel.distanthorizons.core.dataObjects.fullData.sources.FullDataSourceV2;
import com.seibel.distanthorizons.core.wrapperInterfaces.block.IBlockStateWrapper;
import elysium.dhemissive.EmissiveFalloff;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyVariable;

/** Runs wherever DH builds lower detail levels: server and client. */
@Mixin(value = FullDataSourceV2.class, remap = false)
public class FullDataSourceV2Mixin
{
	/**
	 * Tied to DH 3.3.2. Hooks the store of the local `blockLight` in the 2x2
	 * merge. Names come from the jar's debug info. A DH update may rename them.
	 */
	@ModifyVariable(method = "mergeInputTwoByTwoDataColumn", at = @At("STORE"), name = "blockLight", remap = false)
	private static byte elysium$scaleEmissiveLight(
		byte blockLight,
		@Local(name = "mergeIds") int[] mergeIds,
		@Local(name = "id") int id,
		@Local(argsOnly = true) FullDataSourceV2 inputDataSource)
	{
		// Hot path: most columns are dark. scaleBlockLight(0, ...) is 0 anyway,
		// so skip the loop and both block lookups.
		if (blockLight == 0)
		{
			return blockLight;
		}

		int covered = 0;
		for (int mergeId : mergeIds)
		{
			if (mergeId == id)
			{
				covered++;
			}
		}
		if (covered == 0)
		{
			return blockLight; // all four differed and DH averaged them. nothing won.
		}

		IBlockStateWrapper block = inputDataSource.mapping.getBlockStateWrapper(id);
		int emission = block.getLightEmission();
		int after = EmissiveFalloff.scaleBlockLight(blockLight, emission, covered);
		return (byte) after;
	}
}
