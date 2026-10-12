#!/usr/bin/env python3
"""
Turns the CSV from `/seasonalspawns shares` into an outlier report and a heatmap.

    python3 dev/shares.py path/to/seasonal-spawns-shares.csv [out-dir]

Writes out-dir/shares-report.txt and out-dir/shares.html (default: next to the CSV).
Standard library only, so it runs anywhere.

What a "share" is: inside one category (creature, ambient, water_ambient ...), one biome and one
season, an animal's weight x average group size x seasonal chance, divided by the total of the
same number for every animal listed there. It is the odds that the next animal the spawner
spawns there is this one. It is NOT how many exist. The creature cap and vanilla's own caps
decide how many.

Weak spots, said plainly:
  - Every biome counts the same. A rare biome counts as much as plains.
  - Shares only compare animals inside one category. A butterfly in "ambient" and a deer in
    "creature" never compete.
  - The Nether and End are dropped by name (see SKIP_BIOME). It is a hack. A new dimension mod
    will leak in until its biomes are added there.

The thresholds below are the project's idea of "absurd". Change them and rerun.
"""
import csv
import html
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

DOMINANT = 0.50      # one animal this big in a biome-season is "taking over"
FADED = 0.02         # below this a listed animal is practically never the next spawn
GHOST_MAX = 0.03     # an animal that never reaches this share anywhere is "hard to ever see"
HOG_MEAN = 0.25      # mean share this high across many biomes is an everywhere-animal
HOG_MIN_BIOMES = 8
SWING = 4.0          # summer vs winter reach changes by this factor or more
MIN_LISTED = 3       # dominance only counts where at least this many animals are listed

SEASON_ORDER = ["spring", "summer", "autumn", "winter", "dry", "wet"]
SKIP_BIOME = re.compile(r"nether|soul_sand|crimson|warped_forest|basalt|the_end|end_|_end|nullscape|small_end")


def load(path):
    """Rows as dicts with the numbers parsed. Drops other dimensions."""
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            if SKIP_BIOME.search(r["biome"]):
                continue
            r["weight_listed"] = int(r["weight_listed"])
            r["weight_capped"] = int(r["weight_capped"])
            r["mean_group"] = float(r["mean_group"])
            r["chance"] = float(r["chance"])
            r["mass"] = r["weight_capped"] * r["mean_group"] * r["chance"]
            rows.append(r)
    return rows


def add_shares(rows):
    """r['share'] = mass / total mass of the same category, biome and season."""
    totals = defaultdict(float)
    for r in rows:
        totals[(r["category"], r["biome"], r["season"])] += r["mass"]
    for r in rows:
        t = totals[(r["category"], r["biome"], r["season"])]
        r["share"] = r["mass"] / t if t > 0 else 0.0


def pct(x):
    return f"{100 * x:4.0f}%"


# ---- the report ------------------------------------------------------------

