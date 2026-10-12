package elysium.seasonalspawns;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.util.random.Weighted;
import net.minecraft.world.entity.MobCategory;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.MobSpawnSettings;
import net.minecraft.world.level.levelgen.Heightmap;
import sereneseasons.api.season.SeasonHelper;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * The game-facing half of the creature cap. Capacity.java holds the math.
 * This file reads the biomes, builds one row per biome, and answers one
 * question for the mixin: "what is this player's land-animal cap right now?"
 *
 * Built once per server start and once per data reload. Server thread only.
 *
 * How a player's cap is worked out:
 *   - Sample 9 spots around the player, 64 blocks apart. That covers the area
 *     the game counts animals over (about 128 blocks). Each spot is read at the
 *     surface, so a miner underground still gets the cap of the land above.
 *   - Each spot's biome has a row in the table: a fraction of the reference.
 *   - Average the fractions of the spots that are land. Ocean has no land
 *     animals, so it is skipped and does not drag a beach cap down.
 *   - cap = base x average, never below the floor. The base is the cap
 *     Respawning Animals already set (15 by default).
 *   - Cached for 100 ticks per player. The biome noise is not free.
 */
final class CapacityTable {

    /** One biome. sums and fractions have 4 entries (ordinary) or 2 (tropical). */
    record Row(double[] sums, double[] fractions, boolean tropical, boolean land) {}

    private static final int REFRESH_TICKS = 100;
    private static final int SAMPLE_SPACING = 64;

    private static volatile Map<Identifier, Row> table = Map.of();
    private static volatile double referenceSum = 0;
    private static volatile String referenceNote = "";

    /** player -> {tick it was worked out, cap}. Cleared on every rebuild. */
    private static final Map<UUID, double[]> PLAYER_CAP = new HashMap<>();

    static boolean enabled() {
        return !table.isEmpty();
    }

    static String referenceNote() {
        return referenceNote;
    }

    static Map<Identifier, Row> table() {
        return table;
    }

    // ---- building ------------------------------------------------------

    /** Goes through every biome. Call after the registries and tags are loaded. */
    static void rebuild(MinecraftServer server, Rules rules) {
        PLAYER_CAP.clear();
        Rules.CapacitySettings settings = rules.capacity();
        if (settings == null) {
            table = Map.of();
            return;
        }
        Registry<Biome> biomes = server.registryAccess().lookupOrThrow(Registries.BIOME);

        Map<Identifier, double[]> sums = new HashMap<>();
        Map<Identifier, Boolean> tropicalOf = new HashMap<>();
        Map<Identifier, Set<String>> groupsOf = new HashMap<>();
        Map<Identifier, Boolean> landOf = new HashMap<>();
        for (Holder.Reference<Biome> holder : (Iterable<Holder.Reference<Biome>>) biomes.listElements()::iterator) {
            Identifier key = holder.key().identifier();
            Set<String> groups = SeasonalSpawns.computeGroups(holder);
            boolean tropical = SeasonHelper.usesTropicalSeasons(holder);
            List<Capacity.Entry> entries = entriesOf(holder.value());
            double[] s = new double[tropical ? Rules.TROPICAL_SEASONS.size() : Rules.SEASONS.size()];
            for (int phase = 0; phase < s.length; phase++) {
                final int p = phase;
                s[p] = Capacity.weightedSum(entries, id -> rules.chance(id, groups, tropical, p));
            }
            sums.put(key, s);
            tropicalOf.put(key, tropical);
            groupsOf.put(key, groups);
            landOf.put(key, !entries.isEmpty());
        }

        double ref = referenceFrom(settings, sums, tropicalOf);
        referenceSum = ref;

        Map<Identifier, Row> built = new HashMap<>();
        for (Map.Entry<Identifier, double[]> e : sums.entrySet()) {
            Identifier key = e.getKey();
            boolean tropical = tropicalOf.get(key);
            double[] s = e.getValue();
            double[] f = new double[s.length];
            for (int p = 0; p < s.length; p++) {
                f[p] = Capacity.fraction(s[p], ref, rules.capacityMultiplier(groupsOf.get(key), tropical, p));
            }
            built.put(key, new Row(s, f, tropical, landOf.get(key)));
        }
        table = built;
        SeasonalSpawns.LOGGER.info("Creature cap table built for {} biomes. {}", built.size(), referenceNote);
    }

    /** The weight sum that counts as 1.0. Falls back to the largest sum anywhere, loudly. */
    private static double referenceFrom(Rules.CapacitySettings settings, Map<Identifier, double[]> sums,
                                        Map<Identifier, Boolean> tropicalOf) {
        Identifier refKey = Identifier.tryParse(settings.referenceBiome());
        double[] s = refKey == null ? null : sums.get(refKey);
        if (s != null) {
            int phase = Rules.phaseIndex(settings.referencePhase(), tropicalOf.get(refKey));
            if (phase >= 0 && s[phase] > 0) {
                referenceNote = String.format("Reference %s in %s: weight sum %.1f = 1.0.",
                        settings.referenceBiome(), settings.referencePhase(), s[phase]);
                return s[phase];
            }
        }
        double max = 0;
        for (double[] row : sums.values()) {
            for (double v : row) {
                max = Math.max(max, v);
            }
        }
        referenceNote = String.format("Reference %s %s is missing or empty, so the largest weight sum "
                + "anywhere (%.1f) is 1.0 instead.", settings.referenceBiome(), settings.referencePhase(), max);
        SeasonalSpawns.LOGGER.warn("[capacity] {}", referenceNote);
        return max;
    }

