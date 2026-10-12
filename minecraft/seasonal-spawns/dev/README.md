# Dev tools

Not part of the pack. Nothing here is built by `build.py` or shipped to
players or the server.

## shares.py

Turns the CSV from `/seasonalspawns shares` into an outlier report and a
heatmap. Python standard library only.

```sh
python3 -I dev/shares.py <server>/seasonal-spawns-shares.csv [out-dir]
```

It writes `shares-report.txt` (ghosts, hogs, dominant animals, season
swings, poor biomes) and `shares.html` (animal by biome, four seasons per
cell). The thresholds are constants at the top of the script. The README has
the details and the limits ("Seeing who is over- or under-represented").

## testbot

A headless server has no player, and natural spawning only runs near a
player. So a console-only test can call the spawn picker (`/seasonalspawns
sample`) but cannot watch the world fill up. `testbot` fixes that. It logs
a fake creative player in on a dedicated server, answers the packets a
real client would answer, and counts the land animals around it.

```
/testbot join <name> <x> <z>   put a bot on the surface at x, z
/testbot count                 land animals within 128 blocks of each bot, by type,
                               plus how many chunks around it are loaded and ticking
/testbot leave                 remove all bots
```

Build and use:

```sh
JAVA_HOME=/path/to/jdk-25 ../build.sh          # once, downloads what the bot needs
JAVA_HOME=/path/to/jdk-25 testbot/build.sh     # writes testbot/testbot.jar
```

Copy `testbot.jar` into a **test** server's `mods/`. Never the real one.

How the check was run (2026-10):

1. Boot a dedicated server from the pack. Fabric API is already in it.
2. `gamerule respawninganimals:remove_animals_when_far_away true`
3. `season set mid_summer` (or `mid_winter`).
4. `/testbot join` one bot per site, then wait about a minute for the
   chunks around each to load. Check `count` shows 289 loaded and ticking.
5. `kill @e[type=!player]` once the areas are loaded, so animals saved by an
   earlier run do not skew the count. Animals within 32 blocks of a player
   never despawn, so they would stay.
6. `tick sprint 6000` a few times, `count` after each. A sprint runs the
   game as fast as it can. Counts settle after about 30000 ticks.
7. `/seasonalspawns here` at each site shows the cap the mod worked out, to
   compare with the settled count.

Things the bot has to fake, found the hard way:

- A fake `Connection` that records what the server sends. The server only
  ticks connections it accepted itself, so the bot ticks its own listener
  each tick.
- Answer keep-alives, chunk batches ("send more"), teleports, and the
  "player loaded" packet.
- Call `ServerChunkCache.move(player)` each tick. A real client's movement
  packets do that. Without it only the first chunk ever loads.

It reaches into server internals and will probably need fixing after a
Minecraft update.
