package dev.elysium.flora.worldgen;

import com.mojang.serialization.Codec;
import com.mojang.serialization.MapCodec;
import com.mojang.serialization.codecs.RecordCodecBuilder;
import dev.elysium.flora.ElysiumFlora;
import java.util.ArrayList;
import java.util.List;
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
 * on up from there, so the connect decorator can join the whole tree. Each stem ends in a foliage attachment, and
 * with fork_chance a stem splits once into a short side branch with its own smaller crown.
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
        List<FoliagePlacer.FoliageAttachment> crowns = new ArrayList<>();
        int n = this.stems.sample(random);
        for (int s = 0; s < n; s++) {
            BlockPos start = root;
            if (s > 0) {
                if (this.spread == 0) {
                    // Stems share the root block and split one block up.
                    start = root.above();
                } else {
                    start = root.offset(random.nextIntBetweenInclusive(-this.spread, this.spread), 0,
                            random.nextIntBetweenInclusive(-this.spread, this.spread));
                    BlockPos below = start.below();
                    if (!level.getBlockState(below).isFaceSturdy(level, below, Direction.UP)) continue;
                }
            }
            int h = s == 0 ? height : Math.max(2, height - random.nextInt(3));
            Direction way = Direction.Plane.HORIZONTAL.getRandomDirection(random);
            BlockPos.MutableBlockPos p = start.mutable();
            if (s > 0 && this.spread == 0) {
                // Step sideways off the shared trunk so the split is visible.
                this.placeLog(level, replacer, random, p, config);
                p.move(way);
            }
            boolean forked = false;
            for (int y = 0; y < h; y++) {
                this.placeLog(level, replacer, random, p, config);
                if (y > 0 && y < h - 1 && random.nextFloat() < this.lean) {
                    p.move(random.nextFloat() < 0.75F ? way : Direction.Plane.HORIZONTAL.getRandomDirection(random));
                    this.placeLog(level, replacer, random, p, config);
                }
                if (!forked && y >= h / 2 && y < h - 1 && random.nextFloat() < this.forkChance) {
                    forked = true;
                    crowns.add(this.branch(level, replacer, random, p.immutable(), way, config));
                }
                p.move(Direction.UP);
            }
            crowns.add(new FoliagePlacer.FoliageAttachment(p.immutable(), 0, false));
        }
        return crowns;
    }

    /** A 1-3 block side branch rising 1-2 blocks; returns its (smaller) crown. */
    private FoliagePlacer.FoliageAttachment branch(WorldGenLevel level, BiConsumer<BlockPos, BlockState> replacer,
                                                   RandomSource random, BlockPos from, Direction away, TreeConfiguration config) {
        Direction d = random.nextBoolean() ? away.getClockWise() : away.getCounterClockWise();
        BlockPos.MutableBlockPos p = from.mutable();
        int out = 1 + random.nextInt(3);
        for (int i = 0; i < out; i++) {
            p.move(d);
            this.placeLog(level, replacer, random, p, config);
        }
        int up = 1 + random.nextInt(2);
        for (int i = 0; i < up; i++) {
            p.move(Direction.UP);
            this.placeLog(level, replacer, random, p, config);
        }
        return new FoliagePlacer.FoliageAttachment(p.above(), -1, false);
    }
}
