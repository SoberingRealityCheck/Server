"""Pack regions: named groups of RESOLVE Ecoregions 2017 (ECO_ID). Biome variants are keyed by these names.

A region name is frozen once a world uses it. Region 0 ("none") is everywhere not listed: there the formation
biome is used unchanged. ECO_ID 0 ("Rock and Ice") takes the nearest listed region.
Optional "lon": [min, max) splits one ecoregion between regions along a meridian (the border is warped).
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
