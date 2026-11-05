package dev.elysium.flora.worldgen;

import com.mojang.serialization.Codec;
import com.mojang.serialization.DataResult;
import com.mojang.serialization.MapCodec;
import com.mojang.serialization.codecs.RecordCodecBuilder;
import dev.elysium.flora.ElysiumFlora;
import dev.elysium.flora.LeafTone;
import it.unimi.dsi.fastutil.longs.Long2IntOpenHashMap;
import it.unimi.dsi.fastutil.longs.LongArrayFIFOQueue;
import it.unimi.dsi.fastutil.longs.LongOpenHashSet;
import java.util.List;
import java.util.Optional;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.util.RandomSource;
import net.minecraft.util.StringRepresentable;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.block.LeavesBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.feature.stateproviders.BlockStateProvider;
import net.minecraft.world.level.levelgen.feature.treedecorators.TreeDecorator;
import net.minecraft.world.level.levelgen.feature.treedecorators.TreeDecoratorType;

/**
 * Gives a tree's leaves a second look without a second leaf texture, or with one: each layer picks leaves by a
 * cheap rule (one pass over the tree's leaves, O(leaves)) and sets their tone, or swaps them for another block
 * (a blossom, berry, snow or bare-twig leaf block), or both. Layers apply in order; a later one wins.
 *
 * Rules, all on the leaves this tree placed (`param` meaning in brackets):
 *   sun_cap     top of each leaf column, open to the sky [layers down from the top, default 1]
 *   underside   bottom of each leaf column [layers up from the bottom]
 *   shade       interior: all six neighbours are leaves or wood
 *   rim         silhouette: a horizontal neighbour is open
 *   tips        farthest from wood, by steps through leaves [outer layers kept]
 *   gradient    dithered (4x4 Bayer) by height in the crown, top heavy; param 1 makes it bottom heavy
 *   sunny_side  the crown's half facing `direction` (default south) [unused]
 *   patches     whole cells of the crown, so tones come in clumps like branch clusters [cell size, default 3]
 *   random      any leaf
 * `chance` is per leaf, per cell for patches. Tones need tinted leaves to show; for fixed-colour leaves use `block`.
 * The guideline is at most two leaf blocks per tree; tones on one block count as one.
 */
public class LeafTonesDecorator extends TreeDecorator {
    public enum Rule implements StringRepresentable {
        SUN_CAP, UNDERSIDE, SHADE, RIM, TIPS, GRADIENT, SUNNY_SIDE, PATCHES, RANDOM;
        public static final Codec<Rule> CODEC = StringRepresentable.fromEnum(Rule::values);

        @Override
        public String getSerializedName() {
            return name().toLowerCase(java.util.Locale.ROOT);
        }
    }

    private static final Codec<Direction> HORIZONTAL = Direction.CODEC.validate(d -> d.getAxis().isHorizontal()
            ? DataResult.success(d) : DataResult.error(() -> "direction must be horizontal: " + d));

    public record Layer(Rule rule, float chance, Optional<LeafTone> tone, Optional<BlockStateProvider> block, int param,
                        Direction direction) {
        public static final Codec<Layer> CODEC = RecordCodecBuilder.create(i -> i.group(
                Rule.CODEC.fieldOf("rule").forGetter(Layer::rule),
                Codec.floatRange(0F, 1F).optionalFieldOf("chance", 1F).forGetter(Layer::chance),
                LeafTone.CODEC.optionalFieldOf("tone").forGetter(Layer::tone),
                BlockStateProvider.CODEC.optionalFieldOf("block").forGetter(Layer::block),
                Codec.intRange(0, 16).optionalFieldOf("param", 1).forGetter(Layer::param),
                HORIZONTAL.optionalFieldOf("direction", Direction.SOUTH).forGetter(Layer::direction)
        ).apply(i, Layer::new));
    }

    public static final MapCodec<LeafTonesDecorator> CODEC = RecordCodecBuilder.mapCodec(i -> i.group(
            Layer.CODEC.listOf().fieldOf("layers").forGetter(d -> d.layers)
    ).apply(i, LeafTonesDecorator::new));

    private static final int[] BAYER = {0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5};
    private static final Direction[] DIRS = Direction.values();

    private final List<Layer> layers;

    public LeafTonesDecorator(List<Layer> layers) {
        this.layers = layers;
    }

    @Override
    protected TreeDecoratorType<?> type() {
        return ElysiumFlora.LEAF_TONES;
    }

    @Override
    public void place(Context context) {
        List<BlockPos> leaves = context.leaves();
        if (leaves.isEmpty()) return;
        WorldGenLevel level = context.level();
        RandomSource random = context.random();
        LongOpenHashSet leafSet = new LongOpenHashSet(leaves.size());
        for (BlockPos p : leaves) leafSet.add(p.asLong());
        LongOpenHashSet wood = new LongOpenHashSet(context.logs().size());
        for (BlockPos p : context.logs()) wood.add(p.asLong());

        int minY = Integer.MAX_VALUE, maxY = Integer.MIN_VALUE;
        double cx = 0, cz = 0;
        for (BlockPos p : leaves) {
            minY = Math.min(minY, p.getY());
            maxY = Math.max(maxY, p.getY());
            cx += p.getX();
            cz += p.getZ();
        }
        cx /= leaves.size();
        cz /= leaves.size();
        Long2IntOpenHashMap tipDist = null;
        int maxTip = 0;

        for (Layer layer : this.layers) {
            if (layer.rule == Rule.TIPS && tipDist == null) {
                tipDist = woodDistance(leaves, leafSet, wood);
                for (int v : tipDist.values()) maxTip = Math.max(maxTip, v);
            }
            long cellSeed = random.nextLong();
            for (BlockPos p : leaves) {
                if (!picks(layer, p, leafSet, wood, minY, maxY, cx, cz, tipDist, maxTip, cellSeed, random)) continue;
                apply(context, level, random, layer, p);
            }
        }
    }

