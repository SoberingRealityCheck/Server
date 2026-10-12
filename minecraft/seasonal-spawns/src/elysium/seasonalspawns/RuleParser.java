package elysium.seasonalspawns;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

/**
 * Turns the text of the .rules files into a Rules object.
 *
 * The format (the README has the long version):
 *
 *   # a comment
 *   [forest]                                  <- a biome group
 *   biomes = #minecraft:is_forest minecraft:taiga
 *
 *   [bear]                                    <- rules for some animals
 *   animals    = naturalist:bear naturalist:black_bear
 *   confidence = sourced                      <- sourced | reasoned | guess
 *   source     = https://example.org/page     <- needed when sourced
 *   weight     = 20                           <- optional. Caps the spawn weight (see Rules.Section)
 *   why        = Text that can run on
 *                to indented lines.
 *   forest = 0.8 1.0 1.0 0.0                  <- spring summer autumn winter
 *   savanna = 1.0 0.4                         <- dry wet (tropical biomes only)
 *
 * The parser never throws on bad input. It collects every problem as a
 * "file:line: message" string so one run shows all of them.
 */
public final class RuleParser {

    public record Source(String name, String text) {}

    public record Result(Rules rules, List<String> errors) {}

    private static final Pattern NAME = Pattern.compile("[a-z0-9_-]+");
    private static final Pattern ANIMAL_ID = Pattern.compile("[a-z0-9_.-]+:[a-z0-9_./-]+");
    private static final Pattern BIOME_MATCHER = Pattern.compile("#?[a-z0-9_.-]+:[a-z0-9_./-]+");

    /** Keys that hold text. Anything else on the left of "=" is a group name in a rule row. */
    private static final List<String> TEXT_KEYS =
            List.of("animals", "biomes", "why", "source", "confidence", "reference", "floor", "weight");

    /** The one section name that is not a group or an animal list. See Rules.CapacitySettings. */
    private static final String CAPACITY = "capacity";

    /** Hand-set capacity multipliers may go above 1 (up to this). Chances for animals may not. */
    private static final double MAX_CAPACITY_MULTIPLIER = 2.0;

    private record RawRow(String group, List<Double> numbers, int line) {}

    private static final class Raw {
        final String name;
        final String file;
        final int line;
        final Map<String, String> text = new LinkedHashMap<>();
        final Map<String, Integer> textLine = new LinkedHashMap<>();
        final List<RawRow> rows = new ArrayList<>();

        Raw(String name, String file, int line) {
            this.name = name;
            this.file = file;
            this.line = line;
        }
    }

    public static Result parse(List<Source> sources) {
        List<String> errors = new ArrayList<>();
        List<Raw> raws = new ArrayList<>();
        for (Source source : sources) {
            readFile(source, raws, errors);
        }

        Map<String, Rules.Group> groups = new LinkedHashMap<>();
        for (Raw raw : raws) {
            if (raw.text.containsKey("biomes")) {
                buildGroup(raw, groups, errors);
            }
        }

        List<Rules.Section> sections = new ArrayList<>();
        Map<String, Rules.Section> byAnimal = new LinkedHashMap<>();
        Rules.CapacitySettings capacity = null;
        for (Raw raw : raws) {
            if (raw.text.containsKey("biomes")) {
                continue;
            }
            if (raw.name.equals(CAPACITY)) {
                if (capacity != null) {
                    errors.add(where(raw.file, raw.line) + "[capacity] is defined twice");
                } else {
                    capacity = buildCapacity(raw, groups, errors);
                }
                continue;
            }
            if (!raw.text.containsKey("animals")) {
                errors.add(where(raw.file, raw.line) + "[" + raw.name + "] has neither 'biomes =' nor 'animals ='");
                continue;
            }
            Rules.Section section = buildSection(raw, groups, errors);
            if (section == null) {
                continue;
            }
            sections.add(section);
            for (String animal : section.animals()) {
                Rules.Section earlier = byAnimal.put(animal, section);
                if (earlier != null) {
                    errors.add(where(raw.file, raw.line) + animal + " is already in [" + earlier.name()
                            + "] (" + earlier.file() + ":" + earlier.line() + "). Each animal gets one section.");
                }
            }
        }
        return new Result(new Rules(groups, sections, byAnimal, capacity), errors);
    }

