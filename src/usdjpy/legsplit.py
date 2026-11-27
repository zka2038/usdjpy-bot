"""Spec 019: yen-leg / dollar-leg split of the Gotobi-morning move.

Read specs/019-yen-dollar-split.md first; every rule here is fixed there.

    r_UJ = r_XJ - r_XU                    (triangular identity, window log returns)
    J    = mean_X r_XJ                    yen leg: + = yen weaker against the basket
    D    = -mean_X r_XU                   dollar leg: + = dollar stronger against the basket
    J + D = r_UJ                          for X in {EUR, GBP, AUD}

Returns are bid-to-bid, in bp, not side-adjusted. Tests are in USDJPY pip equivalents:
bp x P_hat / 100, with P_hat = mean_X bid_XJ / bid_XU at entry (USDJPY implied by the
crosses, so J and D need no USDJPY quote). USDJPY itself is used only in Step 0.

Stages, each a separate call, in order:
  step0   identity residuals at X-pair shifts of -60/0/+60 min: alignment gate.
  stage1  power from CONTROL days only (B's weekday counts from quote availability).
  stage2  B vs weekday-matched C on J and D: the four declared tests and the readings.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm

from .config import DATA_DIR, HOLDOUT_START
from .datasets import us_eu_dst_mismatch_windows
from .events import compare, stratified_compare
from .gapfill import jst_to_utc, quotes_at

X_CCYS = ("EUR", "GBP", "AUD")
CROSSES = tuple(f"{x}JPY" for x in X_CCYS)
USD_PAIRS = tuple(f"{x}USD" for x in X_CCYS)
PAIRS = CROSSES + USD_PAIRS
WINDOWS = {"prefix": ("08:00", "09:55"), "postfix": ("09:55", "11:00")}   # spec 004's, JST

BAR = 2.5                                   # Bonferroni over 4 two-sided tests at 5% (2.498)
MDE_MULT = BAR + norm.ppf(0.80)             # 3.342: MDE at 80% power against the bar
STEP0_SHIFTS = (0, -60, 60)                 # minutes; 0 first so a tie goes to 0
STEP0_MEDIAN_MAX_BP = 2.0
STEP0_DST_FROM = 2019                       # HistData's EU-date fault (CLAUDE.md trap 8)

# Spec 004's weekday-matched B-vs-C estimates, as run, DST-corrected, side-adjusted pips:
# t x MDE / 3.342 from t 1.91 / 2.28 and MDE 2.73 / 2.14 (spec 004; spec 019 *Stage 1*).
SPEC004_MATCHED_PIPS = {"prefix": 1.560, "postfix": 1.460}
PREDICTED_SIGN_J = {"prefix": +1, "postfix": -1}   # raw returns: prefix up, postfix reversal

TESTS = (("P", "J", "prefix"), ("S1", "J", "postfix"), ("S2", "D", "prefix"), ("S3", "D", "postfix"))

HOLDOUT_UTC = pd.Timestamp(HOLDOUT_START, tz="UTC")


# ---------------------------------------------------------------- returns

def window_times(dates, window: str) -> tuple[pd.DatetimeIndex, pd.DatetimeIndex, pd.DatetimeIndex]:
    """Pre-holdout JST dates and their UTC entry and exit instants for a window. A date is
    kept only if it is before HOLDOUT_START and its exit is before HOLDOUT_START 00:00 UTC
    (the window_trades rule)."""
    d = pd.DatetimeIndex(dates)
    if d.tz is not None:
        d = d.tz_localize(None)
    d = d.normalize().unique().sort_values()
    entry, exit_ = WINDOWS[window]
    t_in, t_out = jst_to_utc(d, entry), jst_to_utc(d, exit_)
    keep = np.asarray((d < pd.Timestamp(HOLDOUT_START)) & (t_out < HOLDOUT_UTC))
    return d[keep], t_in[keep], t_out[keep]


def window_returns(bars: dict[str, pd.Series], dates, window: str, shift_min: int = 0
                   ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per pair (columns) and JST date (rows): bid-to-bid log return in bp, and the entry bid.
    NaN where either end has no quote (`events.quote_at` rule: the bar at ts - 1min, 5-min
    staleness). `shift_min` moves each pair's bar labels forward by that many minutes before
    reading, i.e. reads the stored label ts - shift_min: +60 undoes bars stamped an hour
    early, the direction `datasets.fix_histdata_dst` corrects."""
    d, t_in, t_out = window_times(dates, window)
    lag = pd.Timedelta(minutes=shift_min)
    r, b_in = {}, {}
    for pair, s in bars.items():
        frame = s.to_frame("bid") if isinstance(s, pd.Series) else s[["bid"]]
        q_in = quotes_at(frame, t_in - lag, cols=("bid",))["bid"].to_numpy()
        q_out = quotes_at(frame, t_out - lag, cols=("bid",))["bid"].to_numpy()
        r[pair] = 1e4 * np.log(q_out / q_in)
        b_in[pair] = q_in
    return pd.DataFrame(r, index=d), pd.DataFrame(b_in, index=d)


