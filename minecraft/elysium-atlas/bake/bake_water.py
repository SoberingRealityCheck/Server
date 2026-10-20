"""Bake rivers and lakes for an existing atlas: writes ATLAS/water.bin.gz and adds "water" to atlas.json.

Rivers: Natural Earth 10m centrelines plus the Europe supplement, oriented and sized from hydro_v2
(5 km grid: Q, A). Water level per vertex = running minimum of atlas terrain from the source, so it
never rises downstream. Lakes: Natural Earth 10m lakes plus the Europe supplement; level = low
percentile of atlas terrain inside the outline (the DEM stores the lake surface).

Usage: python3 bake_water.py ATLAS_DIR NE_DIR HYDRO_NPZ [ATLAS_VERSION]
Water changes terrain, so give the atlas a new version (the mod warns when a world's atlas changes).
"""
import gzip, json, math, os, struct, sys, time
import numpy as np
import shapely
from shapely.geometry import shape, LineString, Polygon, MultiPolygon
from shapely.strtree import STRtree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from bake_atlas import ee_fwd, MPB, SEA_Y  # noqa: E402

# ---- frozen parameters (changing any changes terrain: bump the atlas version)
WATER_FORMAT = 1
DENSIFY = 8.0            # blocks between river vertices
SEG_OUT = 16.0           # blocks between output river vertices
MIN_HALF_WIDTH = 4.0     # density terrain is interpolated over 4-block cells, so narrower channels vanish
MAX_HALF_WIDTH = 32.0
Q_FLOOR = 20.0           # m3/s; every NE river is at least this big
MIN_LAKE_AREA = 16 * 16  # blocks^2
BUCKET = 64              # spatial index cell in blocks (Java uses the same)
LAKE_REACH = 128         # lake edges are indexed this far out; interior buckets cover the rest
HYDRO_RES_KM = 5.0


def half_width(q):
    return float(np.clip(1.8 * q ** 0.28, MIN_HALF_WIDTH, MAX_HALF_WIDTH))


def channel_depth(hw):
    return float(np.clip(2.0 + 0.25 * hw, 3.0, 10.0))


def lake_depth(area_blocks):
    return float(np.clip(0.15 * math.sqrt(area_blocks), 3.0, 48.0))


def to_blocks(lon, lat):
    x, y = ee_fwd(np.asarray(lon, np.float64), np.asarray(lat, np.float64))
    return x / MPB, -y / MPB


# ---- atlas sampler (bilinear on cell centres; finest level first, like Atlas.height)
class AtlasSampler:
    def __init__(self, d):
        self.d = d; m = json.load(open(os.path.join(d, "atlas.json")))
        self.levels = sorted(m["levels"], key=lambda l: l["cell"]); self.tile = m["tile_size"]; self.cache = {}

    def _tile(self, lv, tx, tz):
        k = (lv["name"], tx, tz)
        if k not in self.cache:
            p = os.path.join(self.d, lv["dir"], f"{tx}_{tz}.bin.gz"); t = None
            if os.path.exists(p):
                raw = gzip.open(p).read(); n = self.tile * self.tile
                t = np.frombuffer(raw[8:8 + 2 * n], "<i2").reshape(self.tile, self.tile)
            self.cache[k] = t
        return self.cache[k]

    def _cells(self, lv, i, j):
        T = self.tile; out = np.full(i.shape, -32768, np.int32)
        tx, tz = i // T, j // T
        for a, b in set(zip(tx.tolist(), tz.tolist())):
            t = self._tile(lv, a, b)
            if t is None: continue
            m = (tx == a) & (tz == b); out[m] = t[j[m] - b * T, i[m] - a * T]
        return out

    def height(self, x, z):
        x = np.asarray(x, np.float64); z = np.asarray(z, np.float64); res = np.full(x.shape, np.nan)
        for lv in self.levels:
            todo = np.isnan(res)
            if not todo.any(): break
            c = lv["cell"]; u = x[todo] / c - 0.5; v = z[todo] / c - 0.5
            i = np.floor(u).astype(np.int64); j = np.floor(v).astype(np.int64); fu = u - i; fv = v - j
            h00 = self._cells(lv, i, j); h10 = self._cells(lv, i + 1, j); h01 = self._cells(lv, i, j + 1); h11 = self._cells(lv, i + 1, j + 1)
            ok = (h00 > -32768) & (h10 > -32768) & (h01 > -32768) & (h11 > -32768)
            val = ((h00 * (1 - fu) + h10 * fu) * (1 - fv) + (h01 * (1 - fu) + h11 * fu) * fv) / 8.0
            r = res[todo]; r[ok] = val[ok]; res[todo] = r
        return res


