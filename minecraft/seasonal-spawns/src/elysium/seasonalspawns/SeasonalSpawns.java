package elysium.seasonalspawns;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import elysium.seasonalspawns.mixin.NaturalSpawnerAccessor;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.TagKey;
import net.minecraft.util.RandomSource;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.MobCategory;
import net.minecraft.world.level.biome.Biome;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import sereneseasons.api.season.ISeasonState;
import sereneseasons.api.season.SeasonHelper;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.HashSet;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

/**
 * The part that touches the game. It stays thin on purpose. Every
 * decision about a number lives in Rules, which has no Minecraft in it.
 *
 * What it does, in order:
 *   1. Reads config/elysium-seasonal-spawns/*.rules at startup and on /reload.
 *   2. NaturalSpawnerMixin calls allows() each time the game has picked
 *      a land animal to spawn.
 *   3. allows() asks Serene Seasons for the season, works out which biome
 *      groups the spot is in, asks Rules for a chance, and rolls.
 *   4. A failed roll cancels that one spawn. Nothing else changes.
 *
 * Hack: this only filters picks the game already made. It cannot add an
 * animal, and it cannot push a chance above the pack's normal. To get
 * "more deer in autumn", lower everything else, or raise the base rate
 * with the min_animals_near_player gamerule.
 */
public final class SeasonalSpawns implements ModInitializer {

    public static final Logger LOGGER = LoggerFactory.getLogger("elysium-seasonal-spawns");
    private static final String CONFIG_FOLDER = "elysium-seasonal-spawns";

    private static volatile Rules rules = Rules.EMPTY;

    // Server thread only. Both are cleared on every reload.
    private static final Map<Identifier, Set<String>> GROUPS_OF_BIOME = new HashMap<>();
    private static final Map<EntityType<?>, String> ID_OF_TYPE = new IdentityHashMap<>();
    /** animal id -> {allowed, vetoed}. For /seasonalspawns stats. */
    private static final Map<String, long[]> STATS = new TreeMap<>();

    @Override
    public void onInitialize() {
        reload();
        ServerLifecycleEvents.END_DATA_PACK_RELOAD.register((server, resources, success) -> reload());
        CommandRegistrationCallback.EVENT.register((dispatcher, buildContext, selection) -> registerCommands(dispatcher));
    }

    // ---- loading -------------------------------------------------------

    /** Returns true if the files loaded. On any mistake it logs every one and keeps the old rules. */
    static boolean reload() {
        Path dir = FabricLoader.getInstance().getConfigDir().resolve(CONFIG_FOLDER);
        if (!Files.isDirectory(dir)) {
            LOGGER.warn("No rules folder at {}. Seasonal spawns are off.", dir);
            return false;
        }
        RuleParser.Result result;
        try {
            result = RuleParser.parse(Table.readDir(dir));
        } catch (IOException e) {
            LOGGER.error("Could not read {}: {}", dir, e.toString());
            return false;
        }
        if (!result.errors().isEmpty()) {
            LOGGER.error("=== {} problem(s) in {}. Keeping the previous rules ({} animals). ===",
                    result.errors().size(), dir, rules.animals().size());
            result.errors().forEach(LOGGER::error);
            return false;
        }
        rules = result.rules();
        GROUPS_OF_BIOME.clear();
        ID_OF_TYPE.clear();
        LOGGER.info("Loaded {} sections, {} animals, {} biome groups from {}",
                rules.sections().size(), rules.animals().size(), rules.groups().size(), dir);
        return true;
    }

    // ---- the decision --------------------------------------------------

    /** Called by the mixin. True means go ahead with the spawn. */
    public static boolean allows(ServerLevel level, BlockPos pos, EntityType<?> type, RandomSource random) {
        double chance = chanceAt(level, pos, type);
        if (chance >= 1.0) {
            return true;
        }
        boolean ok = random.nextDouble() < chance;
        STATS.computeIfAbsent(idOf(type), k -> new long[2])[ok ? 0 : 1]++;
        return ok;
    }

