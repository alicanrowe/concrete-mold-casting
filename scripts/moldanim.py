#!/usr/bin/env python3
"""moldanim: build the assembly, pour and demold animations for a multi-part mold, and prove them.

It reads the same mold the checker reads (a folder of STLs or one GLB, pulls in the part names),
plus the cast (the part that comes out, e.g. moldcheck's vessel STL), and writes one GLB with
three clips that a web viewer (model-viewer, three.js) can play:

  build    every piece arrives in shop order, then the pour
  pour     the outside opens like a cutaway and the concrete rises in lifts, then it closes
  demold   hardware off, outside pieces off along their pulls, core pieces out by planned paths

Paths are not drawn by hand. Outside pieces move along their pull. Core pieces that can't
come out along their pull alone are planned: a translation search in configuration space
(the mold rasterized, the piece convolved over it) finds a way out past the cast and the pieces
still in place, the path is shortened, and the order is chosen so every piece can leave.

Then every clip is checked. The timeline is sampled every 2 mm of motion and each moving piece
is tested against every other piece showing at that moment, with a signed distance field per
part. A clip passes when nothing goes deeper than --tol (default 1 mm) into anything it
didn't already touch at rest. The report lists every collision with the part, time and depth.

Usage
  python3 moldanim.py MOLD_DIR --cast vessel.stl --spec anim.json --out mold.glb \
      [--report anim.json.out] [--preview previews/] [--meshopt]

The spec (all optional; see references/animation.md):
  {"name": "k_mold", "units": "mm", "up": "z",
   "parts":  {"^HD": {"role": "hardware", "material": "steel"}, ...},   # moldcheck style
   "demold": [{"label": "...", "parts": "^HD", "move": "pull", "dist": 300}, ...,
              {"label": "core", "parts": "^K", "move": "plan", "first": ["key"]}],
   "build":  [{"label": "...", "parts": "^BASE", "move": "pull", "dist": 250}, ...,
              {"label": "core", "parts": "^K", "move": "reverse"}, ...],
   "pour":   {"explode": "^[A-C]\\d", "dist": 260, "lifts": [0.5, 1.0], "pause": 1.5},
   "speed": 320}
"""
import argparse, json, math, os, re, sys, time
import numpy as np
import trimesh
from scipy import ndimage, signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import moldcheck as mc  # noqa: E402

MATERIALS = {  # name: (rgba, roughness, metallic). Same names as the site viewer's K model.
    "shell": ((0.86, 0.84, 0.80, 1), 0.6, 0.0),
    "core": ((0.80, 0.12, 0.10, 1), 0.55, 0.0),
    "base": ((0.22, 0.22, 0.22, 1), 0.6, 0.0),
    "wood": ((0.72, 0.58, 0.40, 1), 0.8, 0.0),
    "steel": ((0.62, 0.63, 0.65, 1), 0.35, 1.0),
    "gfrc": ((0.075, 0.073, 0.07, 1), 0.85, 0.0),
}
ROLE_MATERIAL = {"shell": "shell", "core": "core", "base": "base", "cap": "shell", "funnel": "shell",
                 "hardware": "steel", "cast": "gfrc"}


def code_of(name):
    return name.split("_")[0]


def default_role(name):
    n = name.lower()
    for key, role in (("funnel", "funnel"), ("cap", "cap"), ("base", "base"),
                      ("holddown", "hardware"), ("rod", "hardware"), ("bridge", "hardware"),
                      ("bench", "hardware"), ("core", "core")):
        if key in n:
            return role
    return "shell"


def spec_lookup(name, spec_parts, key, default=None):
    for pat, cfg in spec_parts.items():
        if re.search(pat, name) and key in cfg:
            return cfg[key]
    return default


def smooth(u):
    u = np.clip(u, 0, 1)
    return u * u * (3 - 2 * u)


# ---------------------------------------------------------------- distance fields
class Field:
    """Signed distance (mm, + inside) of one part on its own grid, trilinear lookups."""

    CACHE = None  # folder for cached fields (set by --cache)

    def __init__(self, mesh, max_cells=40e6):
        ext = mesh.bounds[1] - mesh.bounds[0] + 8
        res = max(1.0, float((np.prod(ext) / max_cells) ** (1 / 3)))
        self.grid = mc.Grid(mesh.bounds[0], mesh.bounds[1], res, pad=3 * res)
        f = None
        if Field.CACHE:
            import hashlib
            h = hashlib.sha1(np.ascontiguousarray(mesh.vertices, np.float64).tobytes() +
                             np.ascontiguousarray(mesh.faces, np.int64).tobytes() + str(res).encode()).hexdigest()[:16]
            f = os.path.join(Field.CACHE, h + ".npy")
        if f and os.path.exists(f):
            self.sdf = np.load(f)
        else:
            occ, _ = mc.rasterize(mesh, self.grid)
            din = ndimage.distance_transform_edt(occ) * res
            dout = ndimage.distance_transform_edt(~occ) * res
            self.sdf = np.where(occ, din - 0.5 * res, -(dout - 0.5 * res)).astype(np.float32)
            if f:
                os.makedirs(Field.CACHE, exist_ok=True); np.save(f, self.sdf)
        self.res = res
        self.c0 = self.grid.lo + self.grid.off * res  # centre of voxel 0 (x, y, z)
        self.lo, self.hi = mesh.bounds[0], mesh.bounds[1]

    def depth(self, p):
        """p: (N,3) points in the part's frame. Returns signed depth; outside the grid = far outside."""
        g = (p - self.c0) / self.res
        nz, ny, nx = self.sdf.shape
        i0 = np.floor(g).astype(np.int64)
        f = g - i0
        out = np.full(len(p), -1e3, np.float32)
        ok = (i0[:, 0] >= 0) & (i0[:, 1] >= 0) & (i0[:, 2] >= 0) & \
             (i0[:, 0] < nx - 1) & (i0[:, 1] < ny - 1) & (i0[:, 2] < nz - 1)
        if not ok.any():
            return out
        i0, f = i0[ok], f[ok]
        x, y, z = i0[:, 0], i0[:, 1], i0[:, 2]
        fx, fy, fz = f[:, 0], f[:, 1], f[:, 2]
        S = self.sdf
        c00 = S[z, y, x] * (1 - fx) + S[z, y, x + 1] * fx
        c01 = S[z, y + 1, x] * (1 - fx) + S[z, y + 1, x + 1] * fx
        c10 = S[z + 1, y, x] * (1 - fx) + S[z + 1, y, x + 1] * fx
        c11 = S[z + 1, y + 1, x] * (1 - fx) + S[z + 1, y + 1, x + 1] * fx
        out[ok] = (c00 * (1 - fy) + c01 * fy) * (1 - fz) + (c10 * (1 - fy) + c11 * fy) * fz
        return out


