"""Spec 019: yen-leg / dollar-leg split of the Gotobi-morning move.

    python scripts/019_yen_dollar_split.py                     # known-answer harness only
    python scripts/019_yen_dollar_split.py --step0             # + alignment gate on real data
    python scripts/019_yen_dollar_split.py --stage1            # + power, control days only; then STOP
    python scripts/019_yen_dollar_split.py --stage2 --confirm-stage2    # spends the trial
    add --fix-dst only if Step 0 reported the declared DST-window case (spec 019 *Step 0*)

Every rule is fixed in specs/019-yen-dollar-split.md; the library is src/usdjpy/legsplit.py
and its tests are tests/test_legsplit.py.

Order is enforced: every run does the harness first and refuses real data if any check
fails; --stage1 and --stage2 re-run Step 0 and stop if it fails; --stage2 needs
--confirm-stage2, which stands for the user's decision recorded in the spec with its date.
Stage 2 raises the USDJPY 2007-2024 trial count from 5 to 6.

Data: data/bars_1min/histdata_<pair>_bid_2007_2024.parquet for the six pairs, built by
scripts/fetch_official.py --histdata-pairs (only after the Dukascopy gap-fill fetch is
complete), and USDJPY from datasets.load_minute("combined") for Step 0.
"""
from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

from usdjpy import legsplit as L  # noqa: E402
from usdjpy.calendars import jp_business_days, turn_of_month_groups  # noqa: E402
from usdjpy.config import RESULTS_DIR  # noqa: E402
from usdjpy.datasets import histdata_pair_path, load_histdata_bid, load_minute  # noqa: E402
from usdjpy.events import PERIODS, stratified_compare  # noqa: E402

pd.set_option("display.width", 160, "display.float_format", "{:.3f}".format)

START, END = dt.date(2007, 1, 1), dt.date(2024, 12, 31)


def section(title: str) -> None:
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


def harness() -> None:
    section("HARNESS: known-answer checks (spec 019 *Implementation notes*)")
    results = L.harness_check()
    for name, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: {detail}")
    if not all(ok for _, ok, _ in results):
        raise SystemExit("harness check failed: fix before running on real data")


def load_bars(fix_dst: bool) -> dict[str, pd.Series]:
    missing = [p for p in L.PAIRS if not histdata_pair_path(p).exists()]
    if missing:
        raise SystemExit(f"missing bars for {missing}: scripts/fetch_official.py --histdata-pairs, "
                         "only after the Dukascopy gap-fill fetch is complete")
    bars = {p: load_histdata_bid(p, fix_dst=fix_dst) for p in L.PAIRS}
    bars["USDJPY"] = load_minute("combined")["bid"]
    return bars


def run_step0(bars, fix_dst: bool) -> None:
    section(f"STEP 0: alignment and identity (fix_dst={fix_dst})")
    days = jp_business_days(START, END)
    s0 = L.step0(bars, days)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    s0["cells"].to_csv(RESULTS_DIR / f"019_step0_cells_fixdst{int(fix_dst)}.csv")
    s0["units"].to_csv(RESULTS_DIR / f"019_step0_units_fixdst{int(fix_dst)}.csv")
    print(f"units checked: {len(s0['units'])}; cells: {len(s0['cells'])}")
    print("median |e_X| at shift 0 (bp):", s0["medians"].round(3).to_dict())
    print(s0["cells"].query("is_dst").to_string())
    if s0["passed"]:
        print("STEP 0 PASSED")
        return
    print("STEP 0 FAILED:")
    for f in s0["failures"]:
        print("  " + f)
    if s0["dst_only"] and not fix_dst:
        raise SystemExit("This is the declared case (DST-mismatch windows from 2019 only, at +60). "
                         "Re-run with --fix-dst and record the outcome in docs/DATA.md.")
    raise SystemExit("Stop. Report what was seen; use no data until spec 019 is amended by a dated note.")


def groups_legs(bars, exclude_mof: bool = True) -> dict[str, dict[str, pd.DataFrame]]:
    g = turn_of_month_groups(START, END)
    mof = L.mof_dates() if exclude_mof else pd.DatetimeIndex([])
    out = {}
    for w in L.WINDOWS:
        out[w] = {}
        for k, name in (("A", "A_month_end"), ("B", "B_gotobi_proper"), ("C", "C_control")):
            d = g[name].difference(mof)
            r, b = L.window_returns({p: bars[p] for p in L.PAIRS}, d, w)
            out[w][k] = L.legs(r, b)
    return out


