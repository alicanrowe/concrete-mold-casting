# Mold design

How to design a mold for a cast concrete (GFRC) piece so it fills, vents, holds its shape under the pour, and comes apart without breaking the piece or itself.

## 1. Pick the mold family

| Family | What it is | Good for | Watch out |
|---|---|---|---|
| **Direct negative, printed** | The mold itself is printed (PETG/PLA/ASA) in pieces, bolted together, sealed | 1–20 casts, complex shapes, no master needed | Layer lines print into the concrete unless sealed (XTC-3D, epoxy, primer + sand). PLA creeps warm; PETG or ASA for summer pours. Each piece must fit the bed. |
| **Direct negative, CNC** | Machined MDF/HDPE/foam pieces | Big flat or ruled surfaces, 1–50 casts | Seal MDF (shellac + wax or epoxy). Foam is one-shot unless hard-coated. |
| **Positive master → silicone glove + rigid mother mold** | Print or machine the *piece* (the positive), pour or brush silicone on it, back the silicone with a fiberglass or plaster mother mold | Fine surface, undercuts the glove can peel off, 20–100+ casts | Silicone is expensive (about 1 L per 1.5 L of brush-on for a glove 6–10 mm thick). The mother mold needs its own parting lines and draft. |
| **Positive master → fiberglass (FRP) mold** | Gel coat + chopped mat laid on the master | Large smooth shells, sprayed GFRC face + backer | No undercuts at all. Needs real draft (3°+). |
| **Inflatable / collapsible core** | Bladder or segmented core inside a rigid shell | Closed vessels with a narrow neck | Bladders float: hold them down and size for hydrostatic pressure. |

**Split the piece, not only the mold.** A big piece (a stool, a bench, a long planter) can be cast as several smaller pieces that bolt together, instead of one casting in one big mold. If the pieces are identical (four quarter-shells of a four-legged stool, each one leg and a quarter of the apron, plus a separate seat bowl), one small mold casts all of them: a quarter of the mold to print, every piece fits the bed, no core, and each casting is open and easy to vibrate. The cost is the joint: give every mating edge a cast-in flange 15–20 mm wide with bolt bosses or cast-in threaded inserts every 100–150 mm, register the pieces with pins, and let the bolts and seams show as part of the design rather than hiding them. Check the joint like a part: `seating-load-check` on the assembled piece, with the bolts, not the concrete, carrying the tension. (Seen in a Plasthetic.s stool form study, Nov 2026: four molded leg-quarters flanged and bolted, seat bowl pinned on top.)

For a vessel with a neck narrower than the belly (a planter, an urn) the **core** is the hard part: it has to come out through the neck. Either segment it (keys first, like a barrel's staves), use a collapsible core, or cast upside down with an open bottom and a separate floor.

## 2. Wall, floor and rim
- GFRC premix (vibrated or poured): walls **3/4 in (19 mm)** is comfortable for a vessel that size; 1/2 in (12–13 mm) is the practical minimum with 1/2 in fiber; thinner needs spray-up.
- Sprayed GFRC: 3/8–5/8 in (10–16 mm) total: a 1/8 in face coat plus backer.
- Floors carry the soil load: same as the wall or thicker. A drain hole needs a pin or tube in the mold, and the floor gets thicker around it.
- Keep wall thickness even (±20%). Thick lumps crack on shrinkage and set more slowly; thin spots are weak and show fibers.
- Rims: round or chamfer the outside edge of the casting 1–3 mm in the mold. Sharp concrete edges chip on demold.

## 3. Parting lines and pulls
Each mold piece moves off the casting in one straight direction: its **pull**. Put it in the part's name (`A3_pull_137_deg`, `CORE_pull_up`) so `moldcheck` can read it.

- Every concrete-facing surface must have **draft** away from its pull: the angle between the face and the pull direction, measured so the face moves away from the concrete as the piece slides.
  - Smooth, sealed print or FRP: **1–2°** minimum, 3° is easy.
  - Textured surfaces: add 1° for every 0.001 in (0.025 mm) of texture depth.
  - Silicone gloves can take 0° and modest undercuts (the glove peels).
- **Undercut** = a face that moves *into* the concrete when the piece is pulled. It locks the piece. The checker flags these with their location.
- Put parting lines where they'll be ground or are hidden: on a sharp edge, under a lip, on the bottom. A rounded vessel needs parting lines on the belly; plan to dress them with a diamond pad.
- Radial shells around a round vessel: split into pieces whose pull is radial at the piece centre. A piece spanning more than about 90° of a round shape locks at its edges.
- Cores: segment so the **key pieces** (parallel-sided, pulled inward first) free the others. Name the order in the project page.

## 4. Seal, flange and clamp
- Every seam needs a flange or a tongue-and-groove, sealed with modelling clay or silicone caulk on the outside. Concrete paste leaks through a 0.2 mm gap.
- Bolt spacing on flanges: about 4–6 in (100–150 mm) on the lower half of a tall mold, where pressure is highest. Spring clamps are fine for registration, not for holding pressure.
- Hydrostatic pressure at the bottom = ρ·g·h: for 2,100 kg/m³ and 0.5 m, about 10 kPa (1.5 psi). Over a 300 × 300 mm shell piece that's about 900 N (200 lbf) trying to push it off. `moldcheck` reports this per piece along its pull.
- **Core uplift**: concrete pushes the core up with a force equal to the weight of the concrete it displaces below the core. A 20 L core displacement is about 400 N (90 lbf); bigger cores easily reach 2 kN. Hold the core down with a bolted bridge or threaded rod to the base, not with weight or friction.

## 5. Fill, vent, riser
- Pour at the highest point, into a **funnel or riser** that holds concrete above the rim. The riser feeds shrinkage and is struck off.
- Every ceiling (a surface facing down onto concrete) needs a vent at its highest point, or the mold has to be tilted while filling. `moldcheck` flags trapped air.
- Never let a vent or gap open into the core's interior: the core floods.
- The concrete must not be able to land on top of a lid or cap and stop there. `moldcheck` flags `no_pour_path` for that.

## 6. Release and surface
- Printed molds: seal (XTC-3D or epoxy), sand 220–400, then a release (Formcoat WB250, paste wax, or a water-based release). Re-apply release before every pour.
- Silicone: usually no release; a light mist helps with high-polymer mixes.
- Test release on a scrap printed with the same settings before the first real pour.

## 7. Printing the mold
- Size every piece to fit the bed (put the bed in the spec as `bed`). The checker flags pieces that don't fit in any box orientation.
- 3–4 walls, 15–25% gyroid infill is plenty for a backed shell. Flanges need 100% around bolt holes.
- Print concrete-facing surfaces as vertical walls where possible (smoother than top or bottom skins).
- Count print mass (`print_kg_solid` × infill factor) and time before committing.

## 8. Model it so it can be checked
- One mesh per mold part, all in their assembled positions, one shared frame. Export STL per part or one GLB.
- Watertight solids only.
- Write the spec (`<piece>.moldcheck.json`): units, up axis, wall, min wall, min draft, density, pour point, fill level, rim, bed, groups.
- Run `scripts/moldcheck.py` and read every flag (`references/verification.md`).
