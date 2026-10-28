"""Scored biome placement (slice-8).

Every land cell takes the biome whose niche best fits the cell. A niche comes from the biome's own data
(biome_traits.py: temperature, downfall, c: tags, trees per chunk, landform); the cell's values come from
the warm-branch climate re-lapsed to the cell's elevation, the atlas relief, and the water mask.
No table maps a place to a biome. Biomes themed on one small real place are left to the ecoregion profiles.

score = thermal + moisture + cover + conifer + landform + snow + extra - jitter     (lowest wins)

  thermal   (theta_cell - theta_biome)^2 / S_T^2   theta from mean annual temperature, -15..30 C -> 0..1
  moisture  (mu_cell - mu_biome)^2 / S_M^2          mu from the moisture index, scaled down in cold cells; half where the cell is wetter
  cover     (cover_cell - cover_biome)^2 / S_C^2    woody cover (formation physiognomy, MI and the RESOLVE prior) vs. trees per chunk
  conifer   conifer biomes pay where it is warm and not very wet
  landform  log-distance of relief outside the biome's range (peaks need relief, plains need none)
  snow      the biome lies under snow all year (temperature < 0.15) and the cell does not, or the reverse
  extra     rare, dead and wasteland biomes pay a little; sandy and badlands ground counts as dry
  water     wetland biomes only on the wetland mask, and wetland cells only take them
  jitter    per-biome value noise, so near-ties form coherent patches instead of one winner everywhere
"""
import json, math, os
import numpy as np
from scipy import ndimage as ndi

S_T, S_M, S_C = 0.10, 0.16, 0.22
W_L, W_S, W_RARE, W_CONIFER, JITTER = 2.0, 6.0, 0.6, 2.0, 0.8
NOISE_M = 45000.0            # jitter wavelength in Equal Earth metres (300 blocks)
REALMS = ["Palearctic", "Nearctic", "Neotropic", "Afrotropic", "Indomalayan", "Australasian", "Oceanian", "Antarctic"]

# relief window range (m) per landform; cells outside pay W_L * 4 * log-distance^2
LANDFORM = {"flat": (0, 350), "hill": (250, 1100), "highland": (150, 900), "mesa": (150, 1300),
            "mountain": (700, 2400), "peak": (1300, 1e9), "cliff": (900, 1e9)}
HIGHLAND_MIN_Z = 600.0       # highland and plateau biomes also want height

def theta_of_temperature(t):
    """Minecraft biome temperature -> theta (same 0..1 scale as the cell's)."""
    return float(np.interp(t, [-0.7, 0.0, 0.25, 0.7, 0.95, 1.2, 2.0], [0.02, 0.12, 0.30, 0.55, 0.75, 0.85, 0.95]))
def theta_of_mat(MAT):
    """Cell mean annual temperature (C) -> theta. Vanilla's temperate biomes span about 5-20 C; 'hot' means tropical."""
    return np.interp(MAT, [-15, -5, 0, 8, 15, 20, 25, 30], [0.0, 0.12, 0.27, 0.47, 0.62, 0.72, 0.86, 1.0])
def mu_of_mi(MI):
    """Cell moisture index -> mu, matched to downfall (plains 0.4 ~ MI 0.5, forest 0.8 ~ MI 1)."""
    return np.interp(np.log(np.maximum(MI, 1e-3)), np.log([0.05, 0.2, 0.5, 1.0, 1.5, 2.5]), [0.0, 0.2, 0.4, 0.8, 0.9, 1.0])
