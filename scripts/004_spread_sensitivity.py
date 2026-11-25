"""Spec 004 results, re-read under honest spread assumptions, and kill criteria 4 and 5.

    python scripts/004_spread_sensitivity.py

The synthetic ask in datasets.py is built from a 2024-26 Eightcap RAW-SPREAD
account (~0.25-0.36 pips). That is the tightest retail execution available, and
it is applied to 2007-2024 when retail USDJPY commonly ran 0.6-3.0 pips. The
understatement is 0.65-2.65 pips against a published effect of 2.86 pips, so on
the early slice the spread assumption can be the entire result.

No re-run is needed. Bid-only sources observe the bid; the ask is bid + s. A long
buys bid + s at ENTRY and sells the bid; a short sells the bid and buys back
bid + s at EXIT. Widening the spread to k*s therefore costs (k-1)*s_paid, where
s_paid is the entry spread for a long and the EXIT spread for a short:

    net_adj = net_pips - (k - 1) * spread_paid_pips

Until 2026-11-25 this used spread_in_pips for both legs, which charged the short
postfix leg its entry spread (hour 9, 0.326) instead of its exit spread (hour 11,
0.272) and understated its era columns.

k is chosen by the source of the entry bar (eightcap 1.0, histdata 2.5, dukascopy
5.0), which matches the declared era split (measured from 2024-06-19, x2.5 for
2015-2024, x5 before) except that it classifies the 2024-06-19 boundary trade by the
bar it actually filled on.

ERA MULTIPLIERS ARE JUDGEMENT, NOT MEASUREMENT. They are set wide on purpose:
the point is to find out whether the verdict depends on them. Kill criterion 5 is
judged on the MEASURED column (spec 004 *Gap fill*), which needs the Dukascopy
fetch; until then it is pending and the columns here are assumptions.

The trade CSVs must carry spread_paid_pips, mid_in and source (events.window_trades
from 2026-11-25). For the pre-DST-fix archive, which predates them, use this script
as of commit 560116c: `git show 560116c:scripts/004_spread_sensitivity.py`.
"""
import argparse
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import norm  # noqa: E402

from usdjpy.config import RESULTS_DIR  # noqa: E402
from usdjpy.costs import PESSIMISTIC, PIP, CostModel  # noqa: E402
from usdjpy.events import tradeability_margin  # noqa: E402
from usdjpy.stats import min_detectable_pips  # noqa: E402

pd.set_option("display.width", 150)

# multiplier on the measured 2024-26 raw-spread profile, by the entry bar's source
ERA_BY_SOURCE = {"eightcap": 1.0, "histdata": 2.5, "dukascopy": 5.0}

PUBLISHED_EFFECT_PIPS = 0.018 / 100 * 159.0 / PIP   # 1.8bp at 159 = 2.86 pips
BONF_T = 2.5                                        # pre-declared in spec 004
# Every MDE here is at the test's own bar (|t| >= 2.5), not min_detectable_pips'
# alpha=0.05 default. Until 2026-11-25 this script printed MDEs at t=1.96 (the
# per-group MDE via the default alpha, the Welch MDE via a hard-coded 2.80), which
# understates the bar by 19% and flatters every null (CLAUDE.md, inference rules).
BONF_ALPHA = 2 * (1 - norm.cdf(BONF_T))
MDE_MULT = BONF_T + norm.ppf(0.80)                  # 3.342 standard errors
YEARS = 18                                          # 2007-2024, as spec 004's bars use
LIVE_HAIRCUT = 0.73                                 # CLAUDE.md "Two bars": median backtest-to-live
TODAY_PRICE = 159.0
BASE = CostModel()
RULES = ("prefix_long", "postfix_short")
GROUPS = ("A_month_end", "B_gotobi_proper", "C_control")
COLS = [("net_k1", "as run", "k1"), ("net_era", "era", "era"), ("net_era2", "era x2", "era2")]