def report(rows):
    out = []
    say = out.append
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)

    say("SPAWN SHARE REPORT")
    say("Share = the odds the next spawn in that category, biome and season is this animal.")
    say(f"{len(rows)} rows, {len({r['biome'] for r in rows})} overworld-ish biomes, "
        f"{len({r['animal'] for r in rows})} animals.\n")

    for cat in sorted(by_cat):
        crows = by_cat[cat]
        animals = sorted({r["animal"] for r in crows})
        biomes = sorted({r["biome"] for r in crows})
        say("=" * 78)
        say(f"{cat.upper()}: {len(animals)} animals in {len(biomes)} biomes")
        say("=" * 78)

        # per animal, per season: mean share over the biomes that list it, and reach
        per = defaultdict(lambda: defaultdict(list))   # animal -> season -> [share per biome]
        for r in crows:
            per[r["animal"]][r["season"]].append(r["share"])

        # 1. ghosts
        ghosts = []
        for a in animals:
            best = max(s for ss in per[a].values() for s in ss)
            n_biomes = len({r["biome"] for r in crows if r["animal"] == a and r["chance"] > 0})
            if best < GHOST_MAX:
                ghosts.append((best, a, n_biomes))
        say(f"\nGHOSTS: never reach {GHOST_MAX:.0%} of spawns anywhere in any season (hard to ever see)")
        for best, a, n in sorted(ghosts):
            say(f"  {a:42s} best {best:6.2%}  listed in {n} biomes")
        if not ghosts:
            say("  none")

        # 2. hogs and dominance
        say(f"\nHOGS: mean share >= {HOG_MEAN:.0%} across >= {HOG_MIN_BIOMES} biomes (everywhere-animals)")
        hogs = 0
        for a in animals:
            for season in SEASON_ORDER:
                ss = per[a].get(season, [])
                if len(ss) >= HOG_MIN_BIOMES and sum(ss) / len(ss) >= HOG_MEAN:
                    say(f"  {a:42s} {season:7s} mean {sum(ss) / len(ss):5.1%} over {len(ss)} biomes")
                    hogs += 1
        if not hogs:
            say("  none")

        dom = defaultdict(list)    # animal -> [(biome, season, share)]
        listed_count = defaultdict(set)
        for r in crows:
            listed_count[(r["biome"], r["season"])].add(r["animal"])
        for r in crows:
            if r["share"] >= DOMINANT and len(listed_count[(r["biome"], r["season"])]) >= MIN_LISTED:
                dom[r["animal"]].append((r["biome"], r["season"], r["share"]))
        say(f"\nDOMINANT: animal is >= {DOMINANT:.0%} of spawns in a biome-season with >= {MIN_LISTED} animals listed")
        for a, hits in sorted(dom.items(), key=lambda kv: -len(kv[1])):
            sample = ", ".join(sorted({b.split(':')[-1] for b, _, _ in hits})[:5])
            say(f"  {a:42s} in {len(hits):3d} biome-seasons  e.g. {sample}")
        if not dom:
            say("  none")

        # 3. seasonal swings and gaps (reach = biomes where share >= FADED)
        say(f"\nSEASON REACH: biomes where the animal is >= {FADED:.0%} of spawns, by season. Big swings and gaps:")
        reach = {}
        for a in animals:
            reach[a] = {s: sum(1 for x in per[a].get(s, []) if x >= FADED) for s in SEASON_ORDER}
        shown = 0
        for a in animals:
            std = [reach[a][s] for s in SEASON_ORDER[:4]]
            hi, lo = max(std), min(std)
            if hi >= 2 and (lo == 0 or hi / max(lo, 1) >= SWING):
                say(f"  {a:42s} spring {std[0]:3d}  summer {std[1]:3d}  autumn {std[2]:3d}  winter {std[3]:3d}"
                    f"   (dry {reach[a]['dry']}, wet {reach[a]['wet']})")
                shown += 1
        if not shown:
            say("  none")

        # 4. monoculture biomes
        say(f"\nPOOR BIOMES: effective species < 1.5 where >= {MIN_LISTED} are listed (1 / sum of share^2)")
        poor = []
        by_bs = defaultdict(list)
        for r in crows:
            by_bs[(r["biome"], r["season"])].append(r)
        for (b, s), rs in by_bs.items():
            if len({r["animal"] for r in rs}) < MIN_LISTED:
                continue
            tot = sum(r["share"] for r in rs)
            if tot <= 0:
                continue
            eff = 1.0 / sum((r["share"] / tot) ** 2 for r in rs)
            top = max(rs, key=lambda r: r["share"])
            if eff < 1.5:
                poor.append((eff, b, s, top["animal"], top["share"]))
        for eff, b, s, top, sh in sorted(poor)[:25]:
            say(f"  {b:36s} {s:7s} eff {eff:4.2f}  top {top} {sh:5.1%}")
        if len(poor) > 25:
            say(f"  ... and {len(poor) - 25} more")
        if not poor:
            say("  none")

        # 5. empty biome-seasons: listed animals but every chance is 0
        empties = {(r["biome"], r["season"]) for r in crows}
        live = {(r["biome"], r["season"]) for r in crows if r["mass"] > 0}
        gone = sorted(empties - live)
        say(f"\nEMPTY: biome-seasons where animals are listed but every one is barred ({len(gone)})")
        for b, s in gone[:15]:
            say(f"  {b} {s}")
        if len(gone) > 15:
            say(f"  ... and {len(gone) - 15} more")
        say("")
    return "\n".join(out)


