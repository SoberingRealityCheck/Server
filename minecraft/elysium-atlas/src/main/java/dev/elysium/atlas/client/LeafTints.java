package dev.elysium.atlas.client;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import net.minecraft.client.Minecraft;
import net.minecraft.client.color.block.BlockTintSource;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.BiomeColors;
import net.minecraft.client.renderer.block.BlockAndTintGetter;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.level.biome.Biome;
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
import java.util.Optional;

/**
 * Regional colours for spruce, birch, mangrove and the flora mods' green leaves (elysium_atlas/leaf_tints.json,
 * written by variants/leaf_tints.py). Each species is the biome's foliage colour moved by the species' own offset
 * (hue shift, saturation ratio, value ratio, measured against vanilla's default foliage colour), so species stay
 * distinct and all of them follow the region and the season. A regional variant can set its own colour per leaf
 * type (elysium_atlas/leaf_palettes.json, from the flora profiles' "leaves"), stored the same way against the
 * variant's foliage colour; it replaces the species offset there and is averaged over 5 points 6 blocks apart so
 * biome borders do not step. Evergreen leaves (a palette entry's fourth value, or the "evergreen" leaf blocks outside
 * palettes) take the biome's own foliage colour instead of the seasonal one, so Serene Seasons does not turn conifers
 * and live oaks red in autumn; the share of evergreen stencil points blends the two at borders. Client only.
 */
public final class LeafTints {
    private static final Logger LOG = LoggerFactory.getLogger("elysium_atlas");
    private static Map<Block, List<BlockTintSource>> sources;
    private static Map<Identifier, Map<Block, float[]>> palettes = Map.of();
    private static final int[][] STENCIL = {{0, 0}, {6, 0}, {-6, 0}, {0, 6}, {0, -6}};

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
            java.util.Set<String> evergreen = new java.util.HashSet<>();
            if (j.has("evergreen")) j.getAsJsonArray("evergreen").forEach(x -> evergreen.add(x.getAsString()));
            for (Map.Entry<String, JsonElement> e : j.getAsJsonObject("leaves").entrySet()) {
                Identifier id = Identifier.parse(e.getKey());
                if (!BuiltInRegistries.BLOCK.containsKey(id)) continue;
                Block b = BuiltInRegistries.BLOCK.getValue(id);
                float[] o = vec(e.getValue());
                if (evergreen.contains(e.getKey())) o = new float[]{o[0], o[1], o[2], 1};
                m.put(b, List.of(new Species(b, o, base)));
            }
        } catch (Exception ex) {
            LOG.error("Leaf tints not loaded", ex);
        }
        Map<Identifier, Map<Block, float[]>> p = new HashMap<>();
        try (InputStream in = LeafTints.class.getResourceAsStream("/elysium_atlas/leaf_palettes.json")) {
            if (in != null) {
                JsonObject j = JsonParser.parseReader(new InputStreamReader(in, StandardCharsets.UTF_8)).getAsJsonObject();
                for (Map.Entry<String, JsonElement> v : j.getAsJsonObject("palettes").entrySet()) {
                    Map<Block, float[]> pal = new HashMap<>();
                    for (Map.Entry<String, JsonElement> e : v.getValue().getAsJsonObject().entrySet()) {
                        Identifier id = Identifier.parse(e.getKey());
                        if (BuiltInRegistries.BLOCK.containsKey(id)) pal.put(BuiltInRegistries.BLOCK.getValue(id), vec(e.getValue()));
                    }
                    p.put(Identifier.parse(v.getKey()), pal);
                }
            }
        } catch (Exception ex) {
            LOG.error("Leaf palettes not loaded", ex);
        }
        LOG.info("Regional leaf tints for {} leaf blocks, palettes for {} biomes", m.size(), p.size());
        palettes = p;
        sources = m;
    }

    private static float[] vec(JsonElement e) {
        JsonArray o = e.getAsJsonArray();
        return new float[]{o.get(0).getAsFloat(), o.get(1).getAsFloat(), o.get(2).getAsFloat(), o.size() > 3 ? o.get(3).getAsFloat() : 0};
    }

    record Species(Block block, float[] offset, int base) implements BlockTintSource {
        @Override public int color(BlockState state) { return shift(base, offset[0], offset[1], offset[2]); }
        @Override public int colorInWorld(BlockState state, BlockAndTintGetter level, BlockPos pos) {
            int foliage = BiomeColors.getAverageFoliageColor(level, pos);
            ClientLevel cl = Minecraft.getInstance().level;
            if (cl == null) return shift(foliage, offset[0], offset[1], offset[2]);
            float dh = 0, ds = 0, dv = 0, ev = 0, r = 0, g = 0, b = 0;
            BlockPos.MutableBlockPos q = new BlockPos.MutableBlockPos();
            for (int[] p : STENCIL) {
                Holder<Biome> h = cl.getBiome(q.set(pos.getX() + p[0], pos.getY(), pos.getZ() + p[1]));
                Optional<ResourceKey<Biome>> k = h.unwrapKey();
                Map<Block, float[]> pal = k.isPresent() && !palettes.isEmpty() ? palettes.get(k.get().identifier()) : null;
                float[] o = pal != null ? pal.getOrDefault(block, offset) : offset;
                dh += o[0]; ds += o[1]; dv += o[2];
                if (o[3] > 0) {       // evergreen here: the biome's own (unseasoned) foliage colour
                    int c = h.value().getFoliageColor();
                    ev += 1; r += (c >> 16) & 255; g += (c >> 8) & 255; b += c & 255;
                }
            }
            int n = STENCIL.length;
            if (ev > 0) {
                float w = ev / n;     // evergreen share of the stencil; the rest keeps the seasonal colour
                int fr = Math.round(((foliage >> 16) & 255) * (1 - w) + r / ev * w), fg = Math.round(((foliage >> 8) & 255) * (1 - w) + g / ev * w),
                    fb = Math.round((foliage & 255) * (1 - w) + b / ev * w);
                foliage = fr << 16 | fg << 8 | fb;
            }
            return shift(foliage, dh / n, ds / n, dv / n);
        }
        static int shift(int rgb, float dh, float ds, float dv) {
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
