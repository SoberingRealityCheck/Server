# Mod list -- server-side

Installed automatically via `install.sh` (Pterodactyl egg install
script). See `../client/MODLIST.md` for mods players add to their own
client. Pinned versions, URLs, and checksums: `mods.yaml`.

## Terrain / worldgen

| Name | Purpose |
|---|---|
| Terralith | ~95 realistic biomes, vanilla blocks/mobs only |
| Tectonic | Continent-scale landform/mountain shaping |
| Distant Horizons | Long-distance LOD terrain (also client-side) |

## Performance

| Name | Purpose |
|---|---|
| Lithium | Tick/simulation optimization |
| Krypton | Networking-stack optimization |
| FerriteCore | Reduced memory footprint for loaded chunks/block states |

ModernFix has no Fabric 26.2 build yet.

## Recipe / info

| Name | Purpose |
|---|---|
| JEI | Recipe/item viewer (also client-side; server sync required since 1.21.2) |
| Jade | Hover-to-inspect HUD (also client-side; server adds item storage/brewing data) |

## Inventory / utility

| Name | Purpose |
|---|---|
| Easy Shulker Boxes | View/edit shulker box contents without placing them |
| Bundle Upgrade | Larger/tiered bundles |

Both require Forge Config API Port and Puzzles Lib.

## Required libraries

Fabric API, Lithostitched, Forge Config API Port, Puzzles Lib.

## Compatibility with Matcha Flavoured

Expected to coexist cleanly: Matcha Flavoured is a gameplay-mechanics
datapack (food, progression, loot, trades) and doesn't touch world
generation. Terralith adds no new blocks, mobs, or items, only vanilla
content in new biomes, limiting overlap to Terralith's structures (which
have their own loot tables). Not verified by running the combination.

## Requirements

- Fabric loader egg targeting Minecraft 26.2
- More RAM than a vanilla-only server -- not yet benchmarked; see
  `../../README.md` and `../../../aws/NOTES.md`
