package dev.elysium.atlas.mixin;

import com.llamalad7.mixinextras.injector.ModifyReturnValue;
import dev.elysium.atlas.Variants;
import net.minecraft.core.Holder;
import net.minecraft.resources.Identifier;
import net.minecraft.tags.TagLoader;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Every biome tag that holds a parent also holds its variants, whichever mod or datapack wrote the tag.
 * Runs on world load and on /reload, and the result is what clients receive.
 */
@Mixin(TagLoader.class)
abstract class TagLoaderMixin<T> {
    @Shadow @Final private String directory;
    @Shadow @Final private TagLoader.ElementLookup<T> elementLookup;

    @ModifyReturnValue(method = "build", at = @At("RETURN"))
    private Map<Identifier, List<T>> elysium_atlas$inherit(Map<Identifier, List<T>> tags) {
        if (!"tags/worldgen/biome".equals(directory) || Variants.DEFS.isEmpty()) return tags;
        Map<Identifier, List<Identifier>> children = new HashMap<>();
        for (Variants.Def d : Variants.DEFS.values()) children.computeIfAbsent(d.parent(), k -> new ArrayList<>()).add(d.id());
        Map<Identifier, List<T>> out = new HashMap<>(tags.size());
        for (Map.Entry<Identifier, List<T>> e : tags.entrySet()) {
            List<T> list = e.getValue(), add = null;
            for (T t : list) {
                if (!(t instanceof Holder<?> h)) continue;
                Identifier id = h.unwrapKey().map(k -> k.identifier()).orElse(null);
                List<Identifier> kids = id == null ? null : children.get(id);
                if (kids == null) continue;
                for (Identifier k : kids) {
                    T v = elementLookup.get(k, false).orElse(null);
                    if (v != null && !list.contains(v)) { if (add == null) add = new ArrayList<>(); if (!add.contains(v)) add.add(v); }
                }
            }
            if (add == null) out.put(e.getKey(), list);
            else { List<T> l = new ArrayList<>(list); l.addAll(add); out.put(e.getKey(), List.copyOf(l)); }
        }
        return out;
    }
}