def legs(r: pd.DataFrame, bid_in: pd.DataFrame) -> pd.DataFrame:
    """J, D and r_UJ = J + D in bp and in USDJPY pip equivalents, on dates where all six
    pairs quote at both ends; per-X legs in bp for the descriptives."""
    ok = r[list(PAIRS)].notna().all(axis=1) & bid_in[list(PAIRS)].notna().all(axis=1)
    r, b = r[ok], bid_in[ok]
    out = pd.DataFrame(index=r.index)
    out["J_bp"] = r[list(CROSSES)].mean(axis=1)
    out["D_bp"] = -r[list(USD_PAIRS)].mean(axis=1)
    out["UJ_bp"] = out["J_bp"] + out["D_bp"]
    out["P_hat"] = np.mean([b[f"{x}JPY"] / b[f"{x}USD"] for x in X_CCYS], axis=0)
    scale = out["P_hat"] / 100.0
    for c in ("J", "D", "UJ"):
        out[c] = out[f"{c}_bp"] * scale
    for x in X_CCYS:
        out[f"{x}JPY_bp"] = r[f"{x}JPY"]
        out[f"neg_{x}USD_bp"] = -r[f"{x}USD"]
    return out


def quoted_dates(bars: dict[str, pd.Series], dates, window: str) -> pd.DatetimeIndex:
    """Dates on which all six pairs quote at both ends: quote existence only. Stage 1 uses
    it for B's weekday counts, so B's returns are never formed there."""
    d, t_in, t_out = window_times(dates, window)
    ok = np.ones(len(d), dtype=bool)
    for pair in PAIRS:
        s = bars[pair]
        frame = s.to_frame("bid") if isinstance(s, pd.Series) else s[["bid"]]
        for t in (t_in, t_out):
            ok &= quotes_at(frame, t, cols=("bid",))["bid"].notna().to_numpy()
    return d[ok]


def mof_dates() -> pd.DatetimeIndex:
    """Every date in the transcribed MOF intervention file, any pair (spec 019 *Rules*)."""
    df = pd.read_csv(DATA_DIR / "calendars" / "mof_intervention_transcribed.csv", parse_dates=["date"])
    return pd.DatetimeIndex(sorted(df["date"].dt.normalize().unique()))


# ---------------------------------------------------------------- step 0

