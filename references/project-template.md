# <Piece name>: mold and pour plan

- **Piece:** what it is, size, quantity, finish/colour
- **Current mold file:** path, date, sha256 prefix
- **Spec:** `<piece>.moldcheck.json`
- **Last check:** date, resolution(s), flags left and why they're allowed

## Mold
- Family (printed negative / CNC / silicone + mother mold / FRP)
- Pieces and pulls (table: name, pull, bed fit, mass)
- Parting lines and where the fins end up
- Seal, release, clamps and bolts
- Core hold-down: uplift from `moldcheck` and what resists it
- Pour point, riser, vents

## Mix
- Mode (premix / spray), bagged product or from scratch
- Per-unit litres (from `moldcheck`) and the `gfrc_batch.py` command
- Pigment: product, lot, % of cement
- Fiber, polymer, water reducer
- Test tile result

## Pour, cure, demold
- Lift plan, vibration
- Cure time and temperature
- Demold order (piece by piece)

## Production
- Units, mold sets, cycle time, schedule
- Materials list with quantities and what's bought

## Log
| Unit | Date | Temp | Water | Pigment lot | Demold h | Notes |
|---|---|---|---|---|---|---|

## Changes
Every mold change: date, what, why, and the checker result after.
