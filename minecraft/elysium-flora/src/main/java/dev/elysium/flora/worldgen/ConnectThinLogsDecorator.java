package dev.elysium.flora.worldgen;

import com.mojang.serialization.MapCodec;
import dev.elysium.flora.ElysiumFlora;
import dev.elysium.flora.ThinLogBlock;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.feature.treedecorators.TreeDecorator;
import net.minecraft.world.level.levelgen.feature.treedecorators.TreeDecoratorType;

/**
 * Sets the six connection faces on every thin log the trunk placer put down. Trees place logs through a plain
 * state provider, so they arrive unconnected; this runs once per tree after the trunk and crown are in.
 * List it last in a tree's decorators so it also sees thin logs other decorators added.
 */
public class ConnectThinLogsDecorator extends TreeDecorator {
    public static final ConnectThinLogsDecorator INSTANCE = new ConnectThinLogsDecorator();
    public static final MapCodec<ConnectThinLogsDecorator> CODEC = MapCodec.unit(() -> INSTANCE);

    @Override
    protected TreeDecoratorType<?> type() {
        return ElysiumFlora.CONNECT;
    }

    @Override
    public void place(Context context) {
        WorldGenLevel level = context.level();
        for (BlockPos pos : context.logs()) {
            BlockState state = level.getBlockState(pos);
            if (!(state.getBlock() instanceof ThinLogBlock)) continue;
            BlockState joined = ThinLogBlock.connect(state, level, pos);
            if (joined != state) context.setBlock(pos, joined);
        }
    }
}
