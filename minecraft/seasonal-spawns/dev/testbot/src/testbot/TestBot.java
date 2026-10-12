package testbot;

import com.mojang.authlib.GameProfile;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import io.netty.channel.ChannelFutureListener;
import io.netty.channel.embedded.EmbeddedChannel;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.core.UUIDUtil;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.network.Connection;
import net.minecraft.network.DisconnectionDetails;
import net.minecraft.network.PacketListener;
import net.minecraft.network.ProtocolInfo;
import net.minecraft.network.chat.Component;
import net.minecraft.network.protocol.Packet;
import net.minecraft.network.protocol.PacketFlow;
import net.minecraft.network.protocol.common.ClientboundKeepAlivePacket;
import net.minecraft.network.protocol.common.ServerboundKeepAlivePacket;
import net.minecraft.network.protocol.game.ClientboundChunkBatchFinishedPacket;
import net.minecraft.network.protocol.game.ClientboundPlayerPositionPacket;
import net.minecraft.network.protocol.game.ServerboundAcceptTeleportationPacket;
import net.minecraft.network.protocol.game.ServerboundChunkBatchReceivedPacket;
import net.minecraft.network.protocol.game.ServerboundPlayerLoadedPacket;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ClientInformation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.network.CommonListenerCookie;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.MobCategory;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.phys.AABB;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

/**
 * DEV ONLY. Not part of the pack. Logs a fake player in on a headless server so the
 * real natural-spawn loop runs, then counts the land animals around it.
 *
 *   /testbot join <name> <x> <z>   put a creative player on the surface at x, z
 *   /testbot count                 land animals within 128 blocks of each bot, by type
 *   /testbot leave                 remove all bots
 *
 * The bot has no network. FakeConnection records what the server sends. Each tick we
 * tick the bot's packet listener (the server would do that for a real connection) and
 * answer what a real client answers: keep-alive, chunk batches, teleports, "loaded".
 */
public final class TestBot implements ModInitializer {

    /** A connection that goes nowhere. It keeps what the server sent so we can answer it. */
    static final class FakeConnection extends Connection {
        final List<Packet<?>> sent = new ArrayList<>();

        FakeConnection() {
            super(PacketFlow.SERVERBOUND);
        }

        @Override
        public void send(Packet<?> packet) {
            sent.add(packet);
        }

        @Override
        public void send(Packet<?> packet, ChannelFutureListener listener) {
            sent.add(packet);
        }

        @Override
        public void send(Packet<?> packet, ChannelFutureListener listener, boolean flush) {
            sent.add(packet);
        }

        @Override
        public <T extends PacketListener> void setupInboundProtocol(ProtocolInfo<T> info, T listener) {
            // nothing to set up. There is no pipeline.
        }

        @Override
        public boolean isConnected() {
            return true;
        }

        @Override
        public void disconnect(Component reason) {
            System.out.println("[testbot] server disconnected the bot: " + reason.getString());
        }

        @Override
        public void disconnect(DisconnectionDetails details) {
            System.out.println("[testbot] server disconnected the bot: " + details.reason().getString());
        }
    }

    private record Bot(ServerPlayer player, FakeConnection connection) {}

    private static final Map<String, Bot> BOTS = new LinkedHashMap<>();
    private static final Set<ServerPlayer> LOADED = new HashSet<>();

    @Override
    public void onInitialize() {
        ServerTickEvents.END_SERVER_TICK.register(TestBot::drain);
        CommandRegistrationCallback.EVENT.register((d, ctx, sel) -> d.register(Commands.literal("testbot")
                .requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                .then(Commands.literal("join").then(Commands.argument("name", StringArgumentType.word())
                        .then(Commands.argument("x", IntegerArgumentType.integer())
                                .then(Commands.argument("z", IntegerArgumentType.integer())
                                        .executes(c -> {
                                            try {
                                                return say(c.getSource(), join(c.getSource().getServer(),
                                                        StringArgumentType.getString(c, "name"),
                                                        IntegerArgumentType.getInteger(c, "x"),
                                                        IntegerArgumentType.getInteger(c, "z")));
                                            } catch (Throwable t) {
                                                t.printStackTrace(System.out);
                                                return 0;
                                            }
                                        })))))
                .then(Commands.literal("count").executes(c -> say(c.getSource(), count())))
                .then(Commands.literal("leave").executes(c -> say(c.getSource(), leave(c.getSource().getServer()))))));
    }

    private static int say(CommandSourceStack source, List<String> lines) {
        for (String l : lines) {
            source.sendSuccess(() -> Component.literal(l), false);
        }
        return lines.size();
    }

