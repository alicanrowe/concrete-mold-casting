# Project K: mold and pour plan

Nine black GFRC planters, 35 in tall and 24 in wide, black all the way through, set out in a ring about 6 ft across. Each pot has two large side openings (at 70° and 290°), a 3/4 in wall, a solid floor with a drain hole, feet and a logo on the bottom.

- **Mold file checked:** `K_mold_print_files_STL_2026-10-26_engraved.zip` (53 STLs, the 2026-10-26 engraved set)
- **Specs:**
  - `k.moldcheck.json` (the mold as drawn)
  - `k-fixes.moldcheck.json` (the same mold with the fixes below patched in as voxel solids)
- **Checker output:**
  - `k.check-2mm.json`
  - `k-fixes.check-2mm.json`
  - `k-fixes.check-1.7mm.json`
- **Checked:** 2026-11-17, `moldcheck.py` at 2.0 mm and 1.7 mm

## The mold
- 3D-printed direct negative in 53 pieces:
  - 28 shell pieces in four bands: A lower, B belly, C shoulder, D neck
  - 22 core pieces: KA to KD, with key pieces KA2/KA5, KC2/KC5 and KD2/KD5
  - base plate, pour cap and funnel
- Every piece has its pull in its name, for example `A3_..._pull_137_deg` or `CORE..._pull_up`.
- 41 bolt joints (1/4-20 x 1 in) and 48 spring-clamp positions.
- Assembly order: base, band A, core stacked and lowered in, bands B to D, then the cap and funnel.
- Wall 19 mm, floor 19 mm. The pour goes into the funnel above the neck. The fill level is the top of the funnel throat (z 489 mm). The rim is at z 457 mm.

## What the checker found on the mold as drawn
1. **No pour path.** Concrete poured into the funnel lands on a ring of D1 to D4 that closes the top of the wall gap. It sits at z 463, above the rim, so nothing reaches the cavity. This matches the Nov 13 print check.
   - Fix in CAD: cut that ring back over r 89 to 116 mm so the wall gap opens to the funnel.
   - Then add a riser collar (r 115.5 to 122 mm, up to z 494). Once the ring is open, the riser is open sideways.
2. **The side openings leak.** At both openings the core stops short of the shell's flat wall. That leaves a slot about 12 mm wide, and the concrete runs out through it.
   - Fix in CAD: extend the core pieces at each opening out to the shell's flat wall, or add a closure piece there. The closure is about 2,000 cm² per opening.
   - Seal it with clay.
   - The core's end at the openings is ragged, so a flat board can't seal it. It has to be modelled.
3. **The core floods through its floor vents.** Eight 9 mm holes in the core floor (z −400) let concrete into the core's interior.
   - Plug them with printed plugs or clay, or take them out of the CAD.
4. **The core floats.** The concrete pushes the core up with about 2,080 N (470 lbf), and sideways with about 1,040 N (235 lbf) towards the openings.
   - The pour cap is a press fit on the neck (8 to 15 mm³ overlap with D1 to D4). It holds nothing.
   - Weight on top (gravel bags) is not a dependable hold-down.
   - Fix: two 3/8-16 threaded rods from the base plate up through the core floor to a bridge across the neck, nutted at both ends.
     - Two of the eight vent holes are in the right place for the rods if they're opened up to 10 mm and sealed with a washer and clay.
     - Size the rods and bridge for 4,200 N (about 2× the uplift).
   - Pour in two lifts (see below). That about halves the uplift on the second lift.
5. **Shell pieces need bolts, not clamps, low down.**
   - Hydrostatic pressure at the floor is about 18.7 kPa (2.7 psi).
   - The pieces are pushed off along their pulls with 58 to 540 N each. The largest are C4, C8, B4, A8 and the C3/C5 pair, all 420 to 540 N.
   - A 2 in spring clamp holds a few tens of newtons.
   - Every vertical seam in bands A and B needs bolts at 4 to 6 in spacing. Clamps are for registration only.

Patching fixes 1 to 3 into the spec (`k-fixes.moldcheck.json`) clears `no_pour_path` and `floods`.

