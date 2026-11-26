"""Spec 004 gap fill: the Dukascopy tick tree, step 0, filled trades, measured spreads.

Implements spec 004's *Gap fill* section and its dated amendments (2026-11-25: the
DST amendment, *Weekday-matched comparison*, *Amendment: field standards*). Written
before any filled data was viewed; scripts/004_gap_fill_analysis.py runs it only
once the fetch is complete. Nothing here reads data/tokyo_hours/ unless called with
that root.

- load_tree: 1-min bars from a tick tree (no cache; dukascopy.load_minute_bars
  writes one whose staleness check is by mtime).
- step0_table / step0_verdict: source agreement at the execution bars.
- fill_group: as-run trades unchanged; a dropped day is filled with BOTH legs from
  the tree, only on stage 1 and stage 3 dates (stage 2 is a spread source, never a
  price source). Filled trades use the tree bid + the synthetic profile, so the as
  run and era columns keep one cost assumption across all trades.
- measured_spreads: the spread each trade pays (entry bar for a long, exit bar for
  a short), by the declared hierarchy: a trade priced from real bid/ask (Eightcap)
  keeps its own; otherwise its own Dukascopy quote; else, 2015 to 2024-06, the
  stage 2 yearly MEAN at its paying bar; else imputed from its (fill bar x year)
  cell mean and flagged.
"""
from __future__ import annotations

import datetime as dt
import pathlib

import numpy as np
import pandas as pd

from .config import HOLDOUT_START, SYMBOL
from .costs import PIP, CostModel
from .datasets import _with_synthetic_ask
from .dukascopy import ticks_to_minute_bars
from .events import window_trades

# Spec 004's rules, inherited unchanged from spec 001: (entry JST, exit JST, side).
RULES = {"prefix_long": ("08:00", "09:55", +1), "postfix_short": ("09:55", "11:00", -1)}
EXEC_BARS = ("22:59", "00:54", "01:59")     # bars quote_at reads for 23:00, 00:55, 02:00 UTC
STEP0_MEDIAN_MAX_PIPS = 0.3                 # declared gate, 2007-2014 part
STEP0_GATE_OFFSETS = (-60, 0, 60)           # declared gate: mean |diff| smallest at 0
STEP0_OFFSETS = (-60, -2, -1, 0, 1, 2, 60)  # +/-1, 2 reported only (field-standards amendment)
ONE_SPREAD_PIPS = 0.36                      # entry-hour synthetic spread: scale for distributions
HISTDATA_ERA = ("2015-01-01", "2024-06-18")
TREE_SOURCE = "dukascopy_tree"


def load_tree(root: str | pathlib.Path, sym: str = SYMBOL, days: set[dt.date] | None = None) -> pd.DataFrame:
    """1-min bars from root/SYM/YYYY/YYYY-MM-DD.parquet tick files: bid, ask (last
    quote in the minute), spread_last (ask - bid of that quote, price units),
    spread_mean (minute mean), n_ticks. Empty day files (all hours 404) are skipped."""
    files = sorted(f for f in (pathlib.Path(root) / sym).glob("*/*.parquet") if not f.name.startswith("."))
    if days is not None:
        files = [f for f in files if dt.date.fromisoformat(f.stem) in days]
    parts = []
    for f in files:
        ticks = pd.read_parquet(f)
        if len(ticks):
            parts.append(ticks_to_minute_bars(ticks))
    if not parts:
        return pd.DataFrame(columns=["bid", "ask", "spread_last", "spread_mean", "n_ticks"])
    bars = pd.concat(parts).sort_index()
    bars = bars[~bars.index.duplicated(keep="last")].rename(columns={"spread": "spread_mean"})
    bars["spread_last"] = bars["ask"] - bars["bid"]
    return bars


def real_bars(tree: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"bid": tree["bid"], "ask": tree["ask"], "spread": tree["spread_last"],
                         "source": TREE_SOURCE}, index=tree.index)


def synthetic_bars(tree: pd.DataFrame, profile: pd.Series | None = None) -> pd.DataFrame:
    """Tree bid + the synthetic spread profile: the as-run cost assumption."""
    return _with_synthetic_ask(tree["bid"], TREE_SOURCE, profile=profile)


