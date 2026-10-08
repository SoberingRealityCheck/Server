package dev.elysium.ssdh;

import com.mojang.brigadier.Command;
import com.seibel.distanthorizons.api.DhApi;
import com.seibel.distanthorizons.api.interfaces.world.IDhApiLevelWrapper;
import com.seibel.distanthorizons.api.methods.events.DhApiEventRegister;
import com.seibel.distanthorizons.api.methods.events.abstractEvents.DhApiLevelLoadEvent;
import com.seibel.distanthorizons.api.methods.events.sharedParameterObjects.DhApiEventParam;
import com.seibel.distanthorizons.common.wrappers.block.AbstractDhTintGetter;
import com.seibel.distanthorizons.core.level.ClientLevelModule;
import com.seibel.distanthorizons.core.level.DhClientLevel;
import com.seibel.distanthorizons.core.pos.DhSectionPos;
import com.seibel.distanthorizons.core.pos.blockPos.DhBlockPos2D;
import com.seibel.distanthorizons.core.render.QuadTree.LodRenderSection;
import com.seibel.distanthorizons.core.wrapperInterfaces.world.IClientLevelWrapper;
import com.seibel.distanthorizons.core.wrapperInterfaces.world.ILevelWrapper;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.command.v2.ClientCommands;
import net.fabricmc.fabric.api.client.command.v2.ClientCommandRegistrationCallback;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.minecraft.client.Minecraft;
import net.minecraft.network.chat.Component;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import sereneseasons.api.season.ISeasonState;
import sereneseasons.api.season.Season;
import sereneseasons.api.season.SeasonHelper;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Comparator;

/**
 * Recolors Distant Horizons LODs when the Serene Seasons season changes.
 *
 * Why this exists: DH builds LOD buffers from block + biome data and bakes
 * the tint colors in at build time. Serene Seasons changes the tint every
 * sub-season. Nothing tells DH, so far LODs keep last season's colors.
 *
 * What we do on a season change (or on joining a world):
 *   1. clear DH's color caches
 *   2. rebuild every rendered LOD section, nearest first, a few per tick
 *
 * DH keeps the old buffer on screen until the new one is ready, so there is
 * no flash and no ring. It only costs CPU while the sweep runs.
 *
 * Client only. The server stores block + biome, never colors.
 *
 * Idea from ItsThatNova's "Serene Seasons X Distant Horizons" (MIT).
 * This is a rewrite for 26.2 and shares no code with it.
 */
public class SeasonalLods implements ClientModInitializer {

    static final Logger LOG = LoggerFactory.getLogger("ssdh26");

    // Ticks to wait before sweeping, so a burst of changes becomes one sweep.
    // Joining a world waits longer: DH is still loading and the season state
    // may not have synced from the server yet. Guesses. Tune by watching.
    static final int SEASON_DELAY_TICKS = 10;
    static final int JOIN_DELAY_TICKS = 60;

    // Sections we start rebuilding per tick. DH rebuilds on its own threads,
    // this just stops us queuing thousands at once. Guess. Tune by watching.
    static final int SECTIONS_PER_TICK = 8;

    // A section can be busy when we ask. We retry it later, but not forever.
    static final int MAX_ATTEMPTS = 200;

    private record Pending(LodRenderSection section, int attempts) {}

    private final ArrayDeque<Pending> pending = new ArrayDeque<>();
    private Season.SubSeason lastSubSeason = null;

    // Set from DH's event thread, read on the client tick. -1 means nothing armed.
    private volatile int armedTicks = -1;

    @Override
    public void onInitializeClient() {
        ClientTickEvents.END_CLIENT_TICK.register(this::onTick);

        DhApiEventRegister.on(DhApiLevelLoadEvent.class, new DhApiLevelLoadEvent() {
            @Override
            public void onLevelLoad(DhApiEventParam<EventParam> param) {
                if (param.value == null || param.value.levelWrapper == null) return;
                if (!isOverworld(param.value.levelWrapper)) return;
                LOG.info("DH overworld loaded. Arming a sweep in {} ticks.", JOIN_DELAY_TICKS);
                armedTicks = JOIN_DELAY_TICKS;
            }
        });

        // Manual trigger, for watching it work: /ssdh reload
        ClientCommandRegistrationCallback.EVENT.register((dispatcher, registryAccess) ->
                dispatcher.register(ClientCommands.literal("ssdh")
                        .then(ClientCommands.literal("reload").executes(ctx -> {
                            int n = startSweep();
                            ctx.getSource().sendFeedback(Component.literal("Seasonal LODs: queued " + n + " sections"));
                            return Command.SINGLE_SUCCESS;
                        }))));

        LOG.info("Seasonal LODs loaded.");
    }

