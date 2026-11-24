"""Spec 005 (H3, trade simulation): does a change in the US-Japan 2y spread, or USDJPY's gap from its spread-implied
level, predict the next 5-10 days?

    python scripts/h3_rate_study.py                  # combined seeded data
    python scripts/h3_rate_study.py --source histdata

Variants, parameters and kill criteria are fixed in specs/005-rate-path-trade-test.md.
Writes per-trade CSVs, a summary and the kill-criteria verdict to results/.
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from usdjpy.config import HOLDOUT_START, RESULTS_DIR  # noqa: E402
from usdjpy.costs import PESSIMISTIC, CostModel  # noqa: E402
from usdjpy.datasets import load_minute  # noqa: E402
from usdjpy.horizon import (decision_times, mean_moves, newey_west_slope, newey_west_t,  # noqa: E402
                            quotes_at, simulate, summarize)
from usdjpy import rates  # noqa: E402

# Spec 005 parameters. Do not tune.
LOOKBACK = 5          # V1, V2: spread change over this many decision days
THRESHOLD_BP = 15     # V2
FV_WINDOW = 252       # V3: fair-value regression window
FV_MIN_OBS = 200      # V3: need at least this many valid days in the window
Z_ENTRY = 1.0         # V3
HOLD = {"V1": 5, "V2": 5, "V3": 10}
STALE_DAYS = 5
T_MIN, T_MIN_DRIFT = 3.0, 2.0

pd.set_option("display.width", 150, "display.float_format", "{:.3f}".format)


def build_signals(source: str):
    bars = load_minute(source)
    end = min(bars.index[-1], pd.Timestamp(HOLDOUT_START, tz="UTC") + pd.Timedelta(days=30))
    times = decision_times(bars.index[0].normalize(), end)
    q = quotes_at(bars, times)

    us = rates.asof(rates.us_2y(), times, max_age_days=STALE_DAYS)["value"]
    jp = rates.asof(rates.jgb_2y(), times, max_age_days=STALE_DAYS)["value"]
    spread = (us - jp) * 100  # bp
    x = spread - spread.shift(LOOKBACK)

    # V3: rolling fair value of log(mid) on the spread, fitted on the previous FV_WINDOW days only.
    y = np.log(q["mid"])
    valid = y.notna() & spread.notna()
    yv, sv = y.where(valid).shift(1), spread.where(valid).shift(1)
    roll = lambda s: s.rolling(FV_WINDOW, min_periods=FV_MIN_OBS)  # noqa: E731
    var_s, var_y = roll(sv).var(), roll(yv).var()
    beta = roll(yv).cov(sv) / var_s
    alpha = roll(yv).mean() - beta * roll(sv).mean()
    resid_sd = np.sqrt((var_y - beta**2 * var_s).clip(lower=0))
    z = (y - alpha - beta * spread) / resid_sd

    sides = {
        "V1": np.sign(x).fillna(0),
        "V2": np.sign(x).where(x.abs() >= THRESHOLD_BP, 0).fillna(0),
        "V3": pd.Series(np.where(z >= Z_ENTRY, -1, np.where(z <= -Z_ENTRY, 1, 0)), index=times),
    }
    usd = rates.asof(rates.fed_funds(), times)["value"]
    jpy = rates.asof(rates.boj_call_rate(), times)["value"]
    signals = pd.DataFrame({"us2y": us, "jgb2y": jp, "spread_bp": spread, "chg5_bp": x, "fv_z": z,
                            "usd_rate": usd, "jpy_rate": jpy}).join(q)
    return q, sides, usd, jpy, signals


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="combined", help="combined | histdata | dukascopy | eightcap")
    a = ap.parse_args()

    q, sides, usd, jpy, signals = build_signals(a.source)
    pre = signals.index < pd.Timestamp(HOLDOUT_START, tz="UTC")
    print(f"Source: {a.source}. Decision days with a quote and a spread: "
          f"{int((signals['mid'].notna() & signals['spread_bp'].notna() & pre).sum())} "
          f"({signals.index[0].date()} to 2024-12-31)\n")

    RESULTS_DIR.mkdir(exist_ok=True)
    signals[pre].to_csv(RESULTS_DIR / "h3_signals.csv")
    summary_rows, verdict_rows = [], []
    for v, hold in HOLD.items():
        overlap = v != "V2"
        base = simulate(q, sides[v], hold, CostModel(), usd, jpy, overlap=overlap)
        pess = simulate(q, sides[v], hold, PESSIMISTIC, usd, jpy, overlap=overlap)
        drift = mean_moves(q, hold)
        base["net_minus_drift"] = base["net_pips"] - base["side"] * drift
        base.to_csv(RESULTS_DIR / f"h3_{v}_trades.csv", index=False)

        sb, sp = summarize(base, hold), summarize(pess, hold)
        sd = summarize(base, hold, "net_minus_drift")
        long_share = (base["side"] > 0).mean()
        print(f"=== {v}: hold {hold} days, {'overlapping' if overlap else 'non-overlapping'} trades, "
              f"{long_share:.0%} long ===")
        print("Net pips per trade, base costs:")
        print(sb)
        print("\nNet pips, pessimistic costs:")
        print(sp)
        print(f"\nNet minus drift (average {hold}-day move {drift:+.2f} pips, signed by side):")
        print(sd.loc[["all"]])
        trading_cost = base["mid_pips"] - (base["net_pips"] - base["financing_pips"])
        print(f"Per trade: mid move {base['mid_pips'].mean():+.2f}, spread+commission+slippage "
              f"{-trading_cost.mean():+.2f}, financing {base['financing_pips'].mean():+.2f} pips\n")

        for cost_name, s in (("base", sb), ("pessimistic", sp), ("net_minus_drift", sd)):
            for period, r in s.iterrows():
                summary_rows.append({"variant": v, "costs": cost_name, "period": period, **r.to_dict()})

        checks = [
            ("Mean net pips > 0, base costs", sb.loc["all", "mean"], "> 0", sb.loc["all", "mean"] > 0),
            (f"Newey-West t >= {T_MIN}, base costs", sb.loc["all", "nw_t"], f">= {T_MIN}", sb.loc["all", "nw_t"] >= T_MIN),
            ("Mean net pips > 0 in 2022-2024", sb.loc["2022-2024", "mean"] if "2022-2024" in sb.index else np.nan, "> 0",
             "2022-2024" in sb.index and sb.loc["2022-2024", "mean"] > 0),
            (f"Pessimistic: mean > 0 and t >= {T_MIN}", sp.loc["all", "nw_t"], f">= {T_MIN}",
             sp.loc["all", "mean"] > 0 and sp.loc["all", "nw_t"] >= T_MIN),
            (f"Beats drift: mean > 0 and t >= {T_MIN_DRIFT}", sd.loc["all", "nw_t"], f">= {T_MIN_DRIFT}",
             sd.loc["all", "mean"] > 0 and sd.loc["all", "nw_t"] >= T_MIN_DRIFT),
        ]
        for i, (name, val, need, ok) in enumerate(checks, 1):
            verdict_rows.append({"variant": v, "criterion": i, "name": name, "value": val, "needs": need,
                                 "pass": bool(ok)})

    # Diagnostics (not kill criteria): does the signal predict the raw mid move at all?
    s = signals[pre & signals["mid"].notna()]
    for col, hold, label in (("chg5_bp", 5, "5-day move on 5-day spread change (pips per bp)"),
                             ("fv_z", 10, "10-day move on fair-value z (pips per z)")):
        fwd = (s["mid"].shift(-hold) - s["mid"]) / 0.01
        b, t = newey_west_slope(fwd, s[col], hold)
        print(f"Diagnostic, slope of {label}: {b:+.2f}, Newey-West t {t:+.2f}")

    verdict = pd.DataFrame(verdict_rows)
    pd.DataFrame(summary_rows).to_csv(RESULTS_DIR / "h3_summary.csv", index=False)
    verdict.to_csv(RESULTS_DIR / "h3_verdict.csv", index=False)
    print("\n=== Kill criteria (spec 005) ===")
    for v, g in verdict.groupby("variant"):
        status = "PASSES" if g["pass"].all() else f"REJECTED (fails {', '.join(str(c) for c in g.loc[~g['pass'], 'criterion'])})"
        print(f"{v}: {status}")
        for _, r in g.iterrows():
            print(f"   {r.criterion}. {r['name']:<42} {r.value:+8.3f}  needs {r.needs:<6} {'pass' if r['pass'] else 'FAIL'}")


if __name__ == "__main__":
    main()
