package dev.elysium.atlas;

import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.item.BlockItem;
import net.minecraft.world.item.Item;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.CarpetBlock;
import net.minecraft.world.level.block.state.BlockBehaviour;

/**
 * Greyscale copies of untinted ground blocks, coloured per region like leaves (LeafTints, leaf_tints.json and the
 * regional palettes): moss carpet (reindeer lichen, regional mosses) and moss block. Same behaviour as the vanilla
 * blocks they copy; their models carry tint index 0 and greyscale textures.
 */
public final class TintedBlocks {
    public static Block MOSS_CARPET, MOSS_BLOCK;

    static void register() {
        MOSS_CARPET = block("tinted_moss_carpet", p -> new CarpetBlock(p), Blocks.MOSS_CARPET);
        MOSS_BLOCK = block("tinted_moss_block", Block::new, Blocks.MOSS_BLOCK);
    }

    private static Block block(String name, java.util.function.Function<BlockBehaviour.Properties, Block> make, Block copy) {
        Identifier id = Identifier.fromNamespaceAndPath(ElysiumAtlas.MOD_ID, name);
        Block b = Registry.register(BuiltInRegistries.BLOCK, id, make.apply(BlockBehaviour.Properties.ofFullCopy(copy).setId(ResourceKey.create(Registries.BLOCK, id))));
        Registry.register(BuiltInRegistries.ITEM, id, new BlockItem(b, new Item.Properties().setId(ResourceKey.create(Registries.ITEM, id)).useBlockDescriptionPrefix()));
        return b;
    }

    private TintedBlocks() {}
}
