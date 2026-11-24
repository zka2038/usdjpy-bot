"""Spec 001: gotobi / Tokyo 9:55 JST fix event study.

    python scripts/gotobi_study.py

Tests, on gotobi days vs ordinary Japanese business days (control):
  1a  long  08:00 -> 09:55 JST   (23:00 -> 00:55 GMT)  importer USD demand into the fix
  1b  short 09:55 -> 11:00 JST   (00:55 -> 02:00 GMT)  post-fix reversal
Writes per-trade CSVs and a summary to results/.
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from usdjpy.calendars import gotobi_days, jp_business_days  # noqa: E402
from usdjpy.config import DATA_DIR, RESULTS_DIR, SYMBOL  # noqa: E402
from usdjpy.costs import CostModel, PESSIMISTIC  # noqa: E402
from usdjpy.dukascopy import load_minute_bars  # noqa: E402
from usdjpy.events import compare, summarize, window_trades  # noqa: E402

pd.set_option("display.width", 140, "display.float_format", "{:.3f}".format)

bars = load_minute_bars(SYMBOL, DATA_DIR)
start, end = bars.index[0].date(), bars.index[-1].date()
gotobi = gotobi_days(start, end)
control = jp_business_days(start, end).difference(gotobi)
print(f"Data {start} -> {end}: {len(gotobi)} gotobi days, {len(control)} control days\n")

RULES = {"1a_prefix_long": ("08:00", "09:55", +1), "1b_postfix_short": ("09:55", "11:00", -1)}
RESULTS_DIR.mkdir(exist_ok=True)
for name, (t_in, t_out, side) in RULES.items():
    g = window_trades(bars, gotobi, t_in, t_out, side, CostModel())
    c = window_trades(bars, control, t_in, t_out, side, CostModel())
    g_pess = window_trades(bars, gotobi, t_in, t_out, side, PESSIMISTIC)
    g.to_csv(RESULTS_DIR / f"{name}_gotobi.csv")
    print(f"=== {name}: {'long' if side > 0 else 'short'} {t_in} -> {t_out} JST ===")
    print("Gotobi, net pips (base costs):")
    print(summarize(g, "net_pips"))
    print("\nGotobi, net pips (pessimistic costs):")
    print(summarize(g_pess, "net_pips"))
    print("\nControl days, net pips:")
    print(summarize(c, "net_pips"))
    print("\nGotobi vs control (mid pips, no costs):", {k: round(float(v), 3) for k, v in compare(g, c).items()})
    print(f"Median entry spread: {g['spread_in_pips'].median():.2f} pips\n")