# ---- hydro_v2 grid (5 km Equal Earth, same projection; km units, y up)
class Hydro:
    def __init__(self, path):
        d = np.load(path); self.Q = d["Q"]; self.A = d["A"]
        ny, nx = self.Q.shape
        self.XM = float(ee_fwd(np.array(11.0 + 179.999), np.array(0.0))[0]) / 1000; self.YM = float(ee_fwd(np.array(0.0), np.array(90.0))[1]) / 1000
        self.nx, self.ny = nx, ny

    def sample(self, bx, bz, arr, r=1):
        xk = np.asarray(bx) * MPB / 1000; yk = -np.asarray(bz) * MPB / 1000
        i = np.floor((xk + self.XM) / HYDRO_RES_KM).astype(int); j = np.floor((self.YM - yk) / HYDRO_RES_KM).astype(int)
        best = np.zeros(i.shape, np.float64)
        for dj in range(-r, r + 1):
            for di in range(-r, r + 1):
                ii = np.clip(i + di, 0, self.nx - 1); jj = np.clip(j + dj, 0, self.ny - 1)
                best = np.maximum(best, arr[jj, ii])
        return best


def load_features(ne, name):
    return json.load(open(os.path.join(ne, name + ".geojson")))["features"]


def project(geom):
    return shapely.transform(geom, lambda c: np.column_stack(to_blocks(c[:, 0], c[:, 1])))


def bake_lakes(ne, atlas):
    main = [f for f in load_features(ne, "ne_10m_lakes") if f["geometry"]]
    eu = [f for f in load_features(ne, "ne_10m_lakes_europe") if f["geometry"]]
    polys = []
    for src, fs in (("main", main), ("eu", eu)):
        for f in fs:
            g = shape(f["geometry"])
            if not g.is_valid: g = g.buffer(0)
            polys.append((src, f["properties"].get("name") or "", g))
    main_tree = STRtree([g for s, _, g in polys if s == "main"])
    lakes, t0 = [], time.time()
    for src, name, g in polys:
        if src == "eu":
            rp = g.representative_point()
            if len(main_tree.query(rp, predicate="within")): continue
        pb = project(g)
        if not pb.is_valid: pb = pb.buffer(0)
        for p in (pb.geoms if isinstance(pb, MultiPolygon) else [pb]):
            if p.area < MIN_LAKE_AREA: continue
            lakes.append((name, shapely.geometry.polygon.orient(p, 1.0)))
    # level: the DEM stores either the flat lake surface or (big lakes) bathymetry. Flat interior -> its
    # median; otherwise just under the shore. Never above the low shore points, or the water spills.
    out = []
    for name, p in lakes:
        minx, minz, maxx, maxz = p.bounds; step = max(4.0, math.sqrt(p.area) / 24)
        gx, gz = np.meshgrid(np.arange(minx + step / 2, maxx, step), np.arange(minz + step / 2, maxz, step))
        inside = shapely.contains_xy(p, gx, gz)
        if not inside.any():
            c = p.representative_point(); gx, gz, inside = np.array([c.x]), np.array([c.y]), np.array([True])
        hi = atlas.height(gx[inside], gz[inside]); hi = hi[~np.isnan(hi)]
        ring = p.buffer(3).exterior; n = int(max(16, ring.length / 8))
        sp = np.array([ring.interpolate(t, normalized=True).coords[0] for t in np.linspace(0, 1, n, endpoint=False)])
        hs = atlas.height(sp[:, 0], sp[:, 1]); hs = hs[~np.isnan(hs)]
        if len(hi) == 0 or len(hs) == 0: continue
        p20, p50 = np.percentile(hi, [20, 50]); shore = math.floor(np.percentile(hs, 5))
        level = min(math.floor(p50) + 1 if p50 - p20 < 1.5 else shore - 1, shore)
        level = max(level, SEA_Y)  # a lake at sea level merges with the sea
        out.append({"name": name, "poly": p, "level": level, "depth": lake_depth(p.area)})
    print(f"lakes: {len(out)} kept of {len(polys)} ({time.time() - t0:.0f} s)", flush=True)
    return out


