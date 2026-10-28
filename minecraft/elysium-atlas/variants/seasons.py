"""Explicit season palettes (art direction ask 20): leaf and grass colour per region and Serene Seasons subseason.

Inputs in db/seasons/ (from the art direction thread, /mnt/project-files/art-direction):
  species_phenology.yaml  leaf colour tracks (6 keys) of deciduous trees and shrubs, plus special cases
  grass_phenology.yaml    grass colour tracks (6 keys), from grass_tracks.py there
  region_climate.yaml     per region: phase (when the keys fall on subseasons) and winter class; edit by hand
  season_palettes.yaml    hand-authored palettes; per block they win over the derived ones

palettes(eid, prof, leaves_of) gives {block or "grass": [colour or "bare", ...]} with 12 entries (early_spring ..
late_winter) or 6 for the tropical regime (early_wet .. late_dry), and the leaf-block moves the palettes assume:
where an evergreen and a deciduous species share a leaf block, the evergreen moves to an evergreen-only block.
"""
import json, os
import yaml
import db

HERE = os.path.dirname(os.path.abspath(__file__))
SD = os.path.join(HERE, "db", "seasons")
KEYS6 = ("spring", "summer", "early_autumn", "autumn", "late_autumn", "winter")
SUB = [f"{a}_{s}" for s in ("spring", "summer", "autumn", "winter") for a in ("early", "mid", "late")]
TROP = ["early_wet", "mid_wet", "late_wet", "early_dry", "mid_dry", "late_dry"]
CHERRY = "minecraft:cherry_leaves"    # Clay's call: vanilla pink all year, untinted
# hand palettes written for brief layouts that have not landed in the db yet; the derived palette applies until then
HAND_WAITING = {391, 437, 682, 654}

# which track key (or an even blend of two) each subseason shows, per phase class
PHASE = {
    "cold": dict(early_spring="winter", mid_spring="winter", late_spring="spring", early_summer="spring",
                 mid_summer="summer", late_summer="summer", early_autumn="early_autumn", mid_autumn="autumn",
                 late_autumn="late_autumn", early_winter="winter", mid_winter="winter", late_winter="winter"),
    "mid": dict(early_spring=("winter", "spring"), mid_spring="spring", late_spring=("spring", "summer"),
                early_summer="summer", mid_summer="summer", late_summer="summer", early_autumn="early_autumn",
                mid_autumn="autumn", late_autumn="late_autumn", early_winter="winter", mid_winter="winter", late_winter="winter"),
    "warm": dict(early_spring="spring", mid_spring=("spring", "summer"), late_spring="summer", early_summer="summer",
                 mid_summer="summer", late_summer="summer", early_autumn="early_autumn", mid_autumn=("early_autumn", "autumn"),
                 late_autumn="autumn", early_winter="late_autumn", mid_winter="winter", late_winter=("winter", "spring")),
    "tropical": dict(early_wet="spring", mid_wet="summer", late_wet="summer", early_dry="early_autumn",
                     mid_dry="late_autumn", late_dry="winter"),
}
# phase and winter class by WWF biome number, for regions region_climate.yaml does not list
DEFAULT = {1: ("warm", "mild"), 2: ("tropical", "dry"), 3: ("tropical", "dry"), 4: ("mid", "snow"), 5: ("mid", "snow"),
           6: ("cold", "snow"), 7: ("warm", "mild"), 8: ("mid", "snow"), 9: ("mid", "snow"), 10: ("cold", "snow"),
           11: ("cold", "snow"), 12: ("warm", "summer_dry"), 13: ("warm", "dry")}
CONIFER = ("pine", "spruce", "fir", "larch", "juniper", "cedar", "arborvitae", "hemlock", "cypress")
_c = {}


def _load():
    if not _c:
        y = lambda n: yaml.safe_load(open(os.path.join(SD, n))) or {}
        sp = y("species_phenology.yaml"); sp.pop("evergreen_flag_fixes", None)   # applied in db/plants
        _c.update(species=sp, special=sp.pop("special", {}), grass=y("grass_phenology.yaml"), climate=y("region_climate.yaml"),
                  hand=y("season_palettes.yaml"),
                  eco=json.load(open(os.path.join(HERE, "data", "ecoregions.json"))))
    return _c


def hx(c): return [int(c[i:i + 2], 16) for i in (1, 3, 5)]
def mix(a, b, t): return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(hx(a), hx(b)))


def mean(items):
    """[(colour or 'bare', weight)] -> colour, or 'bare' when most of the weight is leafless."""
    tot = sum(w for _, w in items)
    if not tot: return None
    if sum(w for c, w in items if c == "bare") / tot >= 0.6: return "bare"
    col = [(hx(c), w) for c, w in items if c != "bare"]; t = sum(w for _, w in col)
    return "#" + "".join(f"{round(sum(c[i] * w for c, w in col) / t):02x}" for i in range(3))


def fill(track, summer):
    """Complete a 6-key track: summer from the db, early and late autumn by blending; bare holds."""
    t = dict(track); t.setdefault("summer", summer)
    if "early_autumn" not in t: t["early_autumn"] = mix(t["summer"], t["autumn"], .4) if t.get("autumn", "bare") != "bare" else t["summer"]
    if "late_autumn" not in t:
        a, w = t.get("autumn"), t.get("winter", "bare")
        t["late_autumn"] = a if w == "bare" or a == "bare" else mix(a, w, .5)
    return t


def key_at(track, k):
    if isinstance(k, tuple):
        a, b = track[k[0]], track[k[1]]
        return a if "bare" in (a, b) else mix(a, b, .5)    # leaf-out and leaf-fall happen at the later key
    return track[k]


