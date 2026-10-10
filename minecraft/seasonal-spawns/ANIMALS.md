# Animals: where they live, and why each rule says what it says

This is the long version of the `why` lines in
`server-overrides/config/elysium-seasonal-spawns/*.rules`. The rules are
what the game runs. This page is what to read when you want to change
one.

## How to read this page

Each animal has up to four parts.

- **In the pack.** The biomes where the game spawns it today. For
  Naturalist this comes from its `has_*` biome tags and its spawn table,
  read from the 2.0.6 jar. For vanilla it comes from the 26.2 biome
  files. Terralith and Biomes O' Plenty biomes are in some of those tags
  too. They are left out here to keep it short.
- **In the real world.** Where the animal lives and what its year looks
  like.
- **Rule.** What the `.rules` file does. A chance of 1.00 is the pack's
  normal. Rows are `spring summer autumn winter`, or `dry wet` in the
  tropical biomes (desert, savanna, jungle, badlands, and mangrove swamp).
- **Confidence.** `sourced`, `reasoned` or `guess`, the same label the
  rule carries.

### What the labels mean

| Label | Meaning |
|---|---|
| sourced | A page I read says the behaviour the rule models. The link is in the rule and below. |
| reasoned | Well-known biology, but I did not read a source for this exact rule. The link, if there is one, is background. Check it before you trust it. |
| guess | A game-balance call. The farm animals use it: the habitat direction is sourced but the size of each cut is a balance call. So do the crab and the mammoth. |

A source can back the behaviour and still not back the number. No page
says "0.5". The size of every drop is my call. The sources say which
direction and roughly when.

Source quality is mixed. Some are papers and agency pages. Some are
park blogs. I left out sites that looked like copied or machine-written
text. Where a search came back empty I say so below and made no
sourced rule.

## What the numbers can and cannot do

- A chance can lower a spawn rate. It cannot raise one above the
  pack's normal. 1.00 is the ceiling.
- It is applied after the game picks an animal. A "no" cancels that one
  pick. The game tries again a moment later.
- It changes the mix and how fast the world refills. It does **not**
  directly set how many animals are in the world. Respawning Animals
  tops the world up to its own cap (the `min_animals_near_player`
  gamerule, 15 by default) and retries every tick. So when a rule bars
  bears in winter, the slot is likely filled by an animal that is not
  barred, often a farm animal. The count stays near the cap and the mix
  moves. This is the expected result and has not been checked in a live
  world. See the README for a check to run.

## Bears

### Brown bear and black bear (`naturalist:bear`, `naturalist:black_bear`)

- **In the pack.** Bear: forest and taiga. Black bear: forest, taiga
  and grove.
- **In the real world.** Bears den for the winter. Near Ely, Minnesota
  they go in September or October and stay 6 to 7 months. In the eastern
  US, where food lasts longer, they go in late November or December and
  stay under 5 months. Before denning they feed constantly. Katmai
  brown bears follow the same pattern, with females and cubs moving up
  to dens first.
- **Rule.** Taiga and snowy: `0.40 1.00 0.80 0.00`. Mountain:
  `0.50 1.00 0.90 0.05`. Everywhere else: `0.80 1.00 1.00 0.15`.
- **Confidence.** sourced. NPS and bear.org say when and how long.
- **Sources.** <https://www.nps.gov/articles/bears-winter.htm>,
  <https://bear.org/5-stages-of-activity-and-hibernation/>.
- **Not backed.** The "20,000 calories a day" figure I saw came from a
  general-interest site. It is not used.

### Polar bear (`minecraft:polar_bear`)

- **In the pack.** Snowy plains, ice spikes, frozen ocean, deep frozen
  ocean.
- **In the real world.** They hunt seals from sea ice. Where the ice
  melts out each summer (western Hudson Bay) they come ashore and live
  on fat until it freezes again in late November or early December. In
  the southern Beaufort Sea most bears (73 to 85 percent) stay on the
  ice instead. Only pregnant females den through winter.
- **Rule.** `polar` group: `1.00 0.50 0.70 1.00`.
- **Confidence.** sourced for the summer drop. "Spring is the best
  hunting season" is background I know, not something I read for this
  rule.
- **Sources.** <https://polarbearagreement.org/polar-bear-biology/movement-and-migration>,
  <https://www.sciencedaily.com/releases/2013/03/130319202040.htm>.

### Panda (`minecraft:panda`). No rule.

Real pandas live in the temperate bamboo forests of mountainous
central China. They do not hibernate. A paper on GPS-collared pandas
found they move up and down the mountain to follow bamboo shoots. In
this game they spawn in jungle and bamboo jungle, which is nothing like
that. A seasonal rule would not fix the real mismatch. Left alone.

