# Seasonal Spawns

Animals spawn at different rates by season and by biome. Bears sleep
through winter. Zebra follow the rains. Frogs wake in spring. Butterflies
fly in summer. Salmon run in autumn. That covers land animals, insects,
bats, fish and other water animals. It does not cover monsters. You set the
numbers in plain text files, and every number has a reason written next
to it.

It does two separate things:

1. **Which animals spawn.** A per-animal chance by season and biome
   (`*.rules`). Bears are barred in winter.
2. **How many animals the area holds.** A per-player cap that depends on
   biome and season (`capacity.rules`). A winter taiga holds fewer animals
   than a summer forest.

It is a small server-side Fabric mod. It needs Serene Seasons for the
calendar. It works with Respawning Animals, which is what makes animals
come and go in the first place.

- **The rules you edit:** `../server-overrides/config/elysium-seasonal-spawns/*.rules`
- **Why each animal has the numbers it has:** [ANIMALS.md](ANIMALS.md)
- **The built jar (checked in):** `../server-overrides/mods/elysium-seasonal-spawns.jar`

## What it does, and what it does not

**Which animals.** Every time the game picks a land animal to spawn, this
mod asks: *is this animal allowed to spawn here, in this season?* The
answer is a number from 0 to 1. The mod rolls against it. A "no" cancels
that one spawn.

**How many.** Respawning Animals fills the world up to a cap of land
animals per player (the `min_animals_near_player` gamerule, 15 by
default) and tries again every tick. Without the second feature, a spawn
the first feature cancels is simply retried, so a slot an animal is barred
from is filled by something that is not barred. The mix changes. The
count does not. So the second feature gives each player a cap that
depends on where they are. See "The creature cap" below.

Things to know:

1. **The chance can only lower a rate.** 1.00 is the pack's normal. It
   cannot go higher. If you want more deer in autumn, lower everything
   else, or raise the base with the `min_animals_near_player` gamerule.
2. **The cap is a ceiling, not a target.** It stops spawning at the cap.
   Where the land cannot hold that many animals anyway (placement rules,
   light, no grass), the count stays lower. In the live test, a taiga and a
   desert site held 1 to 7 animals with the cap off, well under 15.
3. **A falling cap does not remove animals.** Animals within 32 blocks of
   a player never despawn, and ones further out leave slowly. After a
   season change the count drifts down over minutes, not at once.
4. **It cannot tell apart animals that share a type.** Naturalist uses
   one entity (`naturalist:bird`) for six birds and one (`naturalist:snake`)
   for three snakes. Rules for those work on biome only.

