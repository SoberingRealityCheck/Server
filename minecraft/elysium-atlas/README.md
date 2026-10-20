# elysium-atlas

Server-side Fabric mod for MC 26.2. Reads a baked atlas of the whole globe and feeds it into
Tectonic, so a new world follows real terrain and climate. Vertical slice: elevation, coastlines,
relief and surface biomes. No rivers or lakes from the atlas yet.

Tested on a headless 26.2 server with Fabric API 0.161.0, Lithostitched 1.8.0, Tectonic 3.0.28
and Terralith 2.6.4.

## Inert unless the world uses it

The jar ships in `server-overrides/mods/` and does nothing on a world that is not
`level-type=elysium_atlas:globe`. On start it checks the overworld's biome source. If it is not
the atlas source, every hook returns Tectonic's own function and the atlas is never read.
Checked: a normal-preset world, same seed, with and without the jar: 36,863 of 36,864 columns
have the same ground height (the one difference is one block, from a feature placed in a
different order).

## Switching a world to the atlas

1. Put the baked atlas at `config/elysium_atlas/atlas.json` (plus its `L0/`, `L1/` tile folders).
   It is not in this repo: the slice is 25 MB and a full-detail atlas is 1-2 GB.
2. In `config/tectonic.json` set `"max_y": 576` (world height -64..576). Do this only for the new
   world. The checked-in `server-overrides/config/tectonic.json` stays at 320 for the current one.
3. `server.properties`: `level-type=elysium_atlas\:globe`, new `level-name` or the old world moved away.
4. Start. The first start sets spawn to the atlas spawn (Lausanne in slice-2) and writes
   `world/elysium_atlas.properties` with the atlas version. Later starts warn if the installed
   atlas differs from that version, since new chunks would not meet old ones at their borders.

Freeze the atlas, this jar, Tectonic, Lithostitched and Terralith for the life of the world.
Any change to them changes terrain in chunks not yet generated and leaves seams.

## How it hooks Tectonic

- Lithostitched `wrap_density_function` modifiers (`src/main/resources/data/elysium_atlas/lithostitched/`):
  - `tectonic:terrain_spline/offset/final` -> atlas height. Tectonic's depth is
    `1 - y/128 + offset`, so offset = Y/128 - 1 puts the surface at the atlas height.
  - `tectonic:noise/raw_continents` -> continentalness from atlas height, so Tectonic's coast,
    ocean and mountain splines agree with the atlas.
  - `tectonic:terrain_spline/jaggedness/continents` -> scaled by atlas relief. Without this,
    Tectonic's erosion noise raised flat land by up to 40 blocks.
  Each `elysium_atlas:sample` has a `fallback`, used when the world is not an atlas world.
- Biome source `elysium_atlas:atlas`: the baked palette ID per 4x4 column. Below the surface it
  asks the overworld multi_noise preset and keeps only cave biomes (Terralith `cave/*`, lush and
  dripstone caves). Deep dark is left out.
- World preset `elysium_atlas:globe`. Nether and End are vanilla.

## Atlas format

`atlas.json` plus levels of 256 x 256-cell gzip tiles (header `EATL`, u16 version, u16 size, then
per cell i16 Y*8, u8 relief/20 m, u8 biome palette index; little-endian). Slice-2: L0 is the globe
at 32 blocks per cell, L1 is the Alps (4-13.5E, 43.5-48.5N) at 4 blocks per cell. Equal Earth,
central meridian 11E, 150 m per block, sea level Y 63. Height is Catmull-Rom sampled, identical in
`bake/bake_atlas.py` and `AtlasLevel.java`.

`bake/bake_atlas.py OUT TILE_CACHE [--region LON0 LON1 LAT0 LAT1] [--spawn LON LAT]` builds it from
Terrarium elevation tiles and the biome layers in the project's worldgen-experiments folder (set
`ELYSIUM_WORLDGEN_EXPERIMENTS` to its path). Changing a frozen constant in it needs a new
`ATLAS_VERSION` and a new world. `bake/render_world.py` renders generated region files against
the atlas (hillshade, biomes, height error).

## Results (slice-2)

| Test | Mean abs(ground - atlas), blocks |
|---|---|
| Lausanne, 4,624 generated chunks | 4.2 (p95 14.7) |
| Everest, 600 km probe | 2.7 |
| Mid-Atlantic probe | 9.0 (Tectonic ocean noise adds +/-30) |
| Brittany coast probe | 2.4 |
| L1/L0 boundary probe | 1.8 |

18 chunks/s on 4 cores.

## Commands (op level 2)

- `/atlas here`: latitude, longitude, atlas height, relief and biome where you stand.
- `/atlas goto <lat> <lon>`
- `/atlas probe <lat> <lon> <size> <step>`: samples terrain height and biome before features on a
  grid and writes `world/atlas_probe/*.csv`. About 25 columns/s.

On a non-atlas world they reply that the world does not use the atlas.

## Build

`./build.sh` (plain javac, Java 25) writes `../server-overrides/mods/elysium_atlas.jar`.
`build.py` does not build it. Fabric API modules needed at compile time: base, command, lifecycle events.

## Not done

- Rivers and lakes from the atlas. Tectonic's ridge noise still cuts its own valleys; Lake Geneva is flat land.
- Detail outside the Alps box (a global L1 is about 1-2 GB).
- Sea-level rise is a 12 m placeholder.
- Not tested with Distant Horizons, Streams Reflowing or RoadWeaver.
