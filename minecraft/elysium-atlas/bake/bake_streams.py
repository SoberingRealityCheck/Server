"""Small streams for bake_water.py: the hydro_v2 drainage network below the Natural Earth rivers.

Network: each 5 km cell drains to the neighbour with the largest drainage area A above its own, so A
grows strictly downstream (no cycles). Cells with A >= STREAM_MIN_AREA that no NE river line crosses and are not lake, sea
or ice cells are streams. Chains run from a head or junction to the next junction or exit.
Geometry: each cell centre moves to the lowest atlas point within SNAP blocks (per cell, so chains that
share a junction share its point), then corner cutting and a meander that fades out at both ends.
Levels: running minimum of atlas terrain from the chain start, never below the level where it ends
(the downstream chain's start, the NE river or lake it joins, or the sea).
"""
import math, time
import numpy as np
import shapely, shapely.ops
from shapely.strtree import STRtree

from bake_atlas import MPB, SEA_Y

# ---- frozen parameters (changing any changes terrain: bump the atlas version)
STREAM_MIN_AREA = 150.0   # km2
STREAM_HALF_WIDTH = 4.0   # the narrowest channel density terrain keeps (4-block interpolation)
STREAM_DEPTH = 3.0
HEAD_DEPTH = 1.5          # first segment of a chain that starts at a head
SNAP = 12.0               # blocks
MEANDER_AMP = 5.0
MEANDER_WAVE = 80.0
MEANDER_FADE = 40.0
JOIN_REACH = 200.0        # blocks from an exit cell to the NE river or lake it joins
DENSIFY = 8.0
SEG_OUT = 16.0
NB = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def receivers(A):
    ny, nx = A.shape; best = np.full(A.shape, -1, np.int64); bestA = A.astype(np.float64).copy()
    flat = np.arange(ny * nx).reshape(ny, nx)
    P = np.pad(A.astype(np.float64), 1, constant_values=-1); F = np.pad(flat, 1, constant_values=-1)
    for dj, di in NB:
        a = P[1 + dj:1 + dj + ny, 1 + di:1 + di + nx]; f = F[1 + dj:1 + dj + ny, 1 + di:1 + di + nx]
        m = a > bestA; bestA[m] = a[m]; best[m] = f[m]
    return best.ravel()


def chaikin(c, n=2):
    for _ in range(n):
        if len(c) < 3: break
        q = 0.75 * c[:-1] + 0.25 * c[1:]; r = 0.25 * c[:-1] + 0.75 * c[1:]
        mid = np.empty((2 * len(q), 2)); mid[0::2] = q; mid[1::2] = r
        c = np.vstack([c[:1], mid, c[-1:]])
    return c


def resample(c, step):
    s = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(c, axis=0).T))])
    if s[-1] <= 0: return c[:1], s[:1]
    t = np.linspace(0, s[-1], max(2, int(math.ceil(s[-1] / step)) + 1))
    return np.column_stack([np.interp(t, s, c[:, 0]), np.interp(t, s, c[:, 1])]), t


