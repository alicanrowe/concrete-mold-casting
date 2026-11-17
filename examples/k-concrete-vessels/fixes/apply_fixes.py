#!/usr/bin/env python3
"""Apply the moldcheck fixes to the K mold STLs (2026-10-26 engraved set) -> new set.

1. Pour path: cut the lid ring off D1-D4 over the wall gap (r 89.4-115.5, z 457.2 up) and add a
   riser collar (r 115.5-121.85, z 457.2-495) to each D piece's sector, so the funnel feeds the wall.
2. Windows (70 and 290 deg): extend the core skin from d 186 mm to the shell's flat wall (d 208.4),
   following the vessel's inner surface (shell inner surface minus the measured core gap,
   extrapolated linearly), 6.35 mm skin, split among the core pieces that end there.
3. Core floor vents: plug the eight 9 mm holes in KA1-KA6.
4. Core hold-down: a 2x6 bridge on the cap and two 3/8-16 rods to a bench board (new parts).
"""
import glob, os, sys, json
import numpy as np, trimesh, manifold3d as mf

SRC, OUT = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT, exist_ok=True)


def M(m):
    return mf.Manifold(mf.Mesh(vert_properties=np.asarray(m.vertices, np.float32),
                               tri_verts=np.asarray(m.faces, np.uint32)))


def T(man):
    m = man.to_mesh()
    return trimesh.Trimesh(np.asarray(m.vert_properties)[:, :3], np.asarray(m.tri_verts), process=False)


def annulus(r0, r1, z0, z1, seg=256):
    return mf.Manifold.cylinder(z1 - z0, r1, r1, seg).translate([0, 0, z0]) - \
        mf.Manifold.cylinder(z1 - z0 + 2, r0, r0, seg).translate([0, 0, z0 - 1])


def wedge(a0, a1, r=600, z0=-600, z1=900):
    """prism over the sector a0..a1 degrees (ccw)"""
    angs = np.radians(np.linspace(a0, a1, 64))
    poly = [[0, 0]] + [[r * np.cos(a), r * np.sin(a)] for a in angs]
    cs = mf.CrossSection([poly])
    return mf.Manifold.extrude(cs, z1 - z0).translate([0, 0, z0])


parts = {os.path.basename(f)[:-4]: trimesh.load(f) for f in sorted(glob.glob(os.path.join(SRC, "*.stl")))}
man = {k: M(v) for k, v in parts.items()}
log = {}

# ---- 1. rim: open the lid, add the riser collar
cut = annulus(85.0, 115.5, 457.13, 496)
collar = annulus(115.5, 121.85, 457.13, 495.0)
for k in [k for k in man if k.startswith("D")]:
    v = parts[k].vertices
    top = v[v[:, 2] > 450]
    ang = np.degrees(np.arctan2(top[:, 1], top[:, 0]))
    c = {"D1": 90, "D2": 180, "D3": 270, "D4": 0}[k[:2]]
    rel = (ang - c + 180) % 360 - 180
    a0, a1 = c + rel.min(), c + rel.max()
    before = man[k].volume()
    man[k] = (man[k] - cut) + (collar ^ wedge(a0, a1))
    log[k] = f"lid ring cut (r 85-115.5 mm, z 457.2 up), riser collar added over {a0:.1f}..{a1:.1f} deg; volume {before/1e3:.1f} -> {man[k].volume()/1e3:.1f} cm3"
# collar pieces must not overlap each other
ds = sorted(k for k in man if k.startswith("D"))
for i, a in enumerate(ds):
    for b in ds[i + 1:]:
        ov = (man[a] ^ man[b]).volume()
        if ov > 1:
            man[b] = man[b] - man[a]

# ---- 2. window collars (core skin to the flat wall) and ledges (flat wall inward, so the skin seats on it)
from shapely.geometry import LineString
CU, CZ = 0.0, -85.0
SKIN = 6.35
D_END = 208.52
LEDGE_IN = 8.5      # ledge reaches this far inside the collar's outer edge
LEDGE_OVER = 1.5    # and overlaps the existing flat wall by this much


def grown(k):
    c0 = np.asarray(parts[k].centroid) if k in parts else np.zeros(3)
    return man[k].translate(list(-c0)).scale([1.0006, 1.0006, 1.0006]).translate(list(c0))


