package dev.elysium.atlas;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import dev.elysium.atlas.mixin.BiomeAccessor;
import net.minecraft.core.Holder;
import net.minecraft.core.HolderSet;
import net.minecraft.core.Registry;
import net.minecraft.core.RegistryAccess;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.BiomeGenerationSettings;
import net.minecraft.world.level.levelgen.GenerationStep;
import net.minecraft.world.level.levelgen.carver.ConfiguredWorldCarver;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;

import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Regional biome variants (tools/biome_variants.py writes /elysium_atlas/variants.json and the biome files).
 * A variant is a child of a parent biome: it takes the parent's tags (mixin/TagLoaderMixin), its final
 * spawns, carvers and features after every mod has modified it (rebuild), and counts as the parent in
 * biome lists and key checks (mixin/HolderReferenceMixin, mixin/HolderSetDirectMixin). Its own biome file
 * changes only colours and effects; its feature patch is applied here.
 */
public final class Variants {
    public record Def(Identifier id, Identifier parent, List<String> regions, Map<Integer, List<Identifier>> addFeatures, Set<Identifier> removeFeatures) {}

    /** By variant id. Empty when the jar carries no table. */
    public static final Map<Identifier, Def> DEFS = load();
    private static final Map<String, Identifier> BY_REGION_PARENT = new HashMap<>();
    static {
        for (Def d : DEFS.values())
            for (String r : d.regions) {
                Identifier old = BY_REGION_PARENT.put(r + "|" + d.parent, d.id);
                if (old != null) throw new IllegalStateException("biome variants " + old + " and " + d.id + " both claim " + d.parent + " in " + r);
            }
    }

    private Variants() {}

    public static Identifier parentOf(Identifier variant) {
        Def d = DEFS.get(variant);
        return d == null ? null : d.parent;
    }

    /** The variant that replaces a parent biome in a region, or null. */
    public static Identifier variantFor(String region, Identifier parent) {
        return region == null ? null : BY_REGION_PARENT.get(region + "|" + parent);
    }

    private static Map<Identifier, Def> load() {
        Map<Identifier, Def> out = new LinkedHashMap<>();
        try (InputStream in = Variants.class.getResourceAsStream("/elysium_atlas/variants.json")) {
            if (in == null) return Map.of();
            JsonObject root = JsonParser.parseReader(new InputStreamReader(in, StandardCharsets.UTF_8)).getAsJsonObject();
            for (Map.Entry<String, JsonElement> e : root.getAsJsonObject("variants").entrySet()) {
                JsonObject v = e.getValue().getAsJsonObject();
                List<String> regions = new ArrayList<>();
                v.getAsJsonArray("regions").forEach(r -> regions.add(r.getAsString()));
                Map<Integer, List<Identifier>> add = new HashMap<>();
                if (v.has("add_features"))
                    for (Map.Entry<String, JsonElement> s : v.getAsJsonObject("add_features").entrySet()) {
                        List<Identifier> ids = new ArrayList<>();
                        s.getValue().getAsJsonArray().forEach(f -> ids.add(Identifier.parse(f.getAsString())));
                        add.put(GenerationStep.Decoration.valueOf(s.getKey().toUpperCase()).ordinal(), ids);
                    }
                Set<Identifier> remove = new HashSet<>();
                if (v.has("remove_features")) v.getAsJsonArray("remove_features").forEach(f -> remove.add(Identifier.parse(f.getAsString())));
                Identifier id = Identifier.parse(e.getKey());
                out.put(id, new Def(id, Identifier.parse(v.get("parent").getAsString()), List.copyOf(regions), Map.copyOf(add), Set.copyOf(remove)));
            }
        } catch (IOException e) {
            throw new IllegalStateException("cannot read biome variant table", e);
        }
        return Map.copyOf(out);
    }

    /**
     * Run once biome modifications are final (SERVER_STARTING): link each variant holder to its parent and
     * give the variant the parent's final spawns and carvers, and its features with the variant's patch.
     */
    public static void bind(RegistryAccess access) {
        if (DEFS.isEmpty()) return;
        Registry<Biome> biomes = access.lookupOrThrow(Registries.BIOME);
        Registry<PlacedFeature> placed = access.lookupOrThrow(Registries.PLACED_FEATURE);
        int n = 0;
        for (Def d : DEFS.values()) {
            var vh = biomes.get(d.id).orElse(null);
            var ph = biomes.get(d.parent).orElse(null);
            if (vh == null || ph == null) { Atlas.LOG.warn("biome variant {} or its parent {} is not registered", d.id, d.parent); continue; }
            ((VariantHolder) (Object) vh).elysium$setParent(ph);
            Biome parent = ph.value(), variant = vh.value();
            BiomeGenerationSettings.PlainBuilder b = new BiomeGenerationSettings.PlainBuilder();
            for (Holder<ConfiguredWorldCarver<?>> c : parent.getGenerationSettings().getCarvers()) b.addCarver(c);
            List<HolderSet<PlacedFeature>> steps = parent.getGenerationSettings().features();
            for (int s = 0; s < Math.max(steps.size(), GenerationStep.Decoration.values().length); s++) {
                if (s < steps.size())
                    for (Holder<PlacedFeature> f : steps.get(s))
                        if (f.unwrapKey().map(k -> !d.removeFeatures.contains(k.identifier())).orElse(true)) b.addFeature(s, f);
                for (Identifier f : d.addFeatures.getOrDefault(s, List.of()))
                    b.addFeature(s, placed.get(f).orElseThrow(() -> new IllegalStateException("biome variant " + d.id + ": no placed feature " + f)));
            }
            ((BiomeAccessor) (Object) variant).elysium$setGenerationSettings(b.build());
            ((BiomeAccessor) (Object) variant).elysium$setMobSettings(parent.getMobSettings());
            n++;
        }
        Atlas.LOG.info("Bound {} biome variants to their parents", n);
    }

    /** Implemented on Holder.Reference by mixin/HolderReferenceMixin. */
    public interface VariantHolder {
        Holder<?> elysium$parent();
        void elysium$setParent(Holder<?> parent);
    }

    public static ResourceKey<Biome> key(Identifier id) { return ResourceKey.create(Registries.BIOME, id); }
}
