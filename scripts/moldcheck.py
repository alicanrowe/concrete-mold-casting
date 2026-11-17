#!/usr/bin/env python3
"""moldcheck: check a multi-part casting mold before printing, machining or pouring.

Input: a folder of STL files (one per mold part, all in their assembled positions in
one shared frame) or one GLB/glTF with one mesh node per part.

Pull directions come from the part name (`..._pull_70_deg`, `..._pull_up`, `..._pull_down`)
or from the spec. Horizontal angles are degrees counterclockwise from +X seen from above.

What it checks
  hygiene       every part is one closed, consistently wound solid
  interference  two mold parts occupy the same space (more than --interf-tol mm^3)
  pour          concrete poured at `pour` reaches the cavity below `fill_level`
                (no_pour_path when it lands on a surface above the fill level)
  leak          the poured concrete can run out of the mold below the fill level
  floods        the pour fills a large space that isn't wall (a core interior, a gap)
  unfilled      thin cavity the pour never reaches
  air_trap      cavity whose air can't rise to the free surface (a ceiling with no vent)
  undercut      a concrete-facing face that moves into the concrete along the part's pull
  low_draft     concrete-facing area with less than `min_draft` degrees of draft
  thin_wall     cast thinner than `min_wall`
  bed           a part that won't fit the printer bed in any box orientation
Reported, not flagged: cavity volume and concrete mass, wall thickness percentiles,
hydrostatic push-off force on every part along its pull, group forces (core uplift),
print mass. With --cast-stl it also writes the cast (the casting itself) as an STL.

Method: parts are rasterised into a voxel grid (column ray parity, so each part must be
watertight). Empty space thicker than about 1.5 x wall is "big space"; the rest is thin
space. A gravity fill from the pour point floods connected empty voxels up to the fill
level. Air traps come from a top-down sweep: a voxel can vent if it can move sideways in
its layer to a voxel whose upper neighbour vents. Draft and forces use the mesh faces
that face the filled cavity.

Usage
  python3 moldcheck.py MOLD_DIR_or_GLB --spec piece.moldcheck.json [--res 2] [--json out.json]
Exit code 1 if anything is flagged (minus the spec's allow list).
"""
import argparse, glob, json, math, os, re, sys
import numpy as np
import trimesh
from scipy import ndimage

G = 9.81

# ---------------------------------------------------------------- loading
def load_parts(path, units):
    scale = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4}[units]
    parts = {}
    if os.path.isdir(path):
        files = sorted(glob.glob(os.path.join(path, "*.stl")) + glob.glob(os.path.join(path, "*.STL")))
        for f in files:
            m = trimesh.load(f, force="mesh", process=True)
            parts[os.path.splitext(os.path.basename(f))[0]] = m
    else:
        sc = trimesh.load(path, force="scene")
        for node in sc.graph.nodes_geometry:
            T, gname = sc.graph[node]
            m = sc.geometry[gname].copy()
            m.apply_transform(T)
            parts[node] = m
    for k, m in parts.items():
        if scale != 1.0:
            m.apply_scale(scale)
    return parts


