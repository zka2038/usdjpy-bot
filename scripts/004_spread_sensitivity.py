"""Spec 004 results, re-read under honest spread assumptions.

    python scripts/004_spread_sensitivity.py

The synthetic ask in datasets.py is built from a 2024-26 Eightcap RAW-SPREAD
account (~0.25-0.36 pips). That is the tightest retail execution available, and
it is applied to 2007-2024 when retail USDJPY commonly ran 0.6-3.0 pips. The
understatement is 0.65-2.65 pips against a published effect of 2.86 pips, so on
the early slice the spread assumption can be the entire result.

No re-run is needed. Widening the spread is additive: a long buys at
bid + k*s instead of bid + s, a short sells at bid and buys back at bid + k*s,
so EITHER direction loses exactly (k-1)*s per round trip. Therefore

    net_adj = net_pips - (k - 1) * spread_in_pips

applied per trade, with k chosen by era. This reads the saved per-trade CSVs and
reports the result at k = 1 (as run), era-scaled, and 2x era-scaled, so the
reader sees sensitivity rather than one number resting on a guess.

ERA MULTIPLIERS ARE JUDGEMENT, NOT MEASUREMENT. They are set wide on purpose:
the point is to find out whether the verdict depends on them. If it does, the
honest answer is that the early data cannot settle the question.
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from usdjpy.config import RESULTS_DIR  # noqa: E402
from usdjpy.costs import PIP  # noqa: E402
from usdjpy.stats import min_detectable_pips  # noqa: E402

pd.set_option("display.width", 150)

# multiplier on the measured 2024-26 raw-spread profile, by era
ERA = [("2024-06-19", None, 1.0),    # measured directly
       ("2015-01-01", "2024-06-18", 2.5),
       (None,         "2014-12-31", 5.0)]

PUBLISHED_EFFECT_PIPS = 0.018 / 100 * 159.0 / PIP   # 1.8bp at 159 = 2.86 pips
BONF_T = 2.5                                        # pre-declared in spec 004
RULES = ("prefix_long", "postfix_short")
GROUPS = ("A_month_end", "B_gotobi_proper", "C_control")


def era_multiplier(idx: pd.DatetimeIndex) -> np.ndarray:
    k = np.full(len(idx), np.nan)
    for lo, hi, mult in ERA:
        m = np.ones(len(idx), dtype=bool)
        if lo is not None:
            m &= idx >= pd.Timestamp(lo)
        if hi is not None:
            m &= idx <= pd.Timestamp(hi)
        k[m] = mult
    return np.nan_to_num(k, nan=1.0)


def load(rule: str, group: str) -> pd.DataFrame | None:
    p = RESULTS_DIR / f"004_{rule}_{group}.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p, parse_dates=["date"]).set_index("date").sort_index()
    need = {"net_pips", "spread_in_pips", "mid_pips"}
    if not need.issubset(df.columns):
        raise SystemExit(f"{p.name} lacks {need - set(df.columns)}")
    k = era_multiplier(df.index)
    df["k"] = k
    df["net_k1"] = df["net_pips"]
    df["net_era"] = df["net_pips"] - (k - 1.0) * df["spread_in_pips"]
    df["net_era2"] = df["net_pips"] - (2.0 * k - 1.0) * df["spread_in_pips"]
    return df


def stat(x: pd.Series) -> dict:
    x = x.dropna()
    n = len(x)
    sd = x.std(ddof=1) if n > 1 else np.nan
    return {"n": n, "mean": x.mean(), "sd": sd,
            "t": x.mean() / (sd / np.sqrt(n)) if n > 1 and sd > 0 else np.nan,
            "hit": (x > 0).mean(), "mde": min_detectable_pips(sd, n) if n > 1 else np.nan}


def welch(a: pd.Series, b: pd.Series) -> dict:
    a, b = a.dropna(), b.dropna()
    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
    t = (a.mean() - b.mean()) / np.sqrt(va + vb)
    return {"diff": a.mean() - b.mean(), "t": t,
            "mde": 2.80 * np.sqrt(va + vb)}


found = False
for rule in RULES:
    data = {g: load(rule, g) for g in GROUPS}
    if all(v is None for v in data.values()):
        continue
    found = True
    print("=" * 96)
    print(f"{rule}")
    print("=" * 96)

    anyg = next(v for v in data.values() if v is not None)
    print(f"  sample {anyg.index[0].date()} to {anyg.index[-1].date()}")
    kc = anyg["k"].value_counts().sort_index()
    print("  era mix: " + ", ".join(f"k={k:.1f} on {int(v)} trades" for k, v in kc.items()))
    print(f"  median assumed spread as run: {anyg['spread_in_pips'].median():.3f} pips")
    print(f"  published effect to beat:     {PUBLISHED_EFFECT_PIPS:.2f} pips\n")

    print(f"  {'group':<17} {'col':<9} {'n':>5} {'mean':>8} {'t':>7} {'hit':>6} {'MDE':>7}  reading")
    print("  " + "-" * 92)
    for g in GROUPS:
        df = data[g]
        if df is None:
            continue
        for col, lbl in [("net_k1", "as run"), ("net_era", "era"), ("net_era2", "era x2")]:
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

    print("\n  --- decay: does any effect survive after the fix reforms? ---")
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
    print()

if not found:
    raise SystemExit(f"no 004_*.csv found in {RESULTS_DIR}")

print("=" * 96)
print(f"""HOW TO READ THIS

  'as run'  = the 2024-26 raw-spread profile applied to every era. Optimistic
              before 2024 and known to be so.
  'era'     = x2.5 for 2015-2024, x5.0 pre-2015. Judgement, set wide.
  'era x2'  = twice that again, as a stress case.

  If the verdict is the same in all three columns, the spread assumption does
  not matter and the result stands. If it flips between them, the early data
  cannot settle the question and only the 2024-06+ bid/ask slice is admissible --
  which is 6.5 pre-holdout months, far too few month-ends to test anything.

  The mid_pips comparisons carry NO cost assumption, so they are the clean test
  of whether month-end and gotobi-proper behave differently. Read those first;
  the net_pips columns only tell you whether a real difference would survive
  execution.

  MDE is beside every number. A null whose MDE exceeds {PUBLISHED_EFFECT_PIPS:.2f} pips
  is uninformative, not evidence of absence.""")
