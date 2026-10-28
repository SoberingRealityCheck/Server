package dev.elysium.atlas;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * The plant and ecoregion database as built into the mod (elysium_atlas/ecoregions.json, written by
 * variants/biome_variants.py from variants/db): per ecoregion its name, species by layer and derived colours.
 * Read-only; used by /atlas here.
 */
public final class Ecoregions {
    private static JsonObject db;

    private static synchronized JsonObject db() {
        if (db == null) {
            try (InputStream in = Ecoregions.class.getResourceAsStream("/elysium_atlas/ecoregions.json")) {
                db = in == null ? new JsonObject()
                        : JsonParser.parseReader(new InputStreamReader(in, StandardCharsets.UTF_8)).getAsJsonObject().getAsJsonObject("ecoregions");
            } catch (Exception e) {
                db = new JsonObject();
            }
        }
        return db;
    }

    /** A one-paragraph description of a region unit ("eco:689", or a split unit such as "eco:689:western_alps"), or null. */
    public static String describe(String unit) {
        if (unit == null || !unit.startsWith("eco:")) return null;
        String id = unit.substring(4).split(":")[0];
        JsonObject e = db().getAsJsonObject(id);
        if (e == null) return null;
        StringBuilder s = new StringBuilder(e.get("name").getAsString()).append(" (ecoregion ").append(id).append(")");
        s.append(" | grass ").append(e.get("grass").getAsString()).append(" foliage ").append(e.get("foliage").getAsString());
        for (String layer : new String[]{"trees", "shrubs", "ground", "flowers"}) {
            if (!e.has(layer)) continue;
            String list = e.getAsJsonObject(layer).entrySet().stream()
                    .sorted((a, b) -> Double.compare(b.getValue().getAsDouble(), a.getValue().getAsDouble()))
                    .map(Map.Entry::getKey).collect(Collectors.joining(", "));
            s.append(" | ").append(layer).append(": ").append(list);
        }
        return s.toString();
    }

    private Ecoregions() {}
}
