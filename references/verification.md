# Verification: moldcheck flags and what to do

Run:
```
python3 scripts/moldcheck.py MOLD_DIR --spec piece.moldcheck.json --res 2 --json out.json
```
Then run it again at a second resolution (for example `--res 1.7`). Voxel results move a little with resolution: trust a flag that shows up at both.

Fix in this order: hygiene, interference, no_pour_path, leak, floods, air_trap, unfilled, undercut, low_draft, thin_wall, bed.

| Flag | Meaning | Usual fix |
|---|---|---|
| `hygiene` | A part isn't a closed, consistently wound solid | Repair or re-export the mesh; nothing else is trustworthy until it's fixed |
| `no_pull` | No pull direction in the name or spec | Name it `..._pull_N_deg`, `_pull_up` or `_pull_down`, or add it to `parts` in the spec |
| `interference` | Two mold parts overlap | Real overlap: fix CAD. Intended press fit: `allow` it with the reason |
| `no_pour_path` | Concrete poured at `pour` lands on a lid or cap above the fill level, or spills outside | Move the pour point into the funnel or open a path down to the cavity |
| `leak` | The pour reaches the outside below the fill level; `places` shows where | Close the gap: seal, add a flange, extend a piece |
| `floods` | The pour fills a big non-wall space (core interior, gap); `entries` shows where it gets in | Close vents in the core floor, seal core seams, fill the core |
| `unfilled` | Wall cavity the pour never reaches | Usually a blocked passage; open it or add a second pour point |
| `air_trap` | Air under a ceiling can't rise to the surface | Add a vent at the highest point, or tilt the mold while pouring |
| `undercut` | A concrete-facing face moves into the concrete along the part's pull; `at_mm` gives where | Change the pull, split the piece, or add draft |
| `low_draft` | Concrete-facing area below `min_draft` | Add draft in CAD, or use a flexible liner there |
| `thin_wall` | The casting is thinner than `min_wall` somewhere | Thicken the mold gap there; check core centring |
| `bed` | Part doesn't fit the printer bed in any orientation | Split it |

Secondary flags are normal: a leak through a slot also shows `low_draft` (the concrete in the slot locks the piece), a flooded core shows `undercut`. Fix the first cause and re-run.

## Reported numbers
- `cast_cm3`, `cast_below_rim_cm3`, `riser_cm3`, `cast_kg`: what one pour uses and weighs (riser included in the pour, not in the piece).
- `wall_mm` p5/p50/p95: thickness of the casting. p5 well below the design wall points to a thin spot or an off-centre core.
- `parts.<name>.push_off_N`: hydrostatic force pushing that piece off along its pull. Size its bolts or clamps for 2× this.
- `group_force_N`: total force on a group (e.g. the core). Its z is the **uplift**: the hold-down must beat it.
- `print_cm3`, `print_kg_solid`: mold material if printed solid; multiply by your infill factor.

## Spec tools for checking a fix before re-modelling
`add` and `remove` put simple solids into the voxel grid, so a fix can be tried without touching CAD. Each entry has a `name` and a `type`:
- `{"name": "...", "type": "box", "center": [x,y,z], "size": [sx,sy,sz], "rot_z": deg}`
- `{"name": "...", "type": "cylinder", "center": [x,y], "r": r, "z": [z0,z1]}`
- `{"name": "...", "type": "annulus", "center": [x,y], "r": [r0,r1], "z": [z0,z1]}` (centre defaults to the axis)
- add `"plug": true` (or `"in"`) and `"reach": mm` to a box to fill only where it's clear for `reach` mm along its local +x (or −x): a board closing an opening, a cap on a vent. The report gives each plug's area.
Removes run before adds. When a fix works, model it properly in CAD and re-run without the patch.

## What it doesn't check
Strength of the mold under pressure (it gives forces, not stresses), print warping, seal quality, release, how the concrete flows (it fills like water), shrinkage, colour. Look at a section through the cast (`--cast-stl`) and make a test pour.
