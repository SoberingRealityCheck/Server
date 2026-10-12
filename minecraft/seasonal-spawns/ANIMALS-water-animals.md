## Water animals

Rules are in `server-overrides/config/elysium-seasonal-spawns/water-animals.rules`.

Two kinds of rule live here. Some follow the seasons. Some fix a habitat, where the game or a mod puts an animal in water it does not live in. Habitat rows are flat across the year on purpose.

Notes that apply to all of them:

- Warm oceans are **not** tropical in this pack. Only `terralith:deep_warm_ocean` is. So ocean rows have four numbers. That one biome gets 1.00.
- Spawn biomes came from the jars (SeaLife tags, Naturalist `has_*` and `blacklist_*` tags, the 26.2 server jar). Critters and Companions keeps its biomes in code. For the sea bunny and dumbo octopus (5 ocean biomes) and for the otter and koi (river) I read the order of the class constants. That is a hack reading. I did not run it.
- Group names: `cold-ocean` is cold and frozen. `warm-ocean` is warm and lukewarm, shallow and deep. `deep-ocean` is every deep ocean. `ocean` is all of them. See `biomes.rules`.

### Tuna (`sealife:tuna`)

- **In the pack.** Ocean, deep ocean, warm, lukewarm, deep lukewarm.
- **In the real world.** Atlantic bluefin spawn in warm water. Eastern fish reach the Mediterranean in May and June and are back on the North Atlantic feeding grounds in July and August. Western fish go to the Gulf of Mexico in April to June. Spawning waits until the water is over 20 C.
- **Rule.** Warm ocean: `1.00` all year. Ocean and the rest: `0.70 1.00 0.90 0.40`.
- **Confidence.** sourced (direction). The sizes are mine. The paper is about bluefin only. Warm-water tunas stay all year, so warm oceans get no cut.
- **Sources.** <https://pmc.ncbi.nlm.nih.gov/articles/PMC5784186>
- **Not backed.** The winter 0.40.

### Sardine (`sealife:sardine`)

- **In the pack.** Cold ocean, deep cold ocean, ocean, deep ocean.
- **In the real world.** The South African sardine run is a winter event. Sardines move along the coast from May to July when the water drops below about 21 C. They like about 14 to 20 C. The page says the cause is poorly understood.
- **Rule.** `0.90 0.60 0.90 1.00`.
- **Confidence.** reasoned. One regional event is a thin base. The pack's sardines live only in cold and temperate water, so a cool-season peak is a fair reading.
- **Sources.** <https://en.wikipedia.org/wiki/Sardine_run>
- **Not backed.** Every number.

### Anchovy (`sealife:anchovy`)

- **In the pack.** Cold, deep cold, frozen, deep frozen, ocean, deep ocean.
- **In the real world.** FishBase: the European anchovy "tends to move further north and into surface waters in summer, retreating and descending in winter". Spawns April to November, peak in the warmest months.
- **Rule.** Deep ocean `0.70 1.00 0.90 0.60`. Cold ocean `0.60 1.00 0.90 0.30`. Everywhere else `0.70 1.00 0.90 0.50`.
- **Confidence.** sourced (direction and timing). The sizes are mine.
- **Sources.** <https://fishbase.se/summary/66>
- **Not backed.** The numbers. Overwintering grounds were not found.

### Freshwater angelfish (`sealife:angelfish`)

- **In the pack.** Jungle (all kinds) and swamp (including mangrove).
- **In the real world.** Amazon fish. FishBase says adults live in swamps and flooded ground with dense plants, and that the fish is non-migratory. A biotope page says the flood opens up far more living space for fish. It did not name angelfish.
- **Rule.** Jungle and mangrove swamp: `0.70 1.00` (dry, wet). Plain swamp: `0.60 1.00 0.70 0.20`.
- **Confidence.** reasoned. The cold-swamp cut is plain biology: a tropical fish in a real winter. The dry and wet numbers are a guess.
- **Sources.** <https://www.fishbase.se/summary/4717>
- **Not backed.** No study of wild angelfish through the year turned up.

### Silver-stripe blaasop (`sealife:silver_stripe_blaasop`)

- **In the pack.** Cold ocean, deep cold, frozen, deep frozen. Only cold water.
- **In the real world.** A tropical pufferfish (also called the silver-cheeked toadfish) of the Indo-Pacific, 40 N to 40 S, reefs and sand at 18 to 100 m. It entered the Mediterranean through the Suez Canal.
- **Rule.** `0.10 0.60 0.40 0.00`. This is a HACK. The real fix is to move the fish to the warm-ocean tag in the mod. A rule can only lower a rate. So it leaves a trickle when cold seas are warmest.
- **Confidence.** sourced (tropical range). The numbers are a guess.
- **Sources.** <https://fishbase.se/summary/Lagocephalus-sceleratus>
- **Not backed.** FishBase gave no temperature limits.

### Stingray and ray (`sealife:stingray`, `naturalist:ray`)

