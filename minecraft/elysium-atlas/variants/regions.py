"""Region units and named groups.

The region layer (bake/bake_regions.py) stores one unit per RESOLVE Ecoregions 2017 ecoregion, named "eco:<ECO_ID>".
A group below with "lon": [min, max) splits its ecoregion along a meridian (the border is warped); each piece
is its own unit, "eco:<ECO_ID>:<group>". ECO_ID 0 ("Rock and Ice") takes the nearest ecoregion.
Variants name units or groups; group names expand to their units (unit_names). Unit 0 = no ecoregion (sea).
"""
REGIONS = {
    "western_alps":    {"eco": [689], "lon": [-180, 10.0], "why": "Alps west of the Engadin: Savoy, Valais, Bernese Oberland, Ticino."},
    "eastern_alps":    {"eco": [689], "lon": [10.0, 180],  "why": "Tyrol, Dolomites, Carinthia, Styria. Drier, more larch and pine."},
    "atlantic":        {"eco": [664], "why": "European Atlantic mixed forests: oceanic, mild, wet. Brittany to Belgium."},
    "west_european":   {"eco": [686], "why": "Western European broadleaf forests: beech and oak uplands, Jura, Vosges, Black Forest, Bavaria."},
    "central_european": {"eco": [654], "why": "Central European mixed forests: continental, colder winters, pine and spruce in the mix."},
    "po_plain":        {"eco": [675], "why": "Po Basin: flat, hot summers, poplar and oak floodplain."},
    "apennines":       {"eco": [644], "why": "Apennine beech and oak montane forests."},
    "dinaric":         {"eco": [660, 794], "why": "Dinaric and Illyrian karst: limestone, beech and black pine."},
    "mediterranean":   {"eco": [795, 799, 806], "why": "Sclerophyll coast: holm oak, maquis, garrigue, lavender."},
}


def split_groups():
    """ECO_ID -> [(group, lon_min, lon_max)] for ecoregions split along meridians."""
    out = {}
    for g, r in REGIONS.items():
        if "lon" in r:
            for e in r["eco"]: out.setdefault(e, []).append((g, *r["lon"]))
    return out


def unit_names(name):
    """Units a variant's region entry covers: a unit name stays itself, a group name expands."""
    if name.startswith("eco:"): return [name]
    if name not in REGIONS: raise KeyError(name)
    r = REGIONS[name]
    return [f"eco:{e}:{name}" if "lon" in r else f"eco:{e}" for e in r["eco"]]