def step0(bars: dict[str, pd.Series], dates, shifts=STEP0_SHIFTS,
          median_max_bp: float = STEP0_MEDIAN_MAX_BP) -> dict:
    """Spec 019 *Step 0*. e_X = r_UJ - (r_XJ - r_XU) in bp, with the six X pairs read at each
    shift and USDJPY at 0. Unit: one (date, window). Its best shift minimises the mean |e_X|
    over the X available. Cells: each US/EU DST-mismatch window, and each calendar month over
    the units outside those windows. A cell passes if shift 0 is best on more than half its
    units. Also median |e_X| at shift 0 <= median_max_bp for each X, all units pooled.

    Returns passed, dst_only (every failing cell is a mismatch window from 2019 whose modal
    best shift is +60, and the medians pass: the declared fix_histdata_dst case), failures,
    cells, medians and the unit table. Reads identity residuals only: no group means."""
    xs = {p: bars[p] for p in PAIRS}
    units = []
    for w in WINDOWS:
        r_uj, _ = window_returns({"USDJPY": bars["USDJPY"]}, dates, w, 0)
        _, t_in, _ = window_times(dates, w)
        m = {}
        e0 = None
        for k in shifts:
            r_x, _ = window_returns(xs, dates, w, k)
            e = pd.DataFrame({x: r_uj["USDJPY"] - (r_x[f"{x}JPY"] - r_x[f"{x}USD"]) for x in X_CCYS})
            m[k] = e.abs().mean(axis=1)          # NaN where no X is available
            if k == 0:
                e0 = e
        mm = pd.DataFrame(m)
        checked = mm[0].notna()
        best = mm.fillna(np.inf).idxmin(axis=1)   # columns in `shifts` order: ties go to 0
        u = pd.DataFrame({"window": w, "entry_utc": t_in, "best": best, "mean_abs_e0": mm[0]},
                         index=mm.index)
        for x in X_CCYS:
            u[f"e0_{x}"] = e0[x]
        units.append(u[checked.to_numpy()])
    units = pd.concat(units)
    if units.empty:
        return {"passed": False, "dst_only": False, "failures": ["no unit could be checked"],
                "cells": pd.DataFrame(), "medians": pd.Series(dtype=float), "units": units}

    years = range(units["entry_utc"].min().year, units["entry_utc"].max().year + 1)
    win = us_eu_dst_mismatch_windows(years)
    cell = pd.Series("", index=units.index, dtype=object)
    ts = units["entry_utc"]
    for a, b in win:
        cell[((ts >= a) & (ts < b)).to_numpy()] = f"dst {a:%Y-%m-%d}..{b:%Y-%m-%d}"
    outside = cell == ""
    cell[outside] = units.index[outside.to_numpy()].strftime("%Y-%m")
    units["cell"] = cell.to_numpy()

    rows = []
    for c, g in units.groupby("cell"):
        share0 = float((g["best"] == 0).mean())
        modal = int(g["best"].mode().iloc[0])
        rows.append({"cell": c, "n": len(g), "share_best_0": share0, "modal_best": modal,
                     "is_dst": c.startswith("dst"), "year": int(g["entry_utc"].iloc[0].year),
                     "ok": share0 > 0.5})
    cells = pd.DataFrame(rows).set_index("cell")
    medians = units[[f"e0_{x}" for x in X_CCYS]].abs().median()
    medians.index = list(X_CCYS)

    failures = [f"cell {c}: shift 0 best on {r.share_best_0:.0%} of {r.n} units (modal {r.modal_best:+d})"
                for c, r in cells[~cells["ok"]].iterrows()]
    med_fail = [f"median |e_{x}| at shift 0 = {v:.2f} bp > {median_max_bp}" for x, v in medians.items()
                if not (v <= median_max_bp)]
    failures += med_fail
    passed = not failures
    bad = cells[~cells["ok"]]
    dst_only = (not passed and not med_fail and len(bad) > 0 and bool(bad["is_dst"].all())
                and bool((bad["year"] >= STEP0_DST_FROM).all()) and bool((bad["modal_best"] == 60).all()))
    return {"passed": passed, "dst_only": dst_only, "failures": failures, "cells": cells,
            "medians": medians, "units": units}


def shift_in_windows(s: pd.Series, windows, minutes: int) -> pd.Series:
    """Move bar labels by `minutes` inside the given UTC spans. Test helper for building a
    known misalignment; on real HistData use datasets.fix_histdata_dst, which carries the
    double-correction guard."""
    idx = s.index
    mask = np.zeros(len(idx), dtype=bool)
    for a, b in windows:
        mask |= (idx >= a) & (idx < b)
    out = s.copy()
    out.index = idx.where(~mask, idx + pd.Timedelta(minutes=minutes))
    return out.sort_index()


# ---------------------------------------------------------------- stage 1

def matched_se_from_control(control: pd.Series, treat_counts: pd.Series, min_n: int = 2) -> float:
    """SE of the weekday-matched difference (events.stratified_compare's formula) with the
    treated group's within-weekday variance replaced by the control's: B's outcomes are not
    used. treat_counts: B's day count by weekday (0 = Monday)."""
    c = control.dropna()
    wd = pd.Series(c.index.day_of_week, index=c.index)
    used = [w for w in sorted(treat_counts.index)
            if treat_counts[w] >= min_n and (wd == w).sum() >= min_n]
    if not used:
        return float("nan")
    n_t = np.array([treat_counts[w] for w in used], dtype=float)
    weights = n_t / n_t.sum()
    var = np.array([c[wd == w].var(ddof=1) * (1 / treat_counts[w] + 1 / (wd == w).sum()) for w in used])
    return float(np.sqrt(np.dot(weights ** 2, var)))