TAG_THETA = {"c:is_snowy": 0.10, "c:is_icy": 0.08, "c:is_cold": 0.30, "c:is_temperate": 0.60, "c:is_hot": 0.92}
# Woody cover of each g3 formation (physiognomy: closed forest 0.85-1, woodland 0.3-0.6, grass 0-0.1). Half of the cell's cover target.
FORMATION_COVER = {"ice_sheet": 0, "polar_desert": 0, "arctic_tundra": 0.03, "alpine_tundra": 0.05, "cold_plateau_steppe": 0.03,
    "larch_taiga": 0.75, "boreal_taiga": 0.85, "hemiboreal_mixed": 0.85, "hot_desert": 0, "cold_desert": 0, "hot_semidesert": 0.1,
    "cold_steppe": 0.05, "mangrove": 0.9, "tropical_rainforest": 1.0, "tropical_montane": 0.95, "tropical_monsoon": 0.85,
    "tropical_dry_forest": 0.6, "savanna_woodland": 0.35, "savanna_grassland": 0.12, "mediterranean_scrub": 0.25,
    "mediterranean_woodland": 0.5, "subtropical_laurel": 0.9, "temperate_rainforest": 1.0, "temperate_broadleaf": 0.85,
    "forest_steppe": 0.35, "temperate_grassland": 0.08, "temperate_savanna": 0.3}

def has(tags, t): return t in tags or t + "/overworld" in tags

def value_noise(xm, ym, wave, seed):
    gx = xm / wave; gy = ym / wave; ix = np.floor(gx).astype(np.int64); iy = np.floor(gy).astype(np.int64); fx = gx - ix; fy = gy - iy
    def h(a, b):
        k = (a * 73856093) ^ (b * 19349663) ^ seed; k = (k ^ (k >> 13)) * 1274126177; k = k ^ (k >> 16)
        return (k & 0xFFFFFF) / float(0xFFFFFF)
    sx = fx * fx * (3 - 2 * fx); sy = fy * fy * (3 - 2 * fy)
    return (h(ix, iy) * (1 - sx) * (1 - sy) + h(ix + 1, iy) * sx * (1 - sy) + h(ix, iy + 1) * (1 - sx) * sy + h(ix + 1, iy + 1) * sx * sy)

class Niche:
    def __init__(self, bid, tr):
        tags = set(tr["tags"]); self.id = bid; self.tags = tags
        anchors = [v for k, v in TAG_THETA.items() if has(tags, k)]
        th = theta_of_temperature(tr["temperature"])
        if anchors:   # the climate tag sets the band; the temperature only orders biomes inside it
            a = float(np.mean(anchors)); th = a + float(np.clip(0.25 * (th - a), -0.08, 0.08))
        self.theta = th
        # moisture band from the tags (vanilla downfall is a colour knob: savanna has 0), downfall orders biomes inside it
        a = 0.9 if has(tags, "c:is_wet") else 0.2 if has(tags, "c:is_dry") else 0.55
        if tags & {"c:is_desert", "c:is_sandy", "c:is_badlands"}: a = 0.05                 # bare sand or terracotta ground reads as arid
        mu = a + 0.3 * (min(max(tr["downfall"], 0.0), 1.0) - a)
        if "c:is_lush" in tags: mu += 0.1
        self.mu = min(max(mu, 0.0), 1.0)
        cv = min(math.log1p(tr["trees"]) / math.log1p(20.0), 1.0)
        if has(tags, "c:is_sparse_vegetation"): cv -= 0.1
        if has(tags, "c:is_dense_vegetation"): cv += 0.1
        self.cover = min(max(cv, 0.0), 1.0)
        self.conifer = "c:is_taiga" in tags or "c:is_tree/coniferous" in tags
        self.snow = tr["temperature"] < 0.15 or tr["frozen"]
        self.landform = tr["terrain"]; self.wet = tr["wet"]; self.coast = "mangrove" in bid
        self.realms = [REALMS.index(r) for r in tr["realms"]] if tr["realms"] else None
        self.extra = W_RARE * ("c:is_rare" in tags) + W_RARE * bool(tags & {"c:is_dead", "c:is_wasteland"})
        self.seed = int.from_bytes(bid.encode()[-8:].rjust(8, b"\0"), "little") & 0x7FFFFFFF

