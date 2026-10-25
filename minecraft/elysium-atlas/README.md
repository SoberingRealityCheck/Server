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
  - `tectonic:terrain_spline/roughness` -> scaled by atlas relief (0.75 x relief in km, clamped to
    0.1..1). It is vanilla's 3D base noise; at full strength it stood 40-block knobs on the flat
    Edwards Plateau (Hill Country, seed -1117184792348421700, near -65580 -25385).
  - `roughness` and `tectonic:terrain_spline/offset/depth_additive` -> also scaled by `calm`, which is
    0 on water and rises to 1 away from it, so Tectonic's own noise cannot fill a channel.
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

**Biome placement (slice-8, prior since slice-9).** Every land cell takes the biome whose niche fits it best (`bake/placement.py`);
no table maps a place or a climate class to a biome. Niches come from the biomes' own data in the pack's jars
(`bake/biome_traits.py` -> `bake/data/biome_traits.json`, 158 surface biomes from vanilla, Terralith, Biomes O'
Plenty, Wilder Wild and Terrestria): the c: climate tags (hot, temperate, cold, snowy) set a temperature band and
the JSON temperature orders biomes inside it; the c: wet/dry tags and downfall set moisture (sand and terracotta
biomes count as arid); trees per chunk come from the vegetal placed features; the landform from the mountain,
plateau and hill tags and a few name tokens (cliffs, canyon, spires). The cell side is the warm-branch climate
re-lapsed to the cell's elevation, the woody cover of its g3 formation, the atlas relief and the water mask.
Since slice-9 the cover also takes a potential-vegetation prior: 75% of it comes from the cell's present-day
RESOLVE biome type (`PNV_COVER`), because climate alone misses the fire, soils and seasonality that keep prairies,
pampas and montane grasslands open. This makes `placement_check.py` partly circular; read its numbers as a
consistency check, not an independent test.
The score adds squared distances in temperature, moisture and cover, plus terms for landform, year-round snow,
conifers in warm places, jungle where it frosts, and per-biome value noise so near-ties form patches. Terrain-feature
biomes (glacial chasm, cliffs) need 900 m of relief; wetland biomes go only on the wetland mask (flat low land
on a large river's floodplain or by a lake, patchy, or within 4 m of the sea). Biomes themed on one small real
place (sakura, redwoods, lavender, Bryce, Yosemite, bamboo) are left to the ecoregion profiles, which can use them
through `rebase`. `bake/placement_check.py` compares the result with RESOLVE biome types (rule: under 40% of
each type in the wrong vegetation family; flooded grasslands are exempt, the water mask has no seasonal floods).
`bake/season_tags.py` writes the Serene Seasons tags for the flora mods' biomes
(`server-overrides/world/datapacks/z-seasons-floramods`).

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

A variant normally inherits from the atlas biome it replaces. A profile's `rebase` makes it inherit from
another biome instead (Blackland Prairie: atlas forest becomes a child of plains). It keeps the
temperature, downfall and precipitation of the atlas biome.

**Regions.** The atlas region layer (`bake/bake_regions.py`, `regions.bin.gz` format 2, u16, 32-block cells,
warped borders) stores one unit per RESOLVE Ecoregions 2017 ecoregion, `eco:<ECO_ID>`, over the whole globe:
838 units, 0.5 MB. Groups in `variants/regions.py` name sets of ecoregions and can split one along a
meridian. The base biome map is unchanged, so regions change without rebaking terrain.

**Plant and ecoregion database.** `variants/db/` (schema in `variants/db/README.md`) is plain YAML: one entry
per real species (`plants/*.yaml`: Latin name, form, summer leaf or turf colour with the description it is based
on, and how it is built in game) and one per ecoregion (`ecoregions/*.yaml`: weighted species lists for trees,
shrubs, ground, flowers and cacti, tree cover). Ecoregions set no colours: grass, foliage and per-leaf-block
colours are weighted means over their species. Species are built from vanilla blocks (live oak, mesquite,
loblolly pine, bluebonnet as cornflower), vanilla features, or the pack's flora mods (Wilder Wild juniper, swamp
cypress, windmill palm, prickly pear; Terrestria agave, paintbrush, yucca palm; BOP fir, pine, goldenrod, sea
oats). The mod therefore depends on Biomes O' Plenty, Wilder Wild and Terrestria. Their own biomes and
vanilla-biome edits are switched off in `../overrides/config`, so the atlas still picks every biome.

Every atlas biome covering at least 0.3% of a listed ecoregion gets a variant. Its own plants are removed
and the ecoregion's are added. Tree count is the ecoregion's cover times a factor taken from the atlas biome's
own tree count, so forest cells stay denser than plains cells. Ecoregions without an entry keep the atlas
biome. The database covers 25 ecoregions in and around Texas and 37 in Europe (from the spawn outwards), with
147 plants. The built mod carries it as `elysium_atlas/ecoregions.json`; `/atlas here` prints the ecoregion,
its colours and its species.

Niches and ground. Species can be limited by elevation, water and slope (`niche` on a plant, `niches` per
ecoregion for elevation belts): trees are picked per spot by `elysium_atlas:niche_selector`, so the Southern
Rockies run ponderosa, Douglas fir and aspen, then spruce-fir, and stop at about 3,600 m; bald cypress, cottonwood,
willow and alder keep to river banks; junipers, pinyon and creosote avoid them. Each ecoregion also has a
`ground_surface` (rock on steep ground and outcrops, soil patches, subsoil), written as one Lithostitched surface
rule: Edwards limestone in the Hill Country, red beds on the Rolling Plains, chalk under the English downs, karst in
the Dinarides, podzol in the taiga, basalt and moss in Iceland.

`variants/biome_variants.py SERVER_JAR TERRALITH_JAR` writes the biome files, features, names and
`elysium_atlas/variants.json` into `src/main/resources`; `--check` reports stale output. `/atlas variants`
audits every variant against its parent (tags, spawns, features) and lists only problems. `/atlas here` and
F3 show the region.

Leaf colours (client): every green leaf follows the variant's foliage colour, including spruce, birch and the
flora mods' leaves. `variants/leaf_tints.py` makes pre-coloured mod textures greyscale (built-in pack
`regional_leaves`) and gives each leaf block a default offset from the foliage colour. In an ecoregion each leaf
block takes the mean colour of the species that grow it there, stored relative to the foliage
(`leaf_palettes.json`) so seasons still shift it. `docs/ecoregion_colours.png` in the project folder shows every
ecoregion.

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