def run_stage1(bars) -> None:
    section("STAGE 1: power from control days only (B outcomes not computed)")
    g = turn_of_month_groups(START, END)
    mof = L.mof_dates()
    legs_c, b_dates = {}, {}
    for w in L.WINDOWS:
        c = g["C_control"].difference(mof)
        r, b = L.window_returns({p: bars[p] for p in L.PAIRS}, c, w)
        legs_c[w] = L.legs(r, b)
        b_dates[w] = L.quoted_dates(bars, g["B_gotobi_proper"].difference(mof), w)
    tab = L.stage1(legs_c, b_dates)
    tab.to_csv(RESULTS_DIR / "019_stage1_power.csv", index=False)
    print(tab.to_string(index=False))
    print("\nPower is against spec 004's matched estimates "
          f"{L.SPEC004_MATCHED_PIPS} pips, which are probably inflated by selection.")
    print("STOP. Report this to the user. Stage 2 spends one USDJPY spec (N 5 -> 6) and runs only "
          "on their decision, recorded in spec 019 with its date (--confirm-stage2).")


def run_stage2(bars) -> None:
    section("STAGE 2: the declared tests (spends the trial: N 5 -> 6)")
    gl = groups_legs(bars, exclude_mof=True)
    tab = L.stage2_tests({w: gl[w]["B"] for w in L.WINDOWS}, {w: gl[w]["C"] for w in L.WINDOWS})
    tab.to_csv(RESULTS_DIR / "019_stage2_tests.csv")
    print(tab.drop(columns=["strata_dropped"]).to_string())
    print("\nREADINGS:")
    for r in L.readings(tab):
        print("  " + r)

    section("REPORTED, NOT TESTED")
    desc = L.descriptives(gl)
    desc.to_csv(RESULTS_DIR / "019_stage2_descriptives.csv", index=False)
    print(desc.to_string(index=False))
    for w in L.WINDOWS:
        uj = stratified_compare(gl[w]["B"], gl[w]["C"], col="UJ")
        j = stratified_compare(gl[w]["B"], gl[w]["C"], col="J")
        print(f"yen share, {w}: {L.yen_share(uj, j)}  (only where the matched r_UJ difference has |t| >= 2)")
    rows = []
    for w in L.WINDOWS:
        for per, (a, b) in PERIODS.items():
            sl = {k: v[(v.index >= a) & (v.index <= b)] for k, v in gl[w].items()}
            for leg in ("J", "D"):
                if len(sl["B"]) >= 10 and len(sl["C"]) >= 10:
                    r = stratified_compare(sl["B"], sl["C"], col=leg)
                    rows.append({"window": w, "period": per, "leg": leg, "diff": r["diff"], "t": r["t"],
                                 "n_B": r["n_treat"]})
    per = pd.DataFrame(rows)
    per.to_csv(RESULTS_DIR / "019_stage2_periods.csv", index=False)
    print(per.to_string(index=False))
    gl_mof = groups_legs(bars, exclude_mof=False)
    tab_mof = L.stage2_tests({w: gl_mof[w]["B"] for w in L.WINDOWS}, {w: gl_mof[w]["C"] for w in L.WINDOWS})
    tab_mof.to_csv(RESULTS_DIR / "019_stage2_tests_with_mof.csv")
    print("\nwith MOF days included (diagnostic):")
    print(tab_mof[["diff_pips", "t", "n_B"]].to_string())
    print("\nentry-bar spread, B vs C: n/a (HistData is bid-only)")
    print("\nNext: record the results in spec 019, confirmed from a fresh clone; set the trial "
          "count to N = 6 in CLAUDE.md and handoffs/HANDOFF.md §2.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--step0", action="store_true")
    ap.add_argument("--stage1", action="store_true")
    ap.add_argument("--stage2", action="store_true")
    ap.add_argument("--confirm-stage2", action="store_true",
                    help="the user's decision to spend the trial, recorded in spec 019 with its date")
    ap.add_argument("--fix-dst", action="store_true",
                    help="apply datasets.fix_histdata_dst to the six pairs (only in Step 0's declared case)")
    a = ap.parse_args()
    harness()
    if not (a.step0 or a.stage1 or a.stage2):
        return
    if a.stage2 and not a.confirm_stage2:
        raise SystemExit("Stage 2 spends the trial: it needs --confirm-stage2, standing for the "
                         "user's decision recorded in spec 019 with its date.")
    bars = load_bars(a.fix_dst)
    run_step0(bars, a.fix_dst)
    if a.stage1:
        run_stage1(bars)
    if a.stage2:
        run_stage2(bars)


if __name__ == "__main__":
    main()