def densify(coords, step):
    c = np.asarray(coords, np.float64)
    if len(c) < 2: return c
    seg = np.hypot(*np.diff(c, axis=0).T); out = [c[0]]
    for k in range(len(seg)):
        n = max(1, int(math.ceil(seg[k] / step)))
        for t in range(1, n + 1): out.append(c[k] + (c[k + 1] - c[k]) * t / n)
    return np.array(out)


def bake_rivers(ne, atlas, hydro, lakes):
    main = [f for f in load_features(ne, "ne_10m_rivers_lake_centerlines") if f["geometry"]]
    eu = [f for f in load_features(ne, "ne_10m_rivers_europe") if f["geometry"]]
    lines = []
    for src, fs in (("main", main), ("eu", eu)):
        for f in fs:
            g = shape(f["geometry"])
            for ls in (g.geoms if g.geom_type == "MultiLineString" else [g]):
                lb = project(ls)
                if lb.length >= 16: lines.append((src, f["properties"].get("name") or "", lb))
    # Europe lines that retrace a main line would cut a second channel beside it
    main_geoms = [g for s, _, g in lines if s == "main"]; eu_geoms = [g for s, _, g in lines if s == "eu"]
    env = shapely.union_all(eu_geoms).envelope.buffer(64)
    near_main = shapely.union_all([g for g in main_geoms if g.intersects(env)]).buffer(12)
    shapely.prepare(near_main)
    kept = []
    for src, name, lb in lines:
        if src == "eu":
            pts = densify(lb.coords, 64)
            if shapely.contains_xy(near_main, pts[:, 0], pts[:, 1]).mean() > 0.5: continue
        kept.append((name, lb))
    lake_tree = STRtree([l["poly"] for l in lakes])
    segs, t0 = [], time.time()
    for name, lb in kept:
        c = densify(lb.coords, DENSIFY)
        if len(c) < 2: continue
        # orient downstream: drainage area grows downstream
        a_end = hydro.sample(c[[0, -1], 0], c[[0, -1], 1], hydro.A, r=2)
        h_end = atlas.height(c[[0, -1], 0], c[[0, -1], 1])
        if a_end[0] > a_end[1] * 1.05 or (abs(a_end[0] - a_end[1]) <= a_end[1] * 0.05 and np.nan_to_num(h_end[0]) < np.nan_to_num(h_end[1])):
            c = c[::-1]
        h = atlas.height(c[:, 0], c[:, 1])
        if np.isnan(h).all(): continue
        h = np.where(np.isnan(h), SEA_Y - 8, h)
        q = np.maximum.accumulate(np.maximum(hydro.sample(c[:, 0], c[:, 1], hydro.Q, r=1), Q_FLOOR))
        # lake membership per vertex
        in_lake = np.full(len(c), -1)
        for k in lake_tree.query(lb.buffer(1)):
            m = shapely.contains_xy(lakes[k]["poly"], c[:, 0], c[:, 1]); in_lake[m] = k
        level = np.empty(len(c)); cur = np.inf
        for k in range(len(c)):
            if in_lake[k] >= 0: cur = lakes[in_lake[k]]["level"]
            else: cur = min(cur, math.floor(h[k]) - 1)
            level[k] = max(cur, SEA_Y)
        # resample to output spacing, keep runs outside lakes
        step = max(1, int(round(SEG_OUT / DENSIFY)))
        idx = list(range(0, len(c), step))
        if idx[-1] != len(c) - 1: idx.append(len(c) - 1)
        for a, b in zip(idx[:-1], idx[1:]):
            if in_lake[a] >= 0 and in_lake[b] >= 0: continue
            hw0, hw1 = half_width(q[a]), half_width(q[b])
            segs.append((c[a, 0], c[a, 1], c[b, 0], c[b, 1], level[a], level[b], hw0, hw1, channel_depth(max(hw0, hw1))))
    print(f"rivers: {len(kept)} lines, {len(segs)} segments ({time.time() - t0:.0f} s)", flush=True)
    return segs


