package elysium.seasonalspawns;

import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * What the rule files say, as plain data. No Minecraft types in here.
 * That is on purpose. Everything in this file and in RuleParser can be
 * tested by feeding it strings. See SelfTest and Table.
 *
 * A "chance" is the odds that the game is allowed to go ahead with a
 * spawn it just picked. 1.0 means the pack's normal behaviour. 0.0
 * means never. It can lower a rate. It can never raise one above normal.
 */
public final class Rules {

    /** Column order of a 4-number row. Matches Serene Seasons' Season enum order. */
    public static final List<String> SEASONS = List.of("spring", "summer", "autumn", "winter");

    /** Column order of a 2-number row. Used in biomes Serene Seasons treats as tropical. */
    public static final List<String> TROPICAL_SEASONS = List.of("dry", "wet");

    /** Built-in group name that matches every biome. */
    public static final String ANYWHERE = "any";

    public static final Rules EMPTY = new Rules(Map.of(), List.of(), Map.of(), null);

    /** How much to trust a section. Shown by the table and by /seasonalspawns. */
    public enum Confidence {
        /** A source in the section says this. */
        SOURCED,
        /** No direct source. Follows from well-known biology. */
        REASONED,
        /** A game-balance call. No real-world claim behind it. */
        GUESS
    }

    /** A named set of biomes. matchers are "#namespace:tag" or "namespace:biome". */
    public record Group(String name, List<String> matchers, String file, int line) {}

    /** One line of numbers. 4 numbers = spring..winter. 2 numbers = dry, wet. */
    public record Row(String group, double[] chances, int line) {
        public boolean tropical() {
            return chances.length == TROPICAL_SEASONS.size();
        }
    }

    /** A block of rules for one family of animals, with the reasons for them. */
    public record Section(
            String name, String file, int line,
            List<String> animals,
            Confidence confidence, String source, String why,
            List<Row> rows) {}

    /**
     * Settings for the creature cap (see Capacity). Null in Rules means the cap
     * feature is off and the game's own cap is left alone.
     *
     * referenceBiome and referencePhase name the place that counts as 1.0, for
     * example minecraft:forest and summer. floor is the lowest cap a player can
     * be given. rows are hand-set multipliers (0 to 2) by biome group and season,
     * for places the weight sum gets wrong. They use the same row format as the
     * animals: 4 numbers for ordinary biomes, 2 (dry wet) for tropical ones.
     */
    public record CapacitySettings(
            String referenceBiome, String referencePhase, double floor,
            Confidence confidence, String source, String why,
            List<Row> rows, String file, int line) {}

    private final Map<String, Group> groups;
    private final List<Section> sections;
    private final Map<String, Section> byAnimal;
    private final CapacitySettings capacity;

    public Rules(Map<String, Group> groups, List<Section> sections, Map<String, Section> byAnimal,
                 CapacitySettings capacity) {
        this.groups = groups;
        this.sections = sections;
        this.byAnimal = byAnimal;
        this.capacity = capacity;
    }

    /** Null when capacity.rules has no [capacity] section. Then the cap feature is off. */
    public CapacitySettings capacity() {
        return capacity;
    }

    /** The hand-set multiplier for a place. 1.0 when no row fits or the feature is off. */
    public double capacityMultiplier(Set<String> inGroups, boolean tropical, int phase) {
        if (capacity == null) {
            return 1.0;
        }
        return firstRow(capacity.rows(), inGroups, tropical, phase, 1.0);
    }

    /** Index of a season word in SEASONS (not tropical) or TROPICAL_SEASONS (tropical). -1 if unknown. */
    public static int phaseIndex(String word, boolean tropical) {
        return (tropical ? TROPICAL_SEASONS : SEASONS).indexOf(word);
    }

    private static double firstRow(List<Row> rows, Set<String> inGroups, boolean tropical, int phase, double none) {
        for (Row row : rows) {
            if (row.tropical() != tropical) {
                continue;
            }
            if (row.group().equals(ANYWHERE) || inGroups.contains(row.group())) {
                return row.chances()[phase];
            }
        }
        return none;
    }

    public Map<String, Group> groups() {
        return groups;
    }

    public List<Section> sections() {
        return sections;
    }

    public Section sectionOf(String animalId) {
        return byAnimal.get(animalId);
    }

    public Set<String> animals() {
        return byAnimal.keySet();
    }

    /**
     * The chance for one animal at one spot.
     *
     * @param inGroups the groups the biome belongs to
     * @param tropical true if Serene Seasons gives this biome wet and dry seasons
     * @param phase    index into SEASONS, or into TROPICAL_SEASONS if tropical
     *
     * The first row that fits wins. A row fits when its group holds the
     * biome and its kind matches (2 numbers for tropical, 4 for the rest).
     * No row fits means 1.0. An animal with no section means 1.0.
     */
    public double chance(String animalId, Set<String> inGroups, boolean tropical, int phase) {
        Section section = byAnimal.get(animalId);
        if (section == null) {
            return 1.0;
        }
        return firstRow(section.rows(), inGroups, tropical, phase, 1.0);
    }
}
