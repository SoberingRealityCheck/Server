package elysium.dhemissive;

import java.util.concurrent.atomic.AtomicInteger;

/** Debug only. Prints the first few hits per hook so we can see they run. */
public final class Probe
{
	private static final AtomicInteger MERGE_CALLS = new AtomicInteger();
	private static final AtomicInteger MERGE_CHANGED = new AtomicInteger();
	private static final AtomicInteger RENDER_CALLS = new AtomicInteger();
	private static final AtomicInteger RENDER_GLOW = new AtomicInteger();

	private Probe() {}

	public static void merge(int before, int after, int emission, int covered)
	{
		int n = MERGE_CALLS.incrementAndGet();
		if (before != after && MERGE_CHANGED.incrementAndGet() <= 15)
		{
			System.out.println("[elysium-dh] merge changed light " + before + " -> " + after + " emission=" + emission + " covered=" + covered);
		}
		if (n == 1 || n % 100000 == 0)
		{
			System.out.println("[elysium-dh] merge hook calls=" + n + " changed=" + MERGE_CHANGED.get());
		}
	}

	public static void render(int material, int blockLight, int emission)
	{
		int n = RENDER_CALLS.incrementAndGet();
		if ((material == 15 || material == 6) && RENDER_GLOW.incrementAndGet() <= 15)
		{
			System.out.println("[elysium-dh] render glow material=" + material + " blockLight=" + blockLight + " emission=" + emission);
		}
		if (n == 1 || n % 1000000 == 0)
		{
			System.out.println("[elysium-dh] render hook calls=" + n + " glowing=" + RENDER_GLOW.get());
		}
	}
}
