"""Spec 004: turn-of-month separation.

    python scripts/turn_of_month_study.py

Resolves a confound in spec 001. `calendars.gotobi_days()` includes the last
business day of the month, so spec 001's treatment group bundles two mechanisms --
Gotobi importer settlement (5/10/15/20/25) and month-end rebalancing flow -- and
the published fix-spike frequencies say month-end (0.538) dominates the 5th/10th
(0.276). As written, spec 001 cannot attribute an effect to the mechanism it names.

Partitions Japanese business days into three mutually exclusive groups:
  A  month-end        last JP business day of the month
  B  gotobi proper    5/10/15/20/25 rolled back, EXCLUDING month-end
  C  control          everything else

Windows are inherited UNCHANGED from spec 001 so no tuning enters through this
spec. The test that matters is compare(A, B).
"""
import argparse
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from usdjpy.calendars import gotobi_days, jp_business_days  # noqa: E402
from usdjpy.config import DATA_DIR, RESULTS_DIR, SYMBOL  # noqa: E402
from usdjpy.costs import CostModel, PESSIMISTIC  # noqa: E402
from usdjpy.datasets import load_minute  # noqa: E402
from usdjpy.dukascopy import load_minute_bars  # noqa: E402
from usdjpy.events import PERIODS, compare, summarize, window_trades  # noqa: E402
from scipy.stats import norm  # noqa: E402
from usdjpy.stats import min_detectable_pips  # noqa: E402

pd.set_option("display.width", 150, "display.float_format", "{:.3f}".format)

# inherited from spec 001, NOT re-tuned
RULES = {"prefix_long": ("08:00", "09:55", +1), "postfix_short": ("09:55", "11:00", -1)}
BONF_T = 2.5   # pre-declared in spec 004: ~6 comparisons
# min_detectable_pips defaults to alpha=0.05 (t=1.96), but the kill criterion is
# |t| >= 2.5. An MDE computed at 1.96 understates the bar the effect actually has
# to clear by 19%, which flatters every null in the output.
BONF_ALPHA = 2 * (1 - norm.cdf(BONF_T))

# Same loader switch as spec 001 (scripts/gotobi_study.py), so A/B/C run on identical bars.
ap = argparse.ArgumentParser()
ap.add_argument("--source", default="combined", help="combined | histdata | dukascopy | eightcap | dukascopy-ticks")
args = ap.parse_args()
bars = load_minute_bars(SYMBOL, DATA_DIR) if args.source == "dukascopy-ticks" else load_minute(args.source)
print(f"Source: {args.source}")
start, end = bars.index[0].date(), bars.index[-1].date()

jp = jp_business_days(start, end)
month_end = pd.DatetimeIndex(pd.Series(jp).groupby([jp.year, jp.month]).max().values)
gotobi_all = gotobi_days(start, end)
gotobi_proper = gotobi_all.difference(month_end)
control = jp.difference(month_end).difference(gotobi_proper)

GROUPS = {"A_month_end": month_end, "B_gotobi_proper": gotobi_proper, "C_control": control}

print(f"Data {start} -> {end}  ({len(bars):,} minute bars)")
for name, idx in GROUPS.items():
    print(f"  {name:<16} {len(idx):>5} days")
overlap = len(month_end.intersection(gotobi_proper))
print(f"  A/B overlap (must be 0): {overlap}")
assert overlap == 0, "partition is not mutually exclusive"
print(f"  spec 001's gotobi set was {len(gotobi_all)} days, i.e. "
      f"{len(month_end.intersection(gotobi_all))} of them month-end "
      f"({len(month_end.intersection(gotobi_all))/max(1,len(gotobi_all))*100:.0f}% of the treatment group)\n")

RESULTS_DIR.mkdir(exist_ok=True)
for rule, (t_in, t_out, side) in RULES.items():
    print("=" * 78)
    print(f"{rule}: {'long' if side > 0 else 'short'} {t_in} -> {t_out} JST")
    print("=" * 78)
    trades = {}
    for name, idx in GROUPS.items():
        trades[name] = window_trades(bars, idx, t_in, t_out, side, CostModel())
        trades[name].to_csv(RESULTS_DIR / f"004_{rule}_{name}.csv")

    for name, tr in trades.items():
        if tr.empty:
            print(f"\n{name}: no trades")
            continue
        sd = tr["net_pips"].std()
        mde = min_detectable_pips(sd, len(tr), alpha=BONF_ALPHA)
        print(f"\n{name}  (n={len(tr)}, sd={sd:.1f} pips, MDE@80%@t{BONF_T} = {mde:.1f} pips)")
        print(summarize(tr, "net_pips"))

    pess = window_trades(bars, GROUPS["A_month_end"], t_in, t_out, side, PESSIMISTIC)
    if not pess.empty:
        print(f"\nA_month_end under PESSIMISTIC costs:")
        print(summarize(pess, "net_pips"))

    print("\n--- comparisons on mid_pips (no costs) ---")
    for a, b in [("A_month_end", "C_control"), ("B_gotobi_proper", "C_control"),
                 ("A_month_end", "B_gotobi_proper")]:
        if trades[a].empty or trades[b].empty:
            continue
        c = compare(trades[a], trades[b])
        flag = "  <-- THE SPEC 004 TEST" if a == "A_month_end" and b == "B_gotobi_proper" else ""
        verdict = "DIFFERENT" if abs(c["t"]) > BONF_T else "not distinguishable"
        print(f"  {a} vs {b}: diff={c['diff']:+.3f} pips  t={c['t']:+.2f}  "
              f"p={c['p']:.4f}  -> {verdict}{flag}")

    print("\n--- decay check: is any effect a pre-2008 artefact? ---")
    for name in ("A_month_end", "B_gotobi_proper"):
        tr = trades[name]
        if tr.empty:
            continue
        row = []
        for per, (a, b) in PERIODS.items():
            sub = tr.loc[(tr.index >= a) & (tr.index <= b), "net_pips"]
            if len(sub) > 5:
                t = sub.mean() / (sub.std() / len(sub) ** 0.5)
                row.append(f"{per}: {sub.mean():+.2f}p (n={len(sub)}, t={t:+.2f})")
        print(f"  {name}: " + " | ".join(row))
    print()

print("=" * 78)
print("""KILL CRITERIA (spec 004, pre-declared)
  1. mean net pips <= 0 under base costs on pre-holdout data for every group
  2. |t| < 2.5 on the A-vs-B comparison
  3. effect present pre-2008 and absent in 2015-2021 and 2022+ -> decayed
  4. fails under PESSIMISTIC
  5. TRADEABILITY (separate from significance): net pips/trade below the
     PESSIMISTIC all-in cost (~1.84 pips at 159) does not reach Layer 2

Read every null against its MDE column. A null with an MDE far above the
published effect size (~1.8bp over 15 years for Gotobi) is uninformative, not
evidence of absence.""")
