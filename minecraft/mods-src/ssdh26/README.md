# Seasonal LODs (ssdh26)

Recolors Distant Horizons LODs when the Serene Seasons season changes.

Without it, near terrain follows the season and far LODs stay stuck on
the old colors. Trees and grass both. See "How it works" below.

Client only. Needs Minecraft 26.2, Fabric, Distant Horizons 3.3.x and
Serene Seasons.

## Build

Needs Java 25. Put the two jars from `libs/README.md` in `libs/`.

```
./gradlew build
```

The mod lands in `build/libs/ssdh26-1.0.0.jar`.

## How it works

1. Watch the Serene Seasons sub-season every tick.
2. On a change (or joining a world), wait a few ticks.
3. Clear DH's tint cache and block color cache.
4. Walk every rendered LOD section, nearest first. Ask DH to rebuild
   8 per tick.

DH keeps the old buffer on screen until the new one is ready. So the
recolor is a quiet sweep. No flash, no ring.

`/ssdh reload` runs the sweep by hand. Watch the log for `Sweep started`.

## Status

It compiles. It has never been run in a real client. Things to check
when it is:

- Do far LODs actually change color after the sweep? That needs DH's
  tint path to see Serene Seasons' colors. Not confirmed.
- Is 8 sections per tick too slow or too heavy? It's a guess.
- Do the delays (10 ticks after a season change, 60 after joining)
  catch the season sync from the server?

It reaches only public DH fields and methods, no reflection. A DH update
can still rename them and break the build.

## Credit

The idea comes from ItsThatNova's
[Serene Seasons X Distant Horizons](https://github.com/ItsThatNova/serene-seasons-x-distant-horizons)
(MIT, Minecraft 1.21.1). This is a fresh rewrite for 26.2 and shares no
code with it. The MIT license and their copyright notice stay in `LICENSE`.
