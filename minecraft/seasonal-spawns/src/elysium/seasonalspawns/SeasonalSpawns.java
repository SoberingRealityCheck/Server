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
        // The cap table reads every biome, so it waits until the server's registries and tags exist.
        ServerLifecycleEvents.SERVER_STARTED.register(server -> {
            verifyCapHook();
            CapacityTable.rebuild(server, rules);
        });
        ServerLifecycleEvents.END_DATA_PACK_RELOAD.register((server, resources, success) -> {
            reload();
            CapacityTable.rebuild(server, rules);
        });
        CommandRegistrationCallback.EVENT.register((dispatcher, buildContext, selection) -> registerCommands(dispatcher));
    }

    /**
     * Mixins are applied when a class first loads. The cap calculator would not load until
     * the first player walks around, so a broken cap hook would hide until then. Load it now.
     * If the hook is wrong the server stops here with a clear message, like the spawn hook does.
     */
    private static void verifyCapHook() {
        try {
            Class.forName("net.minecraft.world.level.LocalMobCapCalculator");
            Class<?> counts = Class.forName("net.minecraft.world.level.LocalMobCapCalculator$MobCounts");
            if (!elysium.seasonalspawns.mixin.MobCountsAccessor.class.isAssignableFrom(counts)) {
                throw new IllegalStateException("the MobCounts accessor was not applied");
            }
            LOGGER.info("Creature cap hook applied.");
        } catch (Throwable t) {
            LOGGER.error("The creature cap hook did not apply. Minecraft probably changed LocalMobCapCalculator.", t);
            throw new IllegalStateException("elysium-seasonal-spawns: creature cap hook failed", t);
        }
    }

    /** Called by LocalMobCapCalculatorMixin. -1 means "use the game's own cap". */
    public static double capFor(net.minecraft.server.level.ServerPlayer player) {
        return CapacityTable.capFor(player, rules);
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
    static int phase(ServerLevel level, boolean tropical) {
        ISeasonState state = SeasonHelper.getSeasonState(level);
        if (tropical) {
            // EARLY_DRY, MID_DRY, LATE_DRY, EARLY_WET, MID_WET, LATE_WET
            return state.getTropicalSeason().ordinal() < 3 ? 0 : 1;
        }
        // SPRING, SUMMER, AUTUMN, WINTER. Same order as Rules.SEASONS.
        return state.getSeason().ordinal();
    }

    static String idOfType(EntityType<?> type) {
        return idOf(type);
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

    static Set<String> computeGroups(Holder<Biome> biome) {
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
                .then(Commands.literal("capacity").executes(c -> say(c.getSource(), capacity())))
                .then(Commands.literal("reload").executes(c -> {
                    boolean ok = reload();
                    if (ok) {
                        CapacityTable.rebuild(c.getSource().getServer(), rules);
                    }
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
        out.addAll(capHere(source, level, pos));
        return out;
    }

    /** The land-animal cap at the sender's spot, and how many animals are near. */
    private static List<String> capHere(CommandSourceStack source, ServerLevel level, BlockPos pos) {
        List<String> out = new java.util.ArrayList<>();
        if (!CapacityTable.enabled()) {
            out.add("Creature cap: off (no [capacity] section). The game's own cap applies.");
            return out;
        }
        int base = MobCategory.CREATURE.getMaxInstancesPerChunk();
        double area = CapacityTable.areaFraction(level, pos);
        if (area < 0) {
            out.add("Creature cap: no land around here, so the game's own cap (" + base + ") applies.");
            return out;
        }
        double floor = rules.capacity().floor();
        double cap = Capacity.cap(base, area, floor);
        var near = level.getEntitiesOfClass(net.minecraft.world.entity.Mob.class,
                new net.minecraft.world.phys.AABB(pos).inflate(128),
                m -> m.getType().getCategory() == MobCategory.CREATURE
                        && !m.isPersistenceRequired() && !m.requiresCustomPersistence());
        out.add(String.format("Creature cap here: %.1f of a base %d (area average %.2f of the reference, floor %.0f). "
                + "Animals counted within 128 blocks: %d.", cap, base, area, floor, near.size()));
        return out;
    }

    /** The whole table goes to the server log. The chat gets the reference and the extremes. */
    private static List<String> capacity() {
        List<String> out = new java.util.ArrayList<>();
        if (!CapacityTable.enabled()) {
            out.add("Creature cap is off. Add a [capacity] section to capacity.rules to turn it on.");
            return out;
        }
        Rules.CapacitySettings s = rules.capacity();
        out.add(CapacityTable.referenceNote());
        out.add(String.format("Base cap %d (from Respawning Animals). Lowest cap %.0f.",
                MobCategory.CREATURE.getMaxInstancesPerChunk(), s.floor()));
        List<String> lines = CapacityTable.lines();
        LOGGER.info("--- creature cap table: biome, fraction of the reference by season ---");
        lines.forEach(LOGGER::info);
        out.add(lines.size() + " land biomes. Richest five, then poorest five (fractions of the reference):");
        for (int i = 0; i < Math.min(5, lines.size()); i++) {
            out.add("  " + lines.get(i));
        }
        out.add("  ...");
        for (int i = Math.max(5, lines.size() - 5); i < lines.size(); i++) {
            out.add("  " + lines.get(i));
        }
        out.add("The full list is in the server log.");
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
