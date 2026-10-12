## Freshwater fish

Rules: `fish-freshwater.rules`. Mods: SeaLife (v26.2.0) and Naturalist
(2.0.6), plus vanilla salmon.

### How to read these rules

- The game spawns fish in any water inside a biome. "Forest" means a
  pond or river inside a forest.
- The chance can only lower a spawn. The busy season is 1.00. Other
  seasons are cut.
- I read the chance as "how many of this fish you would meet in the
  water". A fish asleep in a deep hole counts as not met. That is a hack.
  It treats seen and present as the same thing.
- Winter is low, not zero, for fish that live under ice.
- Most numbers are my size call. The sources give direction and timing.
- Where I wrote "search summary", I saw the claim in a search result and
  did not open the page. Pages that gave 403 or unreadable PDFs are
  not cited as read.
- "In the pack" comes from the jars: SeaLife's `spawns_*` biome tags and
  Naturalist's `has_*` tags. Terralith and Biomes O' Plenty biomes are
  mostly left out.

### Bass (`sealife:bass`, `naturalist:bass`)

- **In the pack.** SeaLife: forest, plains, swamp, meadow, river.
  Naturalist: swamp, mangrove swamp, river, plus Terralith ice marsh,
  warm river and both oases.
- **In the real world.** Largemouth bass spawn in spring. Males move
  shallow at about 60 F and nest at 63 to 68 F. In winter they are sluggish
  and eat little. A warm spell over 50 F wakes them.
- **Rule.** Snowy: `0.00 0.30 0.10 0.00`. Everywhere else:
  `0.90 1.00 0.70 0.20`.
- **Habitat fix.** Bass do not live in snow country. Naturalist spawns
  them in the ice marsh. That biome is nearly shut. I did not check that
  the ice marsh is in the `snowy` group. Run the audit.
- **Confidence.** sourced.
- **Sources.** <https://ncpedia.org/largemouth-bass-nc-wins>.
- **Not backed.** The autumn number. Mangrove swamp has no row, so it
  stays at 1.0. Florida bass do use fresh mangrove edges, so that is fine.

### Carp, koi and goldfish (`sealife:carp`, `sealife:koi`, `sealife:goldfish`)

- **In the pack.** Carp: forest, plains, swamp, river. Koi: the same
  plus cherry grove and meadow. Goldfish: forest, plains, meadow, river.
- **In the real world.** Common carp winter in deep water and move to
  shallow weedy water in spring. They spawn at about 13 to 18 C. They survive
  under ice. Pond goldfish and koi stop eating under about 10 C and sit
  near the bottom. They eat most in spring and autumn.
- **Rule.** Everywhere: `0.90 1.00 0.70 0.20`.
- **Confidence.** reasoned. Search summaries only.
- **Sources.** <https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11576824/>,
  <https://pondinformer.com/?p=39844>.
- **Not backed.** Koi and goldfish are copied from carp. No wild-koi page
  was read. The summer peak is my call. Carp spawning runs into early summer.

### Catfish (`sealife:catfish`, `naturalist:catfish`)

- **In the pack.** SeaLife: swamp, river. Naturalist: swamp, mangrove
  swamp, Terralith ice marsh, warm river, oases.
- **In the real world.** Channel and blue catfish gather in deep winter
  holes. They start to feed at 55 to 60 F. They spawn in late spring and
  summer at 70 to 85 F.
- **Rule.** Snowy: `0.00 0.20 0.00 0.00`. Everywhere else:
  `0.60 1.00 0.70 0.15`.
- **Habitat fix.** No catfish in an ice marsh, same as bass.
- **Confidence.** reasoned. Search summary only.
- **Sources.** <https://www.in-fisherman.com/editorial/the-spring-catfish-spawn-connection/155780>.
- **Not backed.** The autumn number. Tropical catfish in mangrove swamp
  and oases are left at 1.0.

### Bowfin (`sealife:bowfin`)