    private static boolean picks(Layer l, BlockPos p, LongOpenHashSet leaves, LongOpenHashSet wood, int minY, int maxY,
                                 double cx, double cz, Long2IntOpenHashMap tipDist, int maxTip, long cellSeed,
                                 RandomSource random) {
        int x = p.getX(), y = p.getY(), z = p.getZ();
        boolean hit = switch (l.rule) {
            case SUN_CAP -> {
                int d = Math.max(1, l.param);
                boolean covered = false;
                for (int k = d; k <= maxY - y && !covered; k++) covered = leaves.contains(BlockPos.asLong(x, y + k, z));
                yield !covered;
            }
            case UNDERSIDE -> {
                int d = Math.max(1, l.param);
                boolean under = false;
                for (int k = d; k <= y - minY && !under; k++) under = leaves.contains(BlockPos.asLong(x, y - k, z));
                yield !under;
            }
            case SHADE -> {
                boolean inner = true;
                for (Direction d : DIRS) {
                    long n = BlockPos.asLong(x + d.getStepX(), y + d.getStepY(), z + d.getStepZ());
                    if (!leaves.contains(n) && !wood.contains(n)) { inner = false; break; }
                }
                yield inner;
            }
            case RIM -> {
                boolean open = false;
                for (Direction d : Direction.Plane.HORIZONTAL) {
                    long n = BlockPos.asLong(x + d.getStepX(), y, z + d.getStepZ());
                    if (!leaves.contains(n) && !wood.contains(n)) { open = true; break; }
                }
                yield open;
            }
            case TIPS -> tipDist.get(p.asLong()) > maxTip - Math.max(1, l.param);
            case GRADIENT -> {
                double h = maxY == minY ? 1 : (y - minY) / (double) (maxY - minY);
                if (l.param == 1) h = 1 - h;
                int t = BAYER[(Math.floorMod(x + y, 4)) * 4 + Math.floorMod(z - y, 4)];
                yield h > (t + 0.5) / 16.0;
            }
            case SUNNY_SIDE -> (x - cx) * l.direction.getStepX() + (z - cz) * l.direction.getStepZ() > 0.5;
            case PATCHES -> {
                int s = Math.max(1, l.param);
                long h = cellSeed ^ (Math.floorDiv(x, s) * 0x9E3779B97F4A7C15L) ^ (Math.floorDiv(y, s) * 0xC2B2AE3D27D4EB4FL)
                        ^ (Math.floorDiv(z, s) * 0x165667B19E3779F9L);
                h ^= h >>> 31;
                h *= 0x94D049BB133111EBL;
                h ^= h >>> 29;
                yield (h >>> 40) / (double) (1L << 24) < l.chance;
            }
            case RANDOM -> true;
        };
        if (!hit) return false;
        return l.rule == Rule.PATCHES || l.chance >= 1F || random.nextFloat() < l.chance;
    }

    /** Steps through leaves from the nearest wood (leaves touching wood are 1). Unreached leaves count as far. */
    private static Long2IntOpenHashMap woodDistance(List<BlockPos> leaves, LongOpenHashSet leafSet, LongOpenHashSet wood) {
        Long2IntOpenHashMap dist = new Long2IntOpenHashMap(leaves.size());
        dist.defaultReturnValue(Integer.MAX_VALUE);
        LongArrayFIFOQueue q = new LongArrayFIFOQueue();
        for (BlockPos p : leaves) {
            for (Direction d : DIRS) {
                if (wood.contains(BlockPos.offset(p.asLong(), d))) {
                    dist.put(p.asLong(), 1);
                    q.enqueue(p.asLong());
                    break;
                }
            }
        }
        while (!q.isEmpty()) {
            long c = q.dequeueLong();
            int v = dist.get(c);
            for (Direction d : DIRS) {
                long n = BlockPos.offset(c, d);
                if (leafSet.contains(n) && dist.get(n) > v + 1) {
                    dist.put(n, v + 1);
                    q.enqueue(n);
                }
            }
        }
        int max = 0;
        for (int v : dist.values()) max = Math.max(max, v);
        for (BlockPos p : leaves) if (!dist.containsKey(p.asLong())) dist.put(p.asLong(), max);
        return dist;
    }

    private static void apply(Context context, WorldGenLevel level, RandomSource random, Layer l, BlockPos p) {
        BlockState old = level.getBlockState(p);
        BlockState s = old;
        if (l.block.isPresent()) {
            s = l.block.get().getState(level, random, p);
            if (old.getBlock() instanceof LeavesBlock && s.getBlock() instanceof LeavesBlock) {
                s = s.setValue(LeavesBlock.DISTANCE, old.getValue(LeavesBlock.DISTANCE))
                        .setValue(LeavesBlock.PERSISTENT, old.getValue(LeavesBlock.PERSISTENT))
                        .setValue(LeavesBlock.WATERLOGGED, old.getValue(LeavesBlock.WATERLOGGED));
            }
        }
        if (l.tone.isPresent() && s.hasProperty(LeafTone.TONE)) s = s.setValue(LeafTone.TONE, l.tone.get().ordinal());
        if (s != old) context.setBlock(p, s);
    }
}