def load(rule: str, group: str, results_dir: pathlib.Path) -> pd.DataFrame | None:
    p = results_dir / f"004_{rule}_{group}.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p, parse_dates=["date"]).set_index("date").sort_index()
    need = {"net_pips", "mid_pips", "spread_paid_pips", "mid_in", "source"}
    if not need.issubset(df.columns):
        raise SystemExit(f"{p.name} lacks {sorted(need - set(df.columns))}: written before 2026-11-25? "
                         "Re-run scripts/turn_of_month_study.py, or for the pre-DST-fix archive use "
                         "`git show 560116c:scripts/004_spread_sensitivity.py`.")
    unknown = set(df["source"]) - set(ERA_BY_SOURCE)
    if unknown:
        raise SystemExit(f"{p.name}: no era multiplier for sources {unknown}")
    k = df["source"].map(ERA_BY_SOURCE).to_numpy()
    df["k1"], df["era"], df["era2"] = 1.0, k, 2.0 * k
    for col, _, kc in COLS:
        df[col] = df["net_pips"] - (df[kc] - 1.0) * df["spread_paid_pips"]
    return df


def stat(x: pd.Series) -> dict:
    x = x.dropna()
    n = len(x)
    sd = x.std(ddof=1) if n > 1 else np.nan
    return {"n": n, "mean": x.mean(), "sd": sd, "se": sd / np.sqrt(n) if n > 1 else np.nan,
            "t": x.mean() / (sd / np.sqrt(n)) if n > 1 and sd > 0 else np.nan,
            "hit": (x > 0).mean(), "mde": min_detectable_pips(sd, n, alpha=BONF_ALPHA) if n > 1 else np.nan}


def welch(a: pd.Series, b: pd.Series) -> dict:
    a, b = a.dropna(), b.dropna()
    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
    t = (a.mean() - b.mean()) / np.sqrt(va + vb)
    return {"diff": a.mean() - b.mean(), "t": t,
            "mde": MDE_MULT * np.sqrt(va + vb)}


def sharpe_and_power(df: pd.DataFrame) -> None:
    """Spec 004's Sharpe and power figures for the B leg, at the t=2.5 bar.

    Both are restatements of t, printed because the spec quotes them:
    annual Sharpe = t / sqrt(YEARS) exactly (trades per year = n / YEARS), and
    observed power = Phi(t - 2.5) assumes the true effect equals the estimate.
    The predictive probability that a fresh sample of the same size clears 2.5,
    allowing for estimation error in the effect, is Phi((t - 2.5) / sqrt(2)).
    """
    x = df["net_k1"].dropna()
    n, mean, sd = len(x), x.mean(), x.std(ddof=1)
    se = sd / np.sqrt(n)
    t = mean / se
    per_yr = n / YEARS
    ann = {lbl: df[c].mean() / df[c].std(ddof=1) * np.sqrt(per_yr) for c, lbl, _ in COLS}
    print("\n  --- B_gotobi_proper: Sharpe (annualised; = t/sqrt(18)) and power at the t=2.5 bar ---")
    print(f"    n {n}  trades/yr {per_yr:.1f}  sd/trade {sd:.2f}p  per-trade SR {mean / sd:.4f}")
    print("    Sharpe  " + "  ".join(f"{k} {v:.3f}" for k, v in ann.items())
          + f"  live {ann['as run'] * (1 - LIVE_HAIRCUT):.3f}"
          + f"   [bars: t=2 {2 / np.sqrt(YEARS):.2f}, t=3 {3 / np.sqrt(YEARS):.2f}]")
    print(f"    effect {mean:+.3f}p  sig. threshold {BONF_T * se:.3f}p  observed t {t:+.2f}  "
          f"MDE@80% {MDE_MULT * se:.3f}p")
    print(f"    observed power (= Phi(t-2.5), assumes true = estimate) {norm.cdf(t - BONF_T):.1%}  "
          f"predictive replication (Phi((t-2.5)/sqrt2)) {norm.cdf((t - BONF_T) / np.sqrt(2)):.1%}")