def quotes_at(bars: pd.DataFrame, ts, tolerance: str = "5min") -> pd.DataFrame:
    """Vectorised events.quote_at: for each ts, the last bar at or before ts - 1min,
    NaN where none is within `tolerance` + 1min."""
    ts = pd.DatetimeIndex(ts)
    idx = bars.index
    pos = idx.searchsorted(ts - pd.Timedelta("1min"), side="right") - 1
    ok = pos >= 0
    vals = np.full((len(ts), 2), np.nan)
    if ok.any():
        found = idx[pos[ok]]
        fresh = np.asarray((ts[ok] - found) <= pd.Timedelta(tolerance) + pd.Timedelta("1min"))
        rows = bars.iloc[pos[ok]][["bid", "ask"]].to_numpy(dtype=float)
        vals[ok] = np.where(fresh[:, None], rows, np.nan)
    return pd.DataFrame(vals, index=ts, columns=["bid", "ask"])


def jst_to_utc(days, hhmm: str) -> pd.DatetimeIndex:
    """UTC timestamps of a JST clock time on each JST date."""
    days = pd.DatetimeIndex(days).normalize()
    return (days + pd.Timedelta(hhmm + ":00")).tz_localize("Asia/Tokyo").tz_convert("UTC")


# ---------------------------------------------------------------- step 0

def step0_table(tree_bid: pd.Series, ref_bid: pd.Series, times=EXEC_BARS, offsets=STEP0_OFFSETS,
                one_spread: float = ONE_SPREAD_PIPS) -> pd.DataFrame:
    """|tree bid at T - reference bid at T + offset| in pips, at the execution bars,
    on every bar both quote (exact minutes). One row per offset."""
    hhmm = tree_bid.index.strftime("%H:%M")
    T = tree_bid.index[np.isin(hhmm, list(times))]
    rows = []
    for off in offsets:
        ref = ref_bid.reindex(T + pd.Timedelta(minutes=off)).to_numpy()
        d = np.abs(tree_bid.reindex(T).to_numpy() - ref) / PIP
        d = d[~np.isnan(d)]
        rows.append({"offset_min": off, "n": len(d),
                     "median": np.median(d) if len(d) else np.nan, "mean": d.mean() if len(d) else np.nan,
                     "p90": np.percentile(d, 90) if len(d) else np.nan, "p99": np.percentile(d, 99) if len(d) else np.nan,
                     "share_gt_one_spread": (d > one_spread).mean() if len(d) else np.nan})
    return pd.DataFrame(rows).set_index("offset_min")


def step0_verdict(table: pd.DataFrame) -> tuple[bool, list[str]]:
    """The declared 2007-2014 gate: median |diff| at offset 0 <= 0.3 pips AND the mean
    |diff| smallest at 0 among -60/0/+60."""
    reasons = []
    med0 = table.loc[0, "median"]
    if not (med0 <= STEP0_MEDIAN_MAX_PIPS):
        reasons.append(f"median |diff| at offset 0 is {med0:.3f} pips > {STEP0_MEDIAN_MAX_PIPS}")
    means = table.loc[list(STEP0_GATE_OFFSETS), "mean"]
    if means.idxmin() != 0:
        reasons.append(f"mean |diff| is smallest at offset {means.idxmin()}, not 0 ({means.round(3).to_dict()})")
    if table.loc[0, "n"] == 0:
        reasons.append("no common bars at offset 0")
    return (not reasons), reasons


def cleaning_counts(tree: pd.DataFrame, times=EXEC_BARS) -> dict:
    """Bars a BNHLS-style pass would flag (reported only): last-quote spread above 50x
    the day's median, or mid more than 10 MADs from a centred 51-bar rolling median."""
    day = tree.index.date
    med_spread = tree["spread_last"].groupby(day).transform("median")
    wide = tree["spread_last"] > 50 * med_spread
    mid = (tree["bid"] + tree["ask"]) / 2
    rm = mid.rolling(51, center=True, min_periods=11).median()
    dev = (mid - rm).abs()
    mad = dev.rolling(51, center=True, min_periods=11).median()
    outlier = (mad > 0) & (dev > 10 * mad)
    at = np.isin(tree.index.strftime("%H:%M"), list(times))
    return {"bars": len(tree), "wide_spread": int(wide.sum()), "mid_outlier": int(outlier.sum()),
            "wide_spread_at_exec": int((wide & at).sum()), "mid_outlier_at_exec": int((outlier & at).sum())}


# ---------------------------------------------------------------- fills

