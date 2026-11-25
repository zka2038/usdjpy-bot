"""Spec 003: rate-path revision.

    python scripts/rate_path_study.py            # runs the harness check only
    python scripts/rate_path_study.py --data     # adds the real-data regression

Layer-1 test is a PREDICTIVE REGRESSION, not a trade simulation. Trade rules are
in the spec and must not be built until this passes.

Two things this script enforces, both of which cost real power if ignored:

1. HARNESS CHECK FIRST. It builds a series with a known predictive link and
   confirms the regression recovers it, and that a null does NOT pass. During
   calibration a simulator that built the correlation between x_t and y_t, then
   regressed y_{t+1} on x_t, returned power = size in every cell -- an apparent
   null from a harness with no signal in it. Same error class as pairing FRED's
   noon DEXJPUS snapshot with a US close.

2. TEST AND ESTIMATE ARE DIFFERENT REGRESSIONS.
     standardised spec -> correct size (3.7% at rho=0) and high power. USE TO TEST.
     raw spec          -> unbiased rho (recovers 0.030/0.050/0.080 as
                          0.0296/0.0504/0.0816). USE TO SIZE.
   Dividing both sides by the same vol series introduces a shared divisor that
   inflates the measured correlation 2.2-2.8x. Reading the standardised rho as the
   tradeable correlation turns a Sharpe-0.47 effect into an apparent 1.30 -- the
   difference between "not tradeable" and "clears the bar".

DATA (--data mode). Place these in DATA_DIR:
  dgs2.csv        FRED DGS2            https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS2
  jgbcme_all.csv  MOF JGB curve        https://www.mof.go.jp/policy/international_policy/reference/interest_rate/jgbcme_all.csv
USDJPY comes from datasets.load_minute('combined'), as in specs 001/004. Do NOT substitute DEXJPUS.
FRED unreachable? dgs2.csv can be assembled from Treasury's daily par-curve CSV ('2 Yr'),
which is the same series; keep the observation_date,DGS2 layout. MOF's English file has moved to
  https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from usdjpy.config import DATA_DIR, HOLDOUT_START, RESULTS_DIR, SYMBOL  # noqa: E402
from usdjpy.signals import (build_spread, ewma_vol, forward_return, implied_sharpe,  # noqa: E402
                            predictive_regression, rate_path_signal, synthetic_check)

pd.set_option("display.width", 150, "display.float_format", "{:.4f}".format)

N_LOOKBACK = 5          # pre-declared, not searched
LAM = 0.94              # pre-declared
HORIZONS = (1, 3, 5, 10)
BONF_T = 2.81           # 4 horizons, Bonferroni at 5%
TRADEABILITY_SR = 0.67  # t=3 hurdle on 20y; below this -> "exists, not tradeable"


def harness_check() -> bool:
    print("=" * 78)
    print("HARNESS CHECK — required by spec 003 before any null is trusted")
    print("=" * 78)
    print(f"{'true rho':>9} {'raw t_hc':>9} {'raw SEr':>8} {'std t_hc':>9} {'std SEr':>8} {'recovers':>9}")
    ok = True
    for rho in (0.0, 0.03, 0.05, 0.08):
        r = synthetic_check(true_rho=rho, seed=11)
        raw, std = r["raw"], r["standardised"]
        print(f"{rho:>9.3f} {raw['t_hc']:>+9.2f} {raw['se_ratio']:>8.2f} "
              f"{std['t_hc']:>+9.2f} {std['se_ratio']:>8.2f} {str(r['passes']):>9}")
        if rho == 0.0 and r["passes"]:
            ok = False
            print("  !! NULL CASE PASSED — the harness has a look-ahead leak. STOP.")
        if rho >= 0.03 and not r["passes"]:
            ok = False
            print(f"  !! failed to recover a true rho of {rho} — harness underpowered or broken")
    print(f"\n  harness {'OK' if ok else 'FAILED'}\n")
    return ok


def load_yields():
    us_p, jp_p = DATA_DIR / "dgs2.csv", DATA_DIR / "jgbcme_all.csv"
    missing = [p.name for p in (us_p, jp_p) if not p.exists()]
    if missing:
        raise SystemExit(f"missing {missing} in {DATA_DIR} — see the docstring for URLs")

    us = pd.read_csv(us_p)
    us.columns = [c.strip().lower() for c in us.columns]
    dc = us.columns[0]
    us[dc] = pd.to_datetime(us[dc])
    us2y = pd.Series(pd.to_numeric(us[us.columns[1]], errors="coerce").values,
                     index=us[dc], name="us2y").dropna()

    raw = jp_p.read_bytes()
    for enc in ("utf-8", "shift_jis", "cp932"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    jp = pd.read_csv(pd.io.common.StringIO(text), skiprows=1)
    jp.columns = [str(c).strip() for c in jp.columns]
    jp[jp.columns[0]] = pd.to_datetime(jp.iloc[:, 0], errors="coerce")  # column assign: pandas 3 str dtype
    col2y = next((c for c in jp.columns if c in ("2", "2.0", "2Y")), None)
    if col2y is None:
        raise SystemExit(f"could not find the 2Y column in jgbcme_all.csv; columns: {list(jp.columns)[:12]}")
    jgb2y = pd.Series(pd.to_numeric(jp[col2y], errors="coerce").values,
                      index=jp.iloc[:, 0], name="jgb2y").dropna()
    return us2y, jgb2y


def run_real():
    from usdjpy.datasets import load_minute
    bars = load_minute("combined")
    mid = ((bars["bid"] + bars["ask"]) / 2)
    # one decision timestamp per day: 00:00 UTC, matching build_spread's convention.
    # The label-D value is the last bar of UTC day D, i.e. ~00:00 UTC D+1.
    px = mid.resample("1D").last().dropna()
    # Business days only: resample("1D") also emits a Sunday stub from the ~3h of
    # Sunday-evening UTC trading, which would make n=5 and h count 6-day weeks.
    px = px[px.index.day_of_week < 5]
    # Yields are naive calendar dates; a tz-aware price index reindexes to all-NaN.
    px.index = px.index.tz_localize(None)
    # Truncate BEFORE building forward returns: filtering on t alone lets the last
    # h days of 2024 reach into holdout prices at t+h.
    px = px[px.index < pd.Timestamp(HOLDOUT_START)]

    us2y, jgb2y = load_yields()
    sp = build_spread(us2y, jgb2y)
    sp = sp.reindex(px.index).ffill(limit=3)
    fresh = (sp["us_stale"] <= 3) & (sp["jp_stale"] <= 3)

    rets = np.log(px).diff()
    vol = ewma_vol(rets.dropna(), LAM).reindex(px.index).ffill()
    sig = rate_path_signal(sp["spread"], vol, n=N_LOOKBACK).where(fresh)

    pre = px.index < pd.Timestamp(HOLDOUT_START)
    print("=" * 78)
    print(f"REAL DATA — pre-holdout only ({px.index[0].date()} to {HOLDOUT_START})")
    print(f"  {int(pre.sum()):,} daily observations, signal non-null on "
          f"{int(sig[pre].notna().sum()):,}")
    print("=" * 78)
    print(f"{'h':>3} {'n':>6} {'std rho':>9} {'std t_hc':>9} {'SEr':>6} | "
          f"{'raw rho':>9} {'raw t_hc':>9} {'SEr':>6} | {'SR(raw)':>8} {'MDE rho':>8} {'verdict':>22}")
    rows = []
    for h in HORIZONS:
        y_std = forward_return(px, h, vol)[pre]
        y_raw = forward_return(px, h)[pre]
        x = sig[pre]
        std = predictive_regression(x, y_std, h)
        raw = predictive_regression(x, y_raw, h)
        sr = implied_sharpe(raw["rho"], h) if np.isfinite(raw["rho"]) else np.nan
        if not np.isfinite(std["t_hc"]):
            v = "insufficient data"
        elif abs(std["t_hc"]) < BONF_T:
            v = "null (kill 1)"
        elif abs(sr) < TRADEABILITY_SR:
            v = "exists, NOT tradeable"
        else:
            v = "SURVIVES -> Layer 2"
        # MDE on rho at 80% power against the pre-declared |t| > BONF_T bar
        mde_rho = (BONF_T + 0.8416) / np.sqrt(std["n"]) if std["n"] else np.nan
        print(f"{h:>3} {std['n']:>6} {std['rho']:>+9.4f} {std['t_hc']:>+9.2f} {std['se_ratio']:>6.2f} | "
              f"{raw['rho']:>+9.4f} {raw['t_hc']:>+9.2f} {raw['se_ratio']:>6.2f} | {sr:>+8.2f} "
              f"{mde_rho:>8.4f} {v:>22}")
        rows.append({"h": h, **{f"std_{k}": v2 for k, v2 in std.items()},
                     **{f"raw_{k}": v2 for k, v2 in raw.items()},
                     "sharpe_from_raw": sr, "mde_rho": mde_rho,
                     "mde_sharpe": mde_rho * np.sqrt(252 / h), "verdict": v})
    RESULTS_DIR.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(RESULTS_DIR / "003_rate_path_regression.csv", index=False)

    print(f"\n  Bonferroni threshold |t_hc| > {BONF_T} (4 horizons)")
    print(f"  Tradeability bar: |Sharpe from RAW rho| >= {TRADEABILITY_SR}")
    print("  Sign consistency across h is kill criterion 2 — check the raw rho column.")
    print(f"\n  SE ratio note: expect 5-7 on the RAW spec if signal vol co-moves with")
    print(f"  FX vol, and ~1 on the STANDARDISED spec. A large ratio on the")
    print(f"  standardised spec means the standardisation failed.")


if __name__ == "__main__":
    ok = harness_check()
    if not ok:
        raise SystemExit("harness check failed — fix before running on real data")
    if "--data" in sys.argv:
        run_real()
    else:
        print("harness only. re-run with --data once dgs2.csv and jgbcme_all.csv are in place.")