Only land animals are touched (vanilla's `CREATURE` category). Monsters,
fish, ambient mobs and the Nether never reach the rules or the cap.

## The creature cap

The cap makes the count follow the biome and the season. How it works:

1. For every biome and season, add up
   `spawn weight x average group size x seasonal chance`
   for each land animal the biome can spawn. That is the biome's
   "creature weight". The seasonal chance is the same number the `.rules`
   files already give, so a winter taiga with no bears has a smaller sum.
2. Divide by the creature weight of a **reference place** (summer forest
   by default). That is the biome's fraction. Richer than the reference is
   cut back to 1.0.
3. Multiply by a hand-set row in `capacity.rules` if the weights got a
   place wrong.
4. A player's cap is `base x fraction`, never under a floor (3) and never
   over the base. The base is the cap Respawning Animals already set. The
   fraction is the average over 9 spots around the player, 64 blocks
   apart. Ocean spots are skipped.
5. The game's own check, "is there room for another animal near this
   player?", is wrapped so it compares the count with that cap instead of
   the fixed 15. Any one nearby player with room is still enough.

`/seasonalspawns capacity` prints the whole table. `/seasonalspawns here`
shows the cap at your feet and the count of animals the game sees.

### Known problems with the weight sum

- **Weights are not abundance.** They are odds that mod authors tuned
  against each other. The penguin has weight 50 and groups of 10, so it
  alone made frozen ocean look 65% as rich as a summer forest. The first
  table had that and it is fixed with a `polar` row. Others may be wrong.
  Read the table and fix what looks wrong with a row.
- **The scale is the reference.** If you change the reference place, every
  cap moves. Adding a mod that adds animals to the reference biome
  makes every other place look poorer.
- **Placement rules are ignored.** The sum counts animals a biome lists
  even if they rarely find a place to stand.
- **The floor flattens cold places.** Winter taiga comes out at 0.14 of the
  reference, under the floor of 3. So summer and winter taiga look alike.
  Lower the floor, or raise the taiga row, if you want a bigger swing.
- **Coarse numbers.** The game allows a spawn while `count < cap`, so a cap
  of 3.4 holds up to 4 animals. A pack that spawns together can overshoot
  by a few.

To turn the whole feature off, delete `capacity.rules`. The game's own cap
then applies everywhere.

## Edit the rules

The fast loop:

```sh
cd minecraft/seasonal-spawns
JAVA_HOME=/path/to/jdk-25 ./build.sh test
```

That checks every file, prints each mistake as `file:line: message`, and
prints the table of every rule. It does not need Minecraft or a world.
Read the table. If it looks right, commit. The game does the same check
at startup.

Or edit on a running server. Change the file in `config/elysium-seasonal-spawns/`
then run `/seasonalspawns reload`. A mistake keeps the old rules and
writes every problem to the log. (A pack update puts the repo's files
back, so move the change into the repo too.)

### The file format

```
# Comments start with #.

[forest]                                   <- a biome group (biomes.rules)
biomes = #minecraft:is_forest minecraft:taiga
why    = What this group means.

[bears]                                    <- rules for some animals
animals    = naturalist:bear naturalist:black_bear
confidence = sourced                       <- sourced | reasoned | guess
source     = https://example.org/page      <- needed if sourced
why        = Plain words. What the real animal does.
             Indented lines carry on from the line above.
#          spring summer autumn winter
taiga    = 0.4  1.0  0.8  0.0
any      = 0.8  1.0  1.0  0.15
#          dry  wet
savanna  = 1.0  0.25
```

Rules:

- A **row** is `group = numbers`. Four numbers are `spring summer autumn winter`
  for ordinary biomes. Two numbers are `dry wet` for tropical biomes.
- **Tropical** is not your choice. Serene Seasons decides. In this pack
  deserts, badlands, savannas, jungles and mangrove swamps are tropical.
  Everything else gets four seasons. A 4-number row never applies to a
  tropical biome, and a 2-number row never applies to the rest. Put both
  kinds in one section if an animal lives in both.
- The **first row that fits** wins. Put the narrow group first and
  `any` last. A row that can never run is an error.
- A number is the **chance a picked spawn goes ahead**. `1.0` is normal.
  `0.0` is never. `0.5` is half.
- No row fits means `1.0`. An animal in no section is untouched.
- Each animal goes in **one** section only.
- Rows start at the left edge. Indented lines belong to the `why` or
  `source` above them.
- `why` is required. `source` is required when `confidence = sourced`. The
  loader refuses a section without them, on purpose.

### The three confidence labels

| Label | Meaning |
|---|---|
| `sourced` | A page I read says the behaviour. The link is in the rule. |
| `reasoned` | Well-known biology. No page read for this exact rule. |
| `guess` | A game-balance call. No real-world claim. |

A source can back the direction and the timing and still not back the
size. Nobody published "0.5". Every drop size is a judgement call.
That is why you are meant to edit them.

### Change a group

Biome groups live in `biomes.rules`. A group is a list of `#tags` and
biome ids. Run `/seasonalspawns audit` after a Terralith update. It
logs every biome and the groups it fell into, and says how many are in
none. Biomes in no group are only reached by `any` rows.

## Commands

All need operator level (game master). They also work from the console.

| Command | What it does |
|---|---|
| `/seasonalspawns here` | The season and biome where you stand, the groups it is in, every animal whose chance is under 1.00 right now, and the creature cap here with the count of animals near. The tuning tool. |
| `/seasonalspawns capacity` | The creature cap table. Chat gets the reference and the richest and poorest places. The server log gets every biome with its fraction for each season. |
| `/seasonalspawns sample [n] [category]` | Asks the game's own spawn picker for `n` animals here (default 1000) and shows the mix. The category is the game's name: `creature` (default), `ambient`, `water_creature`, `water_ambient`, `underground_water_creature`, `axolotls`. Fish are `water_ambient`. Stand in the water for water categories. A pick the rules cancelled shows as "nothing". Compare two seasons to see what a rule really does. |
| `/seasonalspawns animals` | Every animal in any biome's spawn list, by category, with whether a rule covers it. The full list goes to the server log, with `[NO RULE]` on the gaps. Run it after adding a mod. |
| `/seasonalspawns stats` | Per animal, how many spawns the rules allowed and cancelled since startup. Only counts picks where the chance was under 1.00. Samples count too. |
| `/seasonalspawns audit` | Lists every biome and its groups in the server log. |
| `/seasonalspawns reload` | Reloads the `.rules` files. Also happens on `/reload`. |

Serene Seasons' own `/season set mid_winter` and `/season get` jump the
calendar. Use them with `sample` to test.

## How it works

```
game picks an animal to spawn          NaturalSpawnerMixin (one hook)
        |
        v
SeasonalSpawns.allows(level, pos, animal)
        |  asks Serene Seasons: season? tropical biome? dry or wet?
        |  works out which biome groups the spot is in (cached)
        v
Rules.chance(animal, groups, tropical, phase)      <- plain data in, number out
        |
        v
roll. A "no" cancels this one pick. The game tries again later.
```

```
game asks "room for another animal near this player?"    LocalMobCapCalculatorMixin
        |
        v
CapacityTable.capFor(player)        <- cached 100 ticks per player
        |  samples 9 spots around the player, looks up each biome's row
        |  (rows were built once at server start from every biome's spawn list)
        v
Capacity.cap(base, fraction, floor)                <- plain numbers in, number out
        |
        v
count < cap ?   (the game's count, read through MobCountsAccessor)
```

The spawn hook is one `@Inject` on `NaturalSpawner.getRandomSpawnMobAt`, at
its return. The cap hook is one `@WrapOperation` on the
`MobCounts.canSpawn` call inside `LocalMobCapCalculator.canSpawn`. The
rules and cap math (`Rules`, `RuleParser`, `Capacity`, `Table`) have no
Minecraft in them, so they are tested with strings and no mocks.

Files:

| File | Job |
|---|---|
| `src/elysium/seasonalspawns/Rules.java` | The rule data and `chance()`. |
| `.../RuleParser.java` | Text in, `Rules` out, or a list of `file:line: message`. |
| `.../Capacity.java` | The cap math: weight sum, fraction, cap. No Minecraft. |
| `.../Table.java` | Reads a folder, prints every rule as a grid. Run by `build.sh`. |
| `.../SelfTest.java` | 44 checks on the files above. Run by `build.sh`. |
| `.../CapacityTable.java` | Builds the per-biome table from the game's spawn lists and answers "what is this player's cap". |
| `.../SeasonalSpawns.java` | Loading, Serene Seasons, commands, the spawn decision. |
| `.../mixin/NaturalSpawnerMixin.java` | The spawn hook. |
| `.../mixin/NaturalSpawnerAccessor.java` | Lets `sample` call the same picker. |
| `.../mixin/LocalMobCapCalculatorMixin.java` | The cap hook. |
| `.../mixin/MobCountsAccessor.java` | Reads the game's per-player animal count. |
| `dev/` | A fake-player test tool. Not in the pack. See `dev/README.md`. |

## Build

```sh
JAVA_HOME=/path/to/jdk-25 ./build.sh          # build the jar, test, print the table
JAVA_HOME=/path/to/jdk-25 ./build.sh test     # test and print only
```

Java 25 is needed because the 26.2 game jar is class version 69. The
script downloads everything it needs into `.build/` (ignored by git). The
jar is checked in, like the Distant Horizons patch. Rebuild after
editing `src/`. You do not need to rebuild to change a `.rules` file.

## Tested, and not tested

Tested on 2026-10-09 on throwaway dedicated servers (Minecraft 26.2,
Fabric Loader 0.19.5, Java 25). Console only, no player. The sample
tables below came from a server with the pack's mod set as of 1.7.1 plus
this jar. A last boot of the exact 1.7.7 pack (jar and rules from
`server-overrides/`) repeated the audit, `here` and a taiga summer and
winter sample with the same results: bears, hedgehogs and snakes at
zero in winter, back to normal in summer.

- The jar loads and the mixin applies. `defaultRequire = 1` means a bad
  target would have stopped the server.
- The rules load: 95 sections, 105 animals, 20 groups in the full pack (with
  insects, bats, fish and water animals added). `animals` lists 22 animals
  with no rule, all on purpose. 51 sections, 52 animals, 15 groups (the last five are
  `second-pass.rules`, added after the runs below, which saw 46 and 47. 22 sections and 23
  animals in the first runs below, before farm animals and the rest were
  added). The audit puts 118 of 165 biomes in a group. The other 47 are
  mostly oceans, caves, Nether and End.
- `audit`, `here`, `sample`, `stats` and `reload` all ran.
- A broken rules file is reported as `file:line: message`, the old rules
  stay, and the next `reload` recovers.
- `sample` goes through the game's real picker and follows the season.
  1000 picks per cell, picks as a share of all tries:

  | Where | Animal | Spring | Summer | Autumn | Winter |
  |---|---|---|---|---|---|
  | Taiga | naturalist:bear | 3.9% | 7.1% | 7.6% | 0% |
  | Taiga | naturalist:hedgehog | 2.2% | 9.6% | 6.3% | 0% |
  | Snowy taiga | naturalist:bear | 4.6% | 11.3% | | 0% |
  | Ice marsh | minecraft:frog | 18.3% | 14.5% | | 2.2% |
  | Ice marsh | naturalist:alligator | 0% | 0% | | 0% |
  | Desert | naturalist:komodo_dragon | 0% | 0% | 0% | 0% |
  | Desert | naturalist:tortoise | 11.2% | 6.4% | 5.2% | 10.7% |
  | Savanna | naturalist:ostrich | 13.3% | 10.7% | 8.8% | 14.2% |

  The desert and savanna rows are wet or dry, not four seasons. In this
  pack the dry half fell on mid-summer and mid-autumn, and the wet half
  on mid-winter and mid-spring. That is Serene Seasons' calendar, not a
  setting here. Small counts are noisy. 1000 picks of a rare animal can
  move a few points by luck.
- A bigger check, 20,000 picks on snowy slopes in each season:
  - Songbirds (`0.8 1.0 0.9 0.4` there) came out at 43.4%, 54.1%,
    49.2% and 22.1% of picks. That is 0.80, 1.00, 0.91 and 0.41 of
    summer. It matches the rule.
  - The tiger (`0.6` in every season) came out at 8.6%, 8.8%, 8.7% and
    8.9%. Flat, as it should be. (A 1000-pick run once showed 6.6% in
    spring. That was luck.)
- **Farm animals,** after `livestock.rules` was added. Share of 3000
  picks in summer taiga: sheep 10.2% to 2.1%, pig 8.3% to 3.8%, cow 6.0%
  to 1.8%, chicken 7.8% to 1.7%. In summer forest each is 1 to 2%. In
  summer savanna each is about 1%, and the donkey and horse are under
  1%. Wild animals take the space.

### The creature cap, with a fake player

`sample` cannot show the cap, because natural spawning only runs near a
player. So `dev/testbot` logs in a fake creative player (see `dev/README.md`)
and the real spawn loop runs. Each run: 6 x 6000 ticks (about 30 game
minutes), after the saved animals were cleared. The number is the
settled count of land animals the game sees near the bot (average of the
last three readings), at a forest site near the world spawn.

| Run | Cap the mod worked out | Animals held |
|---|---|---|
| Summer, cap on | 9.6 | 9.0 |
| Summer, cap off | (15) | 8.7 |
| Winter, cap on | 6.5 | 6.3 |
| Winter, cap off | (15) | 10.7 |
| Summer, cap forced to 2 | 2.0 | 2 |

What this shows:

- **The hook works.** With the cap forced down to 2, the forest holds
  exactly 2 animals instead of about 9. The count follows the cap.
- **The seasonal swing is real, where the land can hold it.** Winter
  forest holds about 6 with the cap on and about 11 with it off. That is
  the cap, not the bears being barred: the control had the same bar and
  the animals were refilled by others.
- **In summer the cap barely binds.** The forest is the reference, so its
  cap is nearly the base, and the natural count there is already
  8 to 13.

What it does not show:

- **Most places never reach their cap.** The taiga and desert sites held 2
  to 9 animals with the cap off, far under 15. Placement, light and
  despawning limit them. The cap only matters where the natural count
  would otherwise be higher.
- **Those two sites are unreliable.** Their animals were mostly saved
  ones in chunks that loaded after the clear, so their counts say little
  about spawning. Pack spawns (capybara groups of up to 6) also overshoot
  a cap of 3.
- **One site, one world seed, one run per cell.** Treat the numbers as a
  demonstration, not a measurement.

Not tested:

- **Players walking around.** The bot stands still. A real player moves, so
  their area changes and animals they leave behind despawn.
- **More than one real player near each other.**
- **Clients.** The jar is server-only. A client that has it installed
  gets no feature from it.
- **Existing worlds.** Respawning Animals defaults off in a world made
  without it. See `MODLIST.md`. Without that gamerule on, animals never
  leave, and this mod has less to act on.

## Hacks and limits

- The spawn hook targets a **private** method by name. The cap hook targets
  one call inside `LocalMobCapCalculator.canSpawn` and grabs the loop's
  player variable by type. A Minecraft update that reshapes either stops
  the server at startup, loudly. The cap hook is forced to load at server
  start (`verifyCapHook`) so it cannot hide until the first player joins.
- The cap is worked out per player and cached for 100 ticks (5 seconds).
  A season change takes up to 5 seconds to show in the cap.
- The cap reads each sample spot at the surface, and skips spots in chunks
  that are not loaded. Biomes are 3D, so reading at the player's height
  would give a miner the cap of the cave they stand in. Checked: at y=-50
  in a deep cave the cap equals the forest surface above it.
- The calendar is global. Every biome shares one year. Differences between
  biomes come only from the rows you write.
- Four seasons only. The three sub-seasons inside each are not used, so a
  rule steps at the season boundary. It does not ease in.
- `mangrove_swamp` is tropical in this pack. Frogs, alligators and tortoises
  there only see 2-number rows.
- Chunk-generation spawns do not go through the hook. With Respawning
  Animals on, new chunks do not spawn animals at generation anyway.

## Ideas not built

- **Migration.** Make out-of-season animals despawn faster, so geese leave
  in autumn and not just spawn less.
- **Cull to the cap.** When the cap falls, make the extra animals despawn,
  instead of waiting for them to wander out of range.
- **A better capacity source.** The weight sum is a stand-in. Hand-written
  capacity by biome group and season, justified by real plant productivity,
  would not depend on how mod authors tuned their weights.
- **Ease between seasons** using the sub-season progress Serene Seasons
  already reports.
- **Split the six birds and three snakes** so each gets its own rules. That
  is a change to Naturalist, not to this mod.