def bar_dates(day: pd.Timestamp, entry: str, exit: str, tz: str = "Asia/Tokyo") -> set[dt.date]:
    """UTC dates of every bar a trade on JST `day` can read (quote_at looks back up to
    6 minutes before each timestamp)."""
    ts_in = jst_to_utc([day], entry)[0]
    ts_out = jst_to_utc([day], exit)[0]
    if ts_out <= ts_in:
        ts_out += pd.Timedelta(days=1)
    return {(t - pd.Timedelta(minutes=m)).date() for t in (ts_in, ts_out) for m in (1, 6)}


def fill_group(asrun: pd.DataFrame, days: pd.DatetimeIndex, tree_synth: pd.DataFrame,
               windows: list[tuple[dt.date, dt.date]], entry: str, exit: str, side: int,
               cost: CostModel = CostModel()) -> pd.DataFrame:
    """As-run trades unchanged (filled=False), plus a tree trade for each pre-holdout
    day the as-run dropped whose bars all fall inside a fill window (filled=True).
    Both legs of a filled trade come from the tree."""
    days = pd.DatetimeIndex(days)
    days = days[days < pd.Timestamp(HOLDOUT_START)]
    have = set(asrun.index) if len(asrun) else set()
    dropped = [d for d in days if d not in have]
    eligible = [d for d in dropped
                if all(any(a <= x <= b for a, b in windows) for x in bar_dates(d, entry, exit))]
    a = asrun.copy()
    a["filled"] = False
    f = window_trades(tree_synth, eligible, entry, exit, side, cost) if eligible else pd.DataFrame()
    if f.empty:
        return a
    f["filled"] = True
    return pd.concat([a, f]).sort_index()


# ---------------------------------------------------------------- measured spreads

def paying_clock(leg: str) -> str:
    entry, exit, side = RULES[leg]
    return entry if side > 0 else exit


def spreads_on_days(tree_real: pd.DataFrame, jst_days, leg: str, tolerance: str = "5min") -> pd.Series:
    """Last-quote spread (pips) at the leg's paying bar on each JST day, NaN if none."""
    jst_days = pd.DatetimeIndex(jst_days)
    q = quotes_at(tree_real, jst_to_utc(jst_days, paying_clock(leg)), tolerance)
    return pd.Series(((q["ask"] - q["bid"]) / PIP).to_numpy(), index=jst_days)


def yearly(spreads: pd.Series) -> pd.DataFrame:
    s = spreads.dropna()
    return s.groupby(s.index.year).agg(["mean", "median", "count"])


def measured_spreads(trades: pd.DataFrame, leg: str, tree_real: pd.DataFrame, stage2_days,
                     cell_days, tolerance: str = "5min") -> pd.DataFrame:
    """s_meas (pips) and s_source per trade, by the declared hierarchy:
    eightcap (priced from real bid/ask: keeps its own spread) > own Dukascopy quote >
    stage 2 yearly mean (2015 to 2024-06) > imputed (fill bar x year cell mean) > none."""
    pay_col = "entry_utc" if RULES[leg][2] > 0 else "exit_utc"
    out = pd.DataFrame({"s_meas": np.nan, "s_source": "none"}, index=trades.index)
    ec = (trades["source"] == "eightcap").to_numpy()
    out.loc[ec, "s_meas"] = trades.loc[ec, "spread_paid_pips"]
    out.loc[ec, "s_source"] = "eightcap"

    q = quotes_at(tree_real, pd.DatetimeIndex(trades[pay_col]).tz_convert("UTC"), tolerance)
    own = ((q["ask"] - q["bid"]) / PIP).to_numpy()
    m = ~ec & ~np.isnan(own)
    out.loc[m, "s_meas"] = own[m]
    out.loc[m, "s_source"] = "own"

    s2 = yearly(spreads_on_days(tree_real, stage2_days, leg, tolerance))["mean"]
    yr = trades.index.year
    in_era = (trades.index >= pd.Timestamp(HISTDATA_ERA[0])) & (trades.index <= pd.Timestamp(HISTDATA_ERA[1]))
    m = (out["s_source"] == "none").to_numpy() & in_era & np.isin(yr, s2.index)
    out.loc[m, "s_meas"] = s2.reindex(yr[m]).to_numpy()
    out.loc[m, "s_source"] = "stage2_mean"

    cell = yearly(spreads_on_days(tree_real, cell_days, leg, tolerance))["mean"]
    m = (out["s_source"] == "none").to_numpy() & np.isin(yr, cell.index)
    out.loc[m, "s_meas"] = cell.reindex(yr[m]).to_numpy()
    out.loc[m, "s_source"] = "imputed"
    return out