## Deer, boar, tiger

### Deer (`naturalist:deer`)

- **In the pack.** Forest and cherry grove.
- **In the real world.** White-tailed deer live in the woods all year.
  Movement peaks in the autumn rut. Does move around before birth in
  spring, then stay near the hidden fawns. Bucks have the biggest
  ranges in spring and fall. In deep snow, deer gather in sheltered
  conifer stands and move to lower ground. (That last part is general
  knowledge. None of the pages I read covered it. A search for winter
  "yarding" came back empty.)
- **Rule.** Mountain `0.90 1.00 1.00 0.40`. Snowy `0.90 1.00 1.00 0.50`.
  Taiga `0.90 1.00 1.00 0.60`. Elsewhere `0.90 1.00 1.00 0.80`.
- **Confidence.** reasoned. The rut and fawning are sourced. The winter
  numbers are not.
- **Sources.** <https://d11.seafwa.org/journal/2004/daily-movements-female-white-tailed-deer-relative-parturition-and-breeding>,
  <https://iowadnr.gov/About-DNR/DNR-News-Releases/ArticleID/2469/Fawning-season-is-here-deer-are-on-the-move>.

### Wild boar (`naturalist:boar`)

- **In the pack.** Savanna and forest.
- **In the real world.** Eurasian wild boar are in oak and mixed woods.
  Acorn crops steer where they feed. A Hungarian study found rooting was
  most intense in autumn. Savanna is a stretch. Wild boar do live in
  Africa (the bushpig and warthog are relatives) but this is
  Naturalist's pick.
- **Rule.** Snowy `1.00 1.00 1.00 0.40`. Taiga and mountain
  `... 0.60`. Elsewhere `... 0.85`.
- **Confidence.** reasoned. The autumn peak is sourced. The snow cut is
  not.
- **Sources.** <https://www.cnrs.fr/en/acorn-production-cycles-influence-wild-boar-populations>,
  <https://link.springer.com/article/10.1007/s10342-019-01248-5>.
- **Why no number goes up in autumn.** A chance cannot go above 1.00.

### Tiger (`naturalist:tiger`)

- **In the pack.** Jungle, mountain, badlands, swamp, mangrove swamp,
  dark forest, desert, cherry grove, snowy plains, snowy slopes, grove.
- **In the real world.** Tigers range from Siberian taiga through
  grassland and tropical forest to mangrove swamp. They avoid open
  ground and are almost never in farmland. Density is higher in
  river flood plains and tropical deciduous forest than in evergreen
  rainforest or the cold temperate range. I found no source that puts
  them in desert and I know of none.
- **Rule.** A **habitat fix**, not a seasonal rule. Desert is cut to
  `0.00 0.00`. Badlands keep a small `0.25 0.25` because dry deciduous
  forest and scrub in India are the edge of their range. Treeless snow
  (snowy plains, ice spikes, snowy slopes, peaks) is cut to `0.60` all
  year. Snowy taiga and grove are forest and are left alone, since
  Siberian tigers live there. No seasonal rows, since tigers do not
  hibernate.
- **Confidence.** sourced for the range.
- **Sources.** <https://www.catsg.org/living-species-tiger>,
  <https://ielc.libguides.com/sdzg/factsheets/tiger/distribution>.
- **Not backed.** A search for Bengal tiger monsoon movement found only
  flood-rescue news. No rule uses it.

### Wolf (`minecraft:wolf`)

- **In the pack.** Forest, taiga, old-growth taiga, grove, snowy taiga,
  sparse jungle, savanna plateau, wooded badlands.
- **In the real world.** Wolves live in cold and temperate country all
  year. They do not hibernate. Pups are born in April and May. GPS
  collars in a Saskatchewan park showed the breeding female going
  underground about the start of April and staying at the den. The den is
  abandoned at about two months, when the pups move to rendezvous sites.
- **Rule.** Everywhere `0.80 1.00 1.00 1.00`. A **habitat fix** too:
  sparse jungle (tropical) is cut to `0.30 0.30`, since wolves are animals
  of cold and temperate country. Savanna plateau and wooded badlands are
  dry open country where wolves do live.
- **Confidence.** sourced.
- **Sources.** <https://ielc.libguides.com/sdzg/factsheets/graywolf/reproduction-development>,
  <https://dec.ny.gov/nature/animals-fish-plants/gray-wolf>,
  <https://amp.cbc.ca/news/canada/saskatchewan/spring-sign-new-wolf-pups-prince-albert-national-park-1.5087945>.
- **Not backed.** I first left wolves out as "no seasonal change". The
  denning is a real, if small, spring effect.