def stage1(legs_c: dict[str, pd.DataFrame], b_dates: dict[str, pd.DatetimeIndex],
           shares=(1.0, 0.5)) -> pd.DataFrame:
    """Spec 019 *Stage 1*, per window and leg: control-day sd, v = Var(D)/Var(J + D),
    corr(J, D), the matched SE implied by B's weekday counts, the MDE (3.342 SE) and power
    Phi(s x effect / SE - 2.5) against spec 004's matched estimate for each yen share s.
    For D the 'share' is the dollar share. Control days only."""
    rows = []
    for w, lc in legs_c.items():
        counts = pd.Series(b_dates[w].day_of_week).value_counts().sort_index()
        v = float(lc["D"].var(ddof=1) / lc["UJ"].var(ddof=1))
        rho = float(lc["J"].corr(lc["D"]))
        for leg in ("J", "D"):
            se = matched_se_from_control(lc[leg], counts)
            row = {"window": w, "leg": leg, "n_C": int(lc[leg].notna().sum()), "n_B": int(counts.sum()),
                   "sd_C": float(lc[leg].std(ddof=1)), "v_D_over_UJ": v, "corr_JD": rho,
                   "se_matched": se, "mde": MDE_MULT * se}
            for s in shares:
                row[f"power_s{s:g}"] = float(norm.cdf(s * SPEC004_MATCHED_PIPS[w] / se - BAR))
            rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- stage 2

