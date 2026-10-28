package dev.elysium.atlas.client;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.core.Holder;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.block.Block;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.InputStream;
import java.io.InputStreamReader;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Explicit season palettes (elysium_atlas/season_palettes.json, written by variants/seasons.py): per region, the colour
 * of grass and of each leaf block in every Serene Seasons subseason (12, or the 6 tropical ones), with -1 for a
 * leafless crown. Colours change only at subseason boundaries, when Serene Seasons re-renders the chunks; between
 * subseasons the build has already blended the keys. Serene Seasons is read by reflection, so the mod runs without it
 * (mid summer, or mid wet for tropical regions). Client only.
 */
public final class SeasonPalettes {
    private static final Logger LOG = LoggerFactory.getLogger("elysium_atlas");
    static final int GRASS = -2;    // pseudo-block index for the grass palette
    private static final List<String> TROPICAL = List.of("EARLY_WET", "MID_WET", "LATE_WET", "EARLY_DRY", "MID_DRY", "LATE_DRY");

    record Region(boolean tropical, int[] grass, Map<Block, int[]> leaves) {}

    private static Map<Integer, Region> regions;
    private static int bare;
    private static final Map<Identifier, Optional<Region>> byBiome = new ConcurrentHashMap<>();

    private record Now(ClientLevel level, long tick, int sub, int trop) {}
    private static volatile Now now;
    private static Method getState, hasSeasons, subSeason, tropicalSeason;
    private static boolean reflected;

    /** The explicit colour of a block (or GRASS) in the region of this biome now, -1 for bare, or null if none. */
    static Integer colour(Holder<Biome> biome, Block block, ClientLevel level) {
        Region r = region(biome);
        if (r == null) return null;
        int[] p = block == null ? r.grass() : r.leaves().get(block);
        if (p == null) return null;
        Now n = now(level);
        int c = p[r.tropical() ? n.trop() : n.sub()];
        return c == -1 ? bare : c;
    }

    private static Region region(Holder<Biome> h) {
        if (regions == null) load();
        Optional<ResourceKey<Biome>> k = h.unwrapKey();
        if (k.isEmpty() || regions.isEmpty()) return null;
        Identifier id = k.get().identifier();
        return byBiome.computeIfAbsent(id, i -> {
            String p = i.getPath();     // elysium:eco/<ecoregion>/<parent>
            if (!i.getNamespace().equals("elysium") || !p.startsWith("eco/")) return Optional.empty();
            int s = p.indexOf('/', 4);
            try { return Optional.ofNullable(regions.get(Integer.parseInt(p.substring(4, s < 0 ? p.length() : s)))); }
            catch (NumberFormatException e) { return Optional.empty(); }
        }).orElse(null);
    }

    private static Now now(ClientLevel level) {
        Now n = now;
        long t = level.getGameTime();
        if (n != null && n.level() == level && n.tick() == t) return n;
        int sub = 4, trop = 1;     // mid summer, mid wet
        try {
            if (!reflected) reflect();
            if (getState != null && (boolean) hasSeasons.invoke(null, level)) {
                Object st = getState.invoke(null, level);
                sub = ((Enum<?>) subSeason.invoke(st)).ordinal();
                trop = TROPICAL.indexOf(((Enum<?>) tropicalSeason.invoke(st)).name());
            }
        } catch (ReflectiveOperationException | RuntimeException e) {
            getState = null;
            LOG.warn("Serene Seasons state unavailable; season palettes stay at mid summer", e);
        }
        n = new Now(level, t, sub, Math.max(0, trop));
        now = n;
        return n;
    }

    private static synchronized void reflect() {
        if (reflected) return;
        reflected = true;
        try {
            Class<?> h = Class.forName("sereneseasons.api.season.SeasonHelper");
            Class<?> s = Class.forName("sereneseasons.api.season.ISeasonState");
            getState = h.getMethod("getSeasonState", Level.class);
            hasSeasons = h.getMethod("hasSeasons", Level.class);
            subSeason = s.getMethod("getSubSeason");
            tropicalSeason = s.getMethod("getTropicalSeason");
        } catch (ReflectiveOperationException e) {
            getState = null;    // no Serene Seasons
        }
    }

    private static synchronized void load() {
        if (regions != null) return;
        Map<Integer, Region> m = new HashMap<>();
        try (InputStream in = SeasonPalettes.class.getResourceAsStream("/elysium_atlas/season_palettes.json")) {
            if (in != null) {
                JsonObject j = JsonParser.parseReader(new InputStreamReader(in, StandardCharsets.UTF_8)).getAsJsonObject();
                bare = 0xFF000000 | j.get("bare").getAsInt();
                for (Map.Entry<String, JsonElement> e : j.getAsJsonObject("regions").entrySet()) {
                    JsonObject r = e.getValue().getAsJsonObject();
                    int[] grass = null;
                    Map<Block, int[]> leaves = new HashMap<>();
                    for (Map.Entry<String, JsonElement> b : r.getAsJsonObject("blocks").entrySet()) {
                        int[] p = ints(b.getValue().getAsJsonArray());
                        if (b.getKey().equals("grass")) { grass = p; continue; }
                        Identifier id = Identifier.parse(b.getKey());
                        if (BuiltInRegistries.BLOCK.containsKey(id)) leaves.put(BuiltInRegistries.BLOCK.getValue(id), p);
                    }
                    m.put(Integer.parseInt(e.getKey()), new Region(r.get("tropical").getAsBoolean(), grass, leaves));
                }
            }
        } catch (Exception ex) {
            LOG.error("Season palettes not loaded", ex);
        }
        LOG.info("Season palettes for {} regions", m.size());
        regions = m;
    }

    private static int[] ints(JsonArray a) {
        int[] o = new int[a.size()];
        for (int i = 0; i < o.length; i++) {
            int v = a.get(i).getAsInt();
            o[i] = v < 0 ? -1 : 0xFF000000 | v;
        }
        return o;
    }

    private SeasonPalettes() {}
}