    // ---- reading lines -------------------------------------------------

    private static void readFile(Source source, List<Raw> raws, List<String> errors) {
        Raw current = null;
        String openKey = null; // the text key that indented lines continue
        String[] lines = source.text().split("\n", -1);
        for (int i = 0; i < lines.length; i++) {
            int lineNo = i + 1;
            String line = lines[i].stripTrailing();
            String trimmed = line.strip();
            if (trimmed.isEmpty()) {
                openKey = null;
                continue;
            }
            if (trimmed.startsWith("#")) {
                continue;
            }
            if (trimmed.startsWith("[")) {
                openKey = null;
                if (!trimmed.endsWith("]")) {
                    errors.add(where(source.name(), lineNo) + "section header must look like [name]");
                    current = null;
                    continue;
                }
                String name = trimmed.substring(1, trimmed.length() - 1).strip();
                if (!NAME.matcher(name).matches()) {
                    errors.add(where(source.name(), lineNo) + "section name '" + name + "' may only use a-z 0-9 _ -");
                }
                current = new Raw(name, source.name(), lineNo);
                raws.add(current);
                continue;
            }
            if (current == null) {
                errors.add(where(source.name(), lineNo) + "this line is outside any [section]");
                continue;
            }
            boolean indented = Character.isWhitespace(line.charAt(0));
            if (indented && openKey != null) {
                current.text.merge(openKey, trimmed, (a, b) -> a + " " + b);
                continue;
            }
            int eq = trimmed.indexOf('=');
            if (eq < 0) {
                errors.add(where(source.name(), lineNo) + "expected 'name = value'");
                openKey = null;
                continue;
            }
            String key = trimmed.substring(0, eq).strip();
            String value = trimmed.substring(eq + 1).strip();
            if (TEXT_KEYS.contains(key)) {
                if (current.text.containsKey(key)) {
                    errors.add(where(source.name(), lineNo) + "'" + key + "' is set twice in [" + current.name + "]");
                }
                current.text.put(key, value);
                current.textLine.put(key, lineNo);
                openKey = key;
            } else {
                openKey = null;
                readRow(source.name(), lineNo, key, value, current, errors);
            }
        }
    }

    private static void readRow(String file, int lineNo, String group, String value, Raw into, List<String> errors) {
        int hash = value.indexOf('#');
        if (hash >= 0) {
            value = value.substring(0, hash); // allow "forest = 1 1 1 0   # note"
        }
        List<Double> numbers = new ArrayList<>();
        for (String word : value.strip().split("\\s+")) {
            try {
                numbers.add(Double.parseDouble(word));
            } catch (NumberFormatException e) {
                errors.add(where(file, lineNo) + "'" + word + "' is not a number. Unknown key '" + group
                        + "'? Text keys are: " + String.join(", ", TEXT_KEYS));
                return;
            }
        }
        into.rows.add(new RawRow(group, numbers, lineNo));
    }

    // ---- building ------------------------------------------------------

    private static void buildGroup(Raw raw, Map<String, Rules.Group> groups, List<String> errors) {
        String at = where(raw.file, raw.line);
        if (raw.name.equals(Rules.ANYWHERE) || raw.name.equals(CAPACITY) || TEXT_KEYS.contains(raw.name)) {
            errors.add(at + "'" + raw.name + "' is reserved and can't be a group name");
            return;
        }
        if (raw.text.containsKey("animals") || !raw.rows.isEmpty()) {
            errors.add(at + "[" + raw.name + "] has 'biomes =' so it is a group. Groups can't have animals or rows.");
            return;
        }
        List<String> matchers = new ArrayList<>();
        for (String word : raw.text.get("biomes").split("\\s+")) {
            if (word.isEmpty()) {
                continue;
            }
            if (!BIOME_MATCHER.matcher(word).matches()) {
                errors.add(at + "'" + word + "' is not a biome id or #tag. Use namespace:name.");
            } else {
                matchers.add(word);
            }
        }
        if (matchers.isEmpty()) {
            errors.add(at + "[" + raw.name + "] lists no biomes");
        }
        if (groups.containsKey(raw.name)) {
            errors.add(at + "group '" + raw.name + "' is defined twice");
            return;
        }
        groups.put(raw.name, new Rules.Group(raw.name, List.copyOf(matchers), raw.file, raw.line));
    }

