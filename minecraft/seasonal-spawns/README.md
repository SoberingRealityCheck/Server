# Seasonal Spawns

Land animals spawn at different rates by season and by biome. Bears sleep
through winter. Zebra follow the rains. Frogs wake in spring. You set the
numbers in plain text files, and every number has a reason written next
to it.

It is a small server-side Fabric mod. It needs Serene Seasons for the
calendar. It works with Respawning Animals, which is what makes animals
come and go in the first place.

- **The rules you edit:** `../server-overrides/config/elysium-seasonal-spawns/*.rules`
- **Why each animal has the numbers it has:** [ANIMALS.md](ANIMALS.md)
- **The built jar (checked in):** `../server-overrides/mods/elysium-seasonal-spawns.jar`

## What it does, and what it does not

Every time the game picks a land animal to spawn, this mod asks one
question: *is this animal allowed to spawn here, in this season?* The
answer is a number from 0 to 1. The mod rolls against it. A "no"
cancels that one spawn.

That is all it does. This has three consequences you should know.

1. **It can only lower a rate.** 1.00 is the pack's normal. It cannot
   go higher. If you want more deer in autumn, lower everything else, or
   raise the base with the `min_animals_near_player` gamerule.
2. **It does not set how many animals are in the world.** It changes the
   mix of what spawns and how fast the world refills. Respawning
   Animals keeps topping up toward a cap of its own. If the world is
   already full, a lower chance only slows the refill. Watch a world
   for a few game days before you count on a density change.
3. **It cannot tell apart animals that share a type.** Naturalist uses
   one entity (`naturalist:bird`) for six birds and one (`naturalist:snake`)
   for three snakes. Rules for those work on biome only.

Only land animals are touched (vanilla's `CREATURE` category). Monsters,
fish, ambient mobs and the Nether never reach the rules.

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
| `/seasonalspawns here` | The season and biome where you stand, the groups it is in, and every animal whose chance is under 1.00 right now. The tuning tool. |
| `/seasonalspawns sample [n]` | Asks the game's own spawn picker for `n` land animals here (default 1000) and shows the mix. A pick the rules cancelled shows as "nothing". Compare two seasons to see what a rule really does. |
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

The hook is one `@Inject` on `NaturalSpawner.getRandomSpawnMobAt`, at its
return. The rules code (`Rules`, `RuleParser`, `Table`) has no Minecraft
in it, so it is tested with strings and no mocks.

Files:

| File | Job |
|---|---|
| `src/elysium/seasonalspawns/Rules.java` | The rule data and `chance()`. |
| `.../RuleParser.java` | Text in, `Rules` out, or a list of `file:line: message`. |
| `.../Table.java` | Reads a folder, prints every rule as a grid. Run by `build.sh`. |
| `.../SelfTest.java` | 21 checks on the two above. Run by `build.sh`. |
| `.../SeasonalSpawns.java` | The only file that talks to the game: loading, Serene Seasons, commands. |
| `.../mixin/NaturalSpawnerMixin.java` | The hook. |
| `.../mixin/NaturalSpawnerAccessor.java` | Lets `sample` call the same picker. |

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

Tested on 2026-10-09, on a throwaway dedicated server built from this
pack's server mods plus this jar (Minecraft 26.2, Fabric Loader 0.19.5,
Java 25). Console only, no player:

- The jar loads and the mixin applies. `defaultRequire = 1` means a bad
  target would have stopped the server.
- The rules load: 22 sections, 23 animals, 15 groups.
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

Not tested:

- **Live spawning with a player.** A headless server has no player, so
  natural spawning never ran. `sample` calls the same picker but it is not
  the full spawn loop.
- **Whether density really drops.** See "does not set how many animals"
  above. Needs a real world and a few game days.
- **Clients.** The jar is server-only. A client that has it installed
  gets no feature from it.
- **Existing worlds.** Respawning Animals defaults off in a world made
  without it. See `MODLIST.md`. Without that gamerule on, animals never
  leave, and this mod has less to act on.

## Hacks and limits

- The mixin targets a **private** method by name. A Minecraft update that
  renames it stops the server at startup, loudly.
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
- **Move the cap by season.** Set `min_animals_near_player` per season. Needs
  a check that Respawning Animals picks up a gamerule changed from code.
- **Ease between seasons** using the sub-season progress Serene Seasons
  already reports.
- **Split the six birds and three snakes** so each gets its own rules. That
  is a change to Naturalist, not to this mod.