# ---- the heatmap -----------------------------------------------------------

def color(share, listed_but_barred):
    if share <= 0:
        return "#7a2e2e" if listed_but_barred else "#e6e6e6"
    # sqrt so a 3% animal is still visible next to a 60% one
    t = math.sqrt(min(share, 1.0))
    lightness = 92 - 62 * t
    hue = 210 - 210 * (1 if share >= DOMINANT else 0)   # blue, red when dominant
    return f"hsl({hue:.0f},70%,{lightness:.0f}%)"


def heatmap(rows):
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
    parts = ["""<!doctype html><html><head><meta charset="utf-8"><title>Spawn shares</title><style>
body{font:13px system-ui;margin:16px;background:#fff;color:#111}
h2{margin-top:32px}
table{border-collapse:collapse}
th.b{writing-mode:vertical-rl;font-weight:normal;font-size:10px;text-align:left;height:150px;padding:0 1px}
td.a{font-size:11px;padding:0 6px 0 0;white-space:nowrap;position:sticky;left:0;background:#fff}
td.c{padding:1px;height:14px}
.strip{display:flex;width:20px;height:14px;gap:0}
.strip div{flex:1}
.note{max-width:70ch;color:#444}
</style></head><body>
<h1>Spawn shares by animal, biome and season</h1>
<p class="note">Each cell is four strips: spring, summer, autumn, winter. Tropical biomes show dry, dry, wet, wet.
Blue shades are the animal's share of its category's spawns there (square-root scale). Red means it takes over
(at least 50%). Dark brown means the animal is listed but barred that season. Light grey means not listed.
Hover a cell for the numbers. Every biome counts the same, however big it is.</p>"""]
    for cat in sorted(by_cat):
        crows = by_cat[cat]
        biomes = sorted({r["biome"] for r in crows})
        cell = {}
        for r in crows:
            cell[(r["animal"], r["biome"], r["season"])] = r
        trop = {r["biome"]: r["tropical"] == "true" for r in crows}
        # most-spawned animals first
        weight_of = defaultdict(float)
        for r in crows:
            weight_of[r["animal"]] += r["share"]
        animals = sorted(weight_of, key=lambda a: -weight_of[a])
        parts.append(f"<h2>{html.escape(cat)}</h2><table><tr><th></th>")
        for b in biomes:
            parts.append(f'<th class="b">{html.escape(b)}</th>')
        parts.append("</tr>")
        for a in animals:
            parts.append(f'<tr><td class="a">{html.escape(a)}</td>')
            for b in biomes:
                seasons = ["dry", "dry", "wet", "wet"] if trop[b] else SEASON_ORDER[:4]
                strips, tips = [], []
                present = False
                for s in seasons:
                    r = cell.get((a, b, s))
                    if r is None:
                        strips.append('<div style="background:#e6e6e6"></div>')
                        continue
                    present = True
                    strips.append(f'<div style="background:{color(r["share"], r["mass"] == 0)}"></div>')
                    tips.append(f'{s} {r["share"]:.1%}')
                tip = html.escape(f"{a} in {b}: " + ", ".join(dict.fromkeys(tips))) if present else ""
                parts.append(f'<td class="c" title="{tip}"><div class="strip">{"".join(strips)}</div></td>')
            parts.append("</tr>")
        parts.append("</table>")
    parts.append("</body></html>")
    return "\n".join(parts)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = load(path)
    add_shares(rows)
    text = report(rows)
    (out_dir / "shares-report.txt").write_text(text)
    (out_dir / "shares.html").write_text(heatmap(rows))
    print(text)
    print(f"\nwrote {out_dir / 'shares-report.txt'} and {out_dir / 'shares.html'}")


if __name__ == "__main__":
    main()
