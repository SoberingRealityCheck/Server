package elysium.seasonalspawns;

import java.util.List;
import java.util.function.ToDoubleFunction;

/**
 * How many land animals a place can hold, as a fraction of a reference place.
 * Pure numbers in, numbers out. No Minecraft in here.
 *
 * The idea, in three steps:
 *   1. A place's "creature weight" is the sum, over every land animal the game
 *      can spawn there, of  spawn weight x average group size x seasonal chance.
 *   2. Divide by the same sum for a chosen reference place (summer forest). That
 *      is the fraction. A place that is as rich as the reference gets 1.0.
 *      Richer places are clamped to 1.0.
 *   3. cap = base cap x fraction, never below a floor and never above the base.
 *      The base is the cap Respawning Animals already uses (15 by default).
 *
 * Hack: spawn weights are not abundance. They are relative pick odds that mod
 * authors tuned against each other. A sum rewards many species and odd weights
 * more than it measures how many animals a biome holds. The capacity rows in
 * capacity.rules exist so a human can fix the places where the sum is wrong.
 */
public final class Capacity {

    /** One animal in a biome's spawn list. meanGroup is (min + max) / 2. */
    public record Entry(String animal, int weight, double meanGroup) {}

    /** Sum of weight x meanGroup x chance. chance is the seasonal chance from Rules. */
    public static double weightedSum(List<Entry> entries, ToDoubleFunction<String> chance) {
        double sum = 0;
        for (Entry e : entries) {
            sum += e.weight() * e.meanGroup() * chance.applyAsDouble(e.animal());
        }
        return sum;
    }

    /**
     * This place's fraction of the reference. multiplier is the hand-set row from
     * capacity.rules (1.0 when none). Result is clamped to 0..1. A reference sum
     * of zero or less means there is nothing to compare to, so it returns 1.0.
     */
    public static double fraction(double sum, double referenceSum, double multiplier) {
        if (referenceSum <= 0) {
            return 1.0;
        }
        return clamp01(sum / referenceSum * multiplier);
    }

    /**
     * The cap for one player. Never above the base, never below the floor
     * (unless the base itself is lower than the floor).
     */
    public static double cap(double base, double fraction, double floor) {
        return Math.min(base, Math.max(floor, base * fraction));
    }

    private static double clamp01(double v) {
        return Math.max(0.0, Math.min(1.0, v));
    }

    private Capacity() {}
}