class Placement:
    def __init__(self, traits_path):
        tr = json.load(open(traits_path))
        self.niches = [Niche(k, v) for k, v in sorted(tr.items()) if not v.get("profile_only")]
        self.ids = [n.id for n in self.niches]

    @staticmethod
    def cell_terms(MAT, Thot, Tcold, MI, dry_months, formation_cover, med, pnv=None):
        theta = theta_of_mat(MAT); mu = mu_of_mi(MI); dry_months = np.asarray(dry_months, np.float32)
        cover = np.clip((MI - 0.45) / 0.7, 0, 1) * np.clip((Thot - 9.0) / 5.0, 0, 1)
        trop = Tcold >= 15
        cover = cover * np.where(trop, 1 - np.clip((dry_months - 4) / 6.0, 0, 0.6), 1)   # long dry season: fire savanna
        cover = 0.5 * cover + 0.5 * formation_cover
        if pnv is not None:
            pc = np.array([0.0] + [PNV_COVER[k] for k in range(1, 15)] + [0.0] * 241, np.float32)[pnv]
            cover = np.where(pnv > 0, (1 - W_PNV) * cover + W_PNV * pc, cover)
        cover = np.where(med, np.maximum(cover, 0.35), cover)    # summer-dry: sclerophyll scrub and woodland, not open grass
        snow = ((Tcold < -6) & (MAT < 3) & (Thot < 16)) | ((Tcold < -15) & (MAT < -3)) | (Thot < 6)   # snow lies most of the year
        wm = np.clip((theta - 0.1) / 0.3, 0.2, 1.0)    # moisture matters little where it is too cold to evaporate
        conifer = np.clip((theta - 0.45) / 0.2, 0, 1) * (1 - np.clip((mu - 0.85) / 0.15, 0, 1))   # warm and not very wet: broadleaf
        return {"theta": theta, "mu": mu, "cover": cover, "snow": snow, "wm": wm, "conifer": conifer}

    def scores(self, n, c):
        """Score of niche n over the cells in dict c (arrays of one shape)."""
        dm = c["mu"] - n.mu         # a cell wetter than the niche shows less than a drier one (plains in rain still read as plains)
        s = ((c["theta"] - n.theta) / S_T) ** 2 + c["wm"] * np.where(dm > 0, 0.5, 1.0) * (dm / S_M) ** 2 + ((c["cover"] - n.cover) / S_C) ** 2
        if n.conifer: s = s + W_CONIFER * c["conifer"]
        lo, hi = LANDFORM[n.landform]; r = c["relief"] + 50.0
        s = s + W_L * 4 * np.where(r < lo + 50, np.log((lo + 50) / r), np.where(r > hi + 50, np.log(r / (hi + 50)), 0)) ** 2
        if n.landform == "highland": s = s + W_L * np.clip((HIGHLAND_MIN_Z - c["zr"]) / HIGHLAND_MIN_Z, 0, 1)
        if n.landform == "cliff": s = s + np.where(c["relief"] < 900, 1e3, 0)          # rule 5: terrain-feature biomes need the terrain
        s = s + W_S * (c["snow"] != n.snow) + n.extra
        s = s + np.where(c["wet"] != n.wet, 1e3, 0)
        if n.coast: s = s + np.where(c["coast"], 0, 1e3)
        if n.realms is not None: s = s + np.where(np.isin(c["realm"], n.realms), 0, 1e3)
        s = s - JITTER * value_noise(c["xm"], c["ym"], NOISE_M, n.seed)
        return s

    def pick(self, c):
        """Index into self.ids per cell. Wet cells with no fitting wetland biome fall back to dry-land picks."""
        best = np.full(c["theta"].shape, np.inf, np.float32); arg = np.zeros(c["theta"].shape, np.int16)
        for i, n in enumerate(self.niches):
            s = self.scores(n, c); m = s < best; best[m] = s[m]; arg[m] = i
        bad = c["wet"] & (best > 500)
        if bad.any():
            c2 = {k: (v[bad] if isinstance(v, np.ndarray) and v.shape == bad.shape else v) for k, v in c.items()}
            c2["wet"] = np.zeros(int(bad.sum()), bool); arg[bad] = self.pick(c2)
        return arg

