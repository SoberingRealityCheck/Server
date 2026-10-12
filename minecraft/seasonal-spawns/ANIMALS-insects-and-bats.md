## Insects and bats (`insects-and-bats.rules`)

These are the most seasonal animals in the pack. Adult insects live a few
weeks or one warm season. So the cold groups (snowy, taiga, mountain) get
zero in winter for most of them.

Two limits apply to every animal below.

- **Biome means the cave biome at the spawn spot.** Lush caves and
  dripstone caves are in the `cave` group (`biomes.rules`). A cave is
  sheltered, so the six bugs that spawn in lush caves have a milder `cave`
  row ahead of the cold rows (for example ladybug `0.8 1.0 0.9 0.6`). Those
  cave numbers are guesses. For bats the plain biome rows are the right
  behaviour, since a cave roost is where bats hibernate.
- **The sources back the timing and the direction.** None of them back the
  size. Every number is a call.

Rows are `spring summer autumn winter`, or `dry wet` in the tropical
biomes.

### Butterfly (`naturalist:butterfly`)

- **In the pack.** 29 biomes.
- **In the real world.** Cold country has almost no adult butterflies in
  winter. Most species winter as caterpillars, pupae or eggs. A few
  (tortoiseshells, anglewings, mourning cloaks) winter as adults, and
  monarchs fly south. In seasonal tropical forest the adults are far more
  abundant in the wet season, hide in the dry season, and come out in a
  mass three to four weeks after the first rains. In wet forests near the
  equator the season matters less.
- **Rule.** Snowy `0.00 0.50 0.00 0.00`. Taiga `0.10 0.90 0.30 0.00`.
  Mountain `0.10 1.00 0.40 0.00`. Elsewhere `0.50 1.00 0.70 0.05`.
  Jungle `0.70 1.00` (dry wet). Other tropical biomes `0.30 1.00`.
- **Confidence.** reasoned. The tropical half was read. The temperate
  winter half comes from search results and general knowledge.
- **Sources.** <https://learnbutterflies.com/abundance-diversity-seasonality/>,
  <https://www.birdsandblooms.com/blog/butterflies-in-winter/>.

### Firefly (`naturalist:firefly`)

- **In the pack.** 32 biomes.
- **In the real world.** Adults live one to four weeks. Most of the life
  is spent as larvae in the soil. Adults peak in May and June in
  Oklahoma. A late-September wave in Texas shows autumn adults happen but
  are rare. Some tropical fireflies fly through much of the year.
- **Rule.** Snowy `0.00 0.30 0.00 0.00`. Taiga and mountain
  `0.20 0.90 0.05 0.00`. Elsewhere `0.60 1.00 0.10 0.00`. Tropical
  biomes `0.60 1.00` (dry wet).
- **Confidence.** reasoned. The fact sheet would not open for me. I saw
  its summary in a search result. The tropical row is a guess that they
  follow the rains.
- **Sources.** <https://extension.okstate.edu/fact-sheets/print-publications/epp-entomology-and-plant-pathologhy/epp-7345-an-introduction-to-fireflies-a.pdf>.

### Bat (`minecraft:bat`)

- **In the pack.** 147 biomes. It spawns in caves everywhere.
- **In the real world.** Temperate bats hibernate in caves from autumn
  to spring. Little brown bats hibernate from October or November to
  March or April, in caves or mines that stay humid and above freezing.
  Some temperate species stay active all year in a warm climate. Tropical
  bats are mostly active all year. Not all of them, since a few warm-cave
  species hibernate in the sub-tropics.
- **Rule.** Snowy `0.30 0.90 0.40 0.00`. Taiga and mountain
  `0.50 1.00 0.70 0.00`. Elsewhere `0.80 1.00 0.90 0.15`. Tropical
  biomes have no row and stay at 1.00.
- **Confidence.** sourced for the hibernation. The sizes are my call. The
  Florida study was seen in a search result only.