### Fox (`minecraft:fox`)

- **In the pack.** Taiga types and grove.
- **In the real world.** Red foxes mate in winter. Kits are born from
  March in the south to May in the far north and stay in and around the
  den until weaned at eight to ten weeks. They stay active through winter.
- **Rule.** Everywhere `0.80 1.00 1.00 1.00`.
- **Confidence.** sourced.
- **Sources.** <https://icwdm.org/species/carnivores/foxes/fox-biology/>,
  <https://naturalresources.extension.wisc.edu/?p=1864>.

## Savanna, desert and jungle (wet and dry)

All rows here are `dry wet`. Seen from a patch of savanna away from
water, the dry half of the year is the thin half. Animals do not leave
the continent. They crowd the waterholes.

### Elephant (`naturalist:elephant`)

- **In the pack.** Savanna only.
- **In the real world.** African savanna and forest elephants. They
  have to drink every two to three days. A GPS study found dry-season
  trips are longer and aimed at water, and groups gather at the few
  waterholes that last.
- **Rule.** Savanna `0.80 1.00`.
- **Confidence.** sourced.
- **Source.** <https://www.frontiersin.org/journals/ecology-and-evolution/articles/10.3389/fevo.2018.00167/full>.
  I did not check which Kenyan or Zimbabwean park that paper covers. I
  cite the page for the dry-season water behaviour only.

### Zebra (`naturalist:zebra`)

- **In the pack.** Savanna only.
- **In the real world.** Plains zebra, mainly east and southern Africa.
  They travel with the wildebeest in the Serengeti and Mara. The loop
  follows rain. Herds move west and north as the dry season starts in
  May, use the Mara River area through the dry months, and return
  south with the rains in October or November.
- **Rule.** Savanna `0.50 1.00`. The biggest dry cut, because it is
  the clearest rain follower.
- **Confidence.** sourced.
- **Source.** <https://www.cms.int/fr/node/41605>. That is an official
  fact sheet, written about wildebeest. It names the wildebeest as the
  driver and the zebra as companions. The dates vary a bit between
  sources.

### Hippo (`naturalist:hippo`)

- **In the pack.** Savanna and jungle.
- **In the real world.** Sub-Saharan rivers and lakes. In a dry
  season a river shrinks to pools and the hippos crowd in. Large young
  males move up to 15 km upstream. In the wet season water spreads and
  they move down and out.
- **Rule.** Savanna `0.50 1.00`. Jungle has no rule.
- **Confidence.** sourced, with the warning that the study is one
  river (Great Ruaha, Tanzania) and followed males.
- **Source.** <https://news.ucsb.edu/2019/019687/hippos-hidden-world>.

### Ostrich (`naturalist:ostrich`)

- **In the pack.** Savanna.
- **In the real world.** Open country in Africa. They breed to hatch at
  the start of the rains. A 15-year Mara-Serengeti study found a major
  breeding peak in February and a small one in October. A forum post I
  found said otherwise. So the months are uncertain.
- **Rule.** Savanna `0.70 1.00`. Only the direction is sourced. The
  size is a guess.
- **Confidence.** sourced (direction only).
- **Source.** <https://agris.fao.org/search/zh/records/65df76284c5aef494fe2c9bb>.

### Vulture (`naturalist:vulture`)

- **In the pack.** Savanna, badlands, desert.
- **In the real world.** Old World vultures are in Africa, southern
  Europe and Asia. They soar on thermals, which come with heat. They
  eat carcasses.
- **Rule.** Savanna, desert, badlands all `1.00 0.70`.
- **Confidence.** reasoned. The page covers thermals. It does not cover
  dry-season die-offs, which is the real reason.
- **Source.** <https://hawkmountain.org/blog/in-the-field/thermal-scouting>.

### Komodo dragon (`naturalist:komodo_dragon`)

- **In the pack.** Badlands, savanna, desert, jungle, sparse jungle.
- **In the real world.** A few dry volcanic islands in eastern
  Indonesia. Komodo, Rinca, Flores, Gili Motang. Tropical savanna and
  open dry forest. Most rain falls from December to March. A 2022
  tracking study found more movement in the dry season, and dry
  season is mating and nesting time.
- **Rule.** A habitat fix and a seasonal rule. Desert `0.00 0.00`.
  Jungle `0.30 0.30`. Savanna and badlands `1.00 0.70`.
- **Confidence.** sourced.
- **Sources.** <https://journal.ugm.ac.id/jtbb/article/download/48280/27394>,
  <https://flore.unifi.it/retrieve/eab0d6df-ed42-4e0e-ab7d-b282c1c9bea7/Jessop_et_al_2022.pdf>,
  <https://zoobarcelona.cat/en/node/231>.

