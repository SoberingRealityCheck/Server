package dev.elysium.atlas.client;

import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.resource.v1.ResourceLoader;
import net.fabricmc.fabric.api.resource.v1.pack.PackActivationType;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.resources.Identifier;

/** Client side: the greyscale leaf textures (resourcepacks/regional_leaves) that LeafTints colours. */
public final class ElysiumAtlasClient implements ClientModInitializer {
    @Override
    public void onInitializeClient() {
        FabricLoader.getInstance().getModContainer("elysium_atlas").ifPresent(c ->
                ResourceLoader.registerBuiltinPack(Identifier.fromNamespaceAndPath("elysium_atlas", "regional_leaves"), c,
                        PackActivationType.ALWAYS_ENABLED));
    }
}