def lake_edges_and_interior(lakes):
    edges, interior = [], {}
    for li, l in enumerate(lakes):
        p = l["poly"]
        for ring in [p.exterior] + list(p.interiors):
            c = np.asarray(ring.coords)
            for k in range(len(c) - 1): edges.append((c[k, 0], c[k, 1], c[k + 1, 0], c[k + 1, 1], li))
        # buckets entirely inside: centre inside and farther than the half-diagonal from the shore
        minx, minz, maxx, maxz = p.bounds
        bx = np.arange(math.floor(minx / BUCKET), math.ceil(maxx / BUCKET)); bz = np.arange(math.floor(minz / BUCKET), math.ceil(maxz / BUCKET))
        if len(bx) * len(bz) == 0: continue
        gx, gz = np.meshgrid(bx, bz); cx = (gx + 0.5) * BUCKET; cz = (gz + 0.5) * BUCKET
        ins = shapely.contains_xy(p, cx, cz)
        if not ins.any(): continue
        d = shapely.distance(p.exterior, shapely.points(cx[ins], cz[ins]))
        for h in p.interiors: d = np.minimum(d, shapely.distance(h, shapely.points(cx[ins], cz[ins])))
        for X, Z, dd in zip(gx[ins], gz[ins], d):
            if dd > BUCKET * 0.7072: interior[(int(X), int(Z))] = li
    return edges, interior


def main():
    atlas_dir, ne, hydro_npz = sys.argv[1:4]
    atlas = AtlasSampler(atlas_dir); hydro = Hydro(hydro_npz)
    lakes = bake_lakes(ne, atlas)
    segs = bake_rivers(ne, atlas, hydro, lakes)
    edges, interior = lake_edges_and_interior(lakes)
    out = os.path.join(atlas_dir, "water.bin.gz")
    with gzip.open(out, "wb", compresslevel=6) as f:
        f.write(b"EWAT" + struct.pack("<HHi", WATER_FORMAT, BUCKET, LAKE_REACH))
        f.write(struct.pack("<i", len(segs)))
        f.write(np.asarray(segs, "<f4").tobytes())
        f.write(struct.pack("<i", len(lakes)))
        for l in lakes: f.write(struct.pack("<if", l["level"], l["depth"]))
        f.write(struct.pack("<i", len(edges)))
        e = np.asarray(edges, np.float64)
        f.write(e[:, :4].astype("<f4").tobytes()); f.write(e[:, 4].astype("<i4").tobytes())
        f.write(struct.pack("<i", len(interior)))
        f.write(np.asarray([(k[0], k[1], v) for k, v in interior.items()], "<i4").tobytes())
    m = json.load(open(os.path.join(atlas_dir, "atlas.json")))
    if len(sys.argv) > 4: m["atlas_version"] = sys.argv[4]
    m["water"] = {"file": "water.bin.gz", "format": WATER_FORMAT, "rivers": len(segs), "lakes": len(lakes),
                  "sources": "Natural Earth 10m rivers, lakes and Europe supplements; hydro_v2 warm Q and A"}
    json.dump(m, open(os.path.join(atlas_dir, "atlas.json"), "w"), indent=1)
    summary = {"segments": len(segs), "lakes": len(lakes), "edges": len(edges), "interior_buckets": len(interior),
               "bytes": os.path.getsize(out)}
    for l in lakes:
        if l["name"] in ("Lake Geneva", "Bodensee", "Lago di Garda", "Lake Superior"): summary[l["name"]] = {"level": l["level"], "depth": round(l["depth"], 1)}
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