- **In the pack.** Swamp and river.
- **In the real world.** Spawns May to early June at 60 to 66 F. The male
  guards a nest in weedy shallows. Bowfin breathe air.
- **Rule.** `0.80 1.00 0.70 0.20`.
- **Confidence.** reasoned. The page I read covers spawning only.
- **Sources.** <https://vtfishandwildlife.com/learn-more/vermont-critters/fish/bowfin>.
- **Not backed.** Any winter behaviour. The winter cut is copied from the
  other warm-water fish.

### Pickerel (`sealife:pickerel`)

- **In the pack.** Forest, swamp, meadow, river.
- **In the real world.** Chain pickerel spawn from late winter to early
  spring in flooded plants. Some southern fish spawn in winter. Some
  populations have a small fall spawn. They hold in weed beds.
- **Rule.** `1.00 0.80 0.80 0.40`.
- **Confidence.** reasoned. Search summaries only.
- **Sources.** <https://en.wikipedia.org/wiki/Chain_pickerel>,
  <https://www.maine.gov/ifw/docs/strategic-management-plans/pickerel.pdf>.
- **Not backed.** Winter activity under ice.

### Minnow (`sealife:minnow`)

- **In the pack.** Forest, plains, meadow, river.
- **In the real world.** The fathead minnow spawns late May to
  mid-August once the water is above about 16 C. Spawning stops under
  about 10 C.
- **Rule.** `0.70 1.00 0.70 0.20`.
- **Confidence.** reasoned. The mod's minnow is generic. The fathead is
  the closest match, not a proven one.
- **Sources.** <https://academics.cehd.umn.edu/hatch/research/fish/fishes/fathead_minnow.html>.
- **Not backed.** Everything about winter.

### Chub (`sealife:chub`)

- **In the pack.** Forest, meadow, river.
- **In the real world.** Creek chub spawn March to July depending on
  latitude, at 12 to 19 C. Males build a gravel ridge in a stream.
- **Rule.** `1.00 0.90 0.60 0.20`.
- **Confidence.** reasoned. Search excerpts of the page.
- **Sources.** <https://academics.cehd.umn.edu/hatch/research/fish/fishes/creek_chub.html>.
- **Not backed.** Winter behaviour.

### Trout (`sealife:trout`)

- **In the pack.** Grove, rivers (including frozen river), taiga.
- **In the real world.** Brook and brown trout spawn in autumn, roughly
  September to November. Eggs sit in gravel redds through winter.
- **Rule.** `0.80 0.60 1.00 0.60`.
- **Confidence.** reasoned.
- **Sources.** <https://tacklevillage.com/when-do-brook-trout-spawn/>,
  <https://www.ctriver.org/post/fall-redds>. A tackle site and a river
  group. Search summaries.
- **Not backed.** The summer dip. It rests on the idea that trout are
  cold-water fish. I did not search for it.

### Northern pike (`sealife:northern_pike`)

- **In the pack.** Frozen river, grove, snowy plains, taiga.
- **In the real world.** Pike spawn as soon as the ice is gone, in shallow
  weedy water and marshes. They may start under the ice.
- **Rule.** `1.00 0.70 0.80 0.60`.
- **Confidence.** sourced, for the spring peak only.
- **Sources.** <https://digital.outdoornebraska.gov/nebraskaland-magazine/ice-off-pikes-up>.
- **Not backed.** Summer and winter numbers. The page does not cover them.

### Perch (`sealife:perch`)

- **In the pack.** Forest, plains, meadow, river.
- **In the real world.** Yellow perch spawn in April or early May, shortly
  after ice-out, at 45 to 52 F. They like colder water and sit deeper.
- **Rule.** `1.00 0.70 0.90 0.60`.
- **Confidence.** sourced for the spawn time.
- **Sources.** <https://dnr.wisconsin.gov/topic/Fishing/species/yperch.html>.
- **Not backed.** "Active all winter under ice". I saw that from a Michigan
  DNR page in a search summary. The page itself gave a 403. The winter
  number is a mild cut for that reason, and is my call.