def stage2_tests(legs_b: dict[str, pd.DataFrame], legs_c: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """The four declared tests (P, S1, S2, S3): weekday-matched B vs C, pips. Predictive
    replication probability Phi((t_dir - 2.5)/sqrt(2)), t_dir being t in the predicted
    direction (|t| where none is predicted)."""
    rows = []
    for name, leg, w in TESTS:
        r = stratified_compare(legs_b[w], legs_c[w], col=leg)
        sign = PREDICTED_SIGN_J[w] if leg == "J" else 0
        t_dir = r["t"] * sign if sign else abs(r["t"])
        rows.append({"test": name, "leg": leg, "window": w, "diff_pips": r["diff"], "se": r["se"],
                     "t": r["t"], "passes_bar": abs(r["t"]) >= BAR, "mde": MDE_MULT * r["se"],
                     "pred_replication": float(norm.cdf((t_dir - BAR) / np.sqrt(2))),
                     "n_B": r["n_treat"], "n_C": r["n_control"], "strata_dropped": r["dropped"]})
    return pd.DataFrame(rows).set_index("test")


def readings(tab: pd.DataFrame) -> list[str]:
    """Spec 019 *Kill criteria and readings* 2-6, from the test table (criterion 1 is Step 0).
    More than one can hold (3 and 4 together); 6 only if none of 2-5 does."""
    p, s2 = tab.loc["P"], tab.loc["S2"]
    out = []
    if p["t"] >= BAR:
        out.append("2: named mechanism supported (yen leg, prefix, t >= +2.5)")
    if p["t"] <= -BAR:
        out.append("5: yen strengthens on B mornings (P t <= -2.5), against the mechanism")
    elif p["diff_pips"] <= 0 and p["mde"] <= SPEC004_MATCHED_PIPS["prefix"]:
        out.append("3: named mechanism contradicted (P <= 0 with MDE at or below spec 004's matched estimate)")
    if abs(p["t"]) < BAR and s2["t"] >= BAR:
        out.append("4: dollar-side move (P |t| < 2.5, S2 t >= +2.5), against the mechanism")
    if not out:
        out.append("6: unresolved; specs 001 and 004 unchanged")
    return out


def descriptives(groups: dict[str, dict[str, pd.DataFrame]]) -> pd.DataFrame:
    """Reported, not tested (spec 019 *Stage 2*). groups[window][name] for A, B, C: unmatched
    B vs C; matched A vs C; C Fridays vs C Mon-Thu; per-X legs B vs matched C."""
    rows = []
    for w, g in groups.items():
        for leg in ("J", "D", "UJ"):
            u = compare(g["B"], g["C"], col=leg)
            rows.append({"window": w, "item": "B vs C unmatched", "col": leg, "diff": u["diff"], "t": u["t"]})
            a = stratified_compare(g["A"], g["C"], col=leg)
            rows.append({"window": w, "item": "A vs C matched", "col": leg, "diff": a["diff"], "t": a["t"]})
            c = g["C"]
            fri = c[c.index.day_of_week == 4]
            mon_thu = c[c.index.day_of_week < 4]
            f = compare(fri, mon_thu, col=leg)
            rows.append({"window": w, "item": "C Fri vs C Mon-Thu", "col": leg, "diff": f["diff"], "t": f["t"]})
        for x in X_CCYS:
            for col in (f"{x}JPY_bp", f"neg_{x}USD_bp"):
                r = stratified_compare(g["B"], g["C"], col=col)
                rows.append({"window": w, "item": "B vs C matched, per X (bp)", "col": col,
                             "diff": r["diff"], "t": r["t"]})
    return pd.DataFrame(rows)


def yen_share(tab_uj: dict, tab_j: dict) -> float | None:
    """J / (J + D) difference, only where the r_UJ difference has |t| >= 2 (spec 019)."""
    if abs(tab_uj["t"]) < 2:
        return None
    return float(tab_j["diff"] / tab_uj["diff"])


# ---------------------------------------------------------------- synthetic

CCY_START = {"USD": 1.0, "JPY": 1 / 110.0, "EUR": 1.30, "GBP": 1.50, "AUD": 0.80}


def synthetic_bars(dates, effect_dates=(), prefix_bp: dict | None = None, sigma_bp: float = 1.2,
                   noise_bp: float = 0.0, seed: int = 0) -> dict[str, pd.Series]:
    """Seven-pair bid bars satisfying the triangular identity exactly (plus optional
    independent per-pair noise), at the minutes Step 0 and the windows read: each execution
    bar ts - 1min and ts - 1min +/- 60 and 120 minutes, on each JST date.

    Each currency's log value is a random walk, sigma_bp bp per sqrt(minute). On
    `effect_dates`, prefix_bp[ccy] bp is added to that currency's log value linearly between
    the two bars the prefix window reads (07:59 and 09:54 JST) and held after it: {"JPY": -1} weakens the yen 1 bp (J = +1);
    {"USD": +1} strengthens the dollar (D = +1). Pair price = value(base) / value(quote)."""
    rng = np.random.default_rng(seed)
    prefix_bp = prefix_bp or {}
    d = pd.DatetimeIndex(dates).normalize()
    eff = set(pd.DatetimeIndex(effect_dates).normalize())
    exec_utc = [jst_to_utc(d, t) for t in ("08:00", "09:55", "11:00")]
    offs = [pd.Timedelta(minutes=m) for m in (-121, -61, -1, 59, 119)]
    # the bars the prefix window reads (quote_at: ts - 1min), so the effect is exact as read
    t_in = jst_to_utc(d, "08:00") - pd.Timedelta("1min")
    t_out = jst_to_utc(d, "09:55") - pd.Timedelta("1min")
    stamps, vals = [], {c: [] for c in CCY_START}
    for i, day in enumerate(d):
        st = sorted({e[i] + o for e in exec_utc for o in offs})
        st = pd.DatetimeIndex(st)
        dt_min = np.diff(np.r_[0.0, (st - st[0]).total_seconds() / 60.0])
        frac = np.clip((st - t_in[i]).total_seconds() / (t_out[i] - t_in[i]).total_seconds(), 0, 1)
        for c, v0 in CCY_START.items():
            walk = np.cumsum(rng.normal(0, sigma_bp, len(st)) * np.sqrt(np.maximum(dt_min, 0)))
            lv = np.log(v0) + 1e-4 * walk
            if day in eff and c in prefix_bp:
                lv = lv + 1e-4 * prefix_bp[c] * frac
            vals[c].append(lv)
        stamps.append(st)
    idx = stamps[0].append(stamps[1:])      # tz-aware UTC, as jst_to_utc returns
    lv ={c: np.concatenate(v) for c, v in vals.items()}
    out = {}
    for base, quote in [("USD", "JPY")] + [(x, "JPY") for x in X_CCYS] + [(x, "USD") for x in X_CCYS]:
        logp = lv[base] - lv[quote] + 1e-4 * rng.normal(0, noise_bp, len(idx)) if noise_bp else lv[base] - lv[quote]
        s = pd.Series(np.exp(logp), index=idx).sort_index()
        out[f"{base}{quote}"] = s[~s.index.duplicated()]
    return out


def _synthetic_groups(seed: int, prefix_bp: dict | None = None, noise_bp: float = 0.0,
                      sigma_bp: float = 0.3, years=(2019, 2020)):
    """Synthetic A/B/C legs for the harness: spec 004's partition over `years`, effect on B."""
    import datetime as dt
    from .calendars import turn_of_month_groups
    g = turn_of_month_groups(dt.date(years[0], 1, 1), dt.date(years[-1], 12, 31))
    alld = g["A_month_end"].union(g["B_gotobi_proper"]).union(g["C_control"])
    bars = synthetic_bars(alld, g["B_gotobi_proper"], prefix_bp, sigma_bp=sigma_bp,
                          noise_bp=noise_bp, seed=seed)
    out = {}
    for w in WINDOWS:
        r, b = window_returns({p: bars[p] for p in PAIRS}, alld, w)
        lg = legs(r, b)
        out[w] = {"A": lg.loc[lg.index.intersection(g["A_month_end"])],
                  "B": lg.loc[lg.index.intersection(g["B_gotobi_proper"])],
                  "C": lg.loc[lg.index.intersection(g["C_control"])]}
    return bars, alld, out


def harness_check(null_reps: int = 40) -> list[tuple[str, bool, str]]:
    """Spec 019 *Implementation notes*: the known-answer checks the script must pass before
    it reads real data. Returns (name, ok, detail) per check."""
    res = []
    # 1. yen-leg effect: P finds it, S2 does not
    _, _, g = _synthetic_groups(11, {"JPY": -3.0})
    t = stage2_tests({w: g[w]["B"] for w in WINDOWS}, {w: g[w]["C"] for w in WINDOWS})
    ok = t.loc["P", "t"] >= 4 and abs(t.loc["S2", "t"]) < BAR
    res.append(("1 yen-leg effect -> P, not S2", bool(ok), f"P t {t.loc['P', 't']:+.2f}, S2 t {t.loc['S2', 't']:+.2f}"))
    # 2. dollar-leg effect: S2 finds it, P does not
    _, _, g = _synthetic_groups(12, {"USD": +3.0})
    t = stage2_tests({w: g[w]["B"] for w in WINDOWS}, {w: g[w]["C"] for w in WINDOWS})
    ok = t.loc["S2", "t"] >= 4 and abs(t.loc["P", "t"]) < BAR
    res.append(("2 dollar-leg effect -> S2, not P", bool(ok), f"S2 t {t.loc['S2', 't']:+.2f}, P t {t.loc['P', 't']:+.2f}"))
    # 3. null: rejection rate near nominal (two-sided 1.96 and the 2.5 bar)
    ts = []
    for k in range(null_reps):
        _, _, g = _synthetic_groups(1000 + k)
        ts += list(stage2_tests({w: g[w]["B"] for w in WINDOWS}, {w: g[w]["C"] for w in WINDOWS})["t"])
    ts = np.abs(np.array(ts))
    r196, r25 = float(np.mean(ts >= 1.96)), float(np.mean(ts >= BAR))
    ok = 0.01 <= r196 <= 0.11 and r25 <= 0.05
    res.append(("3 null size", bool(ok), f"{len(ts)} tests: {r196:.1%} at 1.96 (nominal 5%), {r25:.1%} at 2.5 (1.2%)"))
    # 4. Step 0 catches an hour's misalignment inside one 2019 DST-mismatch window, only there
    bars, alld, _ = _synthetic_groups(13, noise_bp=0.2)
    clean = step0(bars, alld)
    win = [us_eu_dst_mismatch_windows([2019])[0]]
    faulty = dict(bars)
    for p in PAIRS:   # label T now holds the true T+60 price: HistData's fault
        faulty[p] = shift_in_windows(bars[p], win, -60)
    bad = step0(faulty, alld)
    fixed = dict(faulty)
    for p in PAIRS:
        fixed[p] = shift_in_windows(faulty[p], win, +60)
    again = step0(fixed, alld)
    ok = clean["passed"] and (not bad["passed"]) and bad["dst_only"] and again["passed"]
    res.append(("4 Step 0 catches a DST-window shift", bool(ok),
                f"clean {clean['passed']}, faulty {bad['passed']} (dst_only {bad['dst_only']}: "
                f"{'; '.join(bad['failures'][:2])}), corrected {again['passed']}"))
    return res