- **In the pack.** Stingray: ocean, deep ocean, warm, lukewarm, deep lukewarm. Ray: every ocean except frozen.
- **In the real world.** Cownose rays enter Chesapeake Bay every summer to mate and pup. They leave in autumn and winter off Cape Canaveral, Florida.
- **Rule.** Cold ocean `0.50 1.00 0.70 0.20`. Warm ocean `1.00` all year. Ocean `0.70 1.00 0.90 0.40`.
- **Confidence.** reasoned. One species in one place.
- **Sources.** <https://www.sciencedaily.com/releases/2018/08/180823122323.htm>
- **Not backed.** The numbers. Tropical stingrays are not known to move, so warm water gets none.

### Jellyfish (`naturalist:jellyfish`)

- **In the pack.** Every ocean except frozen.
- **In the real world.** Mediterranean monitoring from 2013 to 2020 saw blooms nearly all year, with peaks from March to July and often in autumn. Warm water helps blooms.
- **Rule.** Warm ocean `1.00 1.00 1.00 0.90`. Cold ocean `0.80 1.00 0.90 0.30`. Everywhere else `0.90 1.00 1.00 0.60`.
- **Confidence.** reasoned. One sea, no numbers.
- **Sources.** <https://en.wikipedia.org/wiki/Jellyfish>
- **Not backed.** All the numbers. A Canary Islands sting record and a Chinese strobilation study showed up in search. I did not read them.

### Whale (`naturalist:whale`)

- **In the pack.** Every ocean except frozen and deep frozen.
- **In the real world.** Humpbacks feed in cold, high-latitude water in summer. In winter they go to tropical water to mate and calve. Some trips are 5,000 miles one way.
- **Rule.** Cold ocean `0.80 1.00 0.90 0.35`. Warm ocean `0.90 0.50 0.70 1.00`. Everywhere else `0.90 0.80 0.90 0.80`.
- **Confidence.** sourced. The mod has one whale entity. This reads the humpback and ignores whales that stay put, such as the sperm whale. The sizes are mine.
- **Sources.** <https://www.fisheries.noaa.gov/species/humpback-whale>, <https://en.wikipedia.org/wiki/Humpback_whale>
- **Not backed.** The numbers. Some humpbacks skip migration in some years. That is not modelled.

### Great white shark (`naturalist:great_white_shark`)

- **In the pack.** Warm, lukewarm, deep lukewarm.
- **In the real world.** Great whites visit set coasts at set times. At Gansbaai sightings peak in autumn and winter (March to August). Other studies came up in search but I read only this one. They say fall and winter in central California, late summer and fall at Cape Cod, spring and early summer in Western Australia.
- **Rule.** `0.80 0.50 1.00 1.00`.
- **Confidence.** reasoned. The sites disagree, and fall and winter is the common thread. Real whites are temperate sharks, so the pack's warm-water spawn is cut in summer, the hottest part.
- **Sources.** <https://pmc.ncbi.nlm.nih.gov/articles/PMC3741326>
- **Not backed.** The numbers.

### Dolphin (`minecraft:dolphin`)

- **In the pack.** Ocean, deep ocean, warm, lukewarm, deep lukewarm.
- **In the real world.** Aerial surveys of US mid-Atlantic bottlenose dolphins found the most in winter. Few were seen in late spring, summer and early autumn. The authors link this to water temperature and prey. In warm southern waters dolphins keep to a local range.
- **Rule.** Cold ocean `0.60 1.00 0.70 0.10`. Warm ocean `0.90 0.90 1.00 1.00`. Ocean `0.80 1.00 0.90 0.50`.
- **Confidence.** sourced (that movement follows season and warmth). Sources conflict on which coast is fullest in which season, so all sizes are guesses.
- **Sources.** <https://journal.iwc.int/index.php/jcrm/article/view/748>
- **Not backed.** The survey is one coast, one species. A SeaWorld page and Gulf of Mexico stock papers came up in search. I did not read them.

### Squid (`minecraft:squid`)

- **In the pack.** Ocean (all kinds), river, frozen river.
- **In the real world.** Squid are sea animals. The page describes open ocean, shelf and deep water and never fresh water.
- **Rule.** River `0.0` all year. This is a habitat fix. It started at `0.35`. The server owner does not want squid in rivers, so it is zero now.
- **Confidence.** reasoned.
- **Sources.** <https://en.wikipedia.org/wiki/Squid>
- **Not backed.** A season rule. California market squid spawn inshore from spring to autumn (search result, unread). Atlantic longfin squid spawn inshore in late spring and summer (search result, unread). Species differ too much to pick one.

### Cod (`minecraft:cod`)

- **In the pack.** Cold, deep cold, ocean, deep ocean, lukewarm, deep lukewarm.
- **In the real world.** Cod live in cold and temperate seas and spawn at 5 to 7 C. The classic model has them offshore in winter and inshore in summer. A newer tagging study found some adults wintering inshore. The Animal Diversity page says spawning peaks in winter and spring.
- **Rule.** Warm ocean `0.30 0.10 0.30 0.60`. Deep ocean `0.85 0.80 0.90 1.00`. Everywhere else `1.00 1.00 0.95 0.75`.
- **Confidence.** reasoned. The warm-water cut is a habitat fix. The season part is small because the sources disagree.
- **Sources.** <https://animaldiversity.org/accounts/Gadus_morhua>
- **Not backed.** The numbers. The 1993 Newfoundland migration thesis and DFO documents showed up in search. I did not read them.