    private static Rules.Section buildSection(Raw raw, Map<String, Rules.Group> groups, List<String> errors) {
        String at = where(raw.file, raw.line);
        int before = errors.size();

        List<String> animals = new ArrayList<>();
        for (String word : raw.text.get("animals").split("\\s+")) {
            if (word.isEmpty()) {
                continue;
            }
            if (!ANIMAL_ID.matcher(word).matches()) {
                errors.add(at + "'" + word + "' is not an entity id. Use namespace:name, like minecraft:wolf.");
            } else {
                animals.add(word);
            }
        }
        if (animals.isEmpty()) {
            errors.add(at + "[" + raw.name + "] lists no animals");
        }

        Rules.Confidence confidence = null;
        String confidenceText = raw.text.get("confidence");
        if (confidenceText == null) {
            errors.add(at + "[" + raw.name + "] needs 'confidence = sourced | reasoned | guess'");
        } else {
            try {
                confidence = Rules.Confidence.valueOf(confidenceText.strip().toUpperCase());
            } catch (IllegalArgumentException e) {
                errors.add(at + "confidence '" + confidenceText + "' must be sourced, reasoned or guess");
            }
        }

        String why = raw.text.get("why");
        if (why == null || why.isBlank()) {
            errors.add(at + "[" + raw.name + "] needs a 'why =' line. Say what the real animal does.");
        }
        String source = raw.text.getOrDefault("source", "");
        if (confidence == Rules.Confidence.SOURCED && source.isBlank()) {
            errors.add(at + "[" + raw.name + "] says 'sourced' but has no 'source ='");
        }

        Integer weight = null;
        String weightText = raw.text.get("weight");
        if (weightText != null) {
            try {
                weight = Integer.parseInt(weightText.strip());
                if (weight < 1) {
                    errors.add(at + "weight must be 1 or more. To stop an animal, use a row of 0.00.");
                }
            } catch (NumberFormatException e) {
                errors.add(at + "weight '" + weightText + "' must be a whole number, like 20");
            }
        }

        if (raw.rows.isEmpty() && weightText == null) {
            errors.add(at + "[" + raw.name + "] has no rows and no weight");
        }
        List<Rules.Row> rows = buildRows(raw, groups, errors, 1.0, "chance");

        if (errors.size() > before) {
            return null;
        }
        return new Rules.Section(raw.name, raw.file, raw.line, List.copyOf(animals), confidence,
                source, why, weight, List.copyOf(rows));
    }

