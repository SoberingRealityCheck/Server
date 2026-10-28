package dev.elysium.flora.worldgen;

import com.mojang.serialization.Codec;
import com.mojang.serialization.MapCodec;
import com.mojang.serialization.codecs.RecordCodecBuilder;
import dev.elysium.flora.ElysiumFlora;
import dev.elysium.flora.ThinLogBlock;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.BiConsumer;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.util.RandomSource;
import net.minecraft.util.valueproviders.IntProvider;
import net.minecraft.util.valueproviders.IntProviders;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.feature.configurations.TreeConfiguration;
import net.minecraft.world.level.levelgen.feature.foliageplacers.FoliagePlacer;
import net.minecraft.world.level.levelgen.feature.trunkplacers.TrunkPlacer;
import net.minecraft.world.level.levelgen.feature.trunkplacers.TrunkPlacerType;

/**
 * Several thin stems from one root, each leaning its own way: mesquite, juniper, alder, hazel coppice, rubble scrub.
 * With stems = 1 and lean = 0 it is a straight pole (aspen, birch).
 *
 * Every stem is face-connected: a lean step places a log beside the last one at the same height and the stem carries
 * on up from there. The placer records which neighbours each log grew from and sets the thin log's faces itself, so
 * two stems that grow side by side stay two stems instead of fusing into a ladder (which a neighbour-based join, like
 * connect_thin_logs, would do). Each stem ends in a foliage attachment, and with fork_chance a stem splits once into
 * a short side branch with its own smaller crown.
 *
 * Stems after the first start up to `spread` blocks from the root and are skipped where the ground below is not
 * solid. Logs are placed through the tree's trunk_provider, so no AXIS is set: thin logs have none.
 */
public class MultiStemTrunkPlacer extends TrunkPlacer {
    public static final MapCodec<MultiStemTrunkPlacer> CODEC = RecordCodecBuilder.mapCodec(i -> trunkPlacerParts(i)
            .and(IntProviders.codec(1, 8).fieldOf("stems").forGetter(p -> p.stems))
            .and(Codec.intRange(0, 3).fieldOf("spread").forGetter(p -> p.spread))
            .and(Codec.floatRange(0F, 1F).fieldOf("lean").forGetter(p -> p.lean))
            .and(Codec.floatRange(0F, 1F).fieldOf("fork_chance").forGetter(p -> p.forkChance))
            .apply(i, MultiStemTrunkPlacer::new));

    private final IntProvider stems;
    private final int spread;
    private final float lean;
    private final float forkChance;

    public MultiStemTrunkPlacer(int baseHeight, int randA, int randB, IntProvider stems, int spread, float lean, float forkChance) {
        super(baseHeight, randA, randB);
        this.stems = stems;
        this.spread = spread;
        this.lean = lean;
        this.forkChance = forkChance;
    }

    @Override
    protected TrunkPlacerType<?> type() {
        return ElysiumFlora.MULTI_STEM;
    }

    @Override
    public List<FoliagePlacer.FoliageAttachment> placeTrunk(WorldGenLevel level, BiConsumer<BlockPos, BlockState> replacer,
                                                            RandomSource random, int height, BlockPos root, TreeConfiguration config) {
        placeBelowTrunkBlock(level, replacer, random, root.below(), config);
        Stems g = new Stems();
        List<FoliagePlacer.FoliageAttachment> crowns = new ArrayList<>();
        int n = this.stems.sample(random);
        for (int s = 0; s < n; s++) {
            BlockPos start = root;
            BlockPos.MutableBlockPos p;
            if (s > 0 && this.spread == 0) {
                // Stems share the root block, split one block up and step sideways so the split shows.
                p = root.above().mutable();
                g.add(p);
                g.link(root, p, Direction.UP);
            } else {
                if (s > 0) {
                    start = root.offset(random.nextIntBetweenInclusive(-this.spread, this.spread), 0,
                            random.nextIntBetweenInclusive(-this.spread, this.spread));
                    BlockPos below = start.below();
                    if (!level.getBlockState(below).isFaceSturdy(level, below, Direction.UP)) continue;
                }
                p = start.mutable();
                g.add(p);
                g.ground(p);
            }
            int h = s == 0 ? height : Math.max(2, height - random.nextInt(3));
            Direction way = Direction.Plane.HORIZONTAL.getRandomDirection(random);
            if (s > 0 && this.spread == 0) g.step(p, way);
            boolean forked = false;
            for (int y = 1; y < h; y++) {
                if (y < h - 1 && random.nextFloat() < this.lean) {
                    g.step(p, random.nextFloat() < 0.75F ? way : Direction.Plane.HORIZONTAL.getRandomDirection(random));
                }
                if (!forked && y >= h / 2 && y < h - 1 && random.nextFloat() < this.forkChance) {
                    forked = true;
                    crowns.add(this.branch(g, random, p.immutable(), way));
                }
                g.step(p, Direction.UP);
            }
            crowns.add(new FoliagePlacer.FoliageAttachment(p.above(), 0, false));
        }
        for (Map.Entry<BlockPos, Set<Direction>> e : g.faces.entrySet()) {
            Set<Direction> faces = e.getValue();
            this.placeLog(level, replacer, random, e.getKey(), config, state -> withFaces(state, faces));
        }
        return crowns;
    }

    /** A 1-3 block side branch rising 1-2 blocks; returns its (smaller) crown. */
    private FoliagePlacer.FoliageAttachment branch(Stems g, RandomSource random, BlockPos from, Direction away) {
        Direction d = random.nextBoolean() ? away.getClockWise() : away.getCounterClockWise();
        BlockPos.MutableBlockPos p = from.mutable();
        int out = 1 + random.nextInt(3);
        for (int i = 0; i < out; i++) g.step(p, d);
        int up = 1 + random.nextInt(2);
        for (int i = 0; i < up; i++) g.step(p, Direction.UP);
        return new FoliagePlacer.FoliageAttachment(p.above(), -1, false);
    }

    private static BlockState withFaces(BlockState state, Set<Direction> faces) {
        if (!(state.getBlock() instanceof ThinLogBlock)) return state;
        for (Direction d : Direction.values()) state = state.setValue(ThinLogBlock.FACE.get(d), faces.contains(d));
        return state;
    }

    /** The logs of one tree and which faces each grew through. Placed in one pass at the end. */
    private static final class Stems {
        final Map<BlockPos, Set<Direction>> faces = new LinkedHashMap<>();

        void add(BlockPos pos) {
            faces.computeIfAbsent(pos.immutable(), k -> EnumSet.noneOf(Direction.class));
        }

        void ground(BlockPos pos) {
            faces.get(pos.immutable()).add(Direction.DOWN);
        }

        /** Join a to its neighbour b, which lies in direction d from a. */
        void link(BlockPos a, BlockPos b, Direction d) {
            add(a);
            add(b);
            faces.get(a.immutable()).add(d);
            faces.get(b.immutable()).add(d.getOpposite());
        }

        /** Move p one block in d, joining the two logs. */
        void step(BlockPos.MutableBlockPos p, Direction d) {
            BlockPos from = p.immutable();
            p.move(d);
            link(from, p, d);
        }
    }
}