## What is left after the fixes (seen at both 2.0 and 1.7 mm)
- **Core pieces lock at the edges of the side openings.**
  - KB1 to KB4 and KC1, KC3, KC4, KC6 each have 27 to 43 cm² of face that moves into the concrete along the piece's pull. Each patch is centred at the reveal of an opening, at about 27°, 113°, 247° and 333°.
  - Check these faces in CAD. Either give the reveal faces draft along the pull, or pull those pieces along the opening's axis.
  - KA1 and KA6 have a smaller patch (9 cm², worst −9°).
- **Low draft:**
  - KA2/KA5 have about 42% of their face under 1°. That's the key pieces sliding across the floor of the pot. Accept it with a good release coat, and pull the keys straight.
  - The base plate has 26% under 1°. That's the pocket wall around the floor, at 0°. Add 2° in CAD, or lift the pot off the base rather than sliding it.
  - D1 to D4 have 5% each, and B1, B2, B6, B7, C1, C2, C6 and C7 have 3 to 16% each, near the opening edges.
- **Small leaks and air at the seams.**
  - At 1.7 mm the pour reaches gaps between flange faces that the 2.0 mm grid closes. The cavity grows from 18.9 to 21.0 L, with air pockets in those gaps.
  - In the real mold, clay or caulk on every seam from the outside closes these.
  - The one air pocket seen at both resolutions is small (about 7 cm³), at the lower edge of the 290° opening. Tap there while pouring. If the test pour shows bug holes on that edge, drill a 3 mm vent at its highest point.
- **Thin cast at the bottom:** the logo and feet relief under the floor (z −423) shows as thin. It's intended.
- **Bed:** 13 pieces don't fit a 325 × 320 × 325 mm bed in any orientation: BASE, C1, C2, C6, C7, D1 to D4, F, KC1 and KC6. They need a bigger printer or a split.

## Numbers per pot
| | |
|---|---|
| Concrete below the rim | 18.9 L |
| Riser | 0.5 L |
| Budget per pour | **21 L** (covers seam fill, bucket and funnel loss) |
| Finished pot | about 39.6 kg (87 lb) |
| Wall thickness | p50 20 mm |
| Mold print, solid | 21.6 L. At typical infill, 12 to 14 kg of filament per set |

## Mix: bagged GFRC premix, poured
The mold is closed (shell and core), so this is premix GFRC, poured and vibrated, not spray-up.

The run is 9 pots plus 1 test pour, 21 L each, with 10% waste:
```
python3 scripts/gfrc_batch.py --litres 21 --units 9 --test 1 --bag-kg 22.7 \
    --water-kg-per-bag 3.9 --fiber-kg-per-bag 0.61 --pigment-pct 5 --imperial
```
| Material | Run total | Per batch (2 batches per pot) |
|---|---|---|
| GFRZ Pro (assumed 50 lb bags) | **18 bags**: the 19 in the cart covers it | 19.3 kg (42.6 lb) |
| Water | 70 kg (about 18.5 gal) | 3.32 kg (7.3 lb) |
| AR glass fiber | 11 kg (24 lb): **3 × 10 lb bags, the cart has 2** | 519 g |
| Water reducer (Flow+ Pro) | 0.55 kg at 0.3% of cement. The 1 qt in the cart is enough. Use the maker's dose. | 26 g |
| Black iron oxide | 9.2 kg (20 lb) at 5% of cement: **20 lb from one lot, the cart has 10** | 435 g |

The bag yield isn't published. The calculator estimates 13 L per bag from the weight and density. Weigh the test pour's leftovers to correct it.

The pigment dose assumes the bag is about 45% cement. Make a test tile at 4% and 5% and judge them dry at 7 days before ordering the full lot.

Use one pigment lot for all nine pots, and pre-weigh every dose on a 0.1 g scale.

## Pour day (per pot)
1. Mold sealed with XTC-3D and sanded. Two thin coats of Formcoat WB250. Every seam clayed from the outside. Core floor vents plugged.
2. Assemble in order: bolts on bands A and B, then clamps. Fit the threaded-rod hold-down and the bridge. Level the base.
3. Shop at 60 to 80 °F. In November that means a heated space, for the mix and for the 48 h cure.
4. Batch 1, 11 L:
   - water, water reducer and pigment, 30 s
   - dry mix, 2 to 3 min
   - fiber, 30 to 60 s