class Part:
    def __init__(self, name, mesh, role, material, pull, npts=6000):
        self.name, self.code, self.mesh = name, code_of(name), mesh
        self.role, self.material, self.pull = role, material, pull
        self.lo, self.hi = mesh.bounds
        self.pivot = mesh.bounds.mean(0)
        area = mesh.area
        n = int(min(npts, max(800, area / 6.0)))  # about one point per 6 mm^2, capped
        pts, _ = trimesh.sample.sample_surface_even(mesh, n, seed=1)
        if len(pts) < n // 2:
            pts, _ = trimesh.sample.sample_surface(mesh, n, seed=1)
        self.pts = np.vstack([pts, mesh.vertices[:: max(1, len(mesh.vertices) // 1500)]])
        self._field = None

    @property
    def field(self):
        if self._field is None:
            self._field = Field(self.mesh)
        return self._field


def penetration(a, oa, b, ob):
    """deepest point of a (offset oa) inside b (offset ob) and vice versa, mm"""
    lo_a, hi_a = a.lo + oa, a.hi + oa
    lo_b, hi_b = b.lo + ob, b.hi + ob
    if np.any(hi_a < lo_b - 1) or np.any(hi_b < lo_a - 1):
        return -1e3
    d1 = b.field.depth(a.pts + (oa - ob)).max() - 0.5 * b.field.res
    d2 = a.field.depth(b.pts + (ob - oa)).max() - 0.5 * a.field.res
    # half a voxel of slack: the sampled field can read that deep on a face that only touches
    return float(max(d1, d2))


# ---------------------------------------------------------------- planner
class Planner:
    """Translation-only path planning on a coarse grid: C-obstacle = obstacles (x) reflected piece."""

    def __init__(self, parts, res=8.0, margin=420.0):
        lo = np.min([p.lo for p in parts.values()], 0)
        hi = np.max([p.hi for p in parts.values()], 0)
        self.grid = mc.Grid(lo, hi, res, pad=margin)
        self.res = res
        self.occ = {}
        for k, p in parts.items():
            o, _ = mc.rasterize(p.mesh, self.grid)
            # make it conservative: also mark every cell a surface point falls in
            idx = np.floor((p.pts - self.grid.lo) / res).astype(int)
            o[idx[:, 2], idx[:, 1], idx[:, 0]] = True
            self.occ[k] = o

    def plan(self, mover, present, start_off, fine_ok, log, goal_from=None):
        """Return a list of offsets (mm) from start_off to outside, or None.
        goal_from: the pieces whose box the mover must clear to count as out (default: all of present)."""
        g, r = self.grid, self.res
        obst = np.zeros(g.n[::-1], bool)
        for k in present:
            obst |= self.occ[k]
        M = self.occ[mover]
        zz, yy, xx = np.nonzero(M)
        z0, y0, x0 = zz.min(), yy.min(), xx.min()
        K = M[z0:zz.max() + 1, y0:yy.max() + 1, x0:xx.max() + 1].astype(np.float32)
        # C[s] = sum_c K[c] * obst[c + corner + s]; correlate via fftconvolve with the flipped kernel
        C = signal.fftconvolve(obst.astype(np.float32), K[::-1, ::-1, ::-1], mode="full")
        # full-mode index j corresponds to kernel corner at cell j - (kshape - 1)
        ks = np.array(K.shape)
        free = C < 0.5
        corner0 = np.array([z0, y0, x0])
        s0 = np.round(np.asarray(start_off)[::-1] / r).astype(int)  # (z, y, x) cell offset
        j0 = tuple(corner0 + s0 + ks - 1)
        if not all(0 <= j0[i] < free.shape[i] for i in range(3)):
            return None
        if not free[j0]:
            # the coarse grid is conservative: step to the nearest free cell the fine check allows
            R = 3
            sl = tuple(slice(max(0, j0[i] - R), j0[i] + R + 1) for i in range(3))
            cand = np.argwhere(free[sl]) + np.array([s.start for s in sl])
            cand = cand[np.argsort(np.linalg.norm(cand - np.array(j0), axis=1))]
            for cj in cand[:12]:
                o = ((cj - (ks - 1) - corner0) * r)[::-1]
                if fine_ok(np.asarray(start_off, float), o):
                    j0 = tuple(cj)
                    break
            else:
                return None
        # goal: the piece's box clears the box of everything still present
        gobs = obst
        if goal_from is not None and set(goal_from) != set(present):
            gobs = np.zeros(g.n[::-1], bool)
            for k in goal_from:
                gobs |= self.occ[k]
        oz, oy, ox = np.nonzero(gobs)
        olo = np.array([oz.min(), oy.min(), ox.min()]); ohi = np.array([oz.max(), oy.max(), ox.max()])
        J = [np.arange(n) for n in free.shape]
        lo_c = [J[i] - (ks[i] - 1) for i in range(3)]  # kernel corner cell for each j
        sep = []
        for i in range(3):
            sep.append((lo_c[i] + ks[i] - 1 < olo[i] - 1) | (lo_c[i] > ohi[i] + 1))
        goal = sep[0][:, None, None] | sep[1][None, :, None] | sep[2][None, None, :]
        # stay inside the domain so the piece is never cut by the grid edge
        inside = [(lo_c[i] >= 0) & (lo_c[i] + ks[i] <= g.n[::-1][i]) for i in range(3)]
        dom = inside[0][:, None, None] & inside[1][None, :, None] & inside[2][None, None, :]
        free &= dom
        goal &= free
        # breadth-first wave through free space
        st = ndimage.generate_binary_structure(3, 3)
        dist = np.full(free.shape, -1, np.int32)
        dist[j0] = 0
        front = np.zeros(free.shape, bool); front[j0] = True
        seen = front.copy()
        step, hit = 0, None
        while front.any():
            if (front & goal).any():
                hit = np.argwhere(front & goal)
                break
            step += 1
            nxt = ndimage.binary_dilation(front, st) & free & ~seen
            dist[nxt] = step
            seen |= nxt
            front = nxt
            if step > 400:
                break
        if hit is None:
            return None
        # pick the goal cell closest (straight line) to the start, then walk back down the wave
        h = hit[np.argmin(np.linalg.norm(hit - np.array(j0), axis=1))]
        path = [tuple(h)]
        cur = np.array(h)
        nb = np.argwhere(st) - 1
        while dist[tuple(cur)] > 0:
            cand = cur + nb
            okc = np.all((cand >= 0) & (cand < np.array(free.shape)), 1)
            cand = cand[okc]
            d = dist[cand[:, 0], cand[:, 1], cand[:, 2]]
            m = (d == dist[tuple(cur)] - 1)
            c = cand[m]
            # prefer straight-ish moves
            cur = c[np.argmin(np.linalg.norm(c - cur, axis=1))]
            path.append(tuple(cur))
        path = path[::-1]
        offs = [((np.array(p) - (ks - 1) - corner0) * r)[::-1] for p in path]
        offs[0] = np.asarray(start_off, float)
        # shortcut with fine checks
        out = [offs[0]]
        i = 0
        while i < len(offs) - 1:
            j = len(offs) - 1
            while j > i + 1 and not fine_ok(offs[i], offs[j]):
                j -= 1
            if j == i + 1 and not fine_ok(offs[i], offs[j]):
                log.append(f"{mover}: coarse step {i} fails the fine check")
                return None
            out.append(offs[j]); i = j
        return out


# ---------------------------------------------------------------- timeline
class Timeline:
    """per part: list of (t, offset mm, scale, eased). Between two keys the pose is eased when the
    later key says so (single moves), else linear (paths, whose easing is baked into dense keys)."""

    def __init__(self, parts):
        self.k = {n: [] for n in parts}

    def key(self, n, t, off, s, ease=True):
        self.k[n].append((float(t), np.asarray(off, float), float(s), ease))

    def pose(self, n, t):
        ks = self.k[n]
        if not ks:
            return np.zeros(3), 1.0
        if t <= ks[0][0]:
            return ks[0][1], ks[0][2]
        for (t0, o0, s0, _), (t1, o1, s1, e1) in zip(ks, ks[1:]):
            if t0 <= t <= t1:
                u = 0 if t1 == t0 else (t - t0) / (t1 - t0)
                if e1:
                    u = smooth(u)
                return o0 + (o1 - o0) * u, s0 + (s1 - s0) * u
        return ks[-1][1], ks[-1][2]

    def end(self):
        return max([k[-1][0] for k in self.k.values() if k] + [0])


def path_keys(tl, n, t0, offs, speed, ease=True):
    """move along a polyline at constant speed with eased start and end. Returns end time.
    Every corner of the polyline is a key, so the linear in-between never cuts a corner."""
    offs = [np.asarray(o, float) for o in offs]
    seg = [np.linalg.norm(b - a) for a, b in zip(offs, offs[1:])]
    L = sum(seg)
    T = max(0.5, L / speed + 0.25)
    if L == 0:
        tl.key(n, t0, offs[0], 1); return t0
    cum = np.r_[0, np.cumsum(seg)]
    uu = np.linspace(0, 1, 2001)
    prog = smooth(uu) if ease else uu          # fraction of the length done at time fraction u
    s_all = np.unique(np.r_[smooth(np.linspace(0, 1, max(9, int(L / 12) + 2))) * L, cum])
    for sv in s_all:
        u = float(np.interp(sv / L, prog, uu))
        i = min(np.searchsorted(cum, sv, side="right") - 1, len(seg) - 1)
        f = 0 if seg[i] == 0 else (sv - cum[i]) / seg[i]
        tl.key(n, t0 + u * T, offs[i] + (offs[i + 1] - offs[i]) * f, 1, ease=False)
    return t0 + T


# ---------------------------------------------------------------- main build
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mold")
    ap.add_argument("--cast", help="the cast part (STL), e.g. the vessel moldcheck wrote")
    ap.add_argument("--spec", help="animation spec JSON")
    ap.add_argument("--out", required=True)
    ap.add_argument("--report")
    ap.add_argument("--plan-res", type=float, default=8.0, help="planner grid, mm (default 8)")
    ap.add_argument("--tol", type=float, default=1.0, help="allowed penetration beyond rest contact, mm (plus half a field voxel)")
    ap.add_argument("--faces", type=int, default=7000, help="faces per part in the GLB (decimated copy)")
    ap.add_argument("--slices", type=int, default=48, help="horizontal slices of the cast for the pour")
    ap.add_argument("--no-verify", action="store_true")
    ap.add_argument("--cache", help="folder to keep distance fields between runs (default OUT.cache)")
    a = ap.parse_args()
    t_start = time.time()
    Field.CACHE = a.cache or (a.out + ".cache")
    spec = json.load(open(a.spec)) if a.spec else {}
    sp = spec.get("parts", {})
    raw = mc.load_parts(a.mold, spec.get("units", "mm"))
    mc.to_z_up(raw, spec.get("up", "z"))
    raw = {k: v for k, v in raw.items() if spec_lookup(k, sp, "role") != "ignore" or spec_lookup(k, sp, "animate", False)}
    parts = {}
    for name, m in raw.items():
        role = spec_lookup(name, sp, "role", None) or default_role(name)
        if role == "mold":
            role = default_role(name)
        mat = spec_lookup(name, sp, "material", None) or ROLE_MATERIAL.get(role, "shell")
        parts[code_of(name)] = Part(name, m, role, mat, mc.pull_of(name, sp))
    cast = None
    if a.cast:
        cm = trimesh.load(a.cast, force="mesh")
        cast = Part("CAST_vessel", cm, "cast", "gfrc", None)
    speed = float(spec.get("speed", 320))
    log = []
    report = {"clips": {}, "warnings": log}

    def match(rx):
        return [k for k in parts if re.search(rx, k) or re.search(rx, parts[k].name)]

    # ---------------- demold: plan it first; build reuses its core paths
    demold_stages = spec.get("demold") or default_demold(parts)
    present = set(parts) | ({"CAST"} if cast else set())
    allp = dict(parts)
    if cast:
        allp["CAST"] = cast
    planner = None
    leave = {}   # code -> list of offsets (mm) from rest to outside
    order = []   # (stage index, [codes moving together])
    base_pen = {}

    def rest_pen(x, y):
        key = tuple(sorted((x, y)))
        if key not in base_pen:
            base_pen[key] = penetration(allp[x], np.zeros(3), allp[y], np.zeros(3))
        return base_pen[key]

    def seg_ok(n, oa, ob, others, step=2.0, margin=1.0):
        """straight move oa->ob clear of others; margin < 1 plans with some of the tolerance kept back"""
        L = np.linalg.norm(np.asarray(ob) - np.asarray(oa))
        tl_ = a.tol * margin
        for u in np.linspace(0, 1, max(2, int(L / step) + 1)):
            o = np.asarray(oa) + (np.asarray(ob) - np.asarray(oa)) * u
            for m in others:
                d = penetration(allp[n], o, allp[m], np.zeros(3))
                if d > max(tl_, rest_pen(n, m) + tl_) and (u > 0 or d > rest_pen(n, m) + tl_):
                    return False
        return True

    for si, st in enumerate(demold_stages):
        codes = [c for c in match(st["parts"]) if c in present]
        mv = st.get("move", "pull")
        if mv in ("pull", "vector"):
            for c in codes:
                d = np.array(st["vector"], float) if mv == "vector" else parts[c].pull
                if d is None:
                    log.append(f"{c}: no pull, skipped"); continue
                leave[c] = [np.zeros(3), d / np.linalg.norm(d) * float(st.get("dist", 250))]
            order.append((si, codes))
            present -= set(codes)
        elif mv == "plan":
            if planner is None:
                print("planner: rasterizing at", a.plan_res, "mm ...", flush=True)
                planner = Planner(allp, a.plan_res)
            todo = list(codes)
            first = st.get("first", [])

            def prio(c):
                for i, rx in enumerate(first):
                    if re.search(rx, parts[c].name, re.I):
                        return i
                return len(first)
            while todo:
                todo.sort(key=lambda c: (prio(c), c))
                done = None
                avoid = [k for k in match(st["avoid"])] if st.get("avoid") else []
                for c in todo:
                    # "avoid": pieces already off that the paths must still miss (they're there in the build)
                    others = [o for o in present if o != c] + [o for o in avoid if o not in present]
                    pull = parts[c].pull
                    unlock = float(st.get("unlock", 40))
                    # the first move: along the named pull if it frees the piece, otherwise the
                    # straight move closest to it that does (reported, because the name is then wrong)
                    dirs = [pull] if pull is not None else []
                    cube = np.array([[i, j, k] for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1)
                                     if (i, j, k) != (0, 0, 0)], float)
                    cube /= np.linalg.norm(cube, axis=1)[:, None]
                    ref = pull if pull is not None else np.array([0, 0, 1.0])
                    dirs += [d for d in cube[np.argsort(-(cube @ ref))] if pull is None or d @ pull < 0.999]
                    # the simple case first: straight out along the pull, all the way clear of what's left
                    if pull is not None and others:
                        olo = np.min([allp[o].lo for o in others], 0); ohi = np.max([allp[o].hi for o in others], 0)
                        span = max(0.0, max((ohi - parts[c].lo) @ np.maximum(pull, 0) + (parts[c].hi - olo) @ np.maximum(-pull, 0), 0)) + 10
                        if seg_ok(c, np.zeros(3), pull * span, others, margin=0.6):
                            leave[c] = [np.zeros(3), pull * span, pull * (span + 120)]
                            done = c
                            break
                    starts = []
                    for d in dirs:
                        s_ok = 0.0
                        for s in np.arange(4, unlock + 0.1, 4):
                            if seg_ok(c, d * (s - 4), d * s, others, margin=0.6):
                                s_ok = s
                            else:
                                break
                        if s_ok >= min(16, unlock):
                            starts.append(d * s_ok)
                        if len(starts) >= int(st.get("tries", 4)):
                            break
                    for s0 in starts:
                        fine = (lambda oa, ob, c=c, others=others: seg_ok(c, oa, ob, others, step=2.0, margin=0.6))
                        path = planner.plan(c, others, s0, fine, log, goal_from=[o for o in present if o != c])
                        if path is not None:
                            if pull is not None and (s0 / np.linalg.norm(s0)) @ pull < 0.85:
                                log.append(f"{c}: can't start along its named pull; it frees along "
                                           f"{np.round(s0 / np.linalg.norm(s0), 2).tolist()} instead")
                            pts = ([np.zeros(3)] if np.any(s0 != 0) else []) + path
                            last = pts[-1] - pts[-2] if len(pts) > 1 else np.array([0, 0, 1.0])
                            cen = (parts[c].lo + parts[c].hi) / 2 + pts[-1]
                            rad = np.array([cen[0], cen[1], 0.0])
                            for d in (last, rad, np.array([0, 0, 1.0])):
                                nd = np.linalg.norm(d)
                                if nd == 0:
                                    continue
                                q = pts[-1] + d / nd * 120
                                if seg_ok(c, pts[-1], q, others, margin=0.6):
                                    pts.append(q); break
                            leave[c] = pts
                            done = c
                            break
                    if done:
                        break
                if not done:
                    log.append(f"stage {st.get('label', si)}: no way out for {', '.join(sorted(todo))}")
                    print("NO PATH for", todo, flush=True)
                    break
                print(f"  {done}: out in {len(leave[done]) - 1} legs, "
                      f"{sum(np.linalg.norm(b - x) for x, b in zip(leave[done], leave[done][1:])):.0f} mm", flush=True)
                order.append((si, [done]))
                present.discard(done)
                todo.remove(done)

    # ---------------- demold timeline
    tl_d = Timeline(allp)
    t = 0.8
    for n in allp:
        tl_d.key(n, 0, np.zeros(3), 1)
    last_si = None
    for si, codes in order:
        st = demold_stages[si]
        if last_si is not None and si != last_si:
            t += float(st.get("pause", 0.35))
        stag = float(st.get("stagger", 0.12))
        spd = float(st.get("speed", speed))
        t_end = t
        for i, c in enumerate(codes):
            ts = t + i * stag
            tl_d.key(c, ts, np.zeros(3), 1)
            te = path_keys(tl_d, c, ts, leave[c], spd)
            tl_d.key(c, te + 0.3, leave[c][-1], 0.0)
            t_end = max(t_end, te)
            t_start_last = ts
        # "overlap": the next piece starts before this one is all the way out (checked like the rest)
        ov = float(st.get("overlap", 0)) if len(codes) == 1 else 0
        t = t_end - ov * (t_end - t_start_last) + (0.12 if len(codes) == 1 else 0.25)
        last_si = si
    t += 2.0
    for n in allp:
        tl_d.key(n, t, *tl_d.pose(n, t))
    demold_T = t

    # ---------------- build timeline
    build_stages = spec.get("build") or default_build(parts)
    tl_b = Timeline(allp)
    placed = []
    t = 0.6
    for n in allp:
        tl_b.key(n, 0, (leave.get(n) or [np.zeros(3)])[-1] if n != "CAST" else np.zeros(3), 0.0)
    pour_cfg = spec.get("pour", {})
    for st in build_stages:
        mv = st.get("move", "pull")
        if mv == "pour":
            t = pour_keys(tl_b, allp, parts, cast, t, pour_cfg, speed, match, opened=False)
            continue
        codes = [c for c in match(st["parts"]) if c not in placed]
        if mv == "reverse":
            # the demold paths backwards, last out = first in
            seq = [c for _, cs in order for c in cs if c in codes][::-1]
            spd = float(st.get("speed", speed))
            ov = float(st.get("overlap", 0))
            for c in seq:
                p = leave[c][::-1]
                tl_b.key(c, t, p[0], 0.0); tl_b.key(c, t + 0.25, p[0], 1.0)
                te = path_keys(tl_b, c, t + 0.25, p, spd)
                t = te - ov * (te - t) + 0.08
                placed.append(c)
            t = max(t, te) + float(st.get("pause", 0.3))
        else:
            stag = float(st.get("stagger", 0.12))
            t_end = t
            for i, c in enumerate(codes):
                if mv == "pull":
                    d = parts[c].pull
                elif mv == "drop":
                    d = np.array([0, 0, 1.0])
                else:
                    d = np.array(st["vector"], float)
                d = d / np.linalg.norm(d) * float(st.get("dist", 250))
                ts = t + i * stag
                tl_b.key(c, ts, d, 0.0); tl_b.key(c, ts + 0.25, d, 1.0)
                te = path_keys(tl_b, c, ts + 0.25, [d, np.zeros(3)], speed)
                t_end = max(t_end, te)
                placed.append(c)
            t = t_end + float(st.get("pause", 0.3))
    t += 1.5
    for n in allp:
        tl_b.key(n, t, *tl_b.pose(n, t))
    build_T = t

    # ---------------- pour clip on its own
    tl_p = Timeline(allp)
    for n in allp:
        tl_p.key(n, 0, np.zeros(3), 0.0 if n == "CAST" else 1.0)
    t = pour_keys(tl_p, allp, parts, cast, 0.5, pour_cfg, speed, match, opened=False)
    t += 1.0
    for n in allp:
        tl_p.key(n, t, *tl_p.pose(n, t))

    clips = {"build": tl_b, "pour": tl_p, "demold": tl_d}

    # ---------------- verify every clip
    if not a.no_verify:
        for name, tl in clips.items():
            res = verify(tl, allp, a.tol, rest_pen, cast)
            report["clips"][name] = res
            print(f"verify {name}: {res['samples']} samples, {len(res['collisions'])} collisions, "
                  f"max depth {res['max_depth']:.2f} mm", flush=True)
    for name, tl in clips.items():
        report["clips"].setdefault(name, {})["duration_s"] = round(tl.end(), 2)
    report["demold_order"] = [{"stage": demold_stages[si].get("label", si), "parts": cs} for si, cs in order]
    report["paths_mm"] = {c: [np.round(o, 1).tolist() for o in p] for c, p in leave.items()}

    write_glb(a.out, spec.get("name", "mold"), allp, clips, a.faces, a.slices, cast)
    print("wrote", a.out, f"{os.path.getsize(a.out) / 1e6:.1f} MB", f"in {time.time() - t_start:.0f} s")
    if a.report:
        json.dump(report, open(a.report, "w"), indent=1, default=float)
    bad = sum(len(r.get("collisions", [])) for r in report["clips"].values())
    if log:
        print("\n".join("warning: " + l for l in log))
    sys.exit(1 if bad or any("no way out" in l for l in log) else 0)


def default_demold(parts):
    st = [{"label": "hardware", "parts": "^HD", "move": "pull", "dist": 300},
          {"label": "funnel", "parts": "^F$", "move": "pull", "dist": 250},
          {"label": "cap", "parts": "^CAP$", "move": "pull", "dist": 250}]
    bands = sorted({c[0] for c, p in parts.items() if p.role == "shell" and re.match(r"^[A-Z]\d", c)},
                   key=lambda b: -max(p.hi[2] for c, p in parts.items() if c[0] == b and p.role == "shell"))
    st += [{"label": f"band {b}", "parts": f"^{b}\\d", "move": "pull", "dist": 260} for b in bands]
    st += [{"label": "base", "parts": "^BASE", "move": "pull", "dist": 200},
           {"label": "core", "parts": "^K", "move": "plan", "first": ["key"]}]
    return st


def default_build(parts):
    st = [{"label": "base", "parts": "^BASE", "move": "pull", "dist": 200},
          {"label": "core", "parts": "^K", "move": "reverse"}]
    bands = sorted({c[0] for c, p in parts.items() if p.role == "shell" and re.match(r"^[A-Z]\d", c)},
                   key=lambda b: min(p.lo[2] for c, p in parts.items() if c[0] == b and p.role == "shell"))
    st += [{"label": f"band {b}", "parts": f"^{b}\\d", "move": "pull", "dist": 260} for b in bands]
    st += [{"label": "cap", "parts": "^CAP$", "move": "pull", "dist": 250},
           {"label": "funnel", "parts": "^F$", "move": "pull", "dist": 250},
           {"label": "hardware", "parts": "^HD", "move": "pull", "dist": 300},
           {"label": "pour", "move": "pour"}]
    return st


def pour_keys(tl, allp, parts, cast, t, cfg, speed, match, opened):
    """open the outside (cutaway), raise the concrete in lifts, close it again"""
    if cast is None:
        return t
    rx = cfg.get("explode", r"^[A-Z]\d")
    dist = float(cfg.get("dist", 260))
    ex = [c for c in match(rx) if parts[c].role == "shell"]
    T_open = 1.2
    for c in ex:
        d = parts[c].pull
        if d is None:
            continue
        tl.key(c, t, np.zeros(3), 1); tl.key(c, t + T_open, d * dist, 1)
    t += T_open + 0.3
    # the concrete: one rising level; the GLB writer slices the cast and reads the level from "CAST"
    z0, z1 = cast.lo[2], cast.hi[2]
    lifts = cfg.get("lifts", [0.5, 1.0])
    rate = float(cfg.get("rise_mm_s", 160))
    level = z0
    tl.key("CAST", t, [0, 0, z0], 0.0)   # offset carries the fill level (z), scale>0 shows it
    tl.key("CAST", t + 0.01, [0, 0, z0], 1.0)
    t += 0.01
    for i, f in enumerate(lifts):
        z = z0 + (z1 - z0) * f
        dt = max(0.6, (z - level) / rate)
        tl.key("CAST", t + dt, [0, 0, z], 1.0)
        t += dt
        level = z
        if i < len(lifts) - 1:
            t += float(cfg.get("pause", 1.5))
            tl.key("CAST", t, [0, 0, z], 1.0)
    t += 0.6
    for c in ex:
        d = parts[c].pull
        if d is None:
            continue
        tl.key(c, t, d * dist, 1); tl.key(c, t + T_open, np.zeros(3), 1)
    tl.key("CAST", t + T_open, [0, 0, z1], 1.0)
    return t + T_open + 0.3


def cast_level(tl, t, cast):
    """the fill level (z mm) and visibility of the cast at time t, from the CAST track"""
    ks = tl.k.get("CAST", [])
    o, s = tl.pose("CAST", t)
    # tracks that never fill (build/demold before or without a pour) keep offset 0 = full
    if not any(abs(k[1][2]) > 0 for k in ks):
        return cast.hi[2], s
    return o[2], s


def verify(tl, allp, tol, rest_pen, cast):
    names = [n for n in allp if n != "CAST"]
    T = tl.end()
    # step so no piece moves more than 2 mm between samples
    ts = [0.0]
    t = 0.0
    while t < T:
        vmax = 0
        for n in names:
            o0, _ = tl.pose(n, t)
            o1, _ = tl.pose(n, min(T, t + 0.02))
            vmax = max(vmax, np.linalg.norm(o1 - o0) / 0.02)
        dt = 0.25 if vmax < 1e-6 else min(0.25, 2.0 / vmax)
        t += dt
        ts.append(min(t, T))
    coll, worst = [], 0.0
    prev = {n: tl.pose(n, 0) for n in allp}
    seen = set()
    for t in ts:
        pose = {n: tl.pose(n, t) for n in names}
        level, cs = cast_level(tl, t, cast) if cast else (None, 0)
        moving = [n for n in names if np.linalg.norm(pose[n][0] - prev[n][0]) > 1e-6 and pose[n][1] > 0.99]
        for n in moving:
            for m in names + (["CAST"] if cast and cs > 0.99 and level >= cast.hi[2] - 1 else []):
                if m == n or (m in pose and pose[m][1] < 0.99):
                    continue
                if m in moving and m < n:
                    continue
                om = pose[m][0] if m in pose else np.zeros(3)
                if m == "CAST":
                    om = np.zeros(3)
                d = penetration(allp[n], pose[n][0], allp[m], om)
                lim = max(tol, rest_pen(n, m) + tol)
                worst = max(worst, d - rest_pen(n, m) if rest_pen(n, m) > 0 else d)
                if d > lim and (n, m) not in seen:
                    seen.add((n, m))
                    coll.append({"t": round(t, 2), "moving": n, "hits": m, "depth_mm": round(d, 2)})
        prev = {n: pose.get(n, prev[n]) for n in allp}
    return {"samples": len(ts), "collisions": coll, "max_depth": worst}


# ---------------------------------------------------------------- GLB writer
def yup(v):
    v = np.asarray(v, float)
    return np.stack([v[..., 0], v[..., 2], -v[..., 1]], -1)


def decimate(mesh, faces):
    if len(mesh.faces) <= faces:
        return mesh
    try:
        m = mesh.simplify_quadric_decimation(face_count=faces)
        if len(m.faces) > 0:
            return m
    except Exception:
        pass
    return mesh


def write_glb(path, root_name, allp, clips, faces, nslices, cast):
    import struct
    buf = bytearray()
    J = {"asset": {"version": "2.0", "generator": "concrete-mold-casting moldanim.py"},
         "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"name": root_name, "scale": [0.001] * 3, "children": []}],
         "meshes": [], "materials": [], "accessors": [], "bufferViews": [], "buffers": [], "animations": []}
    mat_ix = {}
    for k, (rgba, rough, metal) in MATERIALS.items():
        mat_ix[k] = len(J["materials"])
        J["materials"].append({"name": k, "pbrMetallicRoughness": {"baseColorFactor": list(rgba),
                               "roughnessFactor": rough, "metallicFactor": metal}})

    def add(arr, target=None, typ=None, minmax=False):
        arr = np.ascontiguousarray(arr)
        while len(buf) % 4:
            buf.append(0)
        off = len(buf); buf.extend(arr.tobytes())
        bv = {"buffer": 0, "byteOffset": off, "byteLength": arr.nbytes}
        if target:
            bv["target"] = target
        J["bufferViews"].append(bv)
        ct = {np.dtype(np.float32): 5126, np.dtype(np.uint32): 5125}[arr.dtype]
        n = arr.shape[1] if arr.ndim > 1 else 1
        acc = {"bufferView": len(J["bufferViews"]) - 1, "componentType": ct, "count": arr.shape[0],
               "type": typ or {1: "SCALAR", 3: "VEC3", 4: "VEC4"}[n]}
        if minmax:
            acc["min"] = arr.min(0).tolist() if arr.ndim > 1 else [float(arr.min())]
            acc["max"] = arr.max(0).tolist() if arr.ndim > 1 else [float(arr.max())]
        J["accessors"].append(acc)
        return len(J["accessors"]) - 1

    def add_mesh(name, mesh, material):
        m = mesh.smooth_shaded if len(mesh.faces) < 200000 else mesh
        v = yup(m.vertices).astype(np.float32)
        nrm = yup(m.vertex_normals).astype(np.float32)
        f = m.faces.astype(np.uint32).reshape(-1)
        J["meshes"].append({"name": name, "primitives": [{
            "attributes": {"POSITION": add(v, 34962, minmax=True), "NORMAL": add(nrm, 34962)},
            "indices": add(f, 34963, "SCALAR"), "material": mat_ix[material]}]})
        return len(J["meshes"]) - 1

    nodes = {}  # name -> (node index, pivot mm z-up)
    for n, p in allp.items():
        if n == "CAST":
            continue
        m = decimate(p.mesh, faces).copy()
        m.apply_translation(-p.pivot)
        mi = add_mesh(n + "_mesh", m, p.material)
        ni = len(J["nodes"])
        J["nodes"].append({"name": n, "translation": yup(p.pivot).tolist(), "children": [ni + 1]})
        J["nodes"].append({"name": n + "_mesh", "mesh": mi})
        J["nodes"][0]["children"].append(ni)
        nodes[n] = (ni, p.pivot)
    slabs = []
    if cast is not None:
        z0, z1 = cast.lo[2], cast.hi[2]
        edges = np.linspace(z0, z1, nslices + 1)
        cm = decimate(cast.mesh, max(faces * 6, 40000))
        for i in range(nslices):
            lo, hi = edges[i], edges[i + 1]
            s = cm.slice_plane([0, 0, lo], [0, 0, 1], cap=True) if i > 0 else cm
            s = s.slice_plane([0, 0, hi], [0, 0, -1], cap=True) if (i < nslices - 1 and s is not None and len(s.faces)) else s
            if s is None or len(s.faces) == 0:
                continue
            piv = np.array([0, 0, lo])
            s = s.copy(); s.apply_translation(-piv)
            mi = add_mesh(f"CAST{i:02d}_mesh", s, "gfrc")
            ni = len(J["nodes"])
            J["nodes"].append({"name": f"CAST{i:02d}", "translation": yup(piv).tolist(), "children": [ni + 1]})
            J["nodes"].append({"name": f"CAST{i:02d}_mesh", "mesh": mi})
            J["nodes"][0]["children"].append(ni)
            slabs.append((ni, lo, hi))

    for cname, tl in clips.items():
        ch, sm = [], []
        T = tl.end()
        for n, (ni, piv) in nodes.items():
            ks = tl.k[n] or [(0, np.zeros(3), 1.0, True)]
            times = sorted({round(k[0], 4) for k in ks} | {0.0, round(T, 4)})
            # dense keys so the glTF linear interpolation follows the eased curve
            dense = []
            for t0, t1 in zip(times, times[1:]):
                dense += list(np.linspace(t0, t1, 6 if t1 - t0 > 0.05 else 2)[:-1])
            dense.append(times[-1])
            dense = np.array(sorted(set(np.round(dense, 4))), np.float32)
            tr = np.array([yup(piv + tl.pose(n, t)[0]) for t in dense], np.float32)
            sc = np.array([[max(1e-4, tl.pose(n, t)[1])] * 3 for t in dense], np.float32)
            ia = add(dense, minmax=True)
            sm.append({"input": ia, "output": add(tr), "interpolation": "LINEAR"})
            ch.append({"sampler": len(sm) - 1, "target": {"node": ni, "path": "translation"}})
            sm.append({"input": ia, "output": add(sc), "interpolation": "LINEAR"})
            ch.append({"sampler": len(sm) - 1, "target": {"node": ni, "path": "scale"}})
        if slabs:
            ks = tl.k.get("CAST", [])
            times = sorted({round(k[0], 4) for k in ks} | {0.0, round(T, 4)})
            dense = []
            for t0, t1 in zip(times, times[1:]):
                dense += list(np.linspace(t0, t1, max(2, int((t1 - t0) * 24)))[:-1])
            dense.append(times[-1])
            dense = np.array(sorted(set(np.round(dense, 4))), np.float32)
            ia = add(dense, minmax=True)
            for ni, lo, hi in slabs:
                vals = []
                for t in dense:
                    lev, vis = cast_level(tl, t, cast)
                    f = 0.0 if vis < 0.5 else float(np.clip((lev - lo) / (hi - lo), 0, 1))
                    vals.append([1.0 if f > 0 else 1e-4, max(f, 1e-4), 1.0 if f > 0 else 1e-4])
                sm.append({"input": ia, "output": add(np.array(vals, np.float32)), "interpolation": "LINEAR"})
                ch.append({"sampler": len(sm) - 1, "target": {"node": ni, "path": "scale"}})
        J["animations"].append({"name": cname, "channels": ch, "samplers": sm})
    while len(buf) % 4:
        buf.append(0)
    J["buffers"].append({"byteLength": len(buf)})
    js = json.dumps(J, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    total = 12 + 8 + len(js) + 8 + len(buf)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<III", 0x46546C67, 2, total))
        fh.write(struct.pack("<II", len(js), 0x4E4F534A)); fh.write(js)
        fh.write(struct.pack("<II", len(buf), 0x004E4942)); fh.write(bytes(buf))


if __name__ == "__main__":
    main()
