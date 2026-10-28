package dev.elysium.flora;

import dev.elysium.flora.worldgen.BranchStubsDecorator;
import dev.elysium.flora.worldgen.ConnectThinLogsDecorator;
import dev.elysium.flora.worldgen.MultiStemTrunkPlacer;
import java.util.ArrayList;
import java.util.List;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.creativetab.v1.CreativeModeTabEvents;
import net.fabricmc.fabric.api.registry.FlammableBlockRegistry;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.item.BlockItem;
import net.minecraft.world.item.Item;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockBehaviour;
import net.minecraft.world.level.levelgen.feature.treedecorators.TreeDecoratorType;
import net.minecraft.world.level.levelgen.feature.trunkplacers.TrunkPlacerType;

/**
 * Thin logs (6 px, six-way connected) for the vanilla woods, and the tree pieces that build thin-trunk trees:
 * the multi_stem trunk placer, and the connect_thin_logs and branch_stubs tree decorators.
 * Trees themselves are data: data/elysium_flora/worldgen/configured_feature/.
 */
public final class ElysiumFlora implements ModInitializer {
    public static final String MOD_ID = "elysium_flora";

    /** Vanilla woods with their full logs. Pale oak is left out on purpose: it is the pale garden's alone. */
    private static final Block[][] WOODS = {
            {Blocks.OAK_LOG, Blocks.STRIPPED_OAK_LOG},
            {Blocks.SPRUCE_LOG, Blocks.STRIPPED_SPRUCE_LOG},
            {Blocks.BIRCH_LOG, Blocks.STRIPPED_BIRCH_LOG},
            {Blocks.JUNGLE_LOG, Blocks.STRIPPED_JUNGLE_LOG},
            {Blocks.ACACIA_LOG, Blocks.STRIPPED_ACACIA_LOG},
            {Blocks.DARK_OAK_LOG, Blocks.STRIPPED_DARK_OAK_LOG},
            {Blocks.MANGROVE_LOG, Blocks.STRIPPED_MANGROVE_LOG},
            {Blocks.CHERRY_LOG, Blocks.STRIPPED_CHERRY_LOG},
    };

    public static TrunkPlacerType<MultiStemTrunkPlacer> MULTI_STEM;
    public static TreeDecoratorType<ConnectThinLogsDecorator> CONNECT;
    public static TreeDecoratorType<BranchStubsDecorator> BRANCH_STUBS;

    @Override
    public void onInitialize() {
        List<Block[]> made = new ArrayList<>();
        for (Block[] wood : WOODS) {
            Block log = wood[0], strippedLog = wood[1];
            Block thin = thinLog(log);
            Block thinStripped = thinLog(strippedLog);
            ThinLogBlock.STRIPPED.put(thin, thinStripped);
            made.add(new Block[]{strippedLog, thin, thinStripped});
        }
        CreativeModeTabEvents.modifyOutputEvent(
                ResourceKey.create(Registries.CREATIVE_MODE_TAB, Identifier.withDefaultNamespace("building_blocks"))).register(content -> {
            for (Block[] m : made) {
                content.insertAfter(m[0], m[1]);
                content.insertAfter(m[1], m[2]);
            }
        });

        MULTI_STEM = Registry.register(BuiltInRegistries.TRUNK_PLACER_TYPE, id("multi_stem"),
                make(TrunkPlacerType.class, MultiStemTrunkPlacer.CODEC));
        CONNECT = Registry.register(BuiltInRegistries.TREE_DECORATOR_TYPE, id("connect_thin_logs"),
                make(TreeDecoratorType.class, ConnectThinLogsDecorator.CODEC));
        BRANCH_STUBS = Registry.register(BuiltInRegistries.TREE_DECORATOR_TYPE, id("branch_stubs"),
                make(TreeDecoratorType.class, BranchStubsDecorator.CODEC));
    }

    /** thin_<log path>, e.g. minecraft:stripped_oak_log -> elysium_flora:thin_stripped_oak_log. */
    private static Block thinLog(Block log) {
        Identifier id = id("thin_" + BuiltInRegistries.BLOCK.getKey(log).getPath());
        Block block = Registry.register(BuiltInRegistries.BLOCK, id, new ThinLogBlock(
                BlockBehaviour.Properties.ofFullCopy(log)
                        .mapColor(log.defaultMapColor()) // the log's own map colour reads its AXIS, which thin logs lack
                        .noOcclusion().setId(ResourceKey.create(Registries.BLOCK, id))));
        Registry.register(BuiltInRegistries.ITEM, id, new BlockItem(block,
                new Item.Properties().setId(ResourceKey.create(Registries.ITEM, id)).useBlockDescriptionPrefix()));
        FlammableBlockRegistry.getDefaultInstance().add(block, 5, 5);
        return block;
    }

    /**
     * new T(codec) for TrunkPlacerType / TreeDecoratorType. Their constructors are private in the game jar and
     * opened by Fabric API's transitive access wideners at run time; build.sh compiles against the plain jar,
     * so construct by reflection rather than widening the compile classpath.
     */
    @SuppressWarnings("unchecked")
    private static <T> T make(Class<?> type, com.mojang.serialization.MapCodec<?> codec) {
        try {
            var ctor = type.getDeclaredConstructor(com.mojang.serialization.MapCodec.class);
            ctor.setAccessible(true);
            return (T) ctor.newInstance(codec);
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException("cannot construct " + type.getName(), e);
        }
    }

    private static Identifier id(String path) {
        return Identifier.fromNamespaceAndPath(MOD_ID, path);
    }
}