def ring_tube(n, t, z, dd, RO, RI):
    nd, nt = len(dd), RO.shape[1]
    th = np.radians(np.arange(nt) * 360.0 / nt)
    V = []
    for rr in (RO, RI):
        for i, d in enumerate(dd):
            V.append(n * d + np.outer(CU + rr[i] * np.cos(th), t) + np.outer(CZ + rr[i] * np.sin(th), z))
    V = np.vstack(V)
    io = lambda i, j: i * nt + (j % nt)
    ii = lambda i, j: nd * nt + i * nt + (j % nt)
    F = []
    for i in range(nd - 1):
        for j in range(nt):
            F += [[io(i, j), io(i + 1, j), io(i + 1, j + 1)], [io(i, j), io(i + 1, j + 1), io(i, j + 1)]]
            F += [[ii(i, j), ii(i + 1, j + 1), ii(i + 1, j)], [ii(i, j), ii(i, j + 1), ii(i + 1, j + 1)]]
    for j in range(nt):
        F += [[io(0, j), io(0, j + 1), ii(0, j + 1)], [io(0, j), ii(0, j + 1), ii(0, j)]]
        F += [[io(nd - 1, j), ii(nd - 1, j + 1), io(nd - 1, j + 1)], [io(nd - 1, j), ii(nd - 1, j), ii(nd - 1, j + 1)]]
    tm = trimesh.Trimesh(V, F, process=True)
    if tm.volume < 0:
        tm.invert()
    assert tm.is_watertight
    return M(tm)


def sector(n, t, z, j0, j1):
    angs = np.radians(np.linspace(j0 - 0.5, j1 - 0.5, max(4, j1 - j0 + 1)))
    poly = [[0, 0]] + [[700 * np.cos(q), 700 * np.sin(q)] for q in angs]
    pr = mf.Manifold.extrude(mf.CrossSection([poly]), 120).translate([0, 0, 120])
    mat = np.c_[np.c_[t, z, n], t * CU + z * CZ]
    return pr.transform(np.array(mat, dtype=np.float64))


def runs_of(owners):
    nt = len(owners); runs, start = [], 0
    for j in range(1, nt + 1):
        if j == nt or owners[j] != owners[start]:
            runs.append((owners[start], start, j)); start = j
    if len(runs) > 1 and runs[0][0] == runs[-1][0]:
        k0, s0, e0 = runs.pop(); k1, s1, e1 = runs.pop(0); runs.append((k0, s0, e1 + 360))
    return runs


def near(k, f=1.012):
    c0 = np.asarray(parts[k].centroid)
    return man[k].translate(list(-c0)).scale([f, f, f]).translate(list(c0))


def attach(seg, key, family, note):
    """union seg into key; any piece of seg that doesn't touch key goes to the family member it is nearest"""
    for other in [o for o in man if o != key and o[0] in family]:
        seg = seg - grown(other)
    for comp in seg.decompose():
        if comp.volume() < 1:
            continue
        tgt = key
        if (comp ^ man[key]).volume() < 0.5:
            cands = [o for o in man if o[0] in family and o in parts]
            tgt = max(cands, key=lambda o: (comp ^ near(o)).volume())
        before = man[tgt].volume()
        man[tgt] = man[tgt] + comp
        log.setdefault(tgt, "")
        log[tgt] += f" {note} (+{(man[tgt].volume()-before)/1e3:.1f} cm3);"


