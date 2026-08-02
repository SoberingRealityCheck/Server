# Mod list -- client-side

Recommended for players' own Fabric client. Not installed by any
automation -- Pterodactyl only manages the server container. See
`../server/MODLIST.md` for what's installed there. Pinned versions,
URLs, and checksums: `mods.yaml`.

## Rendering / performance

| Name | Purpose |
|---|---|
| Sodium | Rendering engine replacement |
| Better Clouds | Replaces vanilla cloud rendering (requires YACL) |

## Terrain / info (also server-side)

| Name | Purpose |
|---|---|
| Distant Horizons | Renders the LOD terrain the server generates |
| JEI | Recipe/item viewer |
| Jade | Hover-to-inspect HUD |

## QOL

| Name | Purpose |
|---|---|
| Xaero's Minimap | Minimap + waypoints |
| Better Advancements | Full-screen advancement UI |

## Decoration

| Name | Purpose |
|---|---|
| Cosy Critters & Creepy Crawlies | Ambient critters -- birds, moths, spiders |

## Sound

| Name | Purpose |
|---|---|
| AmbientSounds | Ambient biome/weather/cave sound layer (requires CreativeCore) |
| Sound Physics Remastered | Sound occlusion/reverb through blocks |

## Required libraries

CreativeCore, YACL.

## Known gap

Particle Rain was requested but has no Fabric 26.2 build yet; the mod's
own latest release still targets 26.1.x.

## Requirements

- Fabric Loader targeting Minecraft 26.2
- Fabric API
