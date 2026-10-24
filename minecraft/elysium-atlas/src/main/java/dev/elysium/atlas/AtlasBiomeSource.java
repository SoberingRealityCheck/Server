package dev.elysium.atlas;

import com.mojang.serialization.MapCodec;
import com.mojang.serialization.codecs.RecordCodecBuilder;
import net.minecraft.core.Holder;
import net.minecraft.core.HolderGetter;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.RegistryOps;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.BiomeSource;
import net.minecraft.world.level.biome.Climate;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Stream;

/**
 * elysium_atlas:atlas. Surface biomes come from the baked atlas palette (one per 4x4 cell on detail levels).
 * Below the surface, cave biomes come from the "underground" source (normally the overworld multi_noise
 * preset, which carries Terralith's caves); its non-cave answers are ignored.
 */
public final class AtlasBiomeSource extends BiomeSource {
    public static final MapCodec<AtlasBiomeSource> CODEC = RecordCodecBuilder.mapCodec(i -> i.group(
            RegistryOps.retrieveGetter(Registries.BIOME),
            BiomeSource.CODEC.optionalFieldOf("underground").forGetter(s -> s.underground),
            net.minecraft.util.ExtraCodecs.NON_NEGATIVE_INT.optionalFieldOf("cave_margin", 12).forGetter(s -> s.caveMargin)
    ).apply(i, AtlasBiomeSource::new));

    /** Vanilla cave biomes allowed through. deep_dark is left out: the fantasy layer places it under big cities. */
    private static final Set<String> VANILLA_CAVES = Set.of("lush_caves", "dripstone_caves");

    private final HolderGetter<Biome> biomes;
    private final Optional<BiomeSource> underground;
    private final int caveMargin;
    /** Resolved on first use, so decoding the world preset does not need the atlas on non-atlas servers. */
    private volatile List<Holder<Biome>> palette;
    private final Holder<Biome> fallback, river, frozenRiver;
    /** Per palette index: cold enough that its rivers freeze. Resolved with the palette. */
    private volatile boolean[] cold;
    /** [region][palette index] -> regional variant, or null. Resolved with the palette. */
    private volatile Holder<Biome>[][] variants;

    private AtlasBiomeSource(HolderGetter<Biome> biomes, Optional<BiomeSource> underground, int caveMargin) {
        this.biomes = biomes;
        this.underground = underground;
        this.caveMargin = caveMargin;
        fallback = biomes.getOrThrow(ResourceKey.create(Registries.BIOME, Identifier.parse("minecraft:deep_ocean")));
        river = biomes.getOrThrow(ResourceKey.create(Registries.BIOME, Identifier.parse("minecraft:river")));
        frozenRiver = biomes.getOrThrow(ResourceKey.create(Registries.BIOME, Identifier.parse("minecraft:frozen_river")));
    }

    private List<Holder<Biome>> palette() {
        List<Holder<Biome>> p = palette;
        if (p == null) {
            p = new ArrayList<>();
            for (String id : Atlas.get().palette)
                p.add(biomes.getOrThrow(ResourceKey.create(Registries.BIOME, Identifier.parse(id))));
            boolean[] c = new boolean[p.size()];
            for (int i = 0; i < c.length; i++) c[i] = p.get(i).value().getBaseTemperature() < 0.15f;
            cold = c;
            variants = resolveVariants(Atlas.get(), p);
            palette = p = List.copyOf(p);
        }
        return p;
    }

    @SuppressWarnings("unchecked")
    private Holder<Biome>[][] resolveVariants(Atlas a, List<Holder<Biome>> p) {
        if (a.regions == null) return new Holder[0][];
        Holder<Biome>[][] v = new Holder[a.regions.names.size() + 1][];
        int n = 0;
        for (int r = 1; r < v.length; r++) {
            v[r] = new Holder[p.size()];
            for (int b = 0; b < p.size(); b++) {
                Identifier id = Variants.variantFor(a.regions.name(r), p.get(b).unwrapKey().orElseThrow().identifier());
                if (id == null) continue;
                var h = biomes.get(Variants.key(id));
                if (h.isPresent()) { v[r][b] = h.get(); n++; }
                else Atlas.LOG.warn("biome variant {} is in the variant table but not registered", id);
            }
        }
        Atlas.LOG.info("Atlas regions: {} regional variants in use", n);
        return v;
    }

    private Stream<Holder<Biome>> variantStream() {
        palette();
        Stream.Builder<Holder<Biome>> s = Stream.builder();
        for (Holder<Biome>[] row : variants) if (row != null) for (Holder<Biome> h : row) if (h != null) s.add(h);
        return s.build();
    }

    @Override
    protected MapCodec<? extends BiomeSource> codec() { return CODEC; }

    @Override
    protected Stream<Holder<Biome>> collectPossibleBiomes() {
        Stream<Holder<Biome>> caves = underground.map(u -> u.possibleBiomes().stream().filter(AtlasBiomeSource::isCave)).orElseGet(Stream::empty);
        return Stream.concat(Stream.concat(Stream.concat(palette().stream(), variantStream()), Stream.of(fallback, river, frozenRiver)), caves).distinct();
    }

    @Override
    public Holder<Biome> getNoiseBiome(int qx, int qy, int qz, Climate.Sampler sampler) {
        Atlas a = Atlas.get();
        double x = (qx << 2) + 2, z = (qz << 2) + 2;
        if (underground.isPresent() && (qy << 2) < a.column(qx << 2 | 2, qz << 2 | 2).height() - caveMargin) {
            Holder<Biome> h = underground.get().getNoiseBiome(qx, qy, qz, sampler);
            if (isCave(h)) return h;
        }
        List<Holder<Biome>> p = palette();
        int b = a.biome(x, z);
        if (a.column(qx << 2 | 2, qz << 2 | 2).river()) return b >= 0 && b < p.size() && cold[b] ? frozenRiver : river;
        if (b < 0 || b >= p.size()) return fallback;
        if (a.regions != null) {
            Holder<Biome>[] row = variants[a.regions.at(x, z)];
            if (row != null && row[b] != null) return row[b];
        }
        return p.get(b);
    }

    static boolean isCave(Holder<Biome> h) {
        return h.unwrapKey().map(k -> {
            Identifier id = k.identifier();
            return id.getPath().startsWith("cave/") || (id.getNamespace().equals("minecraft") && VANILLA_CAVES.contains(id.getPath()));
        }).orElse(false);
    }

    @Override
    public void addDebugInfo(List<String> info, net.minecraft.core.BlockPos pos, Climate.Sampler sampler) {
        Atlas a = Atlas.get();
        double[] ll = a.toLonLat(pos.getX(), pos.getZ());
        info.add(String.format("Atlas %s: %.3f, %.3f  surface Y %.1f  relief %.0f m%s",
                a.version, ll[1], ll[0], a.heightOrOcean(pos.getX(), pos.getZ()), a.relief(pos.getX(), pos.getZ()),
                a.regions == null ? "" : "  region " + a.regions.name(a.regions.at(pos.getX(), pos.getZ()))));
    }
}