def species_track(p):
    """(6-key track, evergreen) of a woody species."""
    c = _load(); e = db.plants()[p]
    if e.get("evergreen"): return {k: e["leaf"] for k in KEYS6}, True
    if p in c["special"]:
        s = c["special"][p]
        if "all" in s: return {k: s["all"] for k in KEYS6}, True
        return fill(s, e["leaf"]), False
    if p in c["species"]: return fill(c["species"][p], e["leaf"]), False
    # deciduous without a track: its db autumn colour if any, else a dull yellow
    return fill({"spring": mix(e["leaf"], "#a8d860", .4), "autumn": e.get("autumn") or "#b09a40", "winter": "bare"}, e["leaf"]), False


def grass_track(g, winter):
    t = {k: _load()["grass"][g][k] for k in KEYS6}; ty = _load()["grass"][g]["type"]
    if ty == "c3" and winter == "mild":
        t["winter"] = mix(t["summer"], t["winter"], .3); t["late_autumn"] = mix(t["summer"], t["late_autumn"], .5)
    if ty in ("c3", "steppe") and winter == "summer_dry":
        s = t["summer"]; t.update(summer=mix(s, "#b8a878", .55), early_autumn="#b8a878", autumn=mix("#b8a878", s, .3),
                                  late_autumn=mix(s, "#86a858", .3), winter=mix(s, "#86a858", .4))
    return t


def classes(eid):
    """(phase, winter class, grass winter class) of a region."""
    c = _load()["climate"].get(eid)
    if c: return c["phase"], c["winter"], c.get("grass", c["winter"])
    ph, w = DEFAULT.get(_load()["eco"].get(str(eid), {}).get("biome_num"), ("mid", "snow"))
    return ph, w, w


def moves(eid, prof, leaves_of):
    """{species: (from, to)} for evergreens that share a leaf block with deciduous species in this region."""
    P = db.plants(); ever = {}
    for L in ("trees", "shrubs") + tuple(db.TINT_LAYERS):
        for p, wt in (prof.get(L) or {}).items():
            if wt <= 0 or not P[p].get("leaf") or P[p]["kind"] not in ("tree", "ref"): continue
            ev = species_track(p)[1]
            for lb in leaves_of(p): ever.setdefault(lb, []).append((p, ev))
    used_dec = {lb for lb, v in ever.items() if any(not ev for _, ev in v)}
    out = {}
    for lb, v in ever.items():
        evs = [p for p, ev in v if ev]
        if not evs or all(ev for _, ev in v) or lb == CHERRY: continue
        for p in evs:
            if P[p]["kind"] != "tree" or len(leaves_of(p)) != 1: continue   # only inline single-leaf features can be rewritten
            conifer = any(k in p for k in CONIFER)
            to = "biomesoplenty:pine_leaves" if conifer else "minecraft:dark_oak_leaves"
            if to in used_dec: to = "biomesoplenty:fir_leaves" if conifer else "minecraft:mangrove_leaves"
            if to in used_dec: continue
            out[p] = (lb, to)
    return out


def expand(pal, subs):
    """A hand palette as a full list. With "all", the other keys are departures held for their own subseason. Without
    it, unkeyed subseasons blend the keys around them, and a bare key holds until the next key."""
    if "all" in pal: return [pal.get(s, pal["all"]) for s in subs]
    keys = [i for i, s in enumerate(subs) if s in pal]
    if not keys: return None
    n, out = len(subs), []
    for i, s in enumerate(subs):
        if s in pal: out.append(pal[s]); continue
        prev = max([k for k in keys if k < i] or [k - n for k in keys])
        nxt = min([k for k in keys if k > i] or [k + n for k in keys])
        a, b = pal[subs[prev % n]], pal[subs[nxt % n]]
        out.append(a if "bare" in (a, b) else mix(a, b, (i - prev) / (nxt - prev)))
    return out


def palettes(eid, prof, leaves_of):
    """({block or "grass": [colour or "bare"] * 12 or 6}, tropical, moves) for one region."""
    P = db.plants(); ph, w, gw = classes(eid)
    hand = _load()["hand"].get(eid) if eid not in HAND_WAITING else None
    tropical = ph == "tropical" or (hand or {}).get("regime") == "tropical"
    if tropical and ph != "tropical": ph = "tropical"
    subs = TROP if tropical else SUB; pmap = PHASE[ph]
    mv = moves(eid, prof, leaves_of)
    out = {}
    grass = [(grass_track(g, gw), wt) for g, wt in (prof.get("ground") or {}).items() if P[g]["form"] == "grass" and wt > 0]
    if grass: out["grass"] = [mean([(key_at(t, pmap[s]), wt) for t, wt in grass]) for s in subs]
    if None in out.get("grass", []): del out["grass"]
    blocks = {}
    for L in ("trees", "shrubs") + tuple(db.TINT_LAYERS):
        for p, wt in (prof.get(L) or {}).items():
            if wt <= 0 or not P[p].get("leaf") or P[p]["kind"] not in ("tree", "ref", "ground"): continue
            lbs = {mv[p][1]} if p in mv else leaves_of(p)
            for lb in lbs:
                if lb != CHERRY: blocks.setdefault(lb, []).append((species_track(p)[0], wt))
    for lb, items in blocks.items():
        v = [mean([(key_at(t, pmap[s]), wt) for t, wt in items]) for s in subs]
        if None not in v: out[lb] = v
    for k, v in (hand or {}).items():
        if k == "regime" or not isinstance(v, dict): continue
        e = expand(v, subs)
        if e and (k == "grass" or k in out): out[k] = e
    return out, tropical, mv