### Tortoise (`naturalist:tortoise`)

- **In the pack.** Swamp, mangrove swamp, desert, jungle.
- **In the real world.** Tortoise species cover very different places.
  Desert tortoises in the Mojave and Sonoran spend most of their life in
  burrows. A Nevada tortoise comes out each spring. Swamp-living
  species in warm places do not have a real cold season. Cold-winter
  species sleep through winter.
- **Rule.** Desert `0.60 1.00`. Swamp `0.70 1.00 0.80 0.10` (plain swamp
  only, since mangrove swamp is tropical here).
- **Confidence.** reasoned. The one page I found (a news story about
  one tortoise) gives no timings and does not back the numbers.

### Capybara (`ambient_creatures:capybara`)

- **In the pack.** Swamp, mangrove swamp, jungle, sparse jungle, bamboo
  jungle, river and savanna. Savanna has the heaviest weight (30).
- **In the real world.** Tropical South America, beside water. In dry
  seasons (the Llanos and Pantanal) they gather at what water is left.
- **Rule.** Savanna `0.50 1.00`.
- **Confidence.** reasoned. No source was read.
- **Note.** Naturalist's own capybara is switched off in
  `naturalist-server.properties`. This is Ambient Creatures'.

### Rhino (`naturalist:rhino`)

- **In the pack.** Savanna.
- **In the real world.** Black rhinos must drink every 24 to 48 hours and
  stay loyal to a permanent water source. A Kruger study found smaller
  home ranges and more site loyalty in the dry season, pointing to surface
  water as the limit. White rhino ranges shrink in the dry season too, and
  they travel daily to the few permanent waters.
- **Rule.** Savanna `0.80 1.00` (dry, wet). Modest, because they stay in
  the region.
- **Confidence.** sourced.
- **Sources.** <https://rhinoresourcecenter.com/wp-content/uploads/2019/12/1577270031.pdf>,
  <https://ielc.libguides.com/sdzg/factsheets/whiterhino/behavior>.

### Lion (`naturalist:lion`)

- **In the pack.** Savanna.
- **In the real world.** Lions follow prey. Studies in Etosha and the
  Serengeti found they hunt near ambush cover in the wet season and near
  permanent water in the dry season.
