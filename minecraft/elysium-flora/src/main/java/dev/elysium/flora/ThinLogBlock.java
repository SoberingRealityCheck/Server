package dev.elysium.flora;

import com.mojang.serialization.MapCodec;
import java.util.HashMap;
import java.util.Map;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.tags.BlockTags;
import net.minecraft.tags.ItemTags;
import net.minecraft.util.RandomSource;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.context.BlockPlaceContext;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.LevelReader;
import net.minecraft.world.level.ScheduledTickAccess;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.PipeBlock;
import net.minecraft.world.level.block.SimpleWaterloggedBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.block.state.properties.BooleanProperty;
import net.minecraft.world.level.material.FluidState;
import net.minecraft.world.level.material.Fluids;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;

/**
 * A 6 px log that joins its neighbours on all six faces, like a fence post that also runs up and down.
 * No block entity: 64 connection states x waterlogged = 128 states per wood.
 *
 * A face connects when the neighbour is another thin log or any block in #minecraft:logs. On placement the face
 * that was clicked also connects if it is sturdy, so a pole stands on the ground or hangs off a wall; a later
 * neighbour change keeps such a connection while that face stays sturdy.
 */
public class ThinLogBlock extends Block implements SimpleWaterloggedBlock {
    public static final MapCodec<ThinLogBlock> CODEC = simpleCodec(ThinLogBlock::new);
    public static final BooleanProperty WATERLOGGED = BlockStateProperties.WATERLOGGED;
    public static final Map<Direction, BooleanProperty> FACE = PipeBlock.PROPERTY_BY_DIRECTION;

    /** thin log -> its stripped form, filled in by ElysiumFlora at registration. */
    static final Map<Block, Block> STRIPPED = new HashMap<>();

    private static final VoxelShape CORE = Block.box(5, 5, 5, 11, 11, 11);
    private static final Map<Direction, VoxelShape> ARM = Map.of(
            Direction.NORTH, Block.box(5, 5, 0, 11, 11, 5),
            Direction.SOUTH, Block.box(5, 5, 11, 11, 11, 16),
            Direction.WEST, Block.box(0, 5, 5, 5, 11, 11),
            Direction.EAST, Block.box(11, 5, 5, 16, 11, 11),
            Direction.DOWN, Block.box(5, 0, 5, 11, 5, 11),
            Direction.UP, Block.box(5, 11, 5, 11, 16, 11));

    private final java.util.function.Function<BlockState, VoxelShape> shapes;

    public ThinLogBlock(Properties properties) {
        super(properties);
        BlockState s = this.stateDefinition.any().setValue(WATERLOGGED, false);
        for (BooleanProperty p : FACE.values()) s = s.setValue(p, false);
        this.registerDefaultState(s);
        this.shapes = this.getShapeForEachState(state -> {
            VoxelShape shape = CORE;
            for (Direction d : Direction.values()) {
                if (state.getValue(FACE.get(d))) shape = Shapes.or(shape, ARM.get(d));
            }
            return shape;
        }, WATERLOGGED);
    }

    @Override
    protected MapCodec<? extends ThinLogBlock> codec() {
        return CODEC;
    }

    @Override
    protected void createBlockStateDefinition(StateDefinition.Builder<Block, BlockState> builder) {
        builder.add(FACE.get(Direction.NORTH), FACE.get(Direction.EAST), FACE.get(Direction.SOUTH),
                FACE.get(Direction.WEST), FACE.get(Direction.UP), FACE.get(Direction.DOWN), WATERLOGGED);
    }

    @Override
    protected VoxelShape getShape(BlockState state, BlockGetter level, BlockPos pos, CollisionContext context) {
        return this.shapes.apply(state);
    }

    /** Joins thin logs and full logs. Shared with the tree decorators so worldgen and players agree. */
    public static boolean joins(BlockState neighbour) {
        return neighbour.getBlock() instanceof ThinLogBlock || neighbour.is(BlockTags.LOGS);
    }

    /** Connections for a thin log at pos from its neighbours; down also connects to sturdy ground. */
    public static BlockState connect(BlockState state, BlockGetter level, BlockPos pos) {
        BlockPos.MutableBlockPos m = new BlockPos.MutableBlockPos();
        for (Direction d : Direction.values()) {
            m.setWithOffset(pos, d);
            BlockState n = level.getBlockState(m);
            boolean on = joins(n) || (d == Direction.DOWN && n.isFaceSturdy(level, m, Direction.UP));
            state = state.setValue(FACE.get(d), on);
        }
        return state;
    }

    @Override
    public BlockState getStateForPlacement(BlockPlaceContext context) {
        Level level = context.getLevel();
        BlockPos pos = context.getClickedPos();
        BlockState state = connect(this.defaultBlockState(), level, pos)
                .setValue(WATERLOGGED, level.getFluidState(pos).is(Fluids.WATER));
        Direction toward = context.getClickedFace().getOpposite();
        BlockPos against = pos.relative(toward);
        if (level.getBlockState(against).isFaceSturdy(level, against, toward.getOpposite())) {
            state = state.setValue(FACE.get(toward), true);
        }
        return state;
    }

    @Override
    protected BlockState updateShape(BlockState state, LevelReader level, ScheduledTickAccess ticks, BlockPos pos,
                                     Direction direction, BlockPos neighbourPos, BlockState neighbour, RandomSource random) {
        if (state.getValue(WATERLOGGED)) {
            ticks.scheduleTick(pos, Fluids.WATER, Fluids.WATER.getTickDelay(level));
        }
        BooleanProperty face = FACE.get(direction);
        boolean sturdy = neighbour.isFaceSturdy(level, neighbourPos, direction.getOpposite());
        return state.setValue(face, joins(neighbour) || (state.getValue(face) && sturdy)
                || (direction == Direction.DOWN && sturdy));
    }

    @Override
    protected FluidState getFluidState(BlockState state) {
        return state.getValue(WATERLOGGED) ? Fluids.WATER.getSource(false) : super.getFluidState(state);
    }

    @Override
    protected InteractionResult useItemOn(ItemStack stack, BlockState state, Level level, BlockPos pos, Player player,
                                          InteractionHand hand, BlockHitResult hit) {
        Block stripped = STRIPPED.get(this);
        if (stripped != null && stack.is(ItemTags.AXES)) {
            level.playSound(player, pos, SoundEvents.AXE_STRIP, SoundSource.BLOCKS, 1.0F, 1.0F);
            if (!level.isClientSide()) {
                level.setBlock(pos, stripped.withPropertiesOf(state), Block.UPDATE_ALL_IMMEDIATE);
                stack.hurtAndBreak(1, player, hand);
            }
            return InteractionResult.SUCCESS;
        }
        return super.useItemOn(stack, state, level, pos, player, hand, hit);
    }
}
