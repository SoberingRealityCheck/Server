package dev.elysium.atlas.client;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import net.minecraft.client.color.block.BlockTintSource;
import net.minecraft.client.renderer.BiomeColors;
import net.minecraft.client.renderer.block.BlockAndTintGetter;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.Identifier;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Regional colours for spruce, birch, mangrove and the flora mods' green leaves (elysium_atlas/leaf_tints.json,
 * written by variants/leaf_tints.py). Each species is the biome's foliage colour moved by the species' own offset
 * (hue shift, saturation ratio, value ratio, measured against vanilla's default foliage colour), so species stay
 * distinct and all of them follow the region and the season. Client only.
 */
public final class LeafTints {
    private static final Logger LOG = LoggerFactory.getLogger("elysium_atlas");
    private static Map<Block, List<BlockTintSource>> sources;

    /** Our tint sources for a block, or null to leave it to vanilla and the other mods. */
    public static List<BlockTintSource> of(Block b) {
        if (sources == null) load();
        return sources.get(b);
    }

    private static synchronized void load() {
        if (sources != null) return;
        Map<Block, List<BlockTintSource>> m = new HashMap<>();
        try (InputStream in = LeafTints.class.getResourceAsStream("/elysium_atlas/leaf_tints.json")) {
            JsonObject j = JsonParser.parseReader(new InputStreamReader(in, StandardCharsets.UTF_8)).getAsJsonObject();
            int base = j.get("foliage_default").getAsInt();
            for (Map.Entry<String, JsonElement> e : j.getAsJsonObject("leaves").entrySet()) {
                Identifier id = Identifier.parse(e.getKey());
                if (!BuiltInRegistries.BLOCK.containsKey(id)) continue;
                JsonArray o = e.getValue().getAsJsonArray();
                m.put(BuiltInRegistries.BLOCK.getValue(id), List.of(new Species(o.get(0).getAsFloat(), o.get(1).getAsFloat(), o.get(2).getAsFloat(), base)));
            }
        } catch (Exception ex) {
            LOG.error("Leaf tints not loaded", ex);
        }
        LOG.info("Regional leaf tints for {} leaf blocks", m.size());
        sources = m;
    }

    record Species(float dh, float ds, float dv, int base) implements BlockTintSource {
        @Override public int color(BlockState state) { return shift(base); }
        @Override public int colorInWorld(BlockState state, BlockAndTintGetter level, BlockPos pos) {
            return shift(BiomeColors.getAverageFoliageColor(level, pos));
        }
        int shift(int rgb) {
            // HSV by hand: no java.awt on the client (it fights GLFW on macOS)
            float r = ((rgb >> 16) & 255) / 255f, g = ((rgb >> 8) & 255) / 255f, b = (rgb & 255) / 255f;
            float max = Math.max(r, Math.max(g, b)), min = Math.min(r, Math.min(g, b)), d = max - min, h;
            if (d == 0) h = 0;
            else if (max == r) h = ((g - b) / d) / 6f;
            else if (max == g) h = ((b - r) / d + 2) / 6f;
            else h = ((r - g) / d + 4) / 6f;
            h += dh; h -= (float) Math.floor(h);
            float s = Math.min(1f, (max == 0 ? 0 : d / max) * ds), v = Math.min(1f, max * dv);
            float c = v * s, x = c * (1 - Math.abs((h * 6) % 2 - 1)), m = v - c, rr, gg, bb;
            switch ((int) (h * 6) % 6) {
                case 0 -> { rr = c; gg = x; bb = 0; }
                case 1 -> { rr = x; gg = c; bb = 0; }
                case 2 -> { rr = 0; gg = c; bb = x; }
                case 3 -> { rr = 0; gg = x; bb = c; }
                case 4 -> { rr = x; gg = 0; bb = c; }
                default -> { rr = c; gg = 0; bb = x; }
            }
            return 0xFF000000 | Math.round((rr + m) * 255) << 16 | Math.round((gg + m) * 255) << 8 | Math.round((bb + m) * 255);
        }
    }

    private LeafTints() {}
}