def criteria_4_and_5(df: pd.DataFrame) -> None:
    """Kill criterion 4 (PESSIMISTIC net) and criterion 5 as evaluated per trade from
    2026-11-25 (spec 004 evaluation note), with the standard measures beside it."""
    p = df["mid_in"].to_numpy()
    pess_extra = np.array([PESSIMISTIC.round_trip_pips(x) - BASE.round_trip_pips(x) for x in p])
    k4 = stat(df["net_pips"] - pess_extra)
    print("\n  --- B_gotobi_proper: kill criteria 4 and 5 ---")
    print(f"    criterion 4, net under PESSIMISTIC: {k4['mean']:+.3f}p  t {k4['t']:+.2f}  (n {k4['n']})")
    mid_bp = df["mid_pips"] * PIP / p * 1e4
    mid_today = mid_bp * TODAY_PRICE / 1e4 / PIP
    rt_shift = np.array([BASE.round_trip_pips(x) + PESSIMISTIC.round_trip_pips(x) for x in p]) \
        - (BASE.round_trip_pips(TODAY_PRICE) + PESSIMISTIC.round_trip_pips(TODAY_PRICE))
    print(f"    criterion 5 margin = mean(net_i - [PESSIMISTIC round trip at price_i + k*spread_paid_i]); "
          "passes if >= 0")
    print(f"    {'column':<8} {'margin':>8} {'SE':>6} {'95% LCB':>8} {'verdict':<28} {'margin @159 (bp view)':>22}")
    for _, lbl, kc in COLS:
        m = tradeability_margin(df, PESSIMISTIC, df[kc].to_numpy())
        s = stat(m)
        if abs(s["mean"]) < s["se"]:
            v = "not resolved (|margin| < 1 SE)"
        else:
            v = "pass" if s["mean"] >= 0 else "fail"
        today = stat(m + (mid_today - df["mid_pips"]) + rt_shift)
        print(f"    {lbl:<8} {s['mean']:>+8.3f} {s['se']:>6.3f} {s['mean'] - 1.645 * s['se']:>+8.3f} {v:<28} "
              f"{today['mean']:>+22.3f}")
    print("    measured  (pending: needs the Dukascopy fetch; this column governs criterion 5)")
    print(f"    break-even round-trip cost (mean mid_pips): {df['mid_pips'].mean():.3f}p = {mid_bp.mean():.3f}bp; "
          f"median spread paid as run {df['spread_paid_pips'].median():.3f}p; "
          f"mean entry price {p.mean():.1f}")


