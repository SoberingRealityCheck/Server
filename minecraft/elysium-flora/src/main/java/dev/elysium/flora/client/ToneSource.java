package dev.elysium.flora.client;

import dev.elysium.flora.LeafTone;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import net.minecraft.client.color.block.BlockTintSource;
import net.minecraft.client.renderer.block.BlockAndTintGetter;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.Property;

/** A tint source with the leaf's tone applied on top of whatever colour the wrapped source gives. */
public record ToneSource(BlockTintSource inner, int tone) implements BlockTintSource {
    private static final ConcurrentHashMap<List<BlockTintSource>, List<BlockTintSource>[]> WRAPPED = new ConcurrentHashMap<>();

    /** sources with each entry toned (null entries kept: they are "no tint" for that index). Cached per list. */
    @SuppressWarnings("unchecked")
    public static List<BlockTintSource> wrap(List<BlockTintSource> sources, int tone) {
        if (sources == null || sources.isEmpty() || tone <= 0 || tone > 3) return sources;
        if (WRAPPED.size() > 1024) WRAPPED.clear();
        List<BlockTintSource>[] byTone = WRAPPED.computeIfAbsent(sources, k -> new List[4]);
        List<BlockTintSource> w = byTone[tone];
        if (w == null) {
            List<BlockTintSource> l = new ArrayList<>(sources.size());
            for (BlockTintSource s : sources) l.add(s == null ? null : new ToneSource(s, tone));
            w = java.util.Collections.unmodifiableList(l);
            byTone[tone] = w;
        }
        return w;
    }

    @Override
    public int color(BlockState state) {
        return ToneColors.shift(this.inner.color(state), this.tone);
    }

    @Override
    public int colorInWorld(BlockState state, BlockAndTintGetter level, BlockPos pos) {
        return ToneColors.shift(this.inner.colorInWorld(state, level, pos), this.tone);
    }

    @Override
    public int colorAsTerrainParticle(BlockState state, BlockAndTintGetter level, BlockPos pos) {
        return ToneColors.shift(this.inner.colorAsTerrainParticle(state, level, pos), this.tone);
    }

    @Override
    public Set<Property<?>> relevantProperties() {
        Set<Property<?>> s = new HashSet<>(this.inner.relevantProperties());
        s.add(LeafTone.TONE);
        return s;
    }
}