for A in (70, 290):
    r = np.load(os.path.join(HERE, f"rho{A}.npz"), allow_pickle=True)
    s = np.load(os.path.join(HERE, f"shell{A}.npz"))
    D, out, own = r["D"], r["out"], r["own"]
    S, DS = s["sin"], list(s["D"])
    G = S[[DS.index(d) for d in D]] - out
    fit = (D >= 150) & (D <= 188)
    P = np.array([np.polyfit(D[fit], G[fit, j], 1) for j in range(360)])
    Q = np.array([np.polyfit(np.array(DS)[-3:], S[-3:, j], 1) for j in range(360)])
    a = np.radians(A); n = np.array([np.cos(a), np.sin(a), 0]); t = np.array([-np.sin(a), np.cos(a), 0]); z = np.array([0, 0, 1.0])

    def ro_at(d):
        sh = np.array([np.interp(d, DS, S[:, j]) if d <= DS[-1] else Q[j, 0] * d + Q[j, 1] for j in range(360)])
        return sh - (P[:, 0] * d + P[:, 1])

    dd = np.r_[np.arange(186.0, D_END, 1.5), D_END]
    RO = np.array([ro_at(d) for d in dd])
    tube = ring_tube(n, t, z, dd, RO, RO - SKIN)
    for owner, j0, j1 in runs_of(own[list(D).index(188.0)]):
        seg = tube ^ sector(n, t, z, j0, j1)
        if seg.volume() >= 1:
            attach(seg, owner[:-4], "K", f"window {A} deg: core skin extended to the flat wall over {j0}..{j1} deg")

    # ledge on the flat wall: frame hole radius and owner from a section through the wall
    segs = []
    for k in [k for k in parts if k[0] in "ABC"]:
        sc = parts[k].section(plane_origin=n * 211.6, plane_normal=n)
        if sc is None:
            continue
        for e in sc.discrete:
            segs.append((k, LineString(np.c_[e @ t, e[:, 2]] - [CU, CZ])))
    hole = np.full(360, np.nan); hown = np.empty(360, object)
    for j in range(360):
        q = np.radians(j)
        ray = LineString([(0, 0), (700 * np.cos(q), 700 * np.sin(q))]); hs = []
        for k, ls in segs:
            x = ray.intersection(ls)
            for p in ([x] if x.geom_type == "Point" else list(getattr(x, "geoms", []))):
                if p.geom_type == "Point":
                    hs.append((np.hypot(p.x, p.y), k))
        if hs:
            hs.sort(); hole[j], hown[j] = hs[0]
    ro_end = ro_at(D_END)
    dl = np.array([208.52, 214.7])
    ROl = np.vstack([hole + LEDGE_OVER] * 2); RIl = np.vstack([ro_end - LEDGE_IN] * 2)
    ledge = ring_tube(n, t, z, dl, ROl, RIl)
    for owner, j0, j1 in runs_of(list(hown)):
        seg = ledge ^ sector(n, t, z, j0, j1)
        if seg.volume() >= 1:
            attach(seg, owner, "ABC", f"window {A} deg: ledge added to the flat wall over {j0}..{j1} deg so the core skin seats on it")

# ---- 3. vents
VENTS = [(-38.1, -76.2), (38.1, -76.2), (-101.6, -38.1), (101.6, -38.1), (-101.6, 38.1), (101.6, 38.1), (38.1, 76.2), (-38.1, 76.2)]
for x, y in VENTS:
    plug = mf.Manifold.cylinder(7.5, 4.7, 4.7, 48).translate([x, y, -399.97])
    for k in [k for k in man if k.startswith("KA")]:
        b = parts[k].bounds
        if b[0, 0] < x < b[1, 0] and b[0, 1] < y < b[1, 1] and (man[k] ^ plug).volume() > 1:
            man[k] = man[k] + plug
            log.setdefault(k, ""); log[k] += f" vent at ({x}, {y}) plugged;"
            break

# ---- 4. hold-down (new parts)
man["HD1_Holddown_bridge_2x6_pull_up"] = mf.Manifold.cube([820, 38.1, 139.7]).translate([-410, -19.05, 578.0])
for i, x in enumerate((-380.0, 380.0)):
    man[f"HD{2+i}_Holddown_rod_3-8-16_pull_up"] = mf.Manifold.cylinder(1235, 4.76, 4.76, 32).translate([x, 0, -475.0])
man["HD4_Bench_board_pull_down"] = mf.Manifold.cube([900, 900, 19.05]).translate([-450, -450, -454.05])
log["HD1-HD4"] = "new: 2x6 bridge on the cap, two 3/8-16 rods at x = +-380 mm, 3/4 in bench board"

for k, m in man.items():
    T(m).export(os.path.join(OUT, k + ".stl"))
json.dump(log, open(os.path.join(OUT, "_changes.json"), "w"), indent=1)
for k, v in log.items():
    print(k, v)
