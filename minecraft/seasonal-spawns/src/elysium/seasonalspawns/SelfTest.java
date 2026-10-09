package elysium.seasonalspawns;

import java.util.List;
import java.util.Set;

/**
 * Plain checks, no test framework. build.sh runs this. Exit code 1 on failure.
 * Nothing here touches Minecraft or the disk.
 */
public final class SelfTest {

    private static int checks = 0;
    private static int failed = 0;

    private static final String GOOD = """
            [forest]
            biomes = #minecraft:is_forest minecraft:taiga

            [savanna]
            biomes = #minecraft:is_savanna

            [bear]
            animals    = test:bear
            confidence = sourced
            source     = https://example.org/bears
            why        = Bears sleep through winter.
                         Second line of the reason.
            forest  = 0.8 1.0 1.0 0.0    # spring summer autumn winter
            any     = 0.5 0.5 0.5 0.5
            savanna = 1.0 0.25

            [lion]
            animals    = test:lion
            confidence = guess
            why        = Plain test data.
            savanna = 1.0 0.25
            """;

    public static void main(String[] args) {
        RuleParser.Result good = RuleParser.parse(List.of(new RuleParser.Source("good.rules", GOOD)));
        check("good file has no errors", good.errors().isEmpty(), good.errors().toString());
        Rules rules = good.rules();

        Set<String> forest = Set.of("forest");
        Set<String> nothing = Set.of();
        Set<String> savanna = Set.of("savanna");

        near("forest winter", 0.0, rules.chance("test:bear", forest, false, 3));
        near("forest spring", 0.8, rules.chance("test:bear", forest, false, 0));
        near("first matching row wins over 'any'", 1.0, rules.chance("test:bear", forest, false, 1));
        near("falls through to 'any'", 0.5, rules.chance("test:bear", nothing, false, 3));
        near("tropical biome uses the 2-number row", 0.25, rules.chance("test:bear", savanna, true, 1));
        near("tropical biome skips 4-number rows, even 'any'", 1.0, rules.chance("test:bear", forest, true, 0));
        near("standard biome ignores 2-number rows", 1.0, rules.chance("test:lion", savanna, false, 1));
        near("animal with no section is untouched", 1.0, rules.chance("test:cow", forest, false, 3));
        check("why text joins continuation lines",
                rules.sectionOf("test:bear").why().equals("Bears sleep through winter. Second line of the reason."),
                rules.sectionOf("test:bear").why());
        check("inline # comment on a row is dropped", rules.sectionOf("test:bear").rows().get(0).chances().length == 4, "");

        // each of these must be rejected, and the message must say where
        fails("unknown group", "[a]\nanimals = t:a\nconfidence = guess\nwhy = x\nnope = 1 1 1 1\n", "unknown biome group 'nope'");
        fails("chance above 1", "[g]\nbiomes = a:b\n[a]\nanimals = t:a\nconfidence = guess\nwhy = x\ng = 1 1 1 2\n", "outside 0 to 1");
        fails("three numbers", "[g]\nbiomes = a:b\n[a]\nanimals = t:a\nconfidence = guess\nwhy = x\ng = 1 1 1\n", "needs 4 numbers");
        fails("missing why", "[g]\nbiomes = a:b\n[a]\nanimals = t:a\nconfidence = guess\ng = 1 1 1 1\n", "needs a 'why =' line");
        fails("sourced without source", "[g]\nbiomes = a:b\n[a]\nanimals = t:a\nconfidence = sourced\nwhy = x\ng = 1 1 1 1\n", "no 'source ='");
        fails("bad confidence", "[g]\nbiomes = a:b\n[a]\nanimals = t:a\nconfidence = sure\nwhy = x\ng = 1 1 1 1\n", "must be sourced, reasoned or guess");
        fails("same animal twice",
                "[g]\nbiomes = a:b\n[a]\nanimals = t:a\nconfidence = guess\nwhy = x\ng = 1 1 1 1\n"
                        + "[b]\nanimals = t:a\nconfidence = guess\nwhy = x\ng = 1 1 1 1\n", "already in [a]");
        fails("row after 'any' can never run",
                "[g]\nbiomes = a:b\n[a]\nanimals = t:a\nconfidence = guess\nwhy = x\nany = 1 1 1 1\ng = 1 1 1 1\n", "can never run");
        fails("bad entity id", "[g]\nbiomes = a:b\n[a]\nanimals = bear\nconfidence = guess\nwhy = x\ng = 1 1 1 1\n", "not an entity id");
        fails("line outside a section", "oops = 1\n", "outside any [section]");

        System.out.println(checks + " checks, " + failed + " failed");
        if (failed > 0) {
            System.exit(1);
        }
    }

    private static void fails(String label, String text, String expectedPart) {
        RuleParser.Result r = RuleParser.parse(List.of(new RuleParser.Source("bad.rules", text)));
        boolean hit = r.errors().stream().anyMatch(e -> e.startsWith("bad.rules:") && e.contains(expectedPart));
        check("rejects: " + label, hit, r.errors().toString());
    }

    private static void near(String label, double want, double got) {
        check(label, Math.abs(want - got) < 1e-9, "want " + want + " got " + got);
    }

    private static void check(String label, boolean ok, String detail) {
        checks++;
        if (!ok) {
            failed++;
            System.out.println("FAIL " + label + (detail.isEmpty() ? "" : "  -> " + detail));
        }
    }

    private SelfTest() {}
}
