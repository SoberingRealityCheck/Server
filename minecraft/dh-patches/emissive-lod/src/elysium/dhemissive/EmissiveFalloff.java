package elysium.dhemissive;

/**
 * Pure math. No Minecraft, no DH, no Mixin. Run main() to see the numbers.
 *
 * Problem: DH merges 2x2 columns into one LOD column and keeps the winning
 * block's full light, no matter how little of the 2x2 it fills. A lantern
 * hanging over open air "wins" its slice (air never votes), so it grows
 * into a full-bright plate at every detail level.
 *
 * Fix: the block's OWN emission shrinks with how much of the 2x2 it fills.
 * Light that spread in from neighbours is left alone.
 *
 * Hack: the sqrt curve is a guess, not physics. Real block light spreads
 * out, so a lone emitter's light would fill the LOD. We want the glow to
 * fade instead, so the guess leans dim on purpose.
 */
public final class EmissiveFalloff
{
	private EmissiveFalloff() {}

	/**
	 * @param blockLight light DH computed for the merged column (0-15)
	 * @param emission   what the winning block gives off by itself (0-15)
	 * @param covered    how many of the 4 sub-columns hold that block (1-4)
	 */
	public static int scaleBlockLight(int blockLight, int emission, int covered)
	{
		if (emission <= 0 || covered >= 4)
		{
			return blockLight;
		}
		double keep = Math.sqrt(covered / 4.0);
		int lost = (int) Math.round(emission * (1.0 - keep));
		return Math.max(0, blockLight - lost);
	}

	/**
	 * Shader packs give ILLUMINATED / LAVA a flat glow that ignores light
	 * level. So once the light is mostly gone, drop the material too.
	 */
	public static boolean keepGlow(int blockLight, int emission)
	{
		return blockLight * 2 >= emission;
	}

	// ---- watch it work: java -cp classes elysium.dhemissive.EmissiveFalloff ----

	public static void main(String[] args)
	{
		int emission = 15;
		System.out.println("emission 15. each cell: blockLight, '*' = shader glow kept");
		System.out.println("level | lone in air (1/4) | 2x2 cluster | half row (2/4) | lava lake");

		int lone = emission;
		int half = emission;
		int lake = emission;
		int cluster = emission;
		for (int level = 1; level <= 6; level++)
		{
			lone = scaleBlockLight(lone, emission, 1);
			half = scaleBlockLight(half, emission, 2);
			lake = scaleBlockLight(lake, emission, 4);
			// 2x2 aligned cluster: fills level 1 completely, then 1/4 each step up
			cluster = scaleBlockLight(cluster, emission, level == 1 ? 4 : 1);
			System.out.printf("  %d   | %-17s | %-11s | %-14s | %s%n",
				level, show(lone, emission), show(cluster, emission), show(half, emission), show(lake, emission));
		}
	}

	private static String show(int light, int emission)
	{
		return light + (keepGlow(light, emission) ? "*" : "");
	}
}