- **Rule.** Savanna `0.85 1.00`. The herbivores crowd water in the dry
  half, and so do lions. A milder cut than the zebra's because a pride
  covers a lot of ground. (I first left lions out, to avoid
  double-counting the prey. That was wrong. A predator's spawn chance
  should follow its prey's.)
- **Confidence.** reasoned. The paper did not open in full.
- **Source.** <https://pmc.ncbi.nlm.nih.gov/articles/PMC4929767>.

### Giraffe (`naturalist:giraffe`)

- **In the pack.** Savanna.
- **In the real world.** Giraffe breed all year. Birth peaks follow local
  rain but sites disagree (Namibia in the wet season, Tarangire in the
  dry, Nairobi in August and September, Serengeti in September). A tree
  browser does not depend on grass or standing water the way zebra and
  rhino do.
- **Rule.** Savanna `0.90 1.00`. A small cut, for the dry months when
  they gather where leaves and water last.
- **Confidence.** reasoned. The paper shows the sites disagree. It does not
  show the gathering.
- **Source.** <https://publish.csiro.au/WR/fulltext/WR13211>.

### Armadillo (`minecraft:armadillo`)

- **In the pack.** Savanna and badlands.
- **In the real world.** Nine-banded armadillos eat insects and worms dug
  from soil. Cold limits their range and they do not hibernate. There is
  no cold in the tropical biomes here, so the only seasonal lever is
  moisture: dry ground is harder to dig.
- **Rule.** Savanna and badlands `0.70 1.00`.
- **Confidence.** reasoned. The fact sheet covers cold and burrows, not
  rain.
- **Source.** <https://gadnrle.org/sites/default/files/Armadillo%20Fact%20Sheet_UGA.pdf>.

### Camel (`minecraft:camel`)

- **In the pack.** Desert (weight 1, already rare).
- **In the real world.** Dromedaries live in desert with a long dry season
  and a short rainy one. They are nomads and travel long distances to
  oases. Feral camels in Australia moved into areas that got more rain
  in the warm months, though the sample was small.
- **Rule.** Desert `0.70 1.00`.
- **Confidence.** sourced, with that warning.
- **Sources.** <https://animaldiversity.org/accounts/Camelus_dromedarius>,
  <https://www.cms.int/sites/default/files/publication/WildCamel_GreatGobi_MNG.pdf>,
  <https://www.publish.csiro.au/RJ/RJ09050>.

## Cold-blooded animals

### Snake (`naturalist:snake`)

- **In the pack.** `naturalist:snake` is **three animals in one type**:
  the plain snake (forest, plains, swamp), the coral snake (jungle,
  river, beach) and the rattlesnake (desert, badlands, savanna). The
  spawn list cannot tell them apart, so the rule works on biome only.
- **In the real world.** Snakes go dormant ("brumate") in the cold. Wild
  timber rattlesnakes in Tennessee went in around 10 October (plus or
  minus 12 days) and came out around 7 April (plus or minus 17). They
  moved about six times all winter, all short. Care guides put the
  cutoff near 15 C. That figure is from pet sites, not a paper.
- **Rule.** Snowy `0.00 0.50 0.00 0.00`. Mountain and taiga
  `0.50 1.00 0.60 0.00`. Elsewhere `0.70 1.00 0.80 0.05`. No rule in
  tropical biomes.
- **Confidence.** sourced (one study, one region).
- **Source.** <https://researchonline.jcu.edu.au/52035/>.

### Lizard (`naturalist:lizard`)

- Same rows as the snake. Cold-blooded, same logic. The study covers
  snakes, not lizards, so it is **reasoned**.

### Alligator (`naturalist:alligator`)

- **In the pack.** Swamp, mangrove swamp, river, and a few Terralith
  and Biomes O' Plenty wetlands, including Terralith's **ice marsh**.
- **In the real world.** The American alligator lives in the
  southeastern US. It stops eating below roughly 20 C and goes dormant
  near 13 C, for about four to five months, but comes out on warm
  days. Mating is in spring and nesting in early summer.
- **Rule.** Snowy `0.00` all year (this catches the ice marsh).
  Taiga `0.10 0.50 0.10 0.00`. Elsewhere `0.80 1.00 0.80 0.10`.
  Mangrove swamp is tropical in this pack, so it gets no seasonal rule.
- **Confidence.** reasoned. The temperatures are repeated across pages
  of mixed quality.
- **Sources.** <https://www.magnoliaplantation.com/magnolia-articles/alligators-magnolia>,
  <https://www.nps.gov/ever/learn/nature/alligator.htm>.

### Frog (`minecraft:frog`)

- **In the pack.** Swamp and mangrove swamp.
- **In the real world.** Temperate frogs go dormant in winter. Warm, wet
  spring weather wakes them and they breed in new pools. Wood frogs
  breed first.
- **Rule.** `1.00 0.90 0.70 0.10`. This reaches plain swamp only. Mangrove
  swamp is tropical in this pack, has no 4-number rows, and stays at 1.00.
- **Confidence.** sourced.
- **Sources.** <https://www.brandywine.org/conservancy/blog/vernal-pools-and-amphibians-who-love-them-your-new-noisy-neighbors>,
  <https://www.sungazette.com/news/outdoors/2023/04/reflections-in-nature-wood-frog-breeding-season-is-early-spring/>.
- **Not backed.** A search for mangrove frogs found one Australian
  paper on a frog breeding in mangrove creeks after rain, September
  to March. It is one species on one coast. Not used.

### Sea turtle (`minecraft:turtle`)

- **In the pack.** Beach only.
- **In the real world.** Sea turtles come ashore to nest in the warm
  months. In Florida the season runs about May to October (a
  conservancy), March to October (a university lab), with the peak in May
  to August (the Archie Carr refuge). Winter nesting is rare. The refuge
  logged one very late nest in December. Many turtles leave for warmer
  or deeper water in the cold.
- **Rule.** Beach `0.60 1.00 0.60 0.10`.
- **Confidence.** sourced.
- **Sources.** <https://www.fws.gov/refuge/archie-carr/species>,
  <https://sccf.org/2024/01/23/where-are-the-sea-turtles/>,
  <https://biology.fau.edu/news/seasonal-seas/index.php>.

### Crab (`friendsandfoes:crab`)

- **In the pack.** Beach and mangrove swamp.
- **Rule.** Beach `0.80 1.00 0.90 0.40`. Mangrove swamp is tropical here
  and gets none.
- **Confidence.** guess. Beach crabs shelter and slow down in the cold.
  No source was read.

### Desert scorpion (`naturalist:desert_scorpion`)

- **In the pack.** Desert and badlands.
- **Rule.** Desert and badlands `0.80 1.00` (dry, wet). Night hunters
  that sit in burrows by day. Desert invertebrates tend to come out and
  feed more when the ground is damp.
- **Confidence.** reasoned. General desert ecology, no source read.
  The jungle scorpion gets no rule because it lives in a warm, wet place
  all year.

### Jumping spider (`crittersandcompanions:jumping_spider`)

- **In the pack.** Jungle, forest, lush caves.
- **Rule.** Snowy `0.60 1.00 0.60 0.00`. Taiga `0.60 1.00 0.60 0.10`.
  Forest `0.80 1.00 0.80 0.20`. Cold-blooded. In cold country they sit
  out winter in a silk retreat. Jungle is tropical and gets no rule.
- **Confidence.** reasoned. No source read.

## Birds

### Songbirds (`naturalist:bird`)

- **In the pack.** One entity, six birds. Blue jay (taiga, hills,
  snowy, mountain). Canary (hills, mountain). Cardinal (forest, savanna,
  swamp, desert). Finch (savanna, forest). Robin (forest, mountain,
  plains, cherry grove). Sparrow (plains, cherry grove).
- **In the real world.** Cardinals and house sparrows stay all year.
  Blue jays are mostly resident, with some short-distance migrants.
  Robins are listed by the US Fish and Wildlife Service as migratory,
  though many northern flocks winter in place and the pages I found
  did not say how many.
- **Rule.** Biome only, because the six cannot be told apart. Snowy
  `0.80 1.00 0.90 0.40`. Taiga and mountain `0.90 1.00 1.00 0.60`.
  Elsewhere `0.95 1.00 1.00 0.80`.
- **Confidence.** reasoned. This is a blend of residents and leavers.
- **Sources.** <https://www.fws.gov/sites/default/files/documents/2024-04/1111.pdf>
  (robin). The cardinal, jay and sparrow facts came from short bird
  guides (a New Jersey state parks guide, a Massachusetts observer
  note) that I would not call authoritative.
- **If you want better.** The only fix is to give each bird its own
  spawn entry. That means changing Naturalist, not this mod.

### Duck (`naturalist:duck`)

- **In the pack.** Swamp and river, plus some Terralith and Biomes O'
  Plenty shrubland and marsh.
- **In the real world.** Northern mallards fly south from late
  September through October and come back from late February, peaking
  in March. City and park ducks often stay. Water that freezes pushes
  them out.
- **Rule.** Snowy `0.90 1.00 0.50 0.00`. Taiga and mountain
  `1.00 1.00 0.80 0.20`. Elsewhere no rule. Winter at mild latitudes is
  when migrants arrive, so there is no cut.
- **Confidence.** sourced. Park-district and Audubon pages, so soft.
- **Sources.** <https://www.metroparks.com/bird-of-the-week-mallard/>,
  <https://www.audubon.org/bird-guide-api/1482>.

### Turkey (`naturalist:turkey`)

- **In the pack.** Forest, flower forest, taiga, old-growth taiga, grove.
- **In the real world.** Wild turkeys do not migrate. In fall and winter
  they gather in larger flocks, hens in big flocks and toms in small
  ones (sometimes hundreds in the west). They shift to oak woods and
  tall roost trees. Home ranges are smallest in winter.
- **Rule.** Snowy `0.90 1.00 1.00 0.60`. Taiga `1.00 1.00 1.00 0.80`. Deep
  snow is hard on a ground-feeding bird.
- **Confidence.** reasoned. The pages cover flocking and roosting, not snow.
- **Sources.** <https://www.nwtf.org/content-hub/how-the-turkey-world-turns>,
  <https://tdl-ir.tdl.org/items/f2841bf9-59d0-4f82-8f55-b9f6d47c6639>.

### Parrot (`minecraft:parrot`). No rule.

Jungle birds with no clean seasonal signal at this level of detail.
Different parrots breed in different seasons. Left alone.

### Penguin (`ambient_creatures:penguin`)

- **In the pack.** Ice spikes, frozen ocean, deep frozen ocean, frozen
  river, stony shore.
- **In the real world.** Species differ. Adelie penguins breed on bare
  ground in summer and spend winter out on the pack ice, up to about
  3000 km from the colony, following the ice edge. Emperors do the
  opposite and breed on the sea ice through the Antarctic winter.
- **Rule.** Polar group `1.00 1.00 0.80 0.60`. Read as the Adelie kind,
  so winter is mostly out at sea. The emperor case is not modelled. Stony
  shore is outside the polar group and stays at 1.00.
- **Confidence.** reasoned. The tracking study was not read in full.
- **Sources.** <https://en.wikipedia.org/wiki/Ad%C3%A9lie_penguin>,
  <https://link.springer.com/doi/10.1007/s00300-007-0352-5>.

## Small mammals

### Hedgehog (`naturalist:hedgehog`)

- **In the pack.** Forest, flower forest, plains, sunflower plains,
  meadow, taiga.
- **In the real world.** European hedgehogs hibernate from about October
  or November to March or April, waking now and then on warm days. In
  mild Irish winters they sleep less and come out earlier.
- **Rule.** Snowy `0.20 1.00 0.50 0.00`. Taiga and mountain
  `0.30 1.00 0.60 0.00`. Elsewhere `0.60 1.00 0.80 0.05`.
- **Confidence.** sourced.
- **Sources.** <https://hiwwt.org.uk/node/6892>,
  <https://research.ucc.ie/en/publications/nesting-behaviour-and-seasonal-body-mass-changes-in-a-rural-irish/>.

### Rabbit (`minecraft:rabbit`)

- **In the pack.** Desert, snowy plains, ice spikes, taiga, grove,
  flower forest, cherry grove, meadow.
- **In the real world.** Active all year. How long they breed follows
  latitude and the growing season. Mediterranean rabbits breed in
  winter and stop when pasture dries. Temperate ones breed from early
  spring into mid-summer. Deep snow is hard on them.
- **Rule.** Snowy `1.00 1.00 0.90 0.60`. Taiga `1.00 1.00 1.00 0.80`.
- **Confidence.** reasoned. The page backs the breeding fact only.
- **Source.** <https://tb.plazi.org/GgServer/html/03822308B754FFEDFF6DF725F820F363>.

### Raccoon (`ambient_creatures:raccoon`)

- **In the pack.** Forest types and river.
- **In the real world.** They do not hibernate. In hard cold they stay
  in a den in torpor for days or weeks and come out on warm days.
  They eat heavily in autumn and can lose up to half their weight over
  winter. The pages that said this were wildlife-removal company
  blogs, so I did not cite them.
- **Rule.** `0.90 1.00 1.00 0.50`.
- **Confidence.** reasoned.

### Mole (`naturalist:mole`)

- **In the pack.** Forest, plains, meadow.
- **In the real world.** Active all year. They cannot hibernate because
  they store little fat. Molehills peak in late winter and spring, when
  males widen their range looking for mates and young moles disperse
  above ground. They dig deeper in cold and drought.
- **Rule.** Snowy `1.00 1.00 1.00 0.50`. Taiga `... 0.70`. No rule
  elsewhere. The animal is always there, so only the frozen ground of a
  hard winter, which keeps them below the surface, gets a cut.
- **Confidence.** reasoned. The pages say nothing about frozen ground.
- **Sources.** <https://www.wildlifeonline.me.uk/animals/species/european-mole>,
  <https://www.rhs.org.uk/biodiversity/moles>.

### Rat (`naturalist:rat`)

- **In the pack.** Forest and plains.
- **In the real world.** Rats live beside people and food. Away from
  buildings they are cold-sensitive and breed best in warm months.
- **Rule.** Snowy `0.70 1.00 0.80 0.30`. Taiga `0.80 1.00 0.90 0.50`.
  Elsewhere `0.90 1.00 1.00 0.80`.
- **Confidence.** reasoned. No source was read.

### Goat (`minecraft:goat`)

- **In the pack.** Frozen peaks, jagged peaks, snowy slopes.
- **In the real world.** Mountain goats summer in high alpine meadows.
  In winter coastal goats come down to forest near the treeline. Goats
  in drier country stay on steep, windswept slopes where snow blows off.
  A study of 42 Cascade goats found they could not be sorted into
  migrants and non-migrants.
- **Rule.** Mountain `0.90 1.00 1.00 0.60`. The game only spawns goats
  at the high summer range, so winter is thin because part of the herd
  has gone down. The size of the drop is a judgement call.
- **Confidence.** sourced for the pattern.
- **Sources.** <https://adfg.alaska.gov/static/education/wns/mountain_goat.pdf>,
  <https://bioone.org/journals/journal-of-wildlife-management/volume-72/issue-8/2007-584/Seasonal-Altitudinal-Movements-of-Mountain-Goats/10.2193/2007-584.full>.

### Mammoth (`naturalist:mammoth`)

- **In the pack.** Snowy plains, ice spikes, snowy slopes, frozen peaks.
- **In the real world.** Extinct. It lived on the cold, dry mammoth steppe
  in the ice ages, in open and semi-open tundra and steppe-tundra with
  intermediate cold. A study cited on the mammoth steppe page found they
  disappeared from northern Europe in the extreme cold of the last
  glacial maximum.
- **Rule.** Bare snow `0.70 0.80 0.70 0.50`. Elsewhere
  `0.80 0.80 0.80 0.60`. The harshest ground is the thinnest. This is an
  extinct animal in a modern game, so the rarity is a balance call.
- **Confidence.** guess.
- **Source.** <https://en.wikipedia.org/wiki/Mammoth_steppe>.

## Farm animals living wild

Cow, sheep, pig, chicken, horse, donkey and llama spawn in 20 to 25
biomes each in vanilla, with the biggest spawn weights in the game
(sheep 12, pig 10, chicken 10, cow 8). They crowd out every wild animal.
They also fill any slot a seasonal rule frees, because the game keeps
trying until the animal cap is full. So they have rules too, in
`livestock.rules`.

The idea: treat them as feral herds. They live where their wild
ancestors lived, and they are scarce. The habitat direction is backed by
sources. The size of each cut is a game-balance call, so all seven
sections are labelled **guess**. If farm animals feel too rare, raise the
numbers. If wild animals are still crowded out, lower them.

| Animal | Wild ancestor and home | Biggest chance | Smallest chance |
|---|---|---|---|
| Cow | Aurochs. Forest, grassland and river plain of Europe, Asia and North Africa. | Plains `0.6` | Jungle `0.15`, badlands `0.10`, snowy winter `0.05` |
| Sheep | Mouflon of Anatolia and Iran, and wild sheep generally. Dry, rocky uplands and steppe. | Mountain `0.9` | Jungle `0.05`, swamp `0.10` |
| Pig | Wild boar. Woodland, scrub and marsh edge. Autumn mast. | Forest autumn `0.7` | Badlands `0.10`, snowy `0.05` |
| Chicken | Red junglefowl. Forest edge in the warm tropics of India and southeast Asia. | Jungle `0.7` | Snowy and cold winter `0.0` |
| Horse | Steppe horses (Przewalski's, tarpan). Open grassland. | Plains `0.7` | Savanna `0.3` |
| Donkey | African wild ass. Dry country of north-east Africa. | Savanna dry `1.0` | Anywhere else `0.3` |
| Llama | Guanaco. High, open Andes. | Mountain `0.9` | Lowlands `0.2` to `0.3` |

- **Sources.** <https://www.fao.org/4/Y2647E/y2647e15.htm>,
  <https://www.fao.org/docrep/pdf/009/x8750e/x8750e03.pdf>,
  <https://przewalskihorse.nl/unique-but-why/original-habitat/>,
  <https://www.cnrs.fr/en/acorn-production-cycles-influence-wild-boar-populations>.
  Two weaker ones are used only for the ancestor's name and region: a
  general-knowledge page on the aurochs, and a quiz table for the red
  junglefowl. The red junglefowl is the weakest, and I found no
  authoritative range page for it.
- **Measured.** Share of 3000 spawn picks in summer taiga, before and
  after: sheep `10.2%` to `2.1%`, pig `8.3%` to `3.8%`, cow `6.0%` to
  `1.8%`, chicken `7.8%` to `1.7%`. Wild animals took the space.
- **Mooshroom** spawns only on mushroom fields and is left alone.

## Left alone on purpose

| Animal | Why |
|---|---|
| Panda, red panda | Real pandas and red pandas live in cool bamboo and montane forest in the Himalaya and China. The game puts both in hot jungle. A seasonal rule cannot fix that. The jungle is the only place the game lets them live. |
| Parrot | Jungle bird with no clean seasonal signal at this level of detail. Different parrots breed in different seasons. |
| Shima enaga | Resident small bird of Japan, snow-white in winter. It stays all year. |
| Ferret (Critters and Companions) | Forest and plains. Polecats stay active all year. Nothing to model without a source. |
| Strider | Nether. The Nether has no seasons, so the mod does nothing there. |
| Glare | Lives in lush caves, underground. Seasons do not reach it. |
| Moobloom | A fantasy cow in flower biomes. |
| Rascal, tuff golem | Spawn from structures (mineshafts, mansions), not from biomes. |
| Jungle scorpion | Lives in a wet, warm place all year. |
| Butterfly, firefly, dragonfly, fish, sharks, whales | Not `CREATURE`. The hook never sees them. |
| Critters and Companions insects, otter, koi, sea bunny, octopus | Ambient or water types. The hook never sees them. |

## What I could not find

These searches came back empty, thin or off-target. The rules for them
are `reasoned` or `guess`. If you find a good source, add it and move
the label to `sourced`.

- Deer winter "yarding".
- Giraffe seasonal movement at the population level (sites disagree).
- Bengal tiger monsoon movement (only flood news).
- Desert tortoise brumation timing (only a one-tortoise news story).
- Authoritative range of the red junglefowl and the vicuña.
- Lion movement (the paper cited did not open in full).
- Moles in frozen ground.