    private void onTick(Minecraft mc) {
        if (mc.level == null) {
            lastSubSeason = null;
            armedTicks = -1;
            pending.clear();
            return;
        }

        Season.SubSeason now = currentSubSeason(mc);
        if (now != null) {
            // First sight after joining is not a change. The join sweep covers it.
            if (lastSubSeason != null && now != lastSubSeason) {
                LOG.info("Season changed {} -> {}. Arming a sweep.", lastSubSeason, now);
                armedTicks = SEASON_DELAY_TICKS;
            }
            lastSubSeason = now;
        }

        int armed = armedTicks;
        if (armed >= 0) {
            armedTicks = armed - 1;
            if (armed == 0) startSweep();
        }

        pump();
    }

    private static Season.SubSeason currentSubSeason(Minecraft mc) {
        try {
            ISeasonState state = SeasonHelper.getSeasonState(mc.level);
            return state == null ? null : state.getSubSeason();
        } catch (Exception e) {
            return null;
        }
    }

    // Serene Seasons only runs in the overworld by default. Same assumption as upstream.
    private static boolean isOverworld(IDhApiLevelWrapper level) {
        return "minecraft:overworld".equals(level.getDimensionName());
    }

    private static IDhApiLevelWrapper findOverworld() {
        var proxy = DhApi.Delayed.worldProxy;
        if (proxy == null) return null;
        for (IDhApiLevelWrapper level : proxy.getAllLoadedLevelWrappers()) {
            if (isOverworld(level)) return level;
        }
        return null;
    }

    /** Clear caches, then queue every rendered section, nearest first. Returns how many. */
    private int startSweep() {
        Minecraft mc = Minecraft.getInstance();
        IDhApiLevelWrapper level = findOverworld();
        if (level == null || mc.player == null) {
            LOG.warn("Sweep skipped: no DH overworld level or no player yet.");
            return 0;
        }

        // Both caches hold colors computed for the old season.
        AbstractDhTintGetter.clear();
        if (level instanceof IClientLevelWrapper clientLevel) clientLevel.clearBlockColorCache();

        var sections = new ArrayList<LodRenderSection>();
        try {
            if (!(level instanceof ILevelWrapper wrapper)) return 0;
            if (!(wrapper.getDhLevel() instanceof DhClientLevel dhLevel)) return 0;
            ClientLevelModule.ClientRenderState state = dhLevel.clientside.ClientRenderStateRef.get();
            if (state == null) {
                LOG.warn("Sweep skipped: DH has no render state yet.");
                return 0;
            }
            state.quadtree.populateListWithEnabledRenderSections(sections);
        } catch (Exception e) {
            LOG.error("Could not list DH sections. Colors will fix themselves as DH rebuilds.", e);
            return 0;
        }

        var player = new DhBlockPos2D((int) mc.player.getX(), (int) mc.player.getZ());
        sections.sort(Comparator.comparingInt(s -> DhSectionPos.getManhattanBlockDistance(s.pos, player)));

        pending.clear();
        for (LodRenderSection s : sections) pending.add(new Pending(s, 0));
        LOG.info("Sweep started: {} sections.", sections.size());
        return sections.size();
    }

    /** Start up to SECTIONS_PER_TICK rebuilds. Busy sections go to the back. */
    private void pump() {
        for (int budget = SECTIONS_PER_TICK; budget > 0 && !pending.isEmpty(); budget--) {
            Pending p = pending.pollFirst();
            if (!p.section().getRenderingEnabled()) continue; // DH dropped it (moved away)

            boolean started;
            try {
                started = p.section().uploadRenderDataToGpuAsync();
            } catch (Exception e) {
                LOG.debug("Section rebuild failed: {}", e.toString());
                continue;
            }
            if (!started && p.attempts() < MAX_ATTEMPTS) {
                pending.addLast(new Pending(p.section(), p.attempts() + 1));
            }
        }
    }
}
