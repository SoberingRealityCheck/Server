package dev.elysium.atlas;

import com.mojang.brigadier.arguments.DoubleArgumentType;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.context.CommandContext;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.dimension.LevelStem;
import net.minecraft.world.level.chunk.ChunkGenerator;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.levelgen.NoiseBasedChunkGenerator;
import net.minecraft.world.level.storage.LevelData;
import net.minecraft.world.level.storage.LevelResource;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Properties;

public final class ElysiumAtlas implements ModInitializer {
    public static final String MOD_ID = "elysium_atlas";

    @Override
    public void onInitialize() {
        Registry.register(BuiltInRegistries.DENSITY_FUNCTION_TYPE, Identifier.fromNamespaceAndPath(MOD_ID, "sample"), AtlasDensityFunction.MAP_CODEC);
        Registry.register(BuiltInRegistries.BIOME_SOURCE, Identifier.fromNamespaceAndPath(MOD_ID, "atlas"), AtlasBiomeSource.CODEC);
        ServerLifecycleEvents.SERVER_STARTING.register(server -> {
            boolean on = usesAtlas(server);
            AtlasFluidPicker.atlasSettings = on && overworldGenerator(server) instanceof NoiseBasedChunkGenerator g ? g.generatorSettings().value() : null;
            Atlas.setActive(on);
        });
        ServerLifecycleEvents.SERVER_STARTED.register(ElysiumAtlas::onStarted);
        ServerLifecycleEvents.SERVER_STOPPED.register(server -> Atlas.setActive(false));
        CommandRegistrationCallback.EVENT.register((dispatcher, registry, env) -> dispatcher.register(
                Commands.literal("atlas").requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                        .then(Commands.literal("here").executes(ElysiumAtlas::here))
                        .then(Commands.literal("probe").then(Commands.argument("lat", DoubleArgumentType.doubleArg(-90, 90))
                                .then(Commands.argument("lon", DoubleArgumentType.doubleArg(-180, 180))
                                        .then(Commands.argument("size", IntegerArgumentType.integer(16, 8192))
                                                .then(Commands.argument("step", IntegerArgumentType.integer(1, 256)).executes(ElysiumAtlas::probe))))))
                        .then(Commands.literal("goto").then(Commands.argument("lat", DoubleArgumentType.doubleArg(-90, 90))
                                .then(Commands.argument("lon", DoubleArgumentType.doubleArg(-180, 180)).executes(ElysiumAtlas::gotoLonLat))))));
    }

    /** Checked before any chunk is generated, from the overworld's level stem. */
    private static ChunkGenerator overworldGenerator(MinecraftServer server) {
        LevelStem stem = server.registryAccess().lookupOrThrow(Registries.LEVEL_STEM).getValue(LevelStem.OVERWORLD);
        return stem == null ? null : stem.generator();
    }

    private static boolean usesAtlas(MinecraftServer server) {
        ChunkGenerator g = overworldGenerator(server);
        return g != null && g.getBiomeSource() instanceof AtlasBiomeSource;
    }

    /** Commands need the atlas; on other worlds they say so instead of throwing. */
    private static Atlas atlasOrFail(CommandContext<CommandSourceStack> c) {
        if (Atlas.active()) return Atlas.get();
        c.getSource().sendFailure(Component.literal("This world does not use the Elysium atlas (level-type elysium_atlas:globe)."));
        return null;
    }