5. Pour it slowly in one place at the funnel. Tap the shell in rings from the bottom up for 3 to 5 minutes.
6. Wait 20 to 40 minutes, until the first lift stiffens. That locks the core.
7. Batch 2: pour to the top of the riser, then vibrate again. Cover the funnel with plastic.
8. Cure 48 h in the mold. Strike the riser at about 12 to 24 h.
9. Demold:
   - funnel, then cap and hold-down bridge
   - D, C, B and A bands in that order, each straight along its pull
   - lift the pot off the base
   - core key pieces first (KD2/KD5, KC2/KC5, then the KB pieces next to them, KA2/KA5), then the rest inward and up through the neck
10. Wrap the pot loosely in plastic for 5 to 7 days. Seal at 28 days: penetrating silane/siloxane first, then a matte enhancing sealer for the black. Waterproof the inside.

## Production: 9 pots from one mold set
| Week | Work |
|---|---|
| 1–3 | Fix the CAD (items 1 to 4 and the core lock at the openings). Re-run `moldcheck` until only the allowed flags are left. Print in PETG, seal and sand. |
| 3 | Order the materials, with one pigment lot. Make test tiles at 4% and 5%. |
| 4 | Test pour (pot 0). Demold at 48 h. Fix the mold, judge the colour at 7 days. |
| 5–8 | Pots 1 to 9 on a 2-day cycle: about 3 pours a week, so about 3 weeks. |
| +28 days each | Seal |

- A second mold set would halve the pouring time but doubles the print.
- Re-seal the concrete faces every 3 to 5 pours.
- Print spares of the pieces with thin flanges.
- Keep the pour log from `references/project-template.md` for every pot.

## Allowed flags after the CAD fixes (to put in the spec's `allow`)
- `thin_wall` at z −423: the logo and feet relief
- `low_draft` on KA2/KA5: sliding on the floor with release
- `interference` CAP with D1 to D4: a press fit, if it's kept as a cover only

## Fixes applied to the STLs (2026-11-17)
The four fixes above are now in the mold files: `K_mold_print_files_STL_2026-11-17_fixes.zip`. It has 57 files, the 53 mold parts (32 changed) plus 4 hold-down parts. They were made by editing the 2026-10-26 STLs with `fixes/apply_fixes.py`. The Onshape model still needs the same changes.

1. **Pour path:**
   - The ring over the wall gap is cut off D1 to D4.
   - Each D piece gets a 6.35 mm riser collar (r 115.5 to 121.85 mm, up to z 495) that carries the funnel.
2. **Side openings:**
   - The core skin continues to the flat wall on the 10 core pieces at each opening, following the vessel's inner surface. The surface is measured by `fixes/measure_core.py` and `fixes/measure_shell.py`. The skin doesn't just extrude straight out, because that would thin the wall at the opening edge by up to 12 mm.
   - The 12 flat-wall shell pieces get an 8.5 mm ledge, so the skin seats on a land. Before, it only had a 1 mm edge to seat on.
3. **Vents:** the eight core floor vents are plugged.
4. **Hold-down:**
   - a 2x6 bridge on the cap
   - two 3/8-16 rods at x = ±380 mm (34 mm clear of the shell), down to a 3/4 in bench board
   - the cap is no longer a press fit
   - a clay bead under the cap

**Re-check** (`k-2026-11-17.moldcheck.json`, at 2.0 and 1.7 mm): there's no `no_pour_path`, leak, flood, air trap or undercut at either resolution.

| | |
|---|---|
| Cast below the rim | 18.5 L |
| Riser | 0.54 L |
| Finished pot | 38.8 kg |
| Core uplift | 2,210 N (about 500 lbf) |
| Sideways push on the core | 1,060 N (about 240 lbf) |

The volume now agrees between the two resolutions, because the seams no longer fill.

What's left is accepted:
- The core skins touch the ledges (contact).
- The logo and feet relief shows as thin.
- Low draft on the base pocket and on the core floor pieces.
- The bed list.