- **Sources.** <https://www.ontario.ca/page/little-brown-bat>,
  <https://digitalcommons.usf.edu/kip_articles/469/>.

### Dragonfly (`crittersandcompanions:dragonfly`)

- **In the pack.** River only.
- **In the real world.** Adults fly from late spring to early autumn in
  temperate country. Larvae live in the water through winter. A Hong Kong
  study had flying seasons start in March or April and in eight species
  run to at least November.
- **Rule.** Snowy `0.00 0.40 0.00 0.00`. Taiga and mountain
  `0.20 1.00 0.40 0.00`. Elsewhere `0.40 1.00 0.60 0.05`. No tropical
  row, since river is never tropical.
- **Confidence.** reasoned. The read page is subtropical. The May to
  September window is from search results.
- **Sources.** <https://www.worlddragonfly.org/article/13887890-2011-570155>.

### Ladybug (`crittersandcompanions:ladybug`)

- **In the pack.** Forest and lush caves (21 biomes).
- **In the real world.** Adults winter in groups. A European study saw
  them arrive at winter sites from late October to early November and
  leave in mid to late April.
- **Rule.** Snowy `0.00 0.60 0.10 0.00`. Taiga and mountain
  `0.30 1.00 0.50 0.00`. Elsewhere `0.60 1.00 0.80 0.10`.
- **Confidence.** sourced for the overwintering and the spring exit. The
  study is one species in one region.
- **Sources.** <https://pmc.ncbi.nlm.nih.gov/articles/PMC5999267/>.

### Stag beetle (`crittersandcompanions:stag_beetle`)

- **In the pack.** Forest and lush caves.
- **In the real world.** Adults fly from the end of May to June or July
  in central Europe. In Britain they are found from late May to the end
  of August. Larvae live for years in rotting wood.
- **Rule.** Snowy `0.00 0.40 0.00 0.00`. Taiga and mountain
  `0.00 1.00 0.10 0.00`. Elsewhere `0.20 1.00 0.10 0.00`.
- **Confidence.** sourced. Both pages are about the European beetle.
- **Sources.** <https://www.donauauen.at/en/facts/nature-science/fauna-engl/stag-beetle>,
  <https://www.newforestnpa.gov.uk/discover/wildlife/beetles/stag-beetle>.

### Weevil (`crittersandcompanions:weevil`)

- **In the pack.** Forest and lush caves.
- **In the real world.** The game has one generic weevil. Many real ones
  winter as adults in leaf litter and come out when the soil warms. The
  cabbage seedpod weevil emerges near 15 C. Others winter as larvae and
  the adults show up in May or June.
- **Rule.** Snowy `0.00 0.50 0.10 0.00`. Taiga and mountain
  `0.40 1.00 0.50 0.00`. Elsewhere `0.70 1.00 0.80 0.10`.
- **Confidence.** reasoned. A few pest pages seen in search results.
- **Sources.** <https://prairiepest.ca/risk-maps/cabbage-seedpod-weevil/>.

### Roly poly (`crittersandcompanions:roly_poly`)

- **In the pack.** Forest and lush caves.
- **In the real world.** Woodlice follow moisture more than warmth. In
  winter most are scarce and sit deep in crevices. A hot summer and a hard
  cold snap both push them into shelter.
- **Rule.** Snowy `0.10 0.60 0.20 0.00`. Taiga and mountain
  `0.50 0.90 1.00 0.10`. Elsewhere `0.80 0.80 1.00 0.30`. Autumn is the
  peak because it is damp and cool.
- **Confidence.** reasoned. I could not open either page in full.
- **Sources.** <https://essexfieldclub.org.uk/archivetext.php/s/028/o/0141>,
  <https://scaber.org/porcellio/woodlice/habitat/>.

### Snail (`crittersandcompanions:snail`)

- **In the pack.** Forest and lush caves.
- **In the real world.** Land snails go dormant when too cold or too dry.
  A pest snail rests briefly each day in winter. In a dry summer the rest
  lasts days to weeks. A UK garden snail study says it wakes after the
  first heavy rain in May, not with the air temperature.
