#!/usr/bin/env python3
"""Build small test molds for moldcheck: one good cup mold and one copy per planted mistake.

The cup: 100 x 100 mm outside, 10 mm wall and floor, 120 mm tall, cast open end up.
Mold: base plate (pull down), four shell sides (pull +x, -x, +y, -y), a tapered core
(pull up, 2 deg draft) hung from a top bar. Concrete is poured into the wall gap at
(45, 0, 135) and filled to the rim at z = 120.

Each fixture is a folder of STLs plus a spec. Run run_tests.py to check moldcheck against them.
"""
import json, os, shutil
import numpy as np
import trimesh
import manifold3d as mf

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fixtures")


def M(mesh):
    return mf.Manifold(mf.Mesh(vert_properties=np.asarray(mesh.vertices, np.float32),
                               tri_verts=np.asarray(mesh.faces, np.uint32)))


def T(man):
    m = man.to_mesh()
    return trimesh.Trimesh(np.asarray(m.vert_properties)[:, :3], np.asarray(m.tri_verts), process=True)


def box(x0, x1, y0, y1, z0, z1):
    b = trimesh.creation.box(extents=[x1 - x0, y1 - y0, z1 - z0])
    b.apply_translation([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2])
    return b


def frustum(w0, w1, z0, z1):
    """square frustum: width w0 at z0, w1 at z1"""
    a, b = w0 / 2, w1 / 2
    v = [[-a, -a, z0], [a, -a, z0], [a, a, z0], [-a, a, z0], [-b, -b, z1], [b, -b, z1], [b, b, z1], [-b, b, z1]]
    return trimesh.convex.convex_hull(np.array(v, float))


def good_parts():
    p = {}
    p["BASE_pull_down"] = box(-70, 70, -70, 70, -10, 0)
    # four shell sides, each covering one face of the cup; corners belong to the x pieces
    p["SX_pos_pull_0_deg"] = box(50, 70, -70, 70, 0, 130)
    p["SX_neg_pull_180_deg"] = box(-70, -50, -70, 70, 0, 130)
    p["SY_pos_pull_90_deg"] = box(-50, 50, 50, 70, 0, 130)
    p["SY_neg_pull_270_deg"] = box(-50, 50, -70, -50, 0, 130)
    # core: 80 mm at the floor (z 10), widening upward at 2 deg, up to z 150; bar on top
    w1 = 80 + 2 * 140 * np.tan(np.radians(2))
    core = M(frustum(80, w1, 10, 150)) + M(box(-80, 80, -6, 6, 150, 160))
    p["CORE_pull_up"] = T(core)
    return p


SPEC = {"units": "mm", "up": "z", "wall": 10.0, "min_wall": 5.0, "min_draft": 1.0, "density": 2100,
        "pour": [47, 0, 140], "fill_level": 120, "rim": 120, "groups": {"core": "^CORE"}}


def write(name, parts, spec=SPEC):
    d = os.path.join(OUT, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    for k, m in parts.items():
        m.export(os.path.join(d, k + ".stl"))
    json.dump(spec, open(os.path.join(OUT, name + ".json"), "w"), indent=1)


def main():
    os.makedirs(OUT, exist_ok=True)
    write("cup_good", good_parts())

    # undercut: core wider at the bottom than the top (pull up locks)
    p = good_parts()
    p["CORE_pull_up"] = T(M(frustum(80, 70, 10, 150)) + M(box(-80, 80, -6, 6, 150, 160)))
    write("cup_undercut", p)

    # no draft: straight core
    p = good_parts()
    p["CORE_pull_up"] = T(M(box(-40, 40, -40, 40, 10, 150)) + M(box(-80, 80, -6, 6, 150, 160)))
    write("cup_no_draft", p)

    # no pour path: a lid closes the top of the wall gap above the rim
    p = good_parts()
    lid = M(box(-50, 50, -50, 50, 122, 126)) - M(frustum(80, 80 + 2 * 140 * np.tan(np.radians(2)), 10, 150))
    p["LID_pull_up"] = T(lid)
    write("cup_no_pour_path", p)

    # leak: a 6 mm slot through one shell side
    p = good_parts()
    p["SY_neg_pull_270_deg"] = T(M(p["SY_neg_pull_270_deg"]) - M(box(-3, 3, -75, -45, 30, 80)))
    write("cup_leak", p)

    # air trap: a blind pocket up into the underside of the core (concrete fills it from below)
    p = good_parts()
    p["CORE_pull_up"] = T(M(p["CORE_pull_up"]) - M(box(-10, 10, -10, 10, 5, 30)))
    write("cup_air_trap", p)

    # floods: a hole in the floor of a hollow core lets concrete into the core
    p = good_parts()
    w1 = 80 + 2 * 140 * np.tan(np.radians(2))
    hollow = M(frustum(80, w1, 10, 150)) - M(frustum(64, w1 - 16, 16, 151))
    hollow = hollow - M(box(-4, 4, -4, 4, 5, 20))
    p["CORE_pull_up"] = T(hollow + M(box(-80, 80, -6, 6, 150, 160)))
    write("cup_floods", p)

    # interference: one side pushed 3 mm into the cavity's neighbour piece
    p = good_parts()
    p["SY_pos_pull_90_deg"] = box(-53, 53, 50, 70, 0, 130)
    write("cup_interference", p)

    # hygiene: an open (non-watertight) shell side
    p = good_parts()
    m = p["SX_neg_pull_180_deg"].copy()
    m.update_faces(np.arange(len(m.faces)) > 1)
    p["SX_neg_pull_180_deg"] = m
    write("cup_hygiene", p)

    # thin wall: a drafted bump on one shell side leaves about 3 mm of wall
    p = good_parts()
    v = [[50, -20, 40], [50, 20, 40], [50, 20, 80], [50, -20, 80],
         [45, -15, 45], [45, 15, 45], [45, 15, 75], [45, -15, 75]]
    bump = trimesh.convex.convex_hull(np.array(v, float))
    p["SX_pos_pull_0_deg"] = T(M(p["SX_pos_pull_0_deg"]) + M(bump))
    write("cup_thin_wall", p)
    print("fixtures written to", OUT)


if __name__ == "__main__":
    main()