    /** 1.0 when no rule applies, or when the dimension has no seasons. */
    static double chanceAt(ServerLevel level, BlockPos pos, EntityType<?> type) {
        Rules current = rules;
        String id = idOf(type);
        if (current.sectionOf(id) == null || !SeasonHelper.hasSeasons(level)) {
            return 1.0;
        }
        Holder<Biome> biome = level.getBiome(pos);
        boolean tropical = SeasonHelper.usesTropicalSeasons(biome);
        return current.chance(id, groupsOf(biome), tropical, phase(level, tropical));
    }

    /** Index into Rules.SEASONS, or into Rules.TROPICAL_SEASONS for tropical biomes. */
    private static int phase(ServerLevel level, boolean tropical) {
        ISeasonState state = SeasonHelper.getSeasonState(level);
        if (tropical) {
            // EARLY_DRY, MID_DRY, LATE_DRY, EARLY_WET, MID_WET, LATE_WET
            return state.getTropicalSeason().ordinal() < 3 ? 0 : 1;
        }
        // SPRING, SUMMER, AUTUMN, WINTER. Same order as Rules.SEASONS.
        return state.getSeason().ordinal();
    }

    private static String idOf(EntityType<?> type) {
        return ID_OF_TYPE.computeIfAbsent(type, t -> BuiltInRegistries.ENTITY_TYPE.getKey(t).toString());
    }

    private static Set<String> groupsOf(Holder<Biome> biome) {
        Identifier key = biome.unwrapKey().map(ResourceKey::identifier).orElse(null);
        if (key == null) {
            return Set.of(); // an inline biome with no registry name. Only 'any' rows can match it.
        }
        return GROUPS_OF_BIOME.computeIfAbsent(key, k -> computeGroups(biome));
    }

    private static Set<String> computeGroups(Holder<Biome> biome) {
        Set<String> found = new HashSet<>();
        for (Rules.Group group : rules.groups().values()) {
            for (String matcher : group.matchers()) {
                boolean hit = matcher.startsWith("#")
                        ? biome.is(TagKey.create(Registries.BIOME, Identifier.parse(matcher.substring(1))))
                        : biome.is(Identifier.parse(matcher));
                if (hit) {
                    found.add(group.name());
                    break;
                }
            }
        }
        return found;
    }

    // ---- commands ------------------------------------------------------

    private static void registerCommands(CommandDispatcher<CommandSourceStack> dispatcher) {
        dispatcher.register(Commands.literal("seasonalspawns")
                .requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                .then(Commands.literal("here").executes(c -> say(c.getSource(), here(c.getSource()))))
                .then(Commands.literal("stats").executes(c -> say(c.getSource(), stats())))
                .then(Commands.literal("audit").executes(c -> say(c.getSource(), audit(c.getSource()))))
                .then(Commands.literal("sample")
                        .executes(c -> say(c.getSource(), sample(c.getSource(), 1000)))
                        .then(Commands.argument("count", IntegerArgumentType.integer(1, 20000))
                                .executes(c -> say(c.getSource(),
                                        sample(c.getSource(), IntegerArgumentType.getInteger(c, "count"))))))
                .then(Commands.literal("reload").executes(c -> {
                    boolean ok = reload();
                    return say(c.getSource(), List.of(ok
                            ? "Reloaded " + rules.animals().size() + " animals."
                            : "Reload failed. Kept the old rules. The problems are in the server log."));
                })));
    }

    private static int say(CommandSourceStack source, List<String> lines) {
        for (String line : lines) {
            source.sendSuccess(() -> Component.literal(line), false);
        }
        return lines.size();
    }

