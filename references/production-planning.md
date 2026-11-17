# Production planning for a small run

How to plan 5–20 identical cast pieces from one mold set.

## 1. One mold or two?
- One mold set gives one cast per 24–48 h (pour, cure, demold, clean, re-release, reassemble).
- Count the cycle: assembly 1–2 h, mixing and pour 1 h, cure 24–48 h, demold 1 h, clean and re-release 1 h.
- 9 units on one mold at a 48 h cycle with a day off a week is about 3 weeks of pouring. A second mold set halves it, at the cost of printing it again.
- Printed molds wear: plan to re-seal after every 3–5 casts and to reprint the pieces that crack. Print one spare of every piece that has a thin flange.

## 2. Test pour first
Pour one unit with the real mold, mix and pigment before buying for the full run. It checks:
- leaks at seams and bolt holes
- core hold-down and uplift
- air at ceilings and vents
- demold order and draft
- colour after 7 days dry
- actual litres used (the riser and spill included)
Fix the mold (in CAD, re-run `moldcheck`) before pour 2. Count the test unit in the materials: it may be sellable.

## 3. Materials
- Buy all pigment from one lot, plus 10%.
- Buy cement or bagged mix for the whole run plus the test plus 10% waste, from one delivery if possible.
- Fiber, water reducer and polymer: check shelf life; polymer must not freeze.
- Consumables per pour: release, clay, plastic sheet, gloves.
- Use `scripts/gfrc_batch.py --units N --test 1` for the list.

## 4. Schedule template
| Day | Work |
|---|---|
| −14 to −7 | Print mold, seal, sand, dry-fit, run `moldcheck` on the as-printed CAD |
| −7 | Order materials (one pigment lot) |
| −3 | Test tile: colour and mix |
| 0 | Test pour |
| 2 | Demold test, inspect, fix mold |
| 7 | Judge colour, sign off |
| 8 onward | Pour every 2 days (or every day with two mold sets) |
| +28 per unit | Seal |

## 5. Keep a log per pour
Unit number, date, temperature, batch weights (actual), water, pigment lot, vibration time, demold time, defects, photos. The same table across all units is what makes the colour match.

## 6. Handling and weight
A 20 L GFRC piece weighs about 42 kg (93 lb). Plan two people or a dolly for demold and moving. Lift from under the floor, not the rim, until 7 days.
