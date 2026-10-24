# elysium-atlas

Server-side Fabric mod for MC 26.2. Reads a baked atlas of the whole globe and feeds it into
Tectonic, so a new world follows real terrain and climate. Vertical slice: elevation, coastlines,
relief, surface biomes, rivers, streams and lakes.

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
   It is not in this repo: slice-4 is 64 MB (tiles plus `water.bin.gz`) and a full-detail atlas is 1-2 GB.
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
  - `tectonic:terrain_spline/roughness` and `tectonic:terrain_spline/offset/depth_additive` -> scaled by
    `calm`, which is 0 on water and rises to 1 away from it, so Tectonic's own noise cannot fill a channel.
  Each `elysium_atlas:sample` has a `fallback`, used when the world is not an atlas world.
- Biome source `elysium_atlas:atlas`: the baked palette ID per 4x4 column. Below the surface it
  asks the overworld multi_noise preset and keeps only cave biomes (Terralith `cave/*`, lush and
  dripstone caves). Deep dark is left out.
- World preset `elysium_atlas:globe`. Nether and End are vanilla.
- Water (`Water.java`, `water.bin.gz`): river centrelines as segments with water level, half-width and
  depth; lake outlines as edges with a level and depth per lake. Per block column: a river channel is
  carved to `level - 1 - depth*(1 - (d/w)^2)` with a levee 1.2 blocks above the water at its edge; a
  lake bed deepens 0.3 blocks per block from the shore up to the lake's depth; a 1.2-block lip outside
  the shore stops lake water spilling. The carved height replaces the atlas height in the offset hook.
  River and lake columns get `minecraft:river` (or `frozen_river` where the atlas biome is cold);
  stream columns keep the land biome. Streams use the same carve with half-width 4 and depth 3.
  The segment index is sorted arrays, not a map: 3.5M segments are about 130 MB of floats plus the index.
- Water above sea level needs two mixins, because Minecraft only fills water below Y 63 on its own:
  `NoiseBasedChunkGeneratorMixin` wraps the generator's global fluid picker where it is read (Tectonic
  replaces it in the constructor, so wrapping `createFluidPicker` does not work), and
  `NoiseBasedAquiferMixin` places atlas water per block before the aquifer's coarse sampling, which
  misses a channel a few blocks wide. Both pass through unless the atlas is active and the generator is
  the overworld's.

## Atlas format

`atlas.json` plus levels of 256 x 256-cell gzip tiles (header `EATL`, u16 version, u16 size, then
per cell i16 Y*8, u8 relief/20 m, u8 biome palette index; little-endian). Slice-2: L0 is the globe
at 32 blocks per cell, L1 is the Alps (4-13.5E, 43.5-48.5N) at 4 blocks per cell. Equal Earth,
central meridian 11E, 150 m per block, sea level Y 63. Height is Catmull-Rom sampled, identical in
`bake/bake_atlas.py` and `AtlasLevel.java`.

`bake/bake_water.py ATLAS_DIR NE_DIR HYDRO_NPZ [ATLAS_VERSION]` adds rivers and lakes to a baked atlas
(about 20 s). Sources: Natural Earth 10m rivers and lakes plus their Europe supplements (geojson from
github.com/nvkelso/natural-earth-vector) and the hydro_v2 warm grid for discharge and flow direction.
River water level is the running minimum of atlas terrain from the source, so it never rises downstream;
half-width is `1.8 * Q^0.28` blocks (4 to 32); a lake's level is the median of its flat DEM surface, or
just under its shore where the DEM holds bathymetry (Lake Superior), and never above its low shore points.

Streams (`bake/bake_streams.py`, about 4 min for the globe): the hydro_v2 drainage network for cells with
at least 150 km2 upstream that no Natural Earth river crosses (about one stream per 100-150 blocks).
Each 5 km cell drains to its neighbour with the largest drainage area; cell centres move to the lowest
atlas point within 12 blocks, then the chains are smoothed and given a meander (5 blocks, 80-block
wavelength) that fades out at both ends. A stream's level never drops below the river, lake, sea or
downstream stream it joins. Slice-4: 3.1M stream segments, `water.bin.gz` 40 MB (format 2).

Sub-biomes (`bake/bake_subbiomes.py ATLAS_DIR TILE_CACHE WC_CACHE`, about 1 min, run last): on the
4-block detail level, each cell gets one of 17 classes from terrain (slope, aspect, hollows, ridges,
flow) and ESA WorldCover 2021 land use (old fields, woods, towns, wetland), then a biome from the class
and the group of the formation biome already there (broadleaf, conifer, mountain, dry). Patches are at
least about 36 blocks. Only L1 biome bytes and `atlas.json` change. Slice-5 = slice-4 + sub-biomes: in
a lowland France window the share of `forest` falls from 41% to 17% and distinct biomes rise from 18
to 28. Behind a TLS proxy set `GDAL_CURL_CA_BUNDLE`.