    /** What the rules say at the sender's feet. The main tuning tool. */
    private static List<String> here(CommandSourceStack source) {
        ServerLevel level = source.getLevel();
        BlockPos pos = BlockPos.containing(source.getPosition());
        List<String> out = new java.util.ArrayList<>();
        if (!SeasonHelper.hasSeasons(level)) {
            out.add("This dimension has no seasons, so no rule applies here.");
            return out;
        }
        Holder<Biome> biome = level.getBiome(pos);
        boolean tropical = SeasonHelper.usesTropicalSeasons(biome);
        int phase = phase(level, tropical);
        String phaseName = tropical ? Rules.TROPICAL_SEASONS.get(phase) : Rules.SEASONS.get(phase);
        out.add((tropical ? "Tropical biome, " : "Standard biome, ") + phaseName + ". Biome: "
                + biome.unwrapKey().map(k -> k.identifier().toString()).orElse("(unnamed)"));
        out.add("Groups: " + String.join(", ", new java.util.TreeSet<>(groupsOf(biome))));
        out.add("Chance a picked spawn goes ahead (1.00 is normal). Only animals that differ:");
        int shown = 0;
        for (String animal : new java.util.TreeSet<>(rules.animals())) {
            double c = rules.chance(animal, groupsOf(biome), tropical, phase);
            if (c < 1.0) {
                Rules.Section s = rules.sectionOf(animal);
                out.add(String.format("  %-34s %.2f   [%s, %s]", animal, c, s.name(), s.confidence().name().toLowerCase()));
                shown++;
            }
        }
        if (shown == 0) {
            out.add("  (none. Every animal is at 1.00 here)");
        }
        return out;
    }

    /**
     * Asks the game's own picker for a land animal many times at the sender's feet,
     * with the rules switched on, and shows what came out. This is the mix the
     * spawner would try here right now. A pick the rules vetoed counts as "none".
     * Samples add to /seasonalspawns stats.
     */
    private static List<String> sample(CommandSourceStack source, int count) {
        ServerLevel level = source.getLevel();
        BlockPos pos = BlockPos.containing(source.getPosition());
        Map<String, Integer> seen = new TreeMap<>();
        for (int i = 0; i < count; i++) {
            var picked = NaturalSpawnerAccessor.elysium$pick(level, level.structureManager(),
                    level.getChunkSource().getGenerator(), MobCategory.CREATURE, level.getRandom(), pos);
            seen.merge(picked.map(p -> idOf(p.type())).orElse("(nothing: vetoed, or no animals here)"), 1, Integer::sum);
        }
        List<String> out = new java.util.ArrayList<>();
        out.add(count + " picks at " + pos.toShortString() + ":");
        seen.entrySet().stream()
                .sorted((a, b) -> b.getValue() - a.getValue())
                .forEach(e -> out.add(String.format("  %-40s %5d  %4.1f%%", e.getKey(), e.getValue(),
                        100.0 * e.getValue() / count)));
        return out;
    }

    private static List<String> stats() {
        List<String> out = new java.util.ArrayList<>();
        out.add("Spawns the rules decided on since startup (allowed / vetoed):");
        if (STATS.isEmpty()) {
            out.add("  (none yet)");
        }
        STATS.forEach((animal, n) -> out.add(String.format("  %-34s %6d / %-6d  (%.0f%% allowed)",
                animal, n[0], n[1], 100.0 * n[0] / Math.max(1, n[0] + n[1]))));
        return out;
    }

    /** Lists every biome and its groups to the server log. Shows biomes no group covers. */
    private static List<String> audit(CommandSourceStack source) {
        var biomes = source.getServer().registryAccess().lookupOrThrow(Registries.BIOME);
        int uncovered = 0;
        int total = 0;
        LOGGER.info("--- biome audit: biome -> groups ---");
        for (Holder.Reference<Biome> holder : (Iterable<Holder.Reference<Biome>>) biomes.listElements()::iterator) {
            Set<String> groups = new java.util.TreeSet<>(computeGroups(holder));
            total++;
            if (groups.isEmpty()) {
                uncovered++;
            }
            LOGGER.info("{} -> {}{}", holder.key().identifier(), groups.isEmpty() ? "(none)" : groups,
                    SeasonHelper.usesTropicalSeasons(holder) ? "  [tropical]" : "");
        }
        return List.of(total + " biomes. " + uncovered + " are in no group (only 'any' rows reach them).",
                "The full list is in the server log.");
    }
}