def bake_streams(atlas, hydro, river_segs, lakes, bbox=None):
    t0 = time.time()
    A, Q = hydro.A, hydro.Q; ny, nx = A.shape
    rs = np.asarray(river_segs, np.float64)
    # NE river cells: the cells the baked river lines pass through (hydro.river marks more cells than the
    # lines cover, which would leave the heads of NE rivers without tributaries)
    riv = np.zeros(ny * nx, bool)
    if len(rs):
        t = np.linspace(0, 1, 5)[:, None]
        px = (rs[:, 0] + t * (rs[:, 2] - rs[:, 0])).ravel(); pz = (rs[:, 1] + t * (rs[:, 3] - rs[:, 1])).ravel()
        i = np.floor((px * MPB / 1000 + hydro.XM) / 5.0).astype(np.int64); j = np.floor((hydro.YM + pz * MPB / 1000) / 5.0).astype(np.int64)
        ok = (i >= 0) & (i < nx) & (j >= 0) & (j < ny); riv[j[ok] * nx + i[ok]] = True
    other = (hydro.sea | hydro.ice | hydro.lake).ravel() | riv
    S = (A.ravel() >= STREAM_MIN_AREA) & ~other
    rec = receivers(A)
    # cell centre in blocks (hydro grid: 5 km, row 0 at the top, same Equal Earth as the atlas)
    def centre(cells):
        j, i = np.divmod(cells, nx)
        xk = -hydro.XM + (i + 0.5) * 5.0; yk = hydro.YM - (j + 0.5) * 5.0
        return np.column_stack([xk * 1000 / MPB, -yk * 1000 / MPB])
    if bbox is not None:
        cc = centre(np.flatnonzero(S)); keep = (cc[:, 0] >= bbox[0]) & (cc[:, 0] <= bbox[2]) & (cc[:, 1] >= bbox[1]) & (cc[:, 1] <= bbox[3])
        idx = np.flatnonzero(S); S[:] = False; S[idx[keep]] = True
    cells = np.flatnonzero(S)
    indeg = np.bincount(rec[cells][rec[cells] >= 0], minlength=ny * nx)
    starts = cells[indeg[cells] != 1]

    chains = []
    for s in starts:
        path = [s]; cur = s; end = "pit"
        while True:
            n = rec[cur]
            if n < 0: break
            path.append(n)
            if not S[n]: end = "exit"; break
            if indeg[n] != 1: end = "junction"; break
            cur = n
        if len(path) >= 2: chains.append((np.array(path), end, indeg[s] == 0))
    print(f"streams: {len(cells)} cells, {len(chains)} chains", flush=True)

    # per-cell snapped point: lowest atlas height on a 5x5 grid within SNAP
    used = np.unique(np.concatenate([c for c, _, _ in chains])) if chains else np.zeros(0, np.int64)
    base = centre(used); off = np.linspace(-SNAP, SNAP, 5)
    ox, oz = np.meshgrid(off, off); ox = ox.ravel(); oz = oz.ravel()
    hs = atlas.height((base[:, 0:1] + ox).ravel(), (base[:, 1:2] + oz).ravel()).reshape(len(used), -1)
    hs = np.where(np.isnan(hs), np.inf, hs); k = np.argmin(hs + 0.01 * np.hypot(ox, oz), axis=1)
    snapped = base + np.column_stack([ox[k], oz[k]])
    pos = {int(c): snapped[n] for n, c in enumerate(used)}

    # where exits join: NE river segments (level along the segment) and lakes
    rtree = STRtree(shapely.linestrings(np.stack([rs[:, 0:2], rs[:, 2:4]], axis=1))) if len(rs) else None
    ltree = STRtree([l["poly"] for l in lakes])

    def join(p, cell):
        """Point and level where an exit cell's chain ends."""
        if hydro.sea.ravel()[cell]: return p, float(SEA_Y)
        pt = shapely.points(p[0], p[1])
        if rtree is not None:
            k = rtree.query_nearest(pt, max_distance=JOIN_REACH)
            if len(k):
                s = rs[k[0]]; a, b = s[0:2], s[2:4]; d = b - a; L2 = d @ d
                t = 0.0 if L2 == 0 else float(np.clip((p - a) @ d / L2, 0, 1))
                return a + t * d, float(s[4] + t * (s[5] - s[4]))
        k = ltree.query_nearest(pt, max_distance=JOIN_REACH)
        if len(k):
            l = lakes[k[0]]; q = shapely.ops.nearest_points(l["poly"], pt)[0]
            return np.array([q.x, q.y]), float(l["level"])
        stats["unjoined"] += 1
        return p, None

    # downstream chains first, so a tributary knows the level at its junction
    order = sorted(range(len(chains)), key=lambda n: -float(A.ravel()[chains[n][0][0]]))
    start_level, segs, stats = {}, [], {"unjoined": 0, "pits": sum(e == "pit" for _, e, _ in chains)}
    for n in order:
        path, end, head = chains[n]
        c = np.array([pos[int(x)] if int(x) in pos else centre(np.array([x]))[0] for x in path])
        end_level = None
        if end == "junction": end_level = start_level.get(int(path[-1]))
        elif end == "exit": c[-1], end_level = join(c[-1], int(path[-1]))
        c = chaikin(c)
        c, s = resample(c, DENSIFY)
        if len(c) < 2: continue
        L = s[-1]; ph = (int(path[0]) * 2654435761 % 4096) / 4096 * 2 * math.pi
        fade = np.clip(np.minimum(s, L - s) / MEANDER_FADE, 0, 1)
        tan = np.gradient(c, axis=0); tan /= np.maximum(np.hypot(tan[:, 0], tan[:, 1]), 1e-9)[:, None]
        c = c + np.column_stack([-tan[:, 1], tan[:, 0]]) * (MEANDER_AMP * np.sin(2 * math.pi * s / MEANDER_WAVE + ph) * fade)[:, None]
        # lakes along the way end the chain at the shore
        inl = np.zeros(len(c), bool); lake_lv = None
        line = shapely.linestrings(c)
        for k in ltree.query(line):
            m = shapely.contains_xy(lakes[k]["poly"], c[:, 0], c[:, 1])
            if m.any() and (not inl.any() or np.argmax(m) < np.argmax(inl)): inl = m; lake_lv = float(lakes[k]["level"])
        if inl.any():
            cut = int(np.argmax(inl)); c = c[:cut + 1]; end_level = lake_lv
            if len(c) < 2: continue
        h = atlas.height(c[:, 0], c[:, 1])
        if np.isnan(h).all(): continue
        h = np.where(np.isnan(h), SEA_Y, h)
        level = np.maximum(np.minimum.accumulate(np.floor(h) - 1), SEA_Y)
        if end_level is not None: level = np.maximum(level, end_level); level[-1] = end_level
        start_level[int(path[0])] = float(level[0])
        st = max(1, int(round(SEG_OUT / DENSIFY))); idx = list(range(0, len(c), st))
        if idx[-1] != len(c) - 1: idx.append(len(c) - 1)
        for m, (a, b) in enumerate(zip(idx[:-1], idx[1:])):
            dep = HEAD_DEPTH if head and m == 0 else STREAM_DEPTH
            segs.append((c[a, 0], c[a, 1], c[b, 0], c[b, 1], level[a], level[b], STREAM_HALF_WIDTH, STREAM_HALF_WIDTH, dep))
    print(f"streams: {len(segs)} segments, {stats} ({time.time() - t0:.0f} s)", flush=True)
    return segs
