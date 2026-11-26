"""Spec 004 gap-fill analysis: step 0, the filled sample, the measured-spread column,
figures 1-7 as run and filled, and the reported-only diagnostics.

    python scripts/004_gap_fill_analysis.py --check     # gate status only (filenames, no contents)
    python scripts/004_gap_fill_analysis.py             # refuses unless the fetch is complete
    python scripts/004_gap_fill_analysis.py --waived F  # F: CSV utc_day,reason,decided_on

Everything here was fixed before any filled data was viewed: spec 004 *Gap fill*, its
DST amendment, *Weekday-matched comparison*, and *Amendment: field standards*
(2026-11-25). Read those first. The library is src/usdjpy/gapfill.py and
src/usdjpy/tradeability.py; tests are tests/test_gapfill.py, on synthetic tick trees.

Gate: every stage of scripts/download_gap_fill.py must have 0 days left
(`missing_days`), except days in --waived. A day may be waived only by a dated
note in spec 004 recording the user's decision that it is unnecessary, made before
filled data is viewed; the waived file must match that note. There is no deadline.

Step 0, 2007-2014 part, is a gate: if it fails, this stops before any fill is used
and the spec must be amended by a dated note saying what was seen.
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from usdjpy import gapfill as gf  # noqa: E402
from usdjpy import tradeability as tr  # noqa: E402
from usdjpy.calendars import jp_business_days, turn_of_month_groups  # noqa: E402
from usdjpy.config import DATA_DIR, HOLDOUT_START, RESULTS_DIR  # noqa: E402
from usdjpy.costs import PIP  # noqa: E402
from usdjpy.datasets import BARS, load_minute  # noqa: E402
from usdjpy.events import PERIODS, compare, stratified_compare, summarize, window_trades  # noqa: E402

_spec = importlib.util.spec_from_file_location("download_gap_fill", ROOT / "scripts" / "download_gap_fill.py")
dgf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dgf)

GROUPS = ("A_month_end", "B_gotobi_proper", "C_control")
PAIRS = (("A_month_end", "C_control"), ("B_gotobi_proper", "C_control"), ("A_month_end", "B_gotobi_proper"))
SETS = ("as run", "filled")

# Deviations from the plan as first declared (spec 004), for the deviations table.
DEVIATIONS = [
    ("2026-11-25", "data correction", "HistData EU-DST clock from 2019 corrected in the loader (fix_histdata_dst)",
     "after as-run results were seen; correction chosen by the user before the corrected re-run"),
    ("2026-11-25", "added test", "weekday-matched comparison (events.stratified_compare)",
     "after as-run results and a weekday-dummy regression were seen; before filled data"),
    ("2026-11-25", "evaluation", "criterion 5 evaluated per trade; the 1.60 bar withdrawn",
     "after as-run results were seen; before filled data"),
    ("2026-11-25", "amendment", "field standards: own quote first, stage 2 mean not median, impute and flag, "
     "no fetch deadline, reported-only diagnostics", "before filled data"),
]


def load_waived(path: str | None) -> dict:
    if not path:
        return {}
    w = pd.read_csv(path, parse_dates=["utc_day"])
    return {d.date(): (r, dec) for d, r, dec in zip(w.utc_day, w.reason, w.decided_on)}


def gate(tree_root: pathlib.Path, waived: dict) -> dict:
    out = {}
    for s, (a, b, days, _) in dgf.STAGES.items():
        miss = [d for d, _n in dgf.missing_days(a, b, days, out_dir=tree_root) if d not in waived]
        out[s] = miss
    return out


def fmt(x, nd=3, sign=True):
    return "nan" if x is None or (isinstance(x, float) and np.isnan(x)) else (f"{x:+.{nd}f}" if sign else f"{x:.{nd}f}")


def section(title):
    print("\n" + "=" * 100 + f"\n{title}\n" + "=" * 100)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree-root", type=pathlib.Path, default=DATA_DIR / "tokyo_hours")
    ap.add_argument("--waived", default=None)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    waived = load_waived(a.waived)
    miss = gate(a.tree_root, waived)
    for s, m in miss.items():
        print(f"stage {s}: {len(m)} days still missing" + (f" (first {m[0]})" if m else ""))
    if waived:
        print(f"waived by dated user decision: {len(waived)} days")
    if a.check:
        return
    if any(miss.values()):
        raise SystemExit("Refusing to run: the fetch is not complete. There is no deadline (spec 004, "
                         "Amendment: field standards); wait, or record a dated waiver.")

    # ------------------------------------------------------------ as run
    combined = load_minute("combined")
    start, end = combined.index[0].date(), combined.index[-1].date()
    groups = turn_of_month_groups(start, end)
    asrun = {leg: {g: window_trades(combined, groups[g], *gf.RULES[leg]) for g in GROUPS} for leg in gf.RULES}

    # ------------------------------------------------------------ tree and step 0
    tree = gf.load_tree(a.tree_root)
    tr_real, tr_syn = gf.real_bars(tree), gf.synthetic_bars(tree)
    s1, s3 = dgf.STAGES["1"], dgf.STAGES["3"]

    section("STEP 0: source agreement at the execution bars")
    old = tree[tree.index < pd.Timestamp("2015-01-01", tz="UTC")]
    export_bid = load_minute("dukascopy")["bid"]
    t1 = gf.step0_table(old["bid"], export_bid)
    ok, why = gf.step0_verdict(t1)
    print("2007-2014, tree vs the third-party export (gate: median <= 0.3 pips at 0, mean smallest at 0 of -60/0/+60):")
    print(t1.round(3).to_string())
    print(f"  -> {'PASS' if ok else 'FAIL: ' + '; '.join(why)}")
    print(f"  0.3-pip gate in scale: {0.3 / gf.ONE_SPREAD_PIPS:.2f} of the entry spread")
    lo, hi = pd.Timestamp(s1[0], tz="UTC"), pd.Timestamp(s1[1], tz="UTC") + pd.Timedelta(days=1)
    s1tree = tree[(tree.index >= lo) & (tree.index < hi)]
    hd_fixed = load_minute("histdata")["bid"]
    print("\nFeb-Jul 2023, tree vs DST-corrected HistData, 00:54 and 01:59 (reported, no threshold):")
    print(gf.step0_table(s1tree["bid"], hd_fixed, times=("00:54", "01:59")).round(3).to_string())
    hd_raw = pd.read_parquet(BARS / "histdata_bid_2015_2025.parquet")["close"].astype(float)
    mar = s1tree[(s1tree.index >= pd.Timestamp("2023-03-12", tz="UTC")) & (s1tree.index < pd.Timestamp("2023-03-25", tz="UTC"))]
    print("\n12-24 March 2023, tree vs HistData AS STORED (uncorrected); the hour offset should show here only:")
    print(gf.step0_table(mar["bid"], hd_raw, times=("00:54", "01:59")).round(3).to_string())
    print(f"\nBNHLS-style cleaning counts on the tree (reported): {gf.cleaning_counts(tree)}")
    if not ok:
        raise SystemExit("Step 0 failed. No fill is used until spec 004 is amended by a dated note saying what was seen.")

    # ------------------------------------------------------------ filled sample and measured spreads
    windows = [(s1[0], s1[1]), (s3[0], s3[1])]
    filled = {leg: {g: gf.fill_group(asrun[leg][g], groups[g], tr_syn, windows, *gf.RULES[leg]) for g in GROUPS}
              for leg in gf.RULES}
    stage2_days = dgf.spread_sample_jst_days(pd.Timestamp("2015-01-01").date(), pd.Timestamp("2024-12-31").date())
    cell_days = jp_business_days(start, (pd.Timestamp(HOLDOUT_START) - pd.Timedelta(days=1)).date())

    def prepare(t, leg, tol="5min"):
        if t.empty:
            return t
        m = gf.measured_spreads(t, leg, tr_real, stage2_days, cell_days, tol)
        return tr.with_cost_columns(t.join(m))

    data = {"as run": {leg: {g: prepare(asrun[leg][g].assign(filled=False), leg) for g in GROUPS} for leg in gf.RULES},
            "filled": {leg: {g: prepare(filled[leg][g], leg) for g in GROUPS} for leg in gf.RULES}}
    RESULTS_DIR.mkdir(exist_ok=True)
    for leg in gf.RULES:
        for g in GROUPS:
            data["filled"][leg][g].to_csv(RESULTS_DIR / f"004_filled_{leg}_{g}.csv")

    # ------------------------------------------------------------ figures
    section("FIGURE 1: day and trade counts")
    hold = pd.Timestamp(HOLDOUT_START)
    for leg in gf.RULES:
        for g in GROUPS:
            days = groups[g][groups[g] < hold]
            ar, fi = data["as run"][leg][g], data["filled"][leg][g]
            print(f"  {leg:<14} {g:<16} days {len(days):>5}  as run {len(ar):>5}  filled {len(fi):>5} "
                  f"(+{int(fi['filled'].sum())})")
    for s in SETS:
        b = data[s]["prefix_long"]["B_gotobi_proper"]
        n23 = int((b.index.year == 2023).sum())
        d23 = int(((groups["B_gotobi_proper"].year == 2023)).sum())
        print(f"  2023 prefix B, {s}: {n23} of {d23}")

    section("FIGURE 2: the clean test, mid_pips; unmatched (declared) and weekday-matched (declared 2026-11-25)")
    for leg in gf.RULES:
        for x, y in PAIRS:
            row = [f"  {leg:<14} {x[0]} vs {y[0]}"]
            for s in SETS:
                c = compare(data[s][leg][x], data[s][leg][y])
                se = c["diff"] / c["t"] if c["t"] else np.nan
                m = stratified_compare(data[s][leg][x], data[s][leg][y])
                row.append(f"{s}: unmatched {fmt(c['diff'])} t{fmt(c['t'], 2)} MDE {fmt(tr.MDE_MULT * abs(se), 2, False)} | "
                           f"matched {fmt(m['diff'])} t{fmt(m['t'], 2)} MDE {fmt(tr.MDE_MULT * m['se'], 2, False)}")
            print("   ".join(row))

    section("FIGURE 3: period stability, B, net pips at base costs")
    for leg in gf.RULES:
        for s in SETS:
            b = data[s][leg]["B_gotobi_proper"]
            print(f"  {leg} {s}:")
            print(summarize(b, "net_as run")[["n", "mean", "t"]].round(3).to_string())

    section("FIGURE 4-5: Sharpe and power, B (both restate t)")
    for leg in gf.RULES:
        for s in SETS:
            b = data[s][leg]["B_gotobi_proper"]
            sp = {c: tr.sharpe_power(b, c) for c in tr.COLUMNS}
            p = sp["as run"]
            print(f"  {leg:<14} {s:<7} n {p['n']}  effect {fmt(p['mean'])} t {fmt(p['t'], 2)}  threshold {fmt(p['threshold'], 3, False)} "
                  f"MDE80 {fmt(p['mde80'], 3, False)}  observed power {p['observed_power']:.1%}  "
                  f"predictive replication {p['predictive_replication']:.1%}")
            print("      Sharpe " + "  ".join(f"{c} {sp[c]['annual_sharpe']:.3f}" for c in tr.COLUMNS)
                  + f"  live {p['live']:.3f}")

    section("FIGURE 6: tradeability, B. Criterion 5 governs on the MEASURED column")
    for leg in gf.RULES:
        for s in SETS:
            b = data[s][leg]["B_gotobi_proper"]
            k4 = tr.criterion_4(b)
            k4m = tr.criterion_4(b, "measured")
            print(f"\n  {leg} {s}: criterion 4 (net under PESSIMISTIC) as run {fmt(k4['mean'])} t{fmt(k4['t'], 2)}; "
                  f"measured {fmt(k4m['mean'])} t{fmt(k4m['t'], 2)}")
            print(f"    {'column':<9} {'net':>8} {'t':>6} {'margin':>8} {'SE':>6} {'95% LCB':>8} {'1-SE':<13} {'95%':<13} "
                  f"{'strict 95%':<13} {'159 view':>9}")
            for c in tr.COLUMNS:
                nt = tr.mean_t(b[f"net_{c}"])
                k5 = tr.criterion_5(b, c)
                v = tr.today_view(b, c)
                print(f"    {c:<9} {fmt(nt['mean']):>8} {fmt(nt['t'], 2):>6} {fmt(k5['margin']):>8} {fmt(k5['se'], 3, False):>6} "
                      f"{fmt(k5['lcb95']):>8} {k5['label_1se']:<13} {k5['label_95']:<13} {k5['strict_label_95']:<13} "
                      f"{'withheld' if v is None else fmt(v):>9}")
            be = tr.break_even(b)
            bem = tr.break_even(b, "measured")
            bp = tr.bp_stats(b)
            st = tr.bp_stability(b)
            print(f"    break-even all-in (as run): zero {fmt(be['zero'], 3, False)}p = {fmt(be['zero_bp'], 3, False)}bp, "
                  f"t=2.5 {fmt(be['t2.5'], 3, False)}, t=1.645 {fmt(be['t1.645'], 3, False)}, / base all-in {be['ratio']:.2f}x; "
                  f"measured: t=2.5 {fmt(bem['t2.5'], 3, False)}, / base {bem['ratio']:.2f}x")
            print(f"    bp at own price: net {fmt(bp['mean'])}bp t{fmt(bp['t'], 2)}; bp-stability slope t {fmt(st['t_slope'], 2)} "
                  f"-> 159 view {'admissible (projection)' if st['admissible'] else 'withheld'}; "
                  f"terciles {st['terciles']['mean'].round(2).to_dict()}")

    section("FIGURE 7: deflated Sharpe, N = 5 specs, trade-series moments")
    for leg in gf.RULES:
        for s in SETS:
            for c in ("as run", "measured"):
                d = tr.dsr(data[s][leg]["B_gotobi_proper"], 5, c)
                print(f"  {leg:<14} {s:<7} {c:<9} SR/trade {d['sr']:.4f} n {d['n']} skew {fmt(d['skew'], 2)} "
                      f"kurt {d['kurt']:.1f}  DSR {d['dsr']:.4f}  max N {d['max_n']}")

    # ------------------------------------------------------------ diagnostics (reported only)
    section("DIAGNOSTICS (reported only; govern nothing)")
    for leg in gf.RULES:
        b = data["filled"][leg]["B_gotobi_proper"]
        share = b.groupby("s_source").agg(trades=("net_pips", "size"), pnl=("net_measured", "sum"))
        share["trade_share"] = share["trades"] / share["trades"].sum()
        print(f"\n  {leg}: measured-spread source per B trade (filled sample)")
        print(share.round(3).to_string())
        cc = b[~b["s_source"].isin(["imputed", "none"])]
        k5 = tr.criterion_5(cc, "measured")
        print(f"    complete-case (imputed dropped, {len(b) - len(cc)} trades): criterion 5 margin {fmt(k5['margin'])} "
              f"({k5['label_95']} at 95%)")
        m1 = gf.measured_spreads(filled[leg]["B_gotobi_proper"], leg, tr_real, stage2_days, cell_days, "1min")
        b1 = tr.with_cost_columns(filled[leg]["B_gotobi_proper"].join(m1))
        k51 = tr.criterion_5(b1, "measured")
        print(f"    1-minute tolerance: criterion 5 margin {fmt(k51['margin'])} ({k51['label_95']} at 95%); "
              f"own quotes {int((m1.s_source == 'own').sum())} vs {int((b.s_source == 'own').sum())} at 5 min")

        s2 = gf.spreads_on_days(tr_real, stage2_days, leg)
        y = gf.yearly(s2)
        y["mean_minus_median"] = y["mean"] - y["median"]
        print("    stage 2 sample spread at the paying bar, by year (pips):")
        print(y.round(3).to_string())
        bday = set(groups["B_gotobi_proper"])
        sb, sc = s2[[d in bday for d in s2.index]].dropna(), s2[[d not in bday for d in s2.index]].dropna()
        print(f"    B vs C sample days: {sb.mean():.3f} vs {sc.mean():.3f} pips (n {len(sb)} / {len(sc)})")
        ownb = b[b.s_source == "own"]["s_meas"]
        ownc = data["filled"][leg]["C_control"]
        ownc = ownc[ownc.s_source == "own"]["s_meas"]
        print(f"    B vs C own quotes, all years: {ownb.mean():.3f} vs {ownc.mean():.3f} pips (n {len(ownb)} / {len(ownc)})")

        allf = pd.concat([data["filled"][leg][g] for g in GROUPS])
        own = allf[(allf.s_source == "own") & (allf.source != "eightcap")]
        ratio = own.groupby(own.index.year).apply(lambda x: x["s_meas"].mean() / x["spread_paid_pips"].mean())
        print("    measured / synthetic spread by year (estimated era multiplier; declared x5 pre-2015, x2.5 after):")
        print("      " + ", ".join(f"{yr}: {r:.2f}" for yr, r in ratio.items()))

        early = dgf.spread_sample_jst_days(pd.Timestamp("2007-01-01").date(), pd.Timestamp("2014-12-31").date())
        est = gf.yearly(gf.spreads_on_days(tr_real, early, leg))["mean"]
        truth = own[own.index < pd.Timestamp("2015-01-01")].groupby(own[own.index < pd.Timestamp("2015-01-01")].index.year)["s_meas"].mean()
        bias = (est - truth).dropna()
        print("    stage-2-style estimator minus per-trade mean, 2007-2014 (bias of the 2015-2024 fallback):")
        print("      " + ", ".join(f"{yr}: {v:+.3f}" for yr, v in bias.items()))

    for hhmm in gf.EXEC_BARS:
        x = tree[tree.index.strftime("%H:%M") == hhmm]
        print(f"\n  instant vs minute-mean spread at {hhmm}: {x['spread_last'].mean() / PIP:.3f} vs "
              f"{x['spread_mean'].mean() / PIP:.3f} pips (n {len(x)})")
    ec = load_minute("eightcap")
    late = [d for d in stage2_days if pd.Timestamp("2024-06-19") <= pd.Timestamp(d) < pd.Timestamp(HOLDOUT_START)]
    for leg in gf.RULES:
        ts = gf.jst_to_utc(late, gf.paying_clock(leg))
        qd, qe = gf.quotes_at(tr_real, ts), gf.quotes_at(ec, ts)
        sd, se_ = (qd.ask - qd.bid) / PIP, (qe.ask - qe.bid) / PIP
        both = sd.notna() & se_.notna()
        print(f"  Dukascopy vs Eightcap, H2-2024 stage 2 days, {leg} paying bar: spread {sd[both].mean():.3f} vs "
              f"{se_[both].mean():.3f} pips, bid diff median {((qd.bid - qe.bid).abs()[both] / PIP).median():.3f} "
              f"(n {int(both.sum())}; pre-holdout only)")

    print("\n  missingness: pre-holdout group days with no as-run trade, by year, and how many the fill restored")
    for leg in gf.RULES:
        entry, exit_, side = gf.RULES[leg]
        for g in GROUPS:
            days = groups[g][groups[g] < hold]
            drop = days[~days.isin(asrun[leg][g].index)]
            if not len(drop):
                continue
            qi = gf.quotes_at(combined, gf.jst_to_utc(drop, entry))["bid"].isna().to_numpy()
            ts_out = gf.jst_to_utc(drop, exit_)
            qo = gf.quotes_at(combined, ts_out)["bid"].isna().to_numpy()
            kind = np.where(qi & qo, "both", np.where(qi, "entry", "exit"))
            restored = drop.isin(data["filled"][leg][g].index)
            t = pd.DataFrame({"year": drop.year, "bar": kind, "restored": restored})
            tab = t.groupby(["year", "bar"]).agg(missing=("restored", "size"), restored=("restored", "sum"))
            print(f"    {leg} {g}: {len(drop)} missing, {int(restored.sum())} restored")
            print("      " + "; ".join(f"{yr} {bar}: {r.missing}/{r.restored}" for (yr, bar), r in tab.iterrows()))

    print("\n  missing-at-random check: |mid_pips| of filled vs as-run trades in the fill years")
    for leg in gf.RULES:
        allf = pd.concat([data["filled"][leg][g] for g in GROUPS])
        yrs = allf[allf.filled].index.year.unique()
        base = allf[(~allf.filled) & allf.index.year.isin(yrs)]
        print(f"    {leg}: filled mean |mid| {allf[allf.filled].mid_pips.abs().mean():.2f} (sd {allf[allf.filled].mid_pips.std():.2f}, "
              f"n {int(allf.filled.sum())}) vs as run {base.mid_pips.abs().mean():.2f} (sd {base.mid_pips.std():.2f}, n {len(base)})")

    print("\n  deviations table (spec 004)")
    for d, kind, what, when in DEVIATIONS:
        print(f"    {d}  {kind:<15} {what}  [{when}]")
    for day, (reason, decided) in sorted(load_waived(a.waived).items()):
        print(f"    {decided}  waived day      {day}: {reason}  [before filled data]")


if __name__ == "__main__":
    main()