### Walleye (`sealife:walleye`)

- **In the pack.** Taiga, meadow, river.
- **In the real world.** Spring spawning run up rivers. On the Maumee
  the peak is the last week of March into early April at 40 to 50 F.
- **Rule.** River: `1.00 0.60 0.70 0.50`. Everywhere else:
  `0.90 0.70 0.80 0.60`.
- **Confidence.** reasoned. A local paper and an angling magazine.
- **Sources.** <https://www.crescent-news.com/sports/outdoors/temperature-stream-flow-key-to-walleye-run/article_f34514c9-a8b2-500e-9f78-5e6c9560e515.html>,
  <https://www.in-fisherman.com/editorial/hot-little-numbers-for-river-walleyes/154576>.
- **Not backed.** The summer and winter numbers.

### Lamprey (`sealife:lamprey`)

- **In the pack.** River, ocean, deep ocean, cold ocean, deep cold ocean.
- **In the real world.** Sea lampreys run up streams in early spring and
  spawn in April. Males start nests above about 4.5 C. In Portugal the
  run is December to June with a peak in February and March. Adults die
  after spawning.
- **Rule.** River only: `1.00 0.20 0.20 0.40`. The oceans have no row.
- **Confidence.** sourced for the spring run.
- **Sources.** <https://www.fws.gov/midwest/SeaLamprey/>.
- **Not backed.** The size of the summer drop. The Portugal dates came
  from a search summary of <https://dl.uc.pt/rest/bitstreams/11354820/retrieve>.

### Salmon (`minecraft:salmon`)

- **In the pack.** River, frozen river, cold ocean, deep cold ocean,
  frozen ocean, deep frozen ocean. I read the 26.2 biome files and found
  those six.
- **In the real world.** Atlantic salmon enter rivers from spring with a
  June peak and spawn from late October through November. Pacific fall
  runs spawn October to December. Most adults die after spawning.
- **Rule.** River only: `0.50 0.70 1.00 0.30`. The oceans have no row.
- **Confidence.** sourced. The Atlantic dates are from the FWS page. The
  Pacific dates are from search summaries.
- **Sources.** <https://trainingcenter.fws.gov/resources/knowledge-resources/salmon/asalmon3.html>.
- **Not backed.** The numbers. The Pacific dates are search-summary only.
  A mountaineers.org page and a sciencefriday page showed in the results.
  The first gave a 403 and I did not open the second.

### Lungfish (`sealife:lungfish`)

- **In the pack.** Jungle and swamp.
- **In the real world.** African lungfish seal themselves in a mud cocoon
  when their water dries up. They wake within a day of the return of
  water. They can stay sealed for months to years.
- **Rule.** Dry/wet: jungle `0.20 1.00`, swamp (mangrove) `0.30 1.00`.
  Plain swamp, four seasons: `0.50 1.00 0.50 0.10`.
- **Habitat fix.** A tropical fish in a temperate swamp with a real winter
  is nearly shut in winter.
- **Confidence.** sourced for the dry-season sleep. The page gave no
  calendar months. The numbers are my call.
- **Sources.** <https://www.frontiersin.org/articles/10.3389/fphys.2016.00532/full>.
  I read the first 100,000 characters.
- **Not backed.** The mod does not say which lungfish it means. The
  Australian lungfish does not estivate. I assumed African.

### Pupfish (`sealife:pupfish`)

- **In the pack.** Desert, river, savanna, savanna plateau.
- **In the real world.** Desert pupfish go dormant in cold water, buried
  in mud. Spawning starts at the end of February and runs through summer.
  Summer heat dries many pools and kills most fish.
- **Rule.** Dry/wet: desert `0.60 1.00`, savanna `0.70 1.00`. River,
  four seasons: `0.90 1.00 0.70 0.10`.
- **Confidence.** reasoned.
- **Sources.** <https://www.desertusa.com/fish/pupfish.html>.
- **Not backed.** Putting the pool-drying on the dry half. It is a guess.
  The page does not say that the dry season is when the pools shrink.