### Nautilus (`minecraft:nautilus`)

- **In the pack.** Cold, deep cold, frozen, deep frozen, ocean, deep ocean, warm, lukewarm, deep lukewarm.
- **In the real world.** Indo-Pacific only, 30 N to 30 S, on deep reef slopes. Mostly below 100 m. They avoid water over 25 C.
- **Rule.** Cold ocean `0.15` all year. Deep ocean `1.00`. Everywhere else `0.50`. A habitat fix. No season is known.
- **Confidence.** sourced (range and depth). The sizes are mine.
- **Sources.** <https://en.wikipedia.org/wiki/Nautilus>
- **Not backed.** The numbers.

### Deep-sea animals in shallow water (`naturalist:anglerfish`, `naturalist:blobfish`, `naturalist:giant_isopod`, `crittersandcompanions:dumbo_octopus`)

- **In the pack.** Naturalist: every ocean except frozen. Dumbo octopus: five ocean biomes (hack reading, see top).
- **In the real world.** Giant isopods live mostly from 170 to 2,140 m. Dumbo octopuses are thought to live at 1,000 to 7,000 m. Deep-sea anglerfish live in the dark water of the deep. Blobfish: the Wikipedia page I fetched was only a disambiguation page, so the 800 m figure comes from a search result and is weak.
- **Rule.** Deep ocean `1.00`. Every other ocean `0.20`. A habitat fix. No season. Giant isopods may breed more in autumn and winter, but that is one line on one page.
- **Confidence.** reasoned.
- **Sources.** <https://en.wikipedia.org/wiki/Giant_isopod>, <https://en.wikipedia.org/wiki/Dumbo_octopus>, <https://en.wikipedia.org/wiki/Anglerfish>
- **Not backed.** The 0.20 and blobfish depth. Whether Naturalist's own spawn code already limits depth. I did not read it.

### Koi (`crittersandcompanions:koi_fish`)

- **In the pack.** River (hack reading).
- **In the real world.** Pond pages put the koi feeding stop at about 10 C and dormancy at about 4 to 10 C. They sit low and still.
- **Rule.** `0.90 1.00 0.90 0.40`.
- **Confidence.** reasoned. No source. The pages were pond shops from search results, and I read none.
- **Not backed.** Everything. Koi are a farmed fish. A wild river koi is a game idea.

## Left alone

| Animal | Why |
|---|---|
| `minecraft:pufferfish` | Warm and lukewarm oceans only. Reef animal. Nothing seasonal found. |
| `minecraft:tropical_fish` | Warm oceans, mangrove swamp, lush caves. Tropical reef fish recruit year-round at low latitudes. A Papua New Guinea study found damselfish recruiting less in the wet season, but that is one site and young fish. |
| `sealife:blue_tang`, `sealife:butterflyfish`, `sealife:damselfish`, `sealife:whitemargin_stargazer` | Warm reef water only. Same reasoning as tropical fish. |
| `sealife:anglerfish` | Deep ocean only already. No season in the deep. |
| `sealife:manta_ray` | Signals exist but they point opposite ways by site. Lady Elliot Island peaks in autumn and winter. Bahia de Banderas peaks around April (search result, unread). Baa Atoll follows the monsoon (search result, unread). |
| `naturalist:clam`, `naturalist:starfish` | Shallow-bottom animals with no useful seasonal signal. I did not search either. |
| `crittersandcompanions:sea_bunny` | Sea slug records (Jorunna parva) span 11 to 28 C. These are diver reports, not a survey. No season found. |
| `crittersandcompanions:otter` | River otters are active year-round (NPS Yellowstone). A Minnesota study (search result, unread) found less activity in winter, but that is movement, not presence. |
| `minecraft:glow_squid` | Underground water in 147 biomes. A cave has no seasons. |
| `minecraft:axolotl` | Lush caves only. A cave has no seasons. |

## What I could not find

- A source for koi in the wild or a study of wild koi through the year.
- A study of wild freshwater angelfish through the year.
- Temperature limits for the silver-stripe blaasop.
- The real spawn tags of Critters and Companions. The biomes are in code, not data. I read constant order only.
- Whether Naturalist's own spawn code limits the depth of its deep-sea animals.
- A depth source for blobfish that I read in full.
- Season data for squid that one rule can use.
- Season data for starfish and clam. I did not search.
- Pages I could only read as search summaries: great white studies other than Gansbaai, the Minnesota otter study, the Mediterranean and Canary Islands jellyfish papers, and the manta sites other than Lady Elliot.
- The IWC humpback page blocked me (403). NOAA and Wikipedia back the whale rule instead.