`bake/bake_atlas.py OUT TILE_CACHE [--region LON0 LON1 LAT0 LAT1] [--spawn LON LAT]` builds it from
Terrarium elevation tiles and the biome layers in the project's worldgen-experiments folder (set
`ELYSIUM_WORLDGEN_EXPERIMENTS` to its path). Changing a frozen constant in it needs a new
`ATLAS_VERSION` and a new world. `bake/render_world.py` renders generated region files against
the atlas (hillshade, biomes, height error).

## Results (slice-2 terrain, slice-3 water)

| Test | Mean abs(ground - atlas), blocks |
|---|---|
| Lausanne, 4,624 generated chunks | 4.2 (p95 14.7) |
| Everest, 600 km probe | 2.7 |
| Mid-Atlantic probe | 9.0 (Tectonic ocean noise adds +/-30) |
| Brittany coast probe | 2.4 |
| L1/L0 boundary probe | 1.8 |

18 chunks/s on 4 cores without water, 16 with it.

Water, slice-3 (`test/` renders in the project files): Lake Geneva, Lake Neuchâtel and the Rhône fill at
Lausanne, with the Rhône entering at Villeneuve and leaving at Geneva. The Rhine, Moselle and Lahn meet at
Koblenz on the coarse (32-block) level. Same-seed normal world with the jar: still identical apart from one
feature block.

Streams, slice-4: 84% of stream vertices at Limoges have water, and 93% in the Massif Central (within
2 blocks); the rest are heads and steep steps. Generation is about 15 chunks/s on 4 cores.

Streams Reflowing 2.14.4 on an atlas world (LOW accuracy) runs without errors but plans no streams on most
inland land (0 segments around Lausanne and most of Limoges, against about 7,000 per 768-block area in a
normal world); its settings did not change that. At MAX accuracy spawn preparation took over an hour in
either kind of world. The atlas draws its own streams instead.

## Commands (op level 2)

- `/atlas here`: latitude, longitude, atlas height, carved height, water level, relief and biome where you stand.
- `/atlas goto <lat> <lon>`
- `/atlas probe <lat> <lon> <size> <step>`: samples terrain height and biome before features on a
  grid and writes `world/atlas_probe/*.csv`. About 25 columns/s.

On a non-atlas world they reply that the world does not use the atlas.

## Build

`./build.sh` (plain javac, Java 25) writes `../server-overrides/mods/elysium_atlas.jar`.
`build.py` does not build it. Fabric API modules needed at compile time: base, command, lifecycle events.

## Regional biome variants

A variant is a child of an existing biome, used in some pack regions: `elysium:larch_slopes` is
`minecraft:windswept_forest` in the eastern Alps. It changes only colours, effects and a feature patch.
Everything else comes from the parent at runtime, so other systems need no edits:

| What | How the variant follows its parent |
|---|---|
| Biome tags (Serene Seasons, Naturalist, structures, mob variants, `c:` tags, any datapack) | `TagLoaderMixin` adds the variant to every biome tag that holds its parent, on load and `/reload` |
| Lists of biome ids (surface rules, loot conditions, feature and structure lists) | `HolderSetDirectMixin`: a list that holds the parent holds the variant |
| Code that checks a biome key (e.g. Ambient Creatures) | `HolderReferenceMixin`: `variant.is(parentKey)` is true; `parent.is(variant)` stays false |
| Spawns and carvers, including ones mods add | `Variants.bind` copies the parent's final settings at server start |
| Features | Parent's final list minus `remove`, plus `add` (copied placed features, appended, so order stays acyclic) |
| Temperature, downfall, precipitation | Never changed, so seasons and snow behave the same |

Definitions: `variants/biome_variants.py` (variants) and `variants/regions.py` (regions as RESOLVE
Ecoregions 2017 groups). The script writes the biome files, copied placed features, names and
`elysium_atlas/variants.json` into `src/main/resources`; `--check` reports stale output. The atlas
stores regions separately (`bake/bake_regions.py`, 32-block cells, warped borders), so the base biome map
does not change and regions can change without rebaking terrain. `/atlas variants` audits each variant
against its parent (tags, spawns, features). `/atlas here` and F3 show the region.

## Distant Horizons SeedGen

SeedGen (0.9.1) draws LODs from the world's density functions and biome source, so atlas terrain and
biomes appear at a distance. It fills water only up to sea level. An optional mixin
(`mixin/compat/SeedGenWaterMixin`, own mixin config, `required: false`) raises each LOD column's water
level to the atlas fluid level, so lakes, rivers and streams above sea level show too. It does nothing
without SeedGen, and nothing on a client joining a server, where the atlas is not loaded. Checked: the
hook weaves into `SeedWorldGenerator.buildColumn` (mixin export). Not yet checked in a rendered LOD.

## Not done

- Streams follow a 5 km drainage grid, so there are none in catchments under 150 km2 and their courses are
  only as exact as that grid.
- Channels narrower than 8 blocks are not possible: terrain density is interpolated over 4-block cells.
- Water levels are whole blocks, so a river steps down 1 block at a time. Generated water is still; a
  step can spill a little when a player disturbs it.
- Natural Earth lines are generalised (about 1 km), so a river can run beside its real valley floor.
- Detail outside the Alps box (a global L1 is about 1-2 GB).
- Sea-level rise is a 12 m placeholder.
- Not tested with RoadWeaver.
