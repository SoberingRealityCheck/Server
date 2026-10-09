package elysium.seasonalspawns;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Stream;

/**
 * Prints every rule as a grid. Run it after editing a .rules file.
 *
 *   java -cp .build/classes elysium.seasonalspawns.Table path/to/rules-dir
 *
 * No Minecraft needed. If a file has a mistake it prints each mistake
 * as "file:line: message" and exits 1. The game does the same check
 * when it loads the files.
 */
public final class Table {

    /** Reads every *.rules file in a directory, in name order. */
    public static List<RuleParser.Source> readDir(Path dir) throws IOException {
        List<Path> files;
        try (Stream<Path> stream = Files.list(dir)) {
            files = stream.filter(p -> p.getFileName().toString().endsWith(".rules")).sorted().toList();
        }
        List<RuleParser.Source> sources = new ArrayList<>();
        for (Path file : files) {
            sources.add(new RuleParser.Source(file.getFileName().toString(), Files.readString(file)));
        }
        return sources;
    }

    /** The grid as text. Honest: rules in, string out. */
    public static String render(Rules rules) {
        StringBuilder out = new StringBuilder();
        out.append("Chance a picked spawn goes ahead. 1.00 = normal. 0.00 = never.\n");
        out.append("Standard biomes use spring/summer/autumn/winter. Tropical biomes use dry/wet.\n");
        for (Rules.Section section : rules.sections()) {
            out.append('\n');
            out.append(String.format("[%s]  %s  (%s:%d)%n", section.name(),
                    section.confidence().name().toLowerCase(), section.file(), section.line()));
            out.append("  ").append(String.join(", ", section.animals())).append('\n');
            boolean anyStandard = section.rows().stream().anyMatch(r -> !r.tropical());
            if (anyStandard) {
                out.append(String.format("  %-18s %7s %7s %7s %7s%n", "", "spring", "summer", "autumn", "winter"));
            }
            for (Rules.Row row : section.rows()) {
                if (!row.tropical()) {
                    out.append(String.format("  %-18s", row.group()));
                    for (double c : row.chances()) {
                        out.append(String.format(" %7.2f", c));
                    }
                    out.append('\n');
                }
            }
            boolean headerDone = false;
            for (Rules.Row row : section.rows()) {
                if (row.tropical()) {
                    if (!headerDone) {
                        out.append(String.format("  %-18s %7s %7s%n", "(tropical)", "dry", "wet"));
                        headerDone = true;
                    }
                    out.append(String.format("  %-18s", row.group()));
                    for (double c : row.chances()) {
                        out.append(String.format(" %7.2f", c));
                    }
                    out.append('\n');
                }
            }
        }
        return out.toString();
    }

    public static void main(String[] args) throws IOException {
        if (args.length != 1) {
            System.err.println("usage: Table <rules-dir>");
            System.exit(2);
        }
        RuleParser.Result result = RuleParser.parse(readDir(Path.of(args[0])));
        if (!result.errors().isEmpty()) {
            result.errors().forEach(System.err::println);
            System.err.println(result.errors().size() + " problem(s). Fix them and run again.");
            System.exit(1);
        }
        System.out.print(render(result.rules()));
        System.out.println();
        System.out.println(result.rules().sections().size() + " sections, "
                + result.rules().animals().size() + " animals, "
                + result.rules().groups().size() + " biome groups.");
    }

    private Table() {}
}
