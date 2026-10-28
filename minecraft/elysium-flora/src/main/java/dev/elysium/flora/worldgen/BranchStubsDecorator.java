package dev.elysium.flora.worldgen;

import com.mojang.serialization.Codec;
import com.mojang.serialization.MapCodec;
import com.mojang.serialization.codecs.RecordCodecBuilder;
import dev.elysium.flora.ElysiumFlora;
import dev.elysium.flora.ThinLogBlock;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.feature.stateproviders.BlockStateProvider;
import net.minecraft.world.level.levelgen.feature.treedecorators.TreeDecorator;
import net.minecraft.world.level.levelgen.feature.treedecorators.TreeDecoratorType;

/**
 * Short thin side branches on a tree's trunk, the look Branched Trees gives vanilla trees, without its block states.
 *
 * For each log in the upper part of the trunk (above `min_height_fraction` of the trunk's height) a stub grows with
 * `probability` in a random horizontal direction, `length` blocks long, then turns up for one block with
 * `rise_chance`. Stubs grow only into air, so inside the crown they stop at the first leaf. `block` must give a
 * thin log; stubs are joined to the trunk and to each other here, and a thin trunk is joined back to the stub.
 */
public class BranchStubsDecorator extends TreeDecorator {
    public static final MapCodec<BranchStubsDecorator> CODEC = RecordCodecBuilder.mapCodec(i -> i.group(
            BlockStateProvider.CODEC.fieldOf("block").forGetter(d -> d.block),
            Codec.floatRange(0F, 1F).fieldOf("probability").forGetter(d -> d.probability),
            Codec.floatRange(0F, 1F).optionalFieldOf("min_height_fraction", 0.4F).forGetter(d -> d.minHeightFraction),
            Codec.intRange(1, 4).optionalFieldOf("length", 2).forGetter(d -> d.length),
            Codec.floatRange(0F, 1F).optionalFieldOf("rise_chance", 0.5F).forGetter(d -> d.riseChance)
    ).apply(i, BranchStubsDecorator::new));

    private final BlockStateProvider block;
    private final float probability;
    private final float minHeightFraction;
    private final int length;
    private final float riseChance;

    public BranchStubsDecorator(BlockStateProvider block, float probability, float minHeightFraction, int length, float riseChance) {
        this.block = block;
        this.probability = probability;
        this.minHeightFraction = minHeightFraction;
        this.length = length;
        this.riseChance = riseChance;
    }

    @Override
    protected TreeDecoratorType<?> type() {
        return ElysiumFlora.BRANCH_STUBS;
    }

    @Override
    public void place(Context context) {
        List<BlockPos> logs = context.logs();
        if (logs.isEmpty()) return;
        WorldGenLevel level = context.level();
        RandomSource random = context.random();
        int bottom = Integer.MAX_VALUE, top = Integer.MIN_VALUE;
        for (BlockPos p : logs) {
            bottom = Math.min(bottom, p.getY());
            top = Math.max(top, p.getY());
        }
        int minY = bottom + Math.round((top - bottom) * this.minHeightFraction);
        for (BlockPos trunk : logs.toArray(new BlockPos[0])) {
            if (trunk.getY() < minY || trunk.getY() >= top || random.nextFloat() >= this.probability) continue;
            Direction d = Direction.Plane.HORIZONTAL.getRandomDirection(random);
            BlockPos.MutableBlockPos p = trunk.mutable();
            BlockPos last = null;
            int steps = this.length + (random.nextFloat() < this.riseChance ? 1 : 0);
            for (int i = 0; i < steps; i++) {
                Direction step = i < this.length ? d : Direction.UP;
                p.move(step);
                if (!context.isAir(p)) break;
                BlockState stub = this.block.getState(level, random, p);
                if (!(stub.getBlock() instanceof ThinLogBlock)) return;
                stub = stub.setValue(ThinLogBlock.FACE.get(step.getOpposite()), true);
                context.setBlock(p, stub);
                if (last != null) {
                    BlockState prev = level.getBlockState(last);
                    context.setBlock(last, prev.setValue(ThinLogBlock.FACE.get(step), true));
                }
                last = p.immutable();
            }
            if (last != null) {
                BlockState t = level.getBlockState(trunk);
                if (t.getBlock() instanceof ThinLogBlock) context.setBlock(trunk, t.setValue(ThinLogBlock.FACE.get(d), true));
            }
        }
    }
}