    /** A biome's land-animal spawn list as plain entries. */
    private static List<Capacity.Entry> entriesOf(Biome biome) {
        List<Capacity.Entry> out = new ArrayList<>();
        for (Weighted<MobSpawnSettings.SpawnerData> w : biome.getMobSettings().getMobs(MobCategory.CREATURE).unwrap()) {
            MobSpawnSettings.SpawnerData data = w.value();
            out.add(new Capacity.Entry(SeasonalSpawns.idOfType(data.type()), w.weight(),
                    (data.minCount() + data.maxCount()) / 2.0));
        }
        return out;
    }

    // ---- asking --------------------------------------------------------

    /**
     * This player's cap for land animals, or -1 if the feature is off, the
     * dimension has no seasons, or no sample spot is land (then the game's own
     * cap is used).
     */
    static double capFor(ServerPlayer player, Rules rules) {
        Rules.CapacitySettings settings = rules.capacity();
        Map<Identifier, Row> rows = table;
        if (settings == null || rows.isEmpty()) {
            return -1;
        }
        ServerLevel level = player.level();
        if (!SeasonHelper.hasSeasons(level)) {
            return -1;
        }
        long now = level.getGameTime();
        double[] cached = PLAYER_CAP.get(player.getUUID());
        if (cached != null && now - (long) cached[0] < REFRESH_TICKS) {
            return cached[1];
        }
        double cap = compute(level, player.blockPosition(), rows, settings);
        PLAYER_CAP.put(player.getUUID(), new double[]{now, cap});
        return cap;
    }

    /**
     * The average fraction around a spot, or -1 if none of the sample spots is usable land.
     *
     * Each spot is looked up AT THE SURFACE, not at the player's height. Biomes are 3D, so a
     * player mining at y=0 would otherwise get a cave biome, and the surface animals above them
     * would be capped by whatever cave they stand in. A spot whose chunk is not loaded is
     * skipped, so this never forces a chunk to load.
     */
    static double areaFraction(ServerLevel level, BlockPos center) {
        Map<Identifier, Row> rows = table;
        double total = 0;
        int n = 0;
        for (int dx = -1; dx <= 1; dx++) {
            for (int dz = -1; dz <= 1; dz++) {
                int x = center.getX() + dx * SAMPLE_SPACING;
                int z = center.getZ() + dz * SAMPLE_SPACING;
                if (!level.hasChunkAt(new BlockPos(x, 0, z))) {
                    continue;
                }
                int y = level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x, z);
                Double f = fractionAt(level, new BlockPos(x, y, z), rows);
                if (f != null) {
                    total += f;
                    n++;
                }
            }
        }
        return n == 0 ? -1 : total / n;
    }

    private static double compute(ServerLevel level, BlockPos center, Map<Identifier, Row> rows,
                                  Rules.CapacitySettings settings) {
        double fraction = areaFraction(level, center);
        if (fraction < 0) {
            return -1;
        }
        return Capacity.cap(MobCategory.CREATURE.getMaxInstancesPerChunk(), fraction, settings.floor());
    }

    /** The fraction for one spot, or null if the biome has no land animals or is not in the table. */
    static Double fractionAt(ServerLevel level, BlockPos pos, Map<Identifier, Row> rows) {
        Holder<Biome> biome = level.getBiome(pos);
        Identifier key = biome.unwrapKey().map(ResourceKey::identifier).orElse(null);
        Row row = key == null ? null : rows.get(key);
        if (row == null || !row.land()) {
            return null;
        }
        return row.fractions()[SeasonalSpawns.phase(level, row.tropical())];
    }

    // ---- reporting -----------------------------------------------------

    /** Every land biome with its fractions, for the log and for /seasonalspawns capacity. */
    static List<String> lines() {
        List<Map.Entry<Identifier, Row>> land = new ArrayList<>();
        for (Map.Entry<Identifier, Row> e : table.entrySet()) {
            if (e.getValue().land()) {
                land.add(e);
            }
        }
        land.sort(Comparator.comparingDouble(
                (Map.Entry<Identifier, Row> e) -> mean(e.getValue().fractions())).reversed());
        List<String> out = new ArrayList<>();
        for (Map.Entry<Identifier, Row> e : land) {
            Row r = e.getValue();
            StringBuilder b = new StringBuilder(String.format("%-36s", e.getKey()));
            List<String> names = r.tropical() ? Rules.TROPICAL_SEASONS : Rules.SEASONS;
            for (int p = 0; p < r.fractions().length; p++) {
                b.append(String.format(" %s %.2f", names.get(p), r.fractions()[p]));
            }
            b.append(String.format("   (weight sum %s)", sumText(r.sums())));
            out.add(b.toString());
        }
        return out;
    }

    private static String sumText(double[] sums) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < sums.length; i++) {
            b.append(i == 0 ? "" : "/").append(String.format("%.0f", sums[i]));
        }
        return b.toString();
    }

    private static double mean(double[] values) {
        double t = 0;
        for (double v : values) {
            t += v;
        }
        return values.length == 0 ? 0 : t / values.length;
    }

    private CapacityTable() {}
}
