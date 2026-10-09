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
    private static final List<String> TEXT_KEYS = List.of("animals", "biomes", "why", "source", "confidence");

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
        for (Raw raw : raws) {
            if (raw.text.containsKey("biomes")) {
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
        return new Result(new Rules(groups, sections, byAnimal), errors);
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
        if (raw.name.equals(Rules.ANYWHERE) || TEXT_KEYS.contains(raw.name)) {
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

        if (raw.rows.isEmpty()) {
            errors.add(at + "[" + raw.name + "] has no rows");
        }
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
                if (n < 0.0 || n > 1.0) {
                    errors.add(rowAt + "chance " + n + " is outside 0 to 1");
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

        if (errors.size() > before) {
            return null;
        }
        return new Rules.Section(raw.name, raw.file, raw.line, List.copyOf(animals), confidence,
                source, why, List.copyOf(rows));
    }

    private static String where(String file, int line) {
        return file + ":" + line + ": ";
    }

    private RuleParser() {}
}