def to_z_up(parts, up):
    if up == "z":
        return
    # glTF is Y up: (x, y, z) -> (x, -z, y)
    R = np.array([[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], float)
    for m in parts.values():
        m.apply_transform(R)


def pull_of(name, spec_parts):
    for pat, cfg in spec_parts.items():
        if re.search(pat, name) and "pull" in cfg:
            return parse_pull(cfg["pull"])
    m = re.search(r"pull_(-?\d+(?:\.\d+)?)_deg", name)
    if m:
        a = math.radians(float(m.group(1)))
        return np.array([math.cos(a), math.sin(a), 0.0])
    if re.search(r"pull_up", name):
        return np.array([0, 0, 1.0])
    if re.search(r"pull_down", name):
        return np.array([0, 0, -1.0])
    return None


def parse_pull(p):
    if isinstance(p, str):
        if p == "up":
            return np.array([0, 0, 1.0])
        if p == "down":
            return np.array([0, 0, -1.0])
        p = float(p)
    if isinstance(p, (int, float)):
        a = math.radians(p)
        return np.array([math.cos(a), math.sin(a), 0.0])
    v = np.array(p, float)
    return v / np.linalg.norm(v)


def role_of(name, spec_parts):
    for pat, cfg in spec_parts.items():
        if re.search(pat, name) and "role" in cfg:
            return cfg["role"]
    return "mold"

# ---------------------------------------------------------------- voxels
class Grid:
    def __init__(self, lo, hi, res, pad):
        self.res = res
        self.lo = np.asarray(lo, float) - pad
        hi = np.asarray(hi, float) + pad
        self.n = np.ceil((hi - self.lo) / res).astype(int)
        # jitter keeps rays off exact vertices and edges
        self.off = np.array([0.5 + 0.01237, 0.5 + 0.00731, 0.5])

    def centers(self, axis):
        return self.lo[axis] + (np.arange(self.n[axis]) + self.off[axis]) * self.res

    def z_of(self, iz):
        return self.lo[2] + (iz + 0.5) * self.res

    def index(self, p):
        return tuple(np.floor((np.asarray(p) - self.lo) / self.res).astype(int)[::-1])  # (iz, iy, ix)


def rasterize(mesh, grid):
    """Return bool array [nz, ny, nx] of voxel centres inside the watertight mesh (z-ray parity)."""
    nx, ny, nz = grid.n
    res = grid.res
    occ_diff = np.zeros((ny, nx, nz + 1), np.int16)
    tri = mesh.triangles  # (T,3,3)
    xs0 = grid.lo[0] + grid.off[0] * res
    ys0 = grid.lo[1] + grid.off[1] * res
    tx, ty = tri[:, :, 0], tri[:, :, 1]
    ix0 = np.ceil((tx.min(1) - xs0) / res).astype(int)
    ix1 = np.floor((tx.max(1) - xs0) / res).astype(int)
    iy0 = np.ceil((ty.min(1) - ys0) / res).astype(int)
    iy1 = np.floor((ty.max(1) - ys0) / res).astype(int)
    keep = (ix1 >= ix0) & (iy1 >= iy0)
    hits_c, hits_z = [], []
    span = np.maximum(ix1 - ix0 + 1, iy1 - iy0 + 1)
    for S in sorted(set(np.clip(span[keep], 1, None).tolist())):
        sel = np.where(keep & (span == S))[0]
        if len(sel) == 0:
            continue
        for chunk in np.array_split(sel, max(1, len(sel) * S * S // 2_000_000 + 1)):
            t = tri[chunk]
            gx = ix0[chunk][:, None, None] + np.arange(S)[None, :, None]
            gy = iy0[chunk][:, None, None] + np.arange(S)[None, None, :]
            gx, gy = np.broadcast_arrays(gx, gy)
            px = xs0 + gx * res
            py = ys0 + gy * res
            a, b, c = t[:, 0], t[:, 1], t[:, 2]
            v0x = (b[:, 0] - a[:, 0])[:, None, None]; v0y = (b[:, 1] - a[:, 1])[:, None, None]
            v1x = (c[:, 0] - a[:, 0])[:, None, None]; v1y = (c[:, 1] - a[:, 1])[:, None, None]
            wx = px - a[:, 0][:, None, None]; wy = py - a[:, 1][:, None, None]
            den = v0x * v1y - v1x * v0y
            with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
                u = (wx * v1y - v1x * wy) / den
                v = (v0x * wy - wx * v0y) / den
            u = np.nan_to_num(u, nan=-1, posinf=-1, neginf=-1); v = np.nan_to_num(v, nan=-1, posinf=-1, neginf=-1)
            inside = (u >= 0) & (v >= 0) & (u + v <= 1) & (np.abs(den) > 1e-12)
            inside &= (gx >= 0) & (gx < nx) & (gy >= 0) & (gy < ny)
            if not inside.any():
                continue
            z = a[:, 2][:, None, None] + u * (b[:, 2] - a[:, 2])[:, None, None] + v * (c[:, 2] - a[:, 2])[:, None, None]
            hits_c.append((gy[inside] * nx + gx[inside]).astype(np.int64))
            hits_z.append(z[inside])
    out = np.zeros((nz, ny, nx), bool)
    if not hits_c:
        return out, 0
    col = np.concatenate(hits_c); zz = np.concatenate(hits_z)
    order = np.lexsort((zz, col))
    col, zz = col[order], zz[order]
    # drop exact duplicate hits (shared edges)
    dup = np.r_[False, (col[1:] == col[:-1]) & (np.abs(zz[1:] - zz[:-1]) < 1e-7)]
    col, zz = col[~dup], zz[~dup]
    ucol, start, cnt = np.unique(col, return_index=True, return_counts=True)
    odd = cnt % 2 == 1
    bad_cols = int(odd.sum())
    good = np.repeat(~odd, cnt)
    col, zz = col[good], zz[good]
    z0 = zz[0::2]; z1 = zz[1::2]; c = col[0::2]
    zc0 = grid.lo[2] + grid.off[2] * res
    i0 = np.clip(np.ceil((z0 - zc0) / res).astype(int), 0, nz)
    i1 = np.clip(np.floor((z1 - zc0) / res).astype(int) + 1, 0, nz)
    ok = i1 > i0
    cy, cx = np.divmod(c[ok], nx)
    np.add.at(occ_diff, (cy, cx, i0[ok]), 1)
    np.add.at(occ_diff, (cy, cx, i1[ok]), -1)
    filled = np.cumsum(occ_diff[:, :, :nz], axis=2) > 0
    return np.transpose(filled, (2, 0, 1)), bad_cols


def prim_mask(prim, grid):
    nz, ny, nx = grid.n[2], grid.n[1], grid.n[0]
    z = grid.centers(2)[:, None, None]
    y = grid.centers(1)[None, :, None]
    x = grid.centers(0)[None, None, :]
    t = prim["type"]
    if t == "box":
        c = np.array(prim["center"], float); s = np.array(prim["size"], float) / 2
        a = math.radians(prim.get("rot_z", 0.0))
        dx, dy = x - c[0], y - c[1]
        lx = dx * math.cos(a) + dy * math.sin(a)
        ly = -dx * math.sin(a) + dy * math.cos(a)
        m = (np.abs(lx) <= s[0]) & (np.abs(ly) <= s[1]) & (np.abs(z - c[2]) <= s[2])
    elif t in ("cylinder", "annulus"):
        c = prim.get("center", [0, 0]); r = np.hypot(x - c[0], y - c[1])
        r0, r1 = (0.0, prim["r"]) if t == "cylinder" else prim["r"]
        z0, z1 = prim["z"]
        m = (r >= r0) & (r <= r1) & (z >= z0) & (z <= z1)
    else:
        raise ValueError("unknown primitive " + t)
    return np.broadcast_to(m, (nz, ny, nx))


def clusters(mask, grid, top=5, min_vox=1):
    lab, n = ndimage.label(mask)
    if n == 0:
        return []
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    coms = ndimage.center_of_mass(mask, lab, range(1, n + 1))
    objs = ndimage.find_objects(lab)
    out = []
    for k in np.argsort(sizes)[::-1][:top]:
        if sizes[k] < min_vox:
            break
        iz, iy, ix = coms[k]
        p = grid.lo + (np.array([ix, iy, iz]) + 0.5) * grid.res
        out.append({"cm3": round(float(sizes[k]) * grid.res ** 3 / 1000, 2),
                    "at_mm": [round(float(v), 1) for v in p],
                    "angle_deg": round(math.degrees(math.atan2(p[1], p[0])) % 360, 1),
                    "r_mm": round(float(math.hypot(p[0], p[1])), 1),
                    "z_range": [round(float(grid.z_of(objs[k][0].start) - 0.5 * grid.res), 1),
                                round(float(grid.z_of(objs[k][0].stop - 1) + 0.5 * grid.res), 1)]})
    return out

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mold")
    ap.add_argument("--spec")
    ap.add_argument("--res", type=float, default=None, help="voxel size, mm (default: wall/8, at least 1.5)")
    ap.add_argument("--units", default=None, help="mm, cm, m or in (default from spec, else mm)")
    ap.add_argument("--up", default=None, help="z (STL, CAD) or y (glTF/GLB)")
    ap.add_argument("--interf-tol", type=float, default=1.0, help="mm^3")
    ap.add_argument("--json")
    ap.add_argument("--cast-stl", help="write the filled cavity (the casting) as an STL")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    spec = json.load(open(a.spec)) if a.spec else {}
    units = a.units or spec.get("units", "mm")
    up = a.up or spec.get("up", "y" if a.mold.lower().endswith((".glb", ".gltf")) else "z")
    sp = spec.get("parts", {})
    wall = float(spec.get("wall", 19.0))
    res = a.res or spec.get("res") or max(1.5, round(wall / 8, 2))
    min_draft = float(spec.get("min_draft", 1.0))
    min_wall = float(spec.get("min_wall", 0.6 * wall))
    rho = float(spec.get("density", 2100))
    allow = spec.get("allow", [])

    parts = load_parts(a.mold, units)
    to_z_up(parts, up)
    names = [n for n in parts if role_of(n, sp) != "ignore"]
    flags = []
    report = {"parts": {}, "res_mm": res}

    def flag(kind, where, msg, **extra):
        key = f"{kind}:{where}"
        if any(re.search(p, key) for p in allow):
            return
        flags.append({"kind": kind, "where": where, "msg": msg, **extra})

    # ---- hygiene
    for n in names:
        m = parts[n]
        bodies = len(m.split(only_watertight=False)) if len(m.faces) < 400000 else 1
        info = {"watertight": bool(m.is_watertight), "winding": bool(m.is_winding_consistent),
                "bodies": bodies, "volume_cm3": round(float(abs(m.volume)) / 1000, 1),
                "pull": None, "role": role_of(n, sp)}
        d = pull_of(n, sp)
        if d is not None:
            info["pull"] = [round(float(v), 3) for v in d]
        report["parts"][n] = info
        if not m.is_watertight or not m.is_winding_consistent or m.volume <= 0:
            flag("hygiene", n, "not a closed, outward-wound solid; fix before trusting anything else")
        elif bodies > 1:
            flag("hygiene", n, f"{bodies} separate bodies in one part")
        if d is None and info["role"] not in ("closure", "fixed"):
            flag("no_pull", n, "no pull direction in the name or spec")

    # ---- interference (manifold3d booleans on bbox-overlapping pairs)
    try:
        import manifold3d as mf
        mans = {}
        for n in names:
            m = parts[n]
            if m.is_watertight:
                mans[n] = mf.Manifold(mf.Mesh(vert_properties=np.asarray(m.vertices, np.float32),
                                              tri_verts=np.asarray(m.faces, np.uint32)))
        bb = {n: parts[n].bounds for n in mans}
        keys = list(mans)
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                A, B = bb[keys[i]], bb[keys[j]]
                if np.any(A[1] < B[0]) or np.any(B[1] < A[0]):
                    continue
                v = (mans[keys[i]] ^ mans[keys[j]]).volume()
                if v > a.interf_tol:
                    flag("interference", f"{keys[i]}~{keys[j]}", f"overlap {v:.1f} mm^3", mm3=round(v, 1))
    except ImportError:
        print("manifold3d not installed: interference check skipped", file=sys.stderr)

    # ---- printer bed
    bed = spec.get("bed")
    if bed:
        bs = sorted(bed)
        for n in names:
            try:
                ext = sorted(parts[n].bounding_box_oriented.primitive.extents)
            except Exception:
                ext = sorted(parts[n].extents)
            if any(e > b + 0.01 for e, b in zip(ext, bs)):
                flag("bed", n, f"{ext[2]:.0f} x {ext[1]:.0f} x {ext[0]:.0f} mm doesn't fit {bed}")

    # ---- voxel grid
    lo = np.min([parts[n].bounds[0] for n in names], axis=0)
    hi = np.max([parts[n].bounds[1] for n in names], axis=0)
    grid = Grid(lo, hi, res, pad=max(3 * res, 2 * wall))
    nz, ny, nx = grid.n[2], grid.n[1], grid.n[0]
    if not a.quiet:
        print(f"grid {nx} x {ny} x {nz} at {res} mm", file=sys.stderr)
    solid = np.zeros((nz, ny, nx), bool)
    for n in names:
        if parts[n].is_watertight:
            occ, bad = rasterize(parts[n], grid)
            solid |= occ
    for prim in spec.get("remove", []):
        solid &= ~prim_mask(prim, grid)
    for prim in spec.get("add", []):
        m = prim_mask(prim, grid)
        if prim.get("plug"):
            # a closure that fills only what you can see through the opening from outside:
            # keep voxels whose path outward (box local +x) is clear of solid for `reach` mm
            a_ = math.radians(prim.get("rot_z", 0.0)); dvec = np.array([math.cos(a_), math.sin(a_), 0.0])
            if prim.get("plug") == "in":
                dvec = -dvec  # fill what the open side (e.g. a hollow core's interior) can see
            iz_, iy_, ix_ = np.nonzero(m & ~solid)
            pts = grid.lo + (np.stack([ix_, iy_, iz_], 1) + 0.5) * res
            clear = np.ones(len(pts), bool)
            start = res if prim.get("plug") == "in" else res
            for step in np.arange(start, prim.get("reach", prim["size"][0] / 2 + 3 * wall), res):
                q = np.floor((pts + dvec * step - grid.lo) / res).astype(int)
                inb = np.all((q >= 0) & (q < grid.n), 1)
                hit = np.zeros(len(pts), bool)
                hit[inb] = solid[q[inb, 2], q[inb, 1], q[inb, 0]]
                clear &= ~hit
            plug = np.zeros_like(solid)
            plug[iz_[clear], iy_[clear], ix_[clear]] = True
            solid |= plug
            report.setdefault("plugs", []).append({"name": prim.get("name", "plug"),
                                                   "area_cm2": round(float(plug.sum()) * res ** 3 / prim["size"][0] / 100, 1)})
        else:
            solid |= m
    empty = ~solid

    # thin vs big space
    r_big = 0.75 * wall
    dist_empty = ndimage.distance_transform_edt(empty, sampling=res)
    core_big = dist_empty > r_big
    big = ndimage.distance_transform_edt(~core_big, sampling=res) <= r_big + 0.5 * res
    big &= empty
    thin = empty & ~big
    del core_big
    # outside = big space connected to the grid border
    lab_big, nb = ndimage.label(big)
    border = np.unique(np.concatenate([lab_big[0].ravel(), lab_big[-1].ravel(), lab_big[:, 0].ravel(),
                                       lab_big[:, -1].ravel(), lab_big[:, :, 0].ravel(), lab_big[:, :, -1].ravel()]))
    outside = np.isin(lab_big, border[border > 0])

    # main cavity = largest thin region not open to the outside
    lab_t, nt = ndimage.label(thin & ~outside)
    if nt:
        sz = np.bincount(lab_t.ravel()); sz[0] = 0
        cavity = lab_t == sz.argmax()
    else:
        cavity = np.zeros_like(thin)
    del lab_t

    # ---- gravity fill
    h = spec.get("fill_level")
    pour = spec.get("pour")
    fill = None
    if pour is not None and h is not None:
        izh = int(np.floor((h - grid.lo[2]) / res - 0.5))
        ix = int((pour[0] - grid.lo[0]) / res); iy = int((pour[1] - grid.lo[1]) / res)
        iz = int((pour[2] - grid.lo[2]) / res)
        iz = min(iz, nz - 1)
        if solid[iz, iy, ix]:
            flag("no_pour_path", "pour", "the pour point is inside a mold part")
        else:
            while iz > 0 and empty[iz - 1, iy, ix]:
                iz -= 1
            land_z = grid.z_of(iz) - 0.5 * res
            report["pour_lands_at_z"] = round(float(land_z), 1)
            if iz > izh:
                flag("no_pour_path", "pour",
                     f"concrete poured here lands on a surface at z {land_z:.1f}, above the fill level {h}: "
                     "nothing reaches the cavity")
            else:
                # what counts as escaping: big space below the fill level that reaches the
                # sides or bottom of the grid (risers and funnels open only upward don't count)
                low = big.copy(); low[izh + 1:] = False
                lab_l, _ = ndimage.label(low)
                sides = np.concatenate([lab_l[0].ravel(), lab_l[:, 0].ravel(), lab_l[:, -1].ravel(),
                                        lab_l[:, :, 0].ravel(), lab_l[:, :, -1].ravel()])
                outside_low = np.isin(lab_l, np.unique(sides[sides > 0]))
                del lab_l, low
                below = empty & ~outside_low; below[izh + 1:] = False
                if outside_low[iz, iy, ix] or not below[iz, iy, ix]:
                    fill = None
                    flag("no_pour_path", "pour",
                         f"concrete poured here lands at z {land_z:.1f} on a surface open to the outside: "
                         "it spills off and never reaches the wall cavity")
                else:
                    lab, _ = ndimage.label(below)
                    fill = lab == lab[iz, iy, ix]
                    del lab
                if fill is not None and not (fill & cavity).any():
                    flag("no_pour_path", "pour", f"concrete poured here lands at z {land_z:.1f} and never reaches the wall cavity")
                    fill = None
                elif fill is not None:
                    edge = ndimage.binary_dilation(fill) & outside_low
                    if edge.any():
                        edge = ndimage.binary_dilation(edge) & fill
                        cl = clusters(edge, grid, top=6, min_vox=2)
                        flag("leak", "cavity", f"the pour runs out of the mold below the fill level ({len(cl)} places shown)",
                             places=cl)
                    bigfill = fill & big
                    if bigfill.sum() > 0.05 * max(1, (fill & thin).sum()):
                        cl = clusters(bigfill, grid, top=3, min_vox=10)
                        entry = ndimage.binary_dilation(bigfill, iterations=2) & cavity & fill
                        ent = clusters(entry, grid, top=8, min_vox=1)
                        flag("floods", "cavity", "the pour also fills large non-wall spaces (core interior? open vents?); "
                             "it gets in where `entries` shows", places=cl, entries=ent)
                    unreached = cavity & ~fill
                    unreached[izh + 1:] = False
                    unreached = ndimage.binary_opening(unreached)
                    cl = clusters(unreached, grid, top=5, min_vox=max(2, int(2000 / res ** 3)))
                    if cl:
                        flag("unfilled", "cavity", "wall cavity the pour doesn't reach", places=cl)
    cast = fill if fill is not None else cavity  # fill already stops at the outside and the fill level
    report["cast_cm3"] = round(float(cast.sum()) * res ** 3 / 1000, 1)
    if h is not None:
        izh = int(np.floor((h - grid.lo[2]) / res - 0.5))
        rim = spec.get("rim")
        if rim is not None:
            izr = int(np.floor((rim - grid.lo[2]) / res - 0.5))
            report["cast_below_rim_cm3"] = round(float(cast[:izr + 1].sum()) * res ** 3 / 1000, 1)
            report["riser_cm3"] = round(report["cast_cm3"] - report["cast_below_rim_cm3"], 1)
    vol_l = (report.get("cast_below_rim_cm3") or report["cast_cm3"]) / 1000
    report["cast_kg"] = round(vol_l * rho / 1000, 1)

    # ---- air traps
    if fill is not None:
        vent = np.zeros_like(fill)
        izh = int(np.floor((h - grid.lo[2]) / res - 0.5))
        vent[izh] = fill[izh]
        for k in range(izh - 1, -1, -1):
            layer = fill[k]
            if not layer.any():
                continue
            seeds = layer & vent[k + 1]
            if not seeds.any():
                continue
            lab2, _ = ndimage.label(layer)
            ids = np.unique(lab2[seeds]); ids = ids[ids > 0]
            vent[k] = np.isin(lab2, ids)
        trap = fill & ~vent
        cl = clusters(trap, grid, top=6, min_vox=max(1, int(200 / res ** 3)))
        if cl:
            flag("air_trap", "cavity", "air can't rise to the free surface from here (add a vent or tilt the mold)",
                 places=cl)

    # ---- wall thickness
    if cast.any():
        d, feat = ndimage.distance_transform_edt(cast, sampling=res, return_indices=True)
        ridge = cast & (d >= ndimage.maximum_filter(d, size=3) - 1e-6) & (d >= res - 1e-6)
        t = 2 * d[ridge]
        if t.size:
            report["wall_mm"] = {"p5": round(float(np.percentile(t, 5)), 1), "p50": round(float(np.percentile(t, 50)), 1),
                                 "p95": round(float(np.percentile(t, 95)), 1)}
            thin_ridge = ridge & (2 * d < min_wall)
            # keep only two-sided thin spots: some neighbour's nearest surface lies on the opposite side.
            # This drops the medial branches that run into convex corners, which are not thin walls.
            if thin_ridge.any():
                pos = np.indices(cast.shape)
                vec = (feat - pos).astype(np.float32)
                vec /= np.maximum(np.linalg.norm(vec, axis=0), 1e-6)
                keep = np.zeros_like(thin_ridge)
                for k, j, i in np.argwhere(thin_ridge):
                    v0 = vec[:, k, j, i]
                    sl = (slice(None), slice(max(k - 1, 0), k + 2), slice(max(j - 1, 0), j + 2), slice(max(i - 1, 0), i + 2))
                    nb = vec[sl].reshape(3, -1)[:, cast[sl[1:]].ravel()]
                    if nb.size and (v0 @ nb).min() < -0.5:
                        keep[k, j, i] = True
                thin_ridge = keep
            cl = clusters(ndimage.binary_dilation(thin_ridge, iterations=1) & cast, grid, top=4, min_vox=8)
            if cl:
                flag("thin_wall", "cast", f"cast thinner than {min_wall} mm", places=cl)

    # ---- per-face draft and hydrostatic force
    face_mask = cast
    groups = spec.get("groups", {})
    gforce = {g: np.zeros(3) for g in groups}
    for n in names:
        m = parts[n]
        if not m.is_watertight:
            continue
        c = m.triangles_center; nrm = m.face_normals; A = m.area_faces
        p = c + nrm * (0.75 * res)
        idx = np.floor((p - grid.lo) / res).astype(int)
        ok = np.all((idx >= 0) & (idx < grid.n), axis=1)
        wet = np.zeros(len(c), bool)
        wet[ok] = face_mask[idx[ok, 2], idx[ok, 1], idx[ok, 0]]
        info = report["parts"][n]
        info["wet_cm2"] = round(float(A[wet].sum()) / 100, 1)
        if not wet.any():
            continue
        if h is not None:
            depth = np.clip(h - c[wet, 2], 0, None) / 1000.0  # m
            pres = rho * G * depth  # Pa
            F = -(nrm[wet] * (pres * A[wet] / 1e6)[:, None]).sum(0)  # N
            info["force_N"] = [round(float(v), 1) for v in F]
            for g, pat in groups.items():
                if re.search(pat, n):
                    gforce[g] += F
        d = pull_of(n, sp)
        if d is None:
            continue
        if spec.get("rim") is not None:
            # the riser above the rim is struck off before it sets: no draft needed there
            wet &= c[:, 2] <= spec["rim"] + 0.5 * res
            if not wet.any():
                continue
        s = nrm[wet] @ d
        ang = np.degrees(np.arcsin(np.clip(-s, -1, 1)))
        aw = A[wet]; tot = aw.sum()
        und = ang < -0.5
        low = (ang >= -0.5) & (ang < min_draft)
        info["draft_pct"] = {"undercut": round(100 * float(aw[und].sum() / tot), 1),
                             "low": round(100 * float(aw[low].sum() / tot), 1),
                             "ok": round(100 * float(aw[~und & ~low].sum() / tot), 1)}
        if h is not None:
            info["push_off_N"] = round(max(0.0, float(np.dot(info["force_N"], d))), 1)
        if aw[und].sum() > 50:  # mm^2
            cc = c[wet][und]
            ctr = np.average(cc, axis=0, weights=aw[und])
            flag("undercut", n, f"{aw[und].sum() / 100:.1f} cm^2 of concrete-facing face locks against pull "
                                f"(worst {ang[und].min():.0f} deg, centred at {np.round(ctr).astype(int).tolist()}, "
                                f"z {cc[:, 2].min():.0f}..{cc[:, 2].max():.0f})",
                 cm2=round(float(aw[und].sum()) / 100, 1), at_mm=[round(float(v), 1) for v in ctr])
        if aw[low].sum() > 0.02 * tot and aw[low].sum() > 100:
            flag("low_draft", n, f"{aw[low].sum() / 100:.1f} cm^2 ({100 * aw[low].sum() / tot:.0f}%) of its concrete face "
                                 f"has under {min_draft} deg draft", cm2=round(float(aw[low].sum()) / 100, 1))
    if groups and h is not None:
        report["group_force_N"] = {g: [round(float(v), 1) for v in f] for g, f in gforce.items()}

    # ---- print mass
    dens = float(spec.get("print_density", 1.27))  # PETG g/cm3
    tot = sum(report["parts"][n]["volume_cm3"] for n in names)
    report["print_cm3"] = round(tot, 1)
    report["print_kg_solid"] = round(tot * dens / 1000, 1)

    # ---- cast export
    if a.cast_stl and cast.any():
        from skimage import measure
        vol = np.pad(cast.astype(np.float32), 1)
        vol = ndimage.gaussian_filter(vol, 0.6)
        verts, faces, _, _ = measure.marching_cubes(vol, 0.5)
        verts = verts[:, ::-1] - 1 + 0.5  # (x,y,z) voxel coords
        verts = grid.lo + verts * res
        trimesh.Trimesh(verts, faces[:, ::-1]).export(a.cast_stl)

    # ---- print
    report["flags"] = flags
    if not a.quiet:
        print(f"cast {report['cast_cm3'] / 1000:.2f} L"
              + (f" ({report['cast_below_rim_cm3'] / 1000:.2f} L below rim, riser {report['riser_cm3'] / 1000:.2f} L)"
                 if "riser_cm3" in report else "")
              + f", about {report['cast_kg']} kg at {rho:.0f} kg/m3")
        if "wall_mm" in report:
            w = report["wall_mm"]; print(f"wall p5/p50/p95: {w['p5']} / {w['p50']} / {w['p95']} mm")
        if "group_force_N" in report:
            for g, f in report["group_force_N"].items():
                print(f"group {g}: force {f} N  (up = {f[2]:.0f} N, {f[2] / 4.448:.0f} lbf)")
        po = sorted(((v.get("push_off_N", 0), k) for k, v in report["parts"].items()), reverse=True)[:8]
        if po and po[0][0] > 0:
            print("largest push-off along pull: " + ", ".join(f"{k} {v:.0f} N" for v, k in po))
        print(f"print: {report['print_cm3'] / 1000:.1f} L of plastic, {report['print_kg_solid']} kg solid")
        for f in flags:
            extra = ""
            if "places" in f and f["places"]:
                extra = "  at " + "; ".join(f"{p['cm3']} cm3 @ {p['at_mm']} ({p['angle_deg']} deg, r {p['r_mm']}, z {p['z_range'][0]}..{p['z_range'][1]})"
                                             for p in f["places"][:4])
            if f.get("entries"):
                extra += "\n    entries: " + "; ".join(f"{p['cm3']} cm3 @ {p['at_mm']} ({p['angle_deg']} deg, z {p['z_range'][0]}..{p['z_range'][1]})"
                                                for p in f["entries"][:8])
            print(f"[{f['kind']}] {f['where']}: {f['msg']}{extra}")
        print(f"{len(flags)} flag(s)")
    if a.json:
        json.dump(report, open(a.json, "w"), indent=1)
    sys.exit(1 if flags else 0)


if __name__ == "__main__":
    main()
