#!/usr/bin/env python3
"""GFRC batch calculator: how much of everything to buy, and what goes in each bucket.

Two ways to make the mix:

  bagged   a complete GFRC mix (cement + sand in the bag, e.g. GFRZ Pro). You add water,
           AR glass fiber, water reducer and pigment. Give the bag weight and the maker's
           water and fiber per bag. Pigment is dosed on the cement in the bag, so give the
           cement fraction if the maker publishes it (default 0.45 is a typical guess).
  scratch  your own premix by weight of cementitious (cement + metakaolin):
           sand 1.0, water 0.32, acrylic polymer solids 6%, water reducer 0.3%,
           metakaolin 10% of the binder, AR fiber 3% of the whole mix, pigment 5% of cement.

Volume comes from the mold check (`cast_below_rim_cm3` + `riser_cm3` per unit), or give it in litres.

Examples
  python3 gfrc_batch.py --litres 19.4 --units 9 --test 1 --mode bagged --bag-kg 22.7 \
      --water-kg-per-bag 3.9 --fiber-kg-per-bag 0.61
  python3 gfrc_batch.py --from-check k.out.json --units 9 --test 1 --mode scratch --pigment-pct 5
"""
import argparse, json, math

LB = 0.45359237


def fmt(kg, imperial):
    if kg < 1:
        s = f"{kg * 1000:.0f} g"
    else:
        s = f"{kg:.2f} kg"
    if imperial:
        s += f" ({kg / LB:.1f} lb)" if kg >= 0.45 else f" ({kg / LB * 16:.1f} oz)"
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--litres", type=float, help="concrete per unit, litres, riser included")
    g.add_argument("--from-check", help="moldcheck --json output; uses cast_below_rim_cm3 + riser_cm3")
    ap.add_argument("--units", type=int, default=1)
    ap.add_argument("--test", type=int, default=1, help="extra test pours with the same mold (default 1)")
    ap.add_argument("--waste", type=float, default=0.10, help="spill, bucket and funnel loss (default 0.10)")
    ap.add_argument("--density", type=float, default=2100, help="fresh GFRC density kg/m3 (default 2100)")
    ap.add_argument("--mode", choices=["bagged", "scratch"], default="bagged")
    ap.add_argument("--bucket-litres", type=float, default=12, help="largest batch you mix at once (default 12 L)")
    ap.add_argument("--pigment-pct", type=float, default=5.0, help="pigment, %% of cement weight (default 5)")
    ap.add_argument("--wr-pct", type=float, default=0.3, help="water reducer, %% of cement weight (default 0.3; use the maker's dose)")
    # bagged
    ap.add_argument("--bag-kg", type=float, default=22.7)
    ap.add_argument("--water-kg-per-bag", type=float, default=3.9)
    ap.add_argument("--fiber-kg-per-bag", type=float, default=0.61)
    ap.add_argument("--cement-fraction", type=float, default=0.45, help="cement share of the bag weight")
    ap.add_argument("--bag-yield-l", type=float, help="litres per bag if the maker publishes it")
    # scratch
    ap.add_argument("--wc", type=float, default=0.32, help="water / binder (counts the polymer's water)")
    ap.add_argument("--sand", type=float, default=1.0, help="sand / binder")
    ap.add_argument("--polymer-pct", type=float, default=6.0, help="acrylic polymer solids, %% of binder")
    ap.add_argument("--polymer-solids", type=float, default=0.47, help="solids fraction of the liquid polymer")
    ap.add_argument("--mk-pct", type=float, default=10.0, help="metakaolin, %% of binder")
    ap.add_argument("--fiber-pct", type=float, default=3.0, help="AR fiber, %% of the total mix weight")
    ap.add_argument("--imperial", action="store_true", help="also print pounds and ounces")
    ap.add_argument("--json", help="write the result here")
    a = ap.parse_args()

    if a.from_check:
        r = json.load(open(a.from_check))
        per_l = ((r.get("cast_below_rim_cm3") or r["cast_cm3"]) + (r.get("riser_cm3") or 0)) / 1000
    else:
        per_l = a.litres
    pours = a.units + a.test
    total_l = per_l * pours * (1 + a.waste)
    rho = a.density / 1000  # kg per litre
    out = {"per_unit_l": round(per_l, 2), "pours": pours, "total_l": round(total_l, 1), "mode": a.mode}
    imp = a.imperial

    if a.mode == "bagged":
        wet_kg_per_bag = a.bag_kg + a.water_kg_per_bag + a.fiber_kg_per_bag
        yld = a.bag_yield_l or wet_kg_per_bag / rho
        cem_bag = a.bag_kg * a.cement_fraction
        per_bag = {"dry mix": a.bag_kg, "water": a.water_kg_per_bag,
                   "AR glass fiber": a.fiber_kg_per_bag, "water reducer": cem_bag * a.wr_pct / 100,
                   "black pigment": cem_bag * a.pigment_pct / 100}
        bags_exact = total_l / yld
        bags = math.ceil(bags_exact)
        out.update(bag_yield_l=round(yld, 2), bags_exact=round(bags_exact, 2), bags=bags,
                   buy={k: round(v * bags, 3) for k, v in per_bag.items()})
        print(f"{per_l:.1f} L per unit x {pours} pours (+{a.waste:.0%} waste) = {total_l:.0f} L")
        print(f"one bag makes about {yld:.1f} L {'(maker)' if a.bag_yield_l else '(estimated from weight and density)'}")
        print(f"bags: {bags_exact:.1f} -> buy {bags}")
        print("totals for the run:")
        for k, v in per_bag.items():
            print(f"  {k:32s} {fmt(v * bags, imp)}")
        # buckets: split each pour into equal batches no bigger than the bucket
        nb = math.ceil(per_l * (1 + a.waste / 2) / a.bucket_litres)
        f = per_l * (1 + a.waste / 2) / nb / yld
        print(f"each pour: {nb} batches of {per_l * (1 + a.waste / 2) / nb:.1f} L, each one:")
        batch = {k: v * f for k, v in per_bag.items()}
        for k, v in batch.items():
            print(f"  {k:32s} {fmt(v, imp)}")
        out["batch"] = {"count_per_pour": nb, "litres": round(per_l * (1 + a.waste / 2) / nb, 2),
                        "kg": {k: round(v, 4) for k, v in batch.items()}}
    else:
        # per kg of binder (cement + metakaolin)
        mk = a.mk_pct / 100
        poly_liq = a.polymer_pct / 100 / a.polymer_solids
        poly_water = poly_liq - a.polymer_pct / 100
        parts = {"cement": 1 - mk, "metakaolin": mk, "sand": a.sand,
                 "water (less the polymer's water)": a.wc - poly_water,
                 "acrylic polymer (liquid)": poly_liq,
                 "water reducer": (1 - mk) * a.wr_pct / 100,
                 "black pigment": (1 - mk) * a.pigment_pct / 100}
        no_fiber = sum(parts.values())
        parts["AR glass fiber"] = no_fiber * a.fiber_pct / (100 - a.fiber_pct)
        kg_per_binder = sum(parts.values())
        binder = total_l * rho / kg_per_binder
        out["buy_kg"] = {k: round(v * binder, 3) for k, v in parts.items()}
        print(f"{per_l:.1f} L per unit x {pours} pours (+{a.waste:.0%} waste) = {total_l:.0f} L, "
              f"{total_l * rho:.0f} kg of wet mix")
        print("totals for the run:")
        for k, v in parts.items():
            print(f"  {k:34s} {fmt(v * binder, imp)}")
        nb = math.ceil(per_l * (1 + a.waste / 2) / a.bucket_litres)
        bl = per_l * (1 + a.waste / 2) / nb
        bb = bl * rho / kg_per_binder
        print(f"each pour: {nb} batches of {bl:.1f} L, each one:")
        for k, v in parts.items():
            print(f"  {k:34s} {fmt(v * bb, imp)}")
        out["batch"] = {"count_per_pour": nb, "litres": round(bl, 2), "kg": {k: round(v * bb, 4) for k, v in parts.items()}}

    print("Weigh pigment and fiber on a 0.1 g scale. Use one pigment lot for every unit, or the colour shifts.")
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
