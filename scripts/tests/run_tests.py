#!/usr/bin/env python3
"""Run moldcheck on every fixture and compare the flag kinds with expected.json."""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
exp = json.load(open(os.path.join(HERE, "expected.json")))
ok = True
for name, want in exp.items():
    out = os.path.join(FIX, name + ".out.json")
    subprocess.run([sys.executable, os.path.join(HERE, "..", "moldcheck.py"), os.path.join(FIX, name),
                    "--spec", os.path.join(FIX, name + ".json"), "--res", "1.25", "--json", out, "--quiet"],
                   check=False)
    got = sorted({f["kind"] for f in json.load(open(out))["flags"]})
    good = sorted(want) == got
    ok &= good
    print(f"{'PASS' if good else 'FAIL'}  {name:20s} expected {sorted(want)}  got {got}")
print("all passed" if ok else "FAILURES")
sys.exit(0 if ok else 1)