    /**
     * The [capacity] section. Keys: reference (a biome id and a season word),
     * floor (a number), why, source, confidence, plus optional rows of
     * multipliers. Rows may be empty, since 1.0 everywhere is a fine start.
     */
    private static Rules.CapacitySettings buildCapacity(Raw raw, Map<String, Rules.Group> groups, List<String> errors) {
        String at = where(raw.file, raw.line);
        int before = errors.size();
        if (raw.text.containsKey("animals") || raw.text.containsKey("biomes")) {
            errors.add(at + "[capacity] can't have 'animals =' or 'biomes ='");
        }

        String referenceBiome = "";
        String referencePhase = "";
        String reference = raw.text.get("reference");
        if (reference == null) {
            errors.add(at + "[capacity] needs 'reference = <biome id> <season>', like minecraft:forest summer");
        } else {
            String[] parts = reference.strip().split("\\s+");
            if (parts.length != 2 || !BIOME_MATCHER.matcher(parts[0]).matches() || parts[0].startsWith("#")) {
                errors.add(at + "reference must be one biome id and one season word, like minecraft:forest summer");
            } else if (!Rules.SEASONS.contains(parts[1]) && !Rules.TROPICAL_SEASONS.contains(parts[1])) {
                errors.add(at + "reference season '" + parts[1] + "' must be one of "
                        + Rules.SEASONS + " or " + Rules.TROPICAL_SEASONS);
            } else {
                referenceBiome = parts[0];
                referencePhase = parts[1];
            }
        }

        double floor = 0;
        String floorText = raw.text.get("floor");
        if (floorText == null) {
            errors.add(at + "[capacity] needs 'floor = <number>', the lowest cap a player is given");
        } else {
            try {
                floor = Double.parseDouble(floorText.strip());
                if (floor < 0) {
                    errors.add(at + "floor must be 0 or more");
                }
            } catch (NumberFormatException e) {
                errors.add(at + "floor '" + floorText + "' is not a number");
            }
        }

        Rules.Confidence confidence = null;
        String confidenceText = raw.text.get("confidence");
        if (confidenceText == null) {
            errors.add(at + "[capacity] needs 'confidence = sourced | reasoned | guess'");
        } else {
            try {
                confidence = Rules.Confidence.valueOf(confidenceText.strip().toUpperCase());
            } catch (IllegalArgumentException e) {
                errors.add(at + "confidence '" + confidenceText + "' must be sourced, reasoned or guess");
            }
        }
        String why = raw.text.get("why");
        if (why == null || why.isBlank()) {
            errors.add(at + "[capacity] needs a 'why =' line");
        }
        String source = raw.text.getOrDefault("source", "");
        if (confidence == Rules.Confidence.SOURCED && source.isBlank()) {
            errors.add(at + "[capacity] says 'sourced' but has no 'source ='");
        }

        List<Rules.Row> rows = buildRows(raw, groups, errors, MAX_CAPACITY_MULTIPLIER, "multiplier");
        if (errors.size() > before) {
            return null;
        }
        return new Rules.CapacitySettings(referenceBiome, referencePhase, floor, confidence, source, why,
                List.copyOf(rows), raw.file, raw.line);
    }

    /**
     * Checks and converts the rows of one section. Used for animals (numbers 0 to 1)
     * and for [capacity] (numbers 0 to 2). A row must have 4 numbers or 2, name a
     * known group (or 'any'), and be reachable: the first matching row wins, so a
     * later row for the same group and kind, or any row after 'any', can never run.
     */
    private static List<Rules.Row> buildRows(
            Raw raw, Map<String, Rules.Group> groups, List<String> errors, double maxValue, String what) {
        List<Rules.Row> rows = new ArrayList<>();
        // "group|kind" -> true once seen, so a later row for the same pair can't ever run
        Map<String, Boolean> seen = new LinkedHashMap<>();
        for (RawRow row : raw.rows) {
            String rowAt = where(raw.file, row.line());
            int count = row.numbers().size();
            if (count != Rules.SEASONS.size() && count != Rules.TROPICAL_SEASONS.size()) {
                errors.add(rowAt + row.group() + " needs 4 numbers (" + String.join(" ", Rules.SEASONS)
                        + ") or 2 numbers (" + String.join(" ", Rules.TROPICAL_SEASONS) + "). Got " + count + ".");
                continue;
            }
            boolean ok = true;
            for (double n : row.numbers()) {
                if (n < 0.0 || n > maxValue) {
                    errors.add(rowAt + what + " " + n + " is outside 0 to " + (maxValue == 1.0 ? "1" : maxValue));
                    ok = false;
                    break;
                }
            }
            if (!row.group().equals(Rules.ANYWHERE) && !groups.containsKey(row.group())) {
                errors.add(rowAt + "unknown biome group '" + row.group() + "'. Define it with [" + row.group()
                        + "] and 'biomes =' in biomes.rules.");
                ok = false;
            }
            String kind = count == 2 ? "tropical" : "standard";
            String key = row.group() + "|" + kind;
            if (seen.containsKey(key) || seen.containsKey(Rules.ANYWHERE + "|" + kind)) {
                errors.add(rowAt + "this row can never run. An earlier " + kind + " row already covers '"
                        + row.group() + "'. The first matching row wins.");
                ok = false;
            }
            seen.put(key, true);
            if (ok) {
                double[] values = row.numbers().stream().mapToDouble(Double::doubleValue).toArray();
                rows.add(new Rules.Row(row.group(), values, row.line()));
            }
        }
        return rows;
    }

    private static String where(String file, int line) {
        return file + ":" + line + ": ";
    }

    private RuleParser() {}
}
