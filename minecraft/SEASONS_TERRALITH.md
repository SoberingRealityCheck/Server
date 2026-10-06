# Serene Seasons and Terralith

What we decided, what we left alone, and what we don't know yet.

The tag files live in
`server-overrides/world/datapacks/z-seasons-terralith/`. They are
generated from `tools/seasons_terralith.py`. That file holds the reason
for every biome, next to the biome. Edit it, then run it. Don't edit the
JSON by hand.

```
python3 tools/seasons_terralith.py            # write the tag files
python3 tools/seasons_terralith.py --audit    # list every biome and what it gets
```

Run the audit after any Terralith update. New biomes get full seasons
until someone puts them in a list.

## How Serene Seasons treats a biome

Read from the mod's bytecode, not from its docs.

| Tag | What the biome gets |
|---|---|
| immune (`blacklisted_biomes`) | Raw temperature. No seasonal snow or ice. No foliage color change. Crops fertile all year. |
| `tropical_biomes` | Fixed warm temperature, so never snow. Wet and dry seasons. Crops follow summer rules all year. |
| `lesser_color_change_biomes` | A milder foliage color change. Nothing else. |
| no tag | Full seasons. |

With no tag, winter subtracts 0.8 from the temperature. That only
happens for biomes with a base temperature of 0.8 or lower. No other
season changes the temperature. So a cold biome stays cold all year, and
a hot biome (above 0.8) never gets winter snow, tag or not.

**Temperature is all or nothing per biome.** There is no "smaller
winter". You can make a biome immune or leave it alone. The color dial is
the only partial one, and it is weak.

## Where the 95 Terralith biomes ended up

19 immune. 26 tropical. 16 with milder colors. 51 on full seasons.
(A biome can be in more than one list.)

- **Immune:** rivers, beaches and caves (vanilla does the same), the
  warm deep ocean, the four skylands, and the winter Alpha islands.
- **Tropical:** every desert, mesa, savanna, dry scrub and jungle, plus
  mirage isles and the warm deep ocean.
- **Milder colors:** swamps and the stylized palettes (sakura, lavender,
  moonlight, amethyst, scarlet, emerald, volcanic, alpha islands).
- **Full seasons:** everything else. All the cold, temperate and
  mountain biomes.

## Mistakes the second pass caught

- `#c:is_badlands` contains `terralith:snowy_badlands`, which has a base
  temperature of 0. Marked tropical, it would never snow. So the
  tropical list uses explicit ids and not the shared tags.
- `#c:is_mushroom` contains `terralith:mirage_isles`. That is right, on
  purpose. Vanilla mushroom fields is tropical and this is its twin.
- Serene Seasons also needs GlitchCore, and Modrinth's metadata didn't
  list it. The first boot failed. The dependency check had named it, but
  I had cut that line off the output.

## Judgement calls

These are my reading of what the biome is for. Change them if you
disagree. Each is one line in the script.

- **Skylands are immune.** Each island is one fixed season by design.
  A side effect: crops are fertile all year there, so they work as
  permanent farmland. `skylands_winter` has a raw temperature of 0.2, above
  the 0.15 snow line, so it rains there. That matches plain Terralith.
- **`alpha_islands_winter` is immune and `alpha_islands` is not.** The
  winter one is named for a season and has a fixed look. Its twin is just
  an island. The pair behaves differently on purpose.
- **`painted_mountains` is tropical.** It is a warm, mesa-like mountain
  at temperature 1.0. It would never snow either way. Tropical gives it
  the wet and dry seasons that the other mesas get.
- **`hot_shrubland` is tropical.** Its temperature is exactly 0.8, so it
  would snow in winter. Snow on a hot shrubland looked wrong.
- **`mirage_isles` is both tropical and milder colors.** It copies
  mushroom fields, and it has a stylized palette.

## Left out on purpose

- **Custom-colored biomes that aren't fantasy.** About 25 more biomes
  set their own grass or foliage color: snowy maple forest (orange
  maples), snowy cherry grove, snowy shield, the siberian pair, cloud
  forest, haze mountain, yosemite lowlands, lush valley, the shield
  biomes, temperate and forested highlands, and the shrublands. They are
  on full seasons. Serene Seasons starts from the biome's own color and
  shifts it, so the palette survives as a base. Whether the shift looks
  bad is something I can't judge without seeing it. Snowy maple forest
  is the first one I'd check.
- **Cold biomes.** `frozen_cliffs`, `glacial_chasm`, `snowy_badlands`,
  the wintry pair, the alpine ones and the snowy ones stay on full
  seasons. They are cold all year already, so winter only makes it a bit
  colder.
- **Volcanic biomes.** Left off the immune and tropical lists. Their
  temperature is 1.0, so they never get winter snow anyway. They only get
  milder colors.
- **`infertile_biomes`.** The tag exists and ships empty. I did not put
  desert sand or volcanic ash in it. That would change farming, and
  nobody asked for it.
- **`rocky_mountains` and `siberian_taiga`.** Terralith gives them no
  precipitation. Winter changes nothing there, because nothing falls.
  I left them alone.
- **Vanilla biomes.** Untouched. Serene Seasons already handles them.
- **Shared `c:` tags for tropical.** Avoided, see the snowy badlands
  mistake. I kept them for rivers, beaches and caves, where I read every
  member and they were all right.
- **Season length and other settings.** Defaults. How long a season
  lasts is a gameplay choice, and nobody has made it yet.
- **Other dimensions.** Not checked. I didn't look at which dimensions
  Serene Seasons is on by default.

## What is not tested

- **How it looks.** Foliage colors, snow cover and crop rules are read
  from code. Nobody has watched a winter in this pack.
- **Client side.** Foliage colors are computed on the client. The tags
  should sync to it, but I have only checked the server.
- **The mod itself.** The 26.2 build is a beta that was built for 26.1.2.
  GlitchCore is a beta too.
- **Terralith updates.** The explicit lists assume today's biome names.

## How the tag files were checked

On the local server, with the datapack loaded: every Terralith biome
against all three tags, 285 checks, 0 mismatches against the lists in
`tools/seasons_terralith.py`. Seven vanilla spot checks passed too, so the
datapack adds to Serene Seasons' own lists and does not replace them.

Rerun it with `python3 minecraft/tools/verify_seasons_live.py` from the
repo root, with the server running. It overwrites one biome cell at
0,80,0, so use a test world.

This proves the tags hold what the script says. It does not prove how the
seasons look.