- **Rule.** Snowy `0.20 0.50 0.30 0.00`. Taiga and mountain
  `0.80 0.90 1.00 0.10`. Elsewhere `1.00 0.70 1.00 0.30`.
- **Confidence.** reasoned. I did not open the pages. Southern California
  is a reverse case (active in winter, dormant in summer). The rule does
  not model it.
- **Sources.** <https://www.publishing.csiro.au/zo/ZO9680857>,
  <https://meetingorganizer.copernicus.org/EGU22/EGU22-5061.html>.

### Stick bug (`crittersandcompanions:stick_bug`)

- **In the pack.** Forest and lush caves. Not jungle.
- **In the real world.** Stick insects are mostly tropical and
  subtropical. A Queensland trap study found one species breeding all
  year with no wet or dry cycle. I found nothing on stick insects in a
  cold forest.
- **Rule.** Snowy `0.00 0.20 0.00 0.00`. Taiga and mountain
  `0.10 0.60 0.40 0.00`. Elsewhere `0.40 1.00 0.80 0.00`.
- **Confidence.** guess. No source for this animal.
- **Sources.** None found.

### Leaf insect (`crittersandcompanions:leaf_insect`)

- **In the pack.** Jungle and forest (27 biomes).
- **In the real world.** Leaf insects live in the tropics of South and
  Southeast Asia. They do not live in snow. The only page, a Queensland
  study, is about a stick insect and found no wet or dry cycle.
- **Rule.** Snowy `0.00 0.10 0.00 0.00`. Taiga and mountain
  `0.00 0.40 0.10 0.00`. Elsewhere `0.30 1.00 0.70 0.00`. Jungle has no
  row and stays at 1.00.
- **Confidence.** reasoned. The cold forest spawn is a mod quirk. The rule
  makes it rare.
- **Sources.** <https://researchonline.jcu.edu.au/5919/>.

## Left alone (insects, bats and leftover land animals)

| Animal | Why |
|---|---|
| Ocelot (`minecraft:ocelot`) | A resident of tropical forest. Breeding may be year-round in the tropics, with peaks that vary by region. Home ranges are large. Flooding can shrink them in the wet season, and activity is mostly nocturnal. Nothing shows a real seasonal swing in how often you would meet one. |
| Cat (`minecraft:cat`) | Spawns in villages and swamp huts. A pet, not a wild animal. |
| Mauler (`friendsandfoes:mauler`) | A made-up burrowing desert predator in three skins (desert, savanna, badlands). It hunts chickens, rabbits, frogs, slimes and zombies. It is a neutral mob and not a monster, but it has no real animal behind it. A rule would be invented. |
| Mooshroom (`minecraft:mooshroom`) | Mushroom fields only. A fantasy cow on an island with no seasons. |
| Strider (`minecraft:strider`) | Nether. The Nether has no seasons. |
| Panda, red panda | A real panda eats spring bamboo shoots at low height from April to June and then moves up the mountain as shoots come later at altitude (Wolong study). A spring-shoot rule would be defensible for that. But the game puts both only in jungle, which is tropical and has dry and wet halves, not a spring. A dry and wet rule would be made up, so both stay at 1.00. |

## What I could not find

- Any page on stick insect or leaf insect numbers by season in a cold
  forest. The stick bug rule is a guess. The leaf insect rule leans on
  "they are tropical".
- A page for the tropical firefly, tropical bat or tropical stag beetle
  season in a wet and dry year. The tropical firefly row is a guess. Bats
  have no tropical row on purpose.
- A butterfly page I could open that says "no adults in cold winter" for
  temperate country. The claim is from search-result summaries and
  general knowledge.
- The Oklahoma firefly sheet, the Essex woodlice page, the CSIRO snail
  abstract and the ladybird extension bulletin would not open as text.
  I used what I read elsewhere or saw in search results.
- A source for the number size on any row.
