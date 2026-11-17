---
name: concrete-mold-casting
description: Use when designing, checking or producing a cast concrete or GFRC piece (planters, vessels, basins, panels, furniture) from a multi-part mold: printed or CNC molds, silicone or fiberglass mother molds, draft and parting lines, GFRC mix with integral pigment, reinforcement, pour, cure, demold and a small production run. Checks the mold model for pour path, leaks, flooding, air traps, undercuts, draft and core uplift.
metadata:
  author: Alican Rowe (@alicanrowe)
---

# Concrete mold casting

Design a mold that fills, vents, holds and comes apart; mix and pour GFRC that comes out the same colour every time; plan the run. Check the mold model before printing or pouring.

## Before designing
1. Read `references/mold-design.md`. For the mix read `references/gfrc-mix.md`; for pour day `references/pour-cure-demold.md`; for more than one unit `references/production-planning.md`.
2. Start a project page from `references/project-template.md`. Write the piece's mold spec (`<piece>.moldcheck.json`): units, up axis, wall, `min_wall`, `min_draft`, density, `pour` point, `fill_level`, `rim`, printer `bed`, and `groups` (for example the core pieces).
3. Editing an existing mold: open the file the project page names as current and check its hash. Never work from remembered sizes.

## While designing
- One mold part = one closed solid, in its assembled position, all parts in one frame. Put each part's pull in its name: `A3_pull_137_deg`, `CORE_pull_up`, `BASE_pull_down`.
- Even wall: 3/4 in (19 mm) for poured premix at planter scale, 1/2 in minimum. Floor as thick as the wall or thicker.
- Every concrete-facing face drafted away from its piece's pull: 1–2° on sealed smooth prints, more for texture. No undercuts, unless the face is a silicone glove that peels.
- Cores come out through the opening: key pieces first, parallel-sided. Name the demold order on the project page.
- A funnel or riser above the rim; a vent at the top of every ceiling; no path from the cavity into the core's interior; nothing that lets the pour land on a lid.
- Flanges on every seam, bolts every 4–6 in on the lower half, clay or caulk on the outside of each seam.
- **Core hold-down** that bolts to the base or a bridge. The checker's `group_force_N` z for the core is the uplift; the hold-down must beat it with margin. Weight and friction caps don't count.
- Every piece fits the printer bed.

## Before saying the mold is done
1. Export a new numbered version (never overwrite), then run:
   `python3 scripts/moldcheck.py MOLD_DIR_or_GLB --spec <piece>.moldcheck.json --res 2 --json out.json`
   and again at `--res 1.7`. Trust flags that show up at both. Needs `pip install trimesh manifold3d numpy scipy scikit-image`.
2. Read every flag (`references/verification.md`). Fix in order: hygiene, interference, no_pour_path, leak, floods, air_trap, unfilled, undercut, low_draft, thin_wall, bed. To test a fix before re-modelling, put it in the spec's `add` / `remove` and re-run; then model it for real and run again without the patch. Anything intended goes in `allow` with the reason.
3. Read the reported numbers: litres per pour, mass, wall p5, push-off force per piece, core uplift. Size bolts and the hold-down to 2× the force.
4. Diff part volumes and bounds against the previous version: any change that wasn't meant is a stray edit.
5. Cut a section through the cast (`--cast-stl`) and look at it.

## Mix, pour and production
- Turn the checker's litres into a shopping list and bucket weights:
  `python3 scripts/gfrc_batch.py --from-check out.json --units N --test 1 --mode bagged|scratch --imperial`
- Integral black: synthetic black iron oxide at 3–6% of cement weight, **one lot** for the whole run, weighed to 0.1 g, mixed in before sand and fiber. Same water every batch; water changes colour more than pigment.
- Closed shell-and-core molds take **premix** GFRC, poured and vibrated, two lifts if uplift is high. Spray-up is for open one-sided molds.
- One test pour before buying for the run. Fix the mold in CAD and re-check before pour 2.
- Keep a pour log (batch weights, water, pigment lot, temperature, demold time, defects) for every unit.

After changing `scripts/moldcheck.py`, run `python3 scripts/tests/make_fixtures.py && python3 scripts/tests/run_tests.py`: every planted mistake must be caught and the good mold must stay clean.