# Potential natural vegetation prior: woody cover per RESOLVE biome type (BIOME_NUM). Climate alone misses fire,
# soils and seasonality (prairies and pampas sit at MI ~1; montane and xeric shrublands stay open), so the cell's
# present-day ecoregion type pulls its cover toward what grows there now. 0 = no prior (rock and ice, lakes, sea).
PNV_COVER = {1: 0.9, 2: 0.6, 3: 0.75, 4: 0.8, 5: 0.75, 6: 0.65, 7: 0.25, 8: 0.1, 9: 0.1, 10: 0.08, 11: 0.03, 12: 0.4, 13: 0.08, 14: 0.85}
W_PNV = 0.75

def resolve_grid(shp, cache):
    """RESOLVE BIOME_NUM on the 10' globe grid (1080 x 2160, row 0 at 90 N); land the polygons miss takes the nearest."""
    if os.path.exists(cache): return np.load(cache)
    import shapefile
    from rasterio import features, transform
    sf = shapefile.Reader(shp, encoding="latin-1")
    shapes = [(sr.shape.__geo_interface__, int(sr.record["BIOME_NUM"])) for sr in sf.iterShapeRecords() if 1 <= int(sr.record["BIOME_NUM"]) <= 14]
    g = features.rasterize(shapes, out_shape=(1080, 2160), transform=transform.from_origin(-180, 90, 1 / 6, 1 / 6), fill=0, dtype="uint8",
                           all_touched=True)
    idx = ndi.distance_transform_edt(g == 0, return_distances=False, return_indices=True)
    g = g[tuple(idx)]
    np.save(cache, g); return g

class Wetland:
    """Rule 3: wetland = flat low land on a large river's floodplain or by a lake, or barely above the sea, in a moist
    climate. Patchy: the share of a floodplain that is wetland grows with the river (noise threshold)."""
    def __init__(self, hydro_npz, ee_fwd):
        h = np.load(hydro_npz); A = np.where(h["river"], h["A"], 0).astype(np.float32)
        self.XM = float(ee_fwd(np.array(11.0 + 179.999), np.array(0.0))[0]) / 1000; self.YM = float(ee_fwd(np.array(0.0), np.array(90.0))[1]) / 1000
        # floodplain half-width grows with the river: 5 km at 20,000 km2 upstream, 50 km at 2,000,000 km2
        self.fpA = np.zeros(A.shape, np.float32)
        for amin, rk in ((2e4, 1), (1e5, 2), (5e5, 5), (2e6, 10)):
            self.fpA = np.maximum(self.fpA, np.where(ndi.binary_dilation(A >= amin, iterations=rk), amin, 0))
        self.lake = ndi.binary_dilation(h["lake"], iterations=1)
        self.ny, self.nx = A.shape
    def mask(self, xb, zb, MPB, relief, zr, MI, xm, ym):
        xk = xb * MPB / 1000; yk = -zb * MPB / 1000
        i = np.clip(np.floor((xk + self.XM) / 5.0).astype(int), 0, self.nx - 1); j = np.clip(np.floor((self.YM - yk) / 5.0).astype(int), 0, self.ny - 1)
        a = self.fpA[j, i]; lk = self.lake[j, i]
        share = np.where(a > 0, np.clip(0.3 + 0.12 * np.log10(np.maximum(a, 1) / 2e4), 0.3, 0.6), 0) + 0.4 * lk
        patch = value_noise(xm, ym, 20000.0, 4242) < share
        flat = (relief < 80) & (zr < 300)
        return flat & patch & ((MI >= 1.0) | ((a >= 5e5) & (MI >= 0.6))) | ((zr < 4) & (relief < 30) & (MI >= 0.9))