    /**
     * On first start of an atlas world: move spawn to the atlas spawn point and record the atlas version.
     * On later starts: warn if the atlas changed, since new chunks would no longer match old ones.
     */
    private static void onStarted(MinecraftServer server) {
        if (!Atlas.active()) return;
        ServerLevel level = server.overworld();
        Atlas a = Atlas.get();
        Path stamp = server.getWorldPath(LevelResource.ROOT).resolve("elysium_atlas.properties");
        Properties p = new Properties();
        try {
            if (Files.exists(stamp)) {
                try (var r = Files.newBufferedReader(stamp)) { p.load(r); }
                String was = p.getProperty("atlas_version");
                if (!a.version.equals(was))
                    Atlas.LOG.warn("World was generated with atlas {} but atlas {} is installed. New chunks will not match old ones at their borders.", was, a.version);
                return;
            }
            int y = level.getChunk(a.spawnX >> 4, a.spawnZ >> 4).getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, a.spawnX & 15, a.spawnZ & 15) + 1;
            level.setRespawnData(LevelData.RespawnData.of(Level.OVERWORLD, new BlockPos(a.spawnX, y, a.spawnZ), 0, 0));
            p.setProperty("atlas_version", a.version);
            p.setProperty("spawn", a.spawnX + " " + y + " " + a.spawnZ);
            try (var w = Files.newBufferedWriter(stamp)) { p.store(w, "Written by elysium_atlas on first start. Do not edit."); }
            Atlas.LOG.info("Atlas world: spawn set to {} {} {}", a.spawnX, y, a.spawnZ);
        } catch (IOException e) {
            Atlas.LOG.error("Could not read or write {}", stamp, e);
        }
    }

    private static int here(CommandContext<CommandSourceStack> c) {
        Atlas a = atlasOrFail(c);
        if (a == null) return 0;
        var pos = c.getSource().getPosition();
        double[] ll = a.toLonLat(pos.x, pos.z);
        int b = a.biome(pos.x, pos.z);
        var col = a.column((int) Math.floor(pos.x), (int) Math.floor(pos.z));
        String msg = String.format("%.4f, %.4f | atlas Y %.1f | carved Y %.1f | water %s | relief %.0f m | atlas biome %s | %s",
                ll[1], ll[0], a.heightOrOcean(pos.x, pos.z), col.height(), col.fluid() == Water.NO_FLUID ? "none" : "below Y " + col.fluid(),
                a.relief(pos.x, pos.z), b >= 0 ? a.palette.get(b) : "none", a.version);
        c.getSource().sendSuccess(() -> Component.literal(msg), false);
        return 1;
    }

    /**
     * Samples the generator's terrain height (before features) and biome on a grid around a point and writes
     * world/atlas_probe/<lat>_<lon>.csv. Checks the atlas -> Tectonic -> terrain path without generating chunks.
     */
    private static int probe(CommandContext<CommandSourceStack> c) {
        Atlas a = atlasOrFail(c);
        if (a == null) return 0;
        double lat = DoubleArgumentType.getDouble(c, "lat"), lon = DoubleArgumentType.getDouble(c, "lon");
        int size = IntegerArgumentType.getInteger(c, "size"), step = IntegerArgumentType.getInteger(c, "step");
        ServerLevel level = c.getSource().getServer().overworld();
        var gen = level.getChunkSource().getGenerator();
        var rs = level.getChunkSource().randomState();
        double[] b = a.toBlock(lon, lat);
        int x0 = (int) Math.round(b[0]) - size / 2, z0 = (int) Math.round(b[1]) - size / 2;
        Path out = c.getSource().getServer().getWorldPath(LevelResource.ROOT).resolve("atlas_probe").resolve(String.format("%.3f_%.3f.csv", lat, lon));
        long t0 = System.nanoTime();
        int n = 0;
        double err = 0, maxErr = 0;
        try {
            Files.createDirectories(out.getParent());
            try (var w = Files.newBufferedWriter(out)) {
                w.write("x,z,floor_y,surface_y,atlas_y,carved_y,fluid_y,biome\n");
                for (int z = z0; z < z0 + size; z += step) {
                    for (int x = x0; x < x0 + size; x += step) {
                        int floor = gen.getBaseHeight(x, z, Heightmap.Types.OCEAN_FLOOR_WG, level, rs);
                        int surf = gen.getBaseHeight(x, z, Heightmap.Types.WORLD_SURFACE_WG, level, rs);
                        double ay = a.heightOrOcean(x, z);
                        var col = a.column(x, z);
                        var biome = gen.getBiomeSource().getNoiseBiome(x >> 2, (Math.max(surf, floor) - 1) >> 2, z >> 2, rs.sampler());
                        w.write(x + "," + z + "," + floor + "," + surf + "," + String.format("%.2f", ay) + "," + String.format("%.2f", col.height()) + "," + (col.fluid() == Water.NO_FLUID ? "" : col.fluid()) + "," + biome.unwrapKey().map(k -> k.identifier().toString()).orElse("?") + "\n");
                        double e = Math.abs(floor - col.height());
                        err += e; maxErr = Math.max(maxErr, e); n++;
                    }
                }
            }
        } catch (IOException e) {
            c.getSource().sendFailure(Component.literal("probe failed: " + e));
            return 0;
        }
        String msg = String.format("probe %d columns in %.1f s: mean |floor - carved atlas| %.2f, max %.1f -> %s", n, (System.nanoTime() - t0) / 1e9, err / n, maxErr, out);
        Atlas.LOG.info(msg);
        c.getSource().sendSuccess(() -> Component.literal(msg), false);
        return 1;
    }

    private static int gotoLonLat(CommandContext<CommandSourceStack> c) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        Atlas a = atlasOrFail(c);
        if (a == null) return 0;
        double[] b = a.toBlock(DoubleArgumentType.getDouble(c, "lon"), DoubleArgumentType.getDouble(c, "lat"));
        var player = c.getSource().getPlayerOrException();
        ServerLevel level = c.getSource().getServer().overworld();
        int bx = (int) Math.floor(b[0]), bz = (int) Math.floor(b[1]);
        int y = level.getChunk(bx >> 4, bz >> 4).getHeight(Heightmap.Types.MOTION_BLOCKING, bx & 15, bz & 15) + 1;
        player.teleportTo(level, bx + 0.5, y, bz + 0.5, java.util.Set.of(), player.getYRot(), player.getXRot(), true);
        c.getSource().sendSuccess(() -> Component.literal(String.format("Teleported to %.0f %.0f %.0f", b[0], y, b[1])), true);
        return 1;
    }
}
