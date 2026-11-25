"""Spec 004: Deflated Sharpe from the trade distribution, not from assumed normality.

    python scripts/004_deflated_sharpe.py [--results-dir DIR] [--trials 5]

CLAUDE.md's trial-budget paragraph quotes DSR 0.9744 at N=5 for the prefix leg
(per-trade SR 0.1062, n=882), passing the 0.95 hurdle up to N=8. Those figures
assume skew 0 and Pearson kurtosis 3. FX trade returns are fat-tailed, and
`stats.deflated_sharpe`'s denominator grows with kurtosis, so the real hurdle is
harder. This prints, for each B leg:
  - DSR at the current trial count, under normality and under the sample moments
  - the largest trial count N whose DSR still clears 0.95, under each
  - DSR at N = 18 (every spec in the index run on this sample)

Pass --results-dir results/archive/004_as_run_pre_dst_fix to reproduce the pre-DST-
fix figures; the default reads results/, the as-run on the corrected loader.
Kurtosis is PEARSON (normal = 3), as `deflated_sharpe` requires.
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402
from scipy.stats import kurtosis, skew  # noqa: E402

from usdjpy.config import RESULTS_DIR  # noqa: E402
from usdjpy.stats import deflated_sharpe  # noqa: E402

LEGS = ("prefix_long", "postfix_short")
HURDLE = 0.95
N_MAX = 200


def max_trials(sr: float, n: int, sk: float, ku: float) -> int:
    """Largest trial count whose DSR still exceeds the hurdle (0 if even N=1 fails).
    DSR falls monotonically in N, so scan up."""
    last = 0
    for k in range(1, N_MAX + 1):
        if deflated_sharpe(sr, n, sk, ku, k)["dsr"] > HURDLE:
            last = k
        else:
            break
    return last


def main(results_dir: pathlib.Path, trials: int) -> None:
    print(f"trade files: {results_dir}   trials now: {trials}   hurdle: DSR > {HURDLE}\n")
    hdr = f"{'leg':<14} {'n':>4} {'SR/trade':>9} {'skew':>7} {'kurt(P)':>8}   {'moments':<9} " \
          f"{'DSR@N=' + str(trials):>9} {'max N':>6} {'DSR@N=18':>9}"
    print(hdr)
    print("-" * len(hdr))
    for leg in LEGS:
        x = pd.read_csv(results_dir / f"004_{leg}_B_gotobi_proper.csv")["net_pips"].dropna()
        n, sr = len(x), x.mean() / x.std(ddof=1)
        sk, ku = float(skew(x)), float(kurtosis(x, fisher=False))
        for label, s_, k_ in (("normal", 0.0, 3.0), ("sample", sk, ku)):
            d_now = deflated_sharpe(sr, n, s_, k_, trials)["dsr"]
            d_18 = deflated_sharpe(sr, n, s_, k_, 18)["dsr"]
            print(f"{leg:<14} {n:>4} {sr:>9.4f} {sk:>+7.3f} {ku:>8.2f}   {label:<9} "
                  f"{d_now:>9.4f} {max_trials(sr, n, s_, k_):>6} {d_18:>9.4f}")
    print("\n'normal' assumes skew 0, Pearson kurtosis 3 (the figures CLAUDE.md quotes);"
          "\n'sample' uses the trade series' own moments. 'max N' is the largest trial count"
          f"\nstill clearing {HURDLE}; headroom = max N - trials run.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", type=pathlib.Path, default=RESULTS_DIR)
    ap.add_argument("--trials", type=int, default=5, help="hypotheses run on USDJPY 2007-2024 so far")
    a = ap.parse_args()
    main(a.results_dir, a.trials)