def main(results_dir: pathlib.Path) -> None:
    found = False
    for rule in RULES:
        data = {g: load(rule, g, results_dir) for g in GROUPS}
        if all(v is None for v in data.values()):
            continue
        found = True
        print("=" * 96)
        print(f"{rule}")
        print("=" * 96)

        anyg = next(v for v in data.values() if v is not None)
        print(f"  sample {anyg.index[0].date()} to {anyg.index[-1].date()}")
        kc = anyg["era"].value_counts().sort_index()
        print("  era mix (first group): " + ", ".join(f"k={k:.1f} on {int(v)} trades" for k, v in kc.items()))
        print(f"  median spread paid as run: {anyg['spread_paid_pips'].median():.3f} pips "
              f"({'entry' if rule.endswith('long') else 'exit'} spread)")
        print(f"  published effect to beat:  {PUBLISHED_EFFECT_PIPS:.2f} pips\n")

        print(f"  {'group':<17} {'col':<9} {'n':>5} {'mean':>8} {'t':>7} {'hit':>6} {'MDE':>7}  reading")
        print("  " + "-" * 92)
        for g in GROUPS:
            df = data[g]
            if df is None:
                continue
            for col, lbl, _ in COLS:
                s = stat(df[col])
                if np.isnan(s["t"]):
                    continue
                sig = "sig" if abs(s["t"]) > BONF_T else ""
                underp = "  (MDE > effect: uninformative)" if s["mde"] > PUBLISHED_EFFECT_PIPS else ""
                print(f"  {g:<17} {lbl:<9} {s['n']:>5} {s['mean']:>+8.3f} {s['t']:>+7.2f} "
                      f"{s['hit']:>6.1%} {s['mde']:>7.2f}  {sig}{underp}")
            print()

        print("  --- comparisons on mid_pips (cost-free, so spread assumption is irrelevant) ---")
        for a, b in [("A_month_end", "C_control"), ("B_gotobi_proper", "C_control"),
                     ("A_month_end", "B_gotobi_proper")]:
            if data[a] is None or data[b] is None:
                continue
            c = welch(data[a]["mid_pips"], data[b]["mid_pips"])
            tag = "  <-- THE SPEC 004 TEST" if (a, b) == ("A_month_end", "B_gotobi_proper") else ""
            v = "DIFFERENT" if abs(c["t"]) > BONF_T else "not distinguishable"
            info = "" if c["mde"] <= PUBLISHED_EFFECT_PIPS else f"  [MDE {c['mde']:.1f}p > {PUBLISHED_EFFECT_PIPS:.1f}p: weak null]"
            print(f"    {a} vs {b}: diff {c['diff']:+7.3f}p  t {c['t']:+6.2f}  "
                  f"MDE {c['mde']:.2f}p  -> {v}{info}{tag}")

        print("\n  --- decay: does any effect survive after the fix reforms? (era column) ---")
        for g in ("A_month_end", "B_gotobi_proper"):
            df = data[g]
            if df is None:
                continue
            out = []
            for lbl, lo, hi in [("<=2008-10", None, "2008-10-31"),
                                ("2008-11..2015-01", "2008-11-01", "2015-01-31"),
                                ("2015-02..2021", "2015-02-01", "2021-12-31"),
                                ("2022+", "2022-01-01", None)]:
                sub = df["net_era"]
                if lo:
                    sub = sub[sub.index >= pd.Timestamp(lo)]
                if hi:
                    sub = sub[sub.index <= pd.Timestamp(hi)]
                s = stat(sub)
                if s["n"] > 5:
                    out.append(f"{lbl} {s['mean']:+.2f}p (n={s['n']}, t={s['t']:+.1f})")
            print(f"    {g}: " + " | ".join(out))

        if data["B_gotobi_proper"] is not None:
            sharpe_and_power(data["B_gotobi_proper"])
            criteria_4_and_5(data["B_gotobi_proper"])
        print()

    if not found:
        raise SystemExit(f"no 004_*.csv found in {results_dir}")

    print("=" * 96)
    print(f"""HOW TO READ THIS

  'as run'  = the 2024-26 raw-spread profile applied to every era. Optimistic
              before 2024 and known to be so.
  'era'     = x2.5 on HistData bars (2015-2024), x5.0 on Dukascopy-export bars
              (pre-2015), x1 on Eightcap. Judgement, set wide.
  'era x2'  = twice that again, as a stress case.
  'measured' (criterion 5's governing column) needs the Dukascopy fetch.

  If the verdict is the same in all three columns, the spread assumption does
  not matter. If it flips between them, only measured spreads can settle it.

  The mid_pips comparisons carry NO cost assumption, so they are the clean test
  of whether month-end and gotobi-proper behave differently. Read those first,
  beside the weekday-matched versions printed by turn_of_month_study.py.

  MDE is beside every number. A null whose MDE exceeds {PUBLISHED_EFFECT_PIPS:.2f} pips
  is uninformative, not evidence of absence.""")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", type=pathlib.Path, default=RESULTS_DIR,
                    help="directory holding the 004_*.csv trade files (default: results/)")
    main(ap.parse_args().results_dir)
