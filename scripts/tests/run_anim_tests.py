#!/usr/bin/env python3
"""moldanim on the cup fixtures: the good mold animates with no collisions; the undercut core has no way out;
a build that sends the base up through the floor is caught."""
import json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
S = os.path.join(HERE, "..")
tmp = tempfile.mkdtemp()
ok = True


def anim(name, spec):
    cast = os.path.join(tmp, name + "_cast.stl")
    subprocess.run([sys.executable, os.path.join(S, "moldcheck.py"), os.path.join(FIX, name), "--spec",
                    os.path.join(FIX, name + ".json"), "--res", "1.25", "--cast-stl", cast, "--quiet"], check=False)
    rep = os.path.join(tmp, name + ".anim.json")
    r = subprocess.run([sys.executable, os.path.join(S, "moldanim.py"), os.path.join(FIX, name), "--cast", cast,
                        "--spec", spec, "--out", os.path.join(tmp, name + ".glb"), "--report", rep,
                        "--plan-res", "4", "--faces", "2000", "--slices", "12"], capture_output=True, text=True)
    return r.returncode, json.load(open(rep))


def check(label, cond, detail):
    global ok
    ok &= bool(cond)
    print(f"{'PASS' if cond else 'FAIL'}  {label:34s} {detail}")


spec = os.path.join(HERE, "anim_cup.json")
code, rep = anim("cup_good", spec)
n = {c: len(v.get("collisions", [])) for c, v in rep["clips"].items()}
check("cup_good animates clean", code == 0 and not any(n.values()), f"exit {code}, collisions {n}")
check("cup_good core planned out", "CORE" in rep["paths_mm"], str(rep["paths_mm"].get("CORE", "no path"))[:60])

code, rep = anim("cup_undercut", spec)
check("cup_undercut core has no way out", code != 0 and any("no way out" in w for w in rep["warnings"]),
      "; ".join(rep["warnings"])[:80])

bad = json.load(open(spec))
bad["build"][0] = {"label": "base", "parts": "^BASE", "move": "vector", "vector": [0, 0, 1], "dist": 120}
bad["build"] = [bad["build"][2], bad["build"][0], bad["build"][1], bad["build"][3]]  # sides, then the base comes down through them
bs = os.path.join(tmp, "bad.json"); json.dump(bad, open(bs, "w"))
code, rep = anim("cup_good", bs)
hits = rep["clips"]["build"].get("collisions", [])
check("collision in build is caught", code != 0 and hits, f"{len(hits)} collisions, first {hits[:1]}")
print("all passed" if ok else "FAILURES")
sys.exit(0 if ok else 1)