### Siamese fighting fish (`sealife:siamese_fighting_fish`)

- **In the pack.** Jungle and swamp.
- **In the real world.** Wild bettas live in rice paddies, swamps and
  ditches. Hobby pages say they spread across flooded land in the rains
  and get stuck in pools in the dry season.
- **Rule.** Dry/wet: jungle and swamp `0.60 1.00`. Plain swamp, four
  seasons: `0.70 1.00 0.70 0.10`.
- **Confidence.** guess. Fish-keeping sites only.
- **Sources.** <https://seriouslyfish.com/species/betta-splendens>,
  <https://sites.google.com/view/lotusfins/betta-fish/splenden-complex>.
- **Not backed.** Breeding season. No page I saw gave one. The dry cut is
  a guess built on the spreading and pooling.

### Neon tetra (`sealife:neon_tetra`)

- **In the pack.** Jungle and swamp.
- **In the real world.** Amazon blackwater fish. I found no page on wild
  seasons.
- **Rule.** Plain swamp only: `0.70 1.00 0.70 0.10`. Jungle and mangrove
  swamp have no row.
- **Confidence.** guess. This is only a habitat fix.
- **Sources.** none found.
- **Not backed.** Any seasonal behaviour. A study of a different tetra
  from Colombia says many tropical fish breed in the flood season. That
  is not enough to cut a neon tetra's dry half.

### Piranha (`sealife:piranha`, `naturalist:piranha`)

- **In the pack.** SeaLife: jungle, swamp. Naturalist: jungle (vanilla and
  common tag) and lush caves.
- **In the real world.** Red-bellied piranha breed twice a year, tied to
  the flood pulse. They spawn in flooded plants. In the dry season they
  crowd the main channel and feed more.
- **Rule.** Plain swamp only: `0.40 1.00 0.40 0.00`. Jungle, mangrove swamp
  and lush caves have no row.
- **Confidence.** guess. Habitat fix only.
- **Sources.** <https://doaj.org/article/32f34c405a0f41d3af255aa492da4830>.
  A search result, not opened.
- **Not backed.** A dry/wet cut. The two effects pull in opposite ways. The
  cold numbers rest on "tropical fish" and I did not search for the
  piranha's cold limit.

## Left alone

| Animal | Where | Why |
|---|---|---|
| `sealife:electric_ray` | ocean, deep ocean, lukewarm, warm ocean | It is a sea fish. The only source I found says Atlantic torpedo rays use shelf waters in late spring and summer. That came from one tracked fish and a trawl survey. Not enough for a number. Warm ocean has little seasonal swing. |
| Salmon, lamprey | oceans | Sea phase has no season. Only the river rows exist. |
| Piranha, neon tetra | jungle, mangrove swamp | No clear seasonal signal. Only the cold swamp has a rule. |
| All temperate fish | mangrove swamp | Tropical in this pack, so they have no 2-number rows. Left at 1.0. |
| Terralith oases and warm river | all fish | Not checked against the groups. |

## What I could not find

- **Wild neon tetra seasons.** No field page.
- **Betta breeding timing.** Hobby sites only, and they do not give it.
- **Piranha cold limit.** Not searched.
- **Trout summer heat limit.** Not searched.
- **Pike and walleye summer behaviour.** The pages cover spawning only.
- **Winter behaviour of bowfin, minnow, chub, pickerel.** No page.
- **Koi in the wild.** Copied from carp.
- **Which SeaLife lungfish.** African or Australian. The jar does not say.
- **Which groups hold Terralith ice marsh, desert oasis and warm river.**
  Run `/seasonalspawns audit`.
- **What the rules do in game.** I ran the parser only. I did not run the
  server or count fish.
- **Open pages.** The SRAC bass fact sheet and the Wisconsin perch PDF
  were unreadable in the fetch tool. Michigan DNR and the mountaineers.org
  page gave 403. I cite none of them as read.
