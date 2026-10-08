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
		elysium.dhemissive.Probe.render(material, blockLight, block.getLightEmission());
		boolean glows = material == EDhApiBlockMaterial.ILLUMINATED.index
			|| material == EDhApiBlockMaterial.LAVA.index;
		if (glows && !EmissiveFalloff.keepGlow(blockLight, block.getLightEmission()))
		{
			return EDhApiBlockMaterial.UNKNOWN.index;
		}
		return material;
	}

	/**
	 * Arg 2 is the packed ARGB color. Under shaders, dim glowing blocks so the
	 * flat shader glow lands near what loaded blocks look like. Skipped with
	 * no shader pack, where the lightmap already handles it.
	 */
	@ModifyArg(
		method = "setRenderColumnView",
		at = @At(value = "INVOKE", target = "Lcom/seibel/distanthorizons/core/util/RenderDataPointUtil;createDataPoint(IIIIII)J"),
		index = 2, remap = false)
	private static int elysium$dimShaderGlow(
		int color,
		@Local(name = "block") IBlockStateWrapper block,
		@Local(name = "blockLight") int blockLight)
	{
		int material = block.getMaterialId();
		boolean glows = material == EDhApiBlockMaterial.ILLUMINATED.index
			|| material == EDhApiBlockMaterial.LAVA.index;
		if (!glows || !EmissiveFalloff.keepGlow(blockLight, block.getLightEmission()) || !shaderPackInUse())
		{
			return color;
		}

		double scale = EmissiveFalloff.glowColorScale(blockLight);
		int r = (int) (((color >> 16) & 0xFF) * scale);
		int g = (int) (((color >> 8) & 0xFF) * scale);
		int b = (int) ((color & 0xFF) * scale);
		return (color & 0xFF000000) | (r << 16) | (g << 8) | b;
	}

	// Iris API by reflection so this compiles and runs without Iris installed.
	// Hack: if the lookup fails we say "no shaders" and dim nothing.
	private static java.lang.reflect.Method irisInUse;
	private static Object irisApi;
	private static boolean irisLooked;

	private static boolean shaderPackInUse()
	{
		if (!irisLooked)
		{
			irisLooked = true;
			try
			{
				Class<?> api = Class.forName("net.irisshaders.iris.api.v0.IrisApi");
				irisApi = api.getMethod("getInstance").invoke(null);
				irisInUse = api.getMethod("isShaderPackInUse");
			}
			catch (Throwable ignored) { }
		}
		if (irisInUse == null)
		{
			return false;
		}
		try
		{
			return (boolean) irisInUse.invoke(irisApi);
		}
		catch (Throwable e)
		{
			return false;
		}
	}
}
