# GFRC mix design, black pigment and reinforcement

GFRC is a cement-rich sand mortar with acrylic polymer and alkali-resistant (AR) glass fiber. It's strong in thin sections because the fiber carries tension. Two ways to place it:

| | Premix (poured or vibrated) | Spray-up (face coat + backer) |
|---|---|---|
| How | Fiber mixed into the batch, poured into a closed mold | Thin face coat sprayed with no fiber, then a fiber-loaded backer sprayed or hand-packed |
| Fiber | 1/2 in (12 mm) AR fiber, 2–3% of mix weight | Backer 3–5% AR fiber, 3/4–1 in |
| Equipment | Paddle mixer, vibration table or tapping | Hopper gun + compressor (face), hopper or hand-pack (backer) |
| Fits | **Closed two-sided molds (shell + core)** like a vessel | Open one-sided molds (panels, basins, the outside of a bowl) |
| Surface | Fewer bug holes if vibrated well | Best surface; face coat has no fiber to show |

A shell-and-core vessel mold is closed, so it's **premix, poured**, with a thin face coat brushed into the shell first if the surface has to be perfect.

## Starting mix (by weight of binder)
Binder = cement + pozzolan. Adjust in a test batch before the first real pour.

| Material | Amount | Notes |
|---|---|---|
| White or grey Portland cement (Type I/II) | 0.90 | Grey is fine for black |
| Metakaolin | 0.10 | Cuts efflorescence (white bloom on black concrete) and strengthens |
| Silica sand, 30–70 mesh, dry | 1.0 | Washed and kiln-dried |
| Water (total, counting the polymer's water) | 0.30–0.35 | Lower is stronger; use the water reducer to get flow |
| Acrylic polymer (e.g. Forton VF-774, Chem-Crete) | 5–7% solids on binder | Lets the piece air-cure without wet curing |
| Water reducer (polycarboxylate) | maker's dose, often 0.2–1% of cement | Add slowly; overdose segregates |
| AR glass fiber (12 mm, premix) | 2–3% of total mix weight | Add last, mix 30–60 s only (long mixing balls it) |
| Black iron oxide pigment | 3–6% of cement weight | See below |

**Bagged complete mixes** (GFRZ Pro, Buddy Rhodes, Xtreme) already contain the cement, sand, pozzolan and polymer. Follow the bag for water and fiber, and dose pigment on the bag's cement content (if the maker won't say, assume 40–50% of the bag weight is cement).

`scripts/gfrc_batch.py` turns a casting volume into a shopping list and per-bucket weights for either kind.

## Black all the way through (integral pigment)
- Use **synthetic black iron oxide** (Fe₃O₄, e.g. Bayferrox 318/330, GOODTAKE black). Carbon black is stronger but washes out outdoors and wrecks strength above about 2%; avoid for planters.
- Dose **3–6% of cement weight**. Colour saturates near 5–6%; more costs strength and doesn't darken.
- **One lot** for the whole run, bought up front. Lots differ visibly.
- Weigh pigment for every batch on a 0.1 g scale. Pre-bag doses the night before.
- Mix pigment with the water (or the dry mix) first, before the sand and fiber, for 2 minutes. Streaks come from short mixing.
- Same water, same cement, same mixing time, same cure, every unit. Water content changes colour more than pigment does: wetter = lighter.
- Black concrete shows efflorescence. Metakaolin in the mix, a cure under plastic, and a penetrating sealer (silane/siloxane) after 28 days keep it away. An acrylic or enhancing sealer deepens the black.
- Make a test tile at the planned dose and let it cure and dry fully (7+ days) before judging colour. Wet concrete looks darker.

## Reinforcement
- **AR glass fiber** is the main reinforcement. Never E-glass: cement eats it.
- A vessel 18–24 in tall with 3/4 in walls in premix GFRC needs nothing more.
- Add an **AR glass scrim** or a basalt mesh layer at the mid-thickness if the piece is larger, carries point loads (feet, lifting), or the wall is under 1/2 in.
- Steel rebar/mesh needs 3/4 in cover each side: impossible in a 3/4 in wall, and it rusts through. Don't.
- Inserts (threaded sockets for feet or lifting) get a sleeve of fiber-rich mix and at least 1 in of edge distance.

## Water-to-cement ratio and strength
- GFRC premix at w/c 0.32 with 6% polymer cures to roughly 6,000–9,000 psi compressive, 1,500–2,500 psi flexural.
- Every 0.05 of added water costs about 10–15% strength and makes the colour lighter and less even.

## Safety
Cement is caustic; AR fiber itches; dry pigment and silica dust are respiratory hazards. Nitrile gloves, eye protection and a P100 respirator when handling dry materials.
