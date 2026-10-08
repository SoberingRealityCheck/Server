package elysium.dhemissive.mixin;

import com.llamalad7.mixinextras.sugar.Local;
import com.seibel.distanthorizons.api.enums.rendering.EDhApiBlockMaterial;
import com.seibel.distanthorizons.core.dataObjects.transformers.FullDataToRenderDataTransformer;
import com.seibel.distanthorizons.core.wrapperInterfaces.block.IBlockStateWrapper;
import elysium.dhemissive.EmissiveFalloff;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyArg;

/** Client only. Only matters under shaders, which key the glow on material id. */
@Mixin(value = FullDataToRenderDataTransformer.class, remap = false)
public class RenderTransformMixin
{
	/**
	 * Tied to DH 3.3.2. The one createDataPoint call in setRenderColumnView.
	 * Arg 5 is the material id. Drop the shader glow when the light is mostly gone.
	 */
	@ModifyArg(
		method = "setRenderColumnView",
		at = @At(value = "INVOKE", target = "Lcom/seibel/distanthorizons/core/util/RenderDataPointUtil;createDataPoint(IIIIII)J"),
		index = 5, remap = false)
	private static int elysium$gateShaderGlow(
		int material,
		@Local(name = "block") IBlockStateWrapper block,
		@Local(name = "blockLight") int blockLight)
	{
		boolean glows = material == EDhApiBlockMaterial.ILLUMINATED.index
			|| material == EDhApiBlockMaterial.LAVA.index;
		if (glows && !EmissiveFalloff.keepGlow(blockLight, block.getLightEmission()))
		{
			return EDhApiBlockMaterial.UNKNOWN.index;
		}
		return material;
	}
}