    private static List<String> join(MinecraftServer server, String name, int x, int z) throws Exception {
        ServerLevel level = server.overworld();
        GameProfile profile = new GameProfile(UUIDUtil.createOfflinePlayerUUID(name), name);
        FakeConnection connection = new FakeConnection();
        EmbeddedChannel channel = new EmbeddedChannel();
        channel.pipeline().addLast("packet_handler", connection);
        connection.channelActive(channel.pipeline().context(connection)); // gives it an address to log
        ServerPlayer player = new ServerPlayer(server, level, profile, ClientInformation.createDefault());
        server.getPlayerList().placeNewPlayer(connection, player, CommonListenerCookie.createInitial(profile, false));
        level.getChunk(x >> 4, z >> 4); // load it so the height is known
        int y = level.getHeight(Heightmap.Types.MOTION_BLOCKING, x, z);
        player.teleportTo(x + 0.5, y + 1, z + 0.5);
        player.setGameMode(GameType.CREATIVE);
        BOTS.put(name, new Bot(player, connection));
        return List.of("Bot " + name + " at " + x + ", " + (y + 1) + ", " + z);
    }

    private static List<String> leave(MinecraftServer server) {
        for (Bot b : BOTS.values()) {
            server.getPlayerList().remove(b.player());
        }
        int n = BOTS.size();
        BOTS.clear();
        LOADED.clear();
        return List.of("Removed " + n + " bots");
    }

    /** Tick each bot's listener, then answer what the server sent it. */
    private static void drain(MinecraftServer server) {
        for (Bot b : BOTS.values()) {
            var conn = b.player().connection;
            if (conn == null) {
                continue;
            }
            List<Packet<?>> out = new ArrayList<>(b.connection().sent);
            b.connection().sent.clear();
            for (Packet<?> o : out) {
                if (o instanceof ClientboundKeepAlivePacket ka) {
                    conn.handleKeepAlive(new ServerboundKeepAlivePacket(ka.getId()));
                } else if (o instanceof ClientboundChunkBatchFinishedPacket) {
                    // a real client says "got them, send more". Without this chunks stop coming.
                    conn.handleChunkBatchReceived(new ServerboundChunkBatchReceivedPacket(25.0f));
                } else if (o instanceof ClientboundPlayerPositionPacket pos) {
                    conn.handleAcceptTeleportPacket(new ServerboundAcceptTeleportationPacket(pos.id()));
                }
            }
            try {
                conn.tick();
                // A real client sends movement packets, and each one makes the server re-centre the
                // chunks it loads and sends. The bot never moves, so do that part by hand.
                b.player().level().getChunkSource().move(b.player());
            } catch (Throwable t) {
                t.printStackTrace(System.out);
            }
            if (!LOADED.contains(b.player()) && b.player().tickCount > 20) {
                conn.handleAcceptPlayerLoad(new ServerboundPlayerLoadedPacket());
                LOADED.add(b.player());
            }
        }
    }

    private static List<String> count() {
        List<String> out = new ArrayList<>();
        for (Map.Entry<String, Bot> e : BOTS.entrySet()) {
            ServerPlayer p = e.getValue().player();
            ServerLevel level = p.level();
            BlockPos pos = p.blockPosition();
            var mobs = level.getEntitiesOfClass(Mob.class, new AABB(pos).inflate(128, 512, 128),
                    m -> m.getType().getCategory() == MobCategory.CREATURE
                            && !m.isPersistenceRequired() && !m.requiresCustomPersistence());
            Map<String, Integer> by = new TreeMap<>();
            for (Mob m : mobs) {
                by.merge(BuiltInRegistries.ENTITY_TYPE.getKey(m.getType()).toString(), 1, Integer::sum);
            }
            int cx = pos.getX() >> 4;
            int cz = pos.getZ() >> 4;
            int loaded = 0;
            int ticking = 0;
            for (int dx = -8; dx <= 8; dx++) {
                for (int dz = -8; dz <= 8; dz++) {
                    if (level.getChunkSource().hasChunk(cx + dx, cz + dz)) {
                        loaded++;
                        if (level.isPositionEntityTicking(new BlockPos((cx + dx) * 16 + 8, 64, (cz + dz) * 16 + 8))) {
                            ticking++;
                        }
                    }
                }
            }
            out.add(String.format("%s at %d,%d: %d counted animals %s (tickCount %d, chunks within 8: %d loaded, %d entity-ticking of 289, dim %s)",
                    e.getKey(), pos.getX(), pos.getZ(), mobs.size(), by, p.tickCount, loaded, ticking,
                    level.dimension().identifier()));
        }
        return out;
    }
}
