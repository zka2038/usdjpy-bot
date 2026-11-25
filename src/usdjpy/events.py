"""Event-study harness for fixed-time-window trades.

A "window trade" enters at a clock time and exits at a later clock time on a set of dates.
Times are given in a named timezone (default JST) and converted to UTC, so Tokyo-fix rules
are written exactly as a Japanese trader would say them.

Fills: long = buy at ask, sell at bid; short = sell at bid, buy at ask. Then costs.py on top.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
from scipy import stats

from .config import HOLDOUT_START
from .costs import PIP, CostModel

PERIODS = {"2005-2014": ("2005-01-01", "2014-12-31"), "2015-2021": ("2015-01-01", "2021-12-31"),
           "2022+": ("2022-01-01", "2100-01-01")}


def quote_at(bars: pd.DataFrame, ts: pd.Timestamp, tolerance: str = "5min") -> pd.Series | None:
    """Last 1-min bar at or before ts (bar labelled t covers [t, t+1min), so we use the bar ending by ts)."""
    pos = bars.index.searchsorted(ts - pd.Timedelta("1min"), side="right") - 1
    if pos < 0:
        return None
    row = bars.iloc[pos]
    if ts - bars.index[pos] > pd.Timedelta(tolerance) + pd.Timedelta("1min"):
        return None  # stale: no quote close enough to ts
    return row


def window_trades(bars: pd.DataFrame, dates, entry: str, exit: str, side: int,
                  cost: CostModel = CostModel(), tz: str = "Asia/Tokyo",
                  allow_holdout: bool = False) -> pd.DataFrame:
    """Simulate one window trade per date.

    dates: calendar dates in `tz` (e.g. gotobi days in JST)
    entry/exit: "HH:MM" in `tz`; if exit <= entry the exit is on the next day
    side: +1 long USDJPY, -1 short
    """
    rows = []
    t_in, t_out = dt.time.fromisoformat(entry), dt.time.fromisoformat(exit)
    for d in pd.DatetimeIndex(dates):
        if not allow_holdout and d >= pd.Timestamp(HOLDOUT_START):
            continue
        ts_in = pd.Timestamp.combine(d.date(), t_in).tz_localize(tz).tz_convert("UTC")
        ts_out = pd.Timestamp.combine(d.date(), t_out).tz_localize(tz).tz_convert("UTC")
        if ts_out <= ts_in:
            ts_out += pd.Timedelta(days=1)
        q_in, q_out = quote_at(bars, ts_in), quote_at(bars, ts_out)
        if q_in is None or q_out is None:
            continue
        if side > 0:
            px_in, px_out = q_in["ask"], q_out["bid"]
        else:
            px_in, px_out = q_in["bid"], q_out["ask"]
        mid_in, mid_out = (q_in["bid"] + q_in["ask"]) / 2, (q_out["bid"] + q_out["ask"]) / 2
        gross = side * (px_out - px_in) / PIP
        s_in, s_out = (q_in["ask"] - q_in["bid"]) / PIP, (q_out["ask"] - q_out["bid"]) / PIP
        rows.append({
            "date": d.normalize(), "entry_utc": ts_in, "exit_utc": ts_out,
            "mid_pips": side * (mid_out - mid_in) / PIP,
            "after_spread_pips": gross,
            "net_pips": gross - cost.round_trip_pips(px_in),
            "spread_in_pips": s_in,
            # Columns below were added 2026-11-25 and change none of the above.
            "spread_out_pips": s_out,
            # Spread paid relative to the BID path, which is the observed series for
            # bid-only sources: a long buys bid+s at entry, a short buys bid+s at exit.
            # Scale this, not spread_in_pips, when widening spreads for a short.
            "spread_paid_pips": s_in if side > 0 else s_out,
            "mid_in": mid_in,
            "source": q_in.get("source", None),
        })
    return pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame()


def tradeability_margin(trades: pd.DataFrame, cost: CostModel, spread_mult: float | np.ndarray = 1.0) -> pd.Series:
    """Spec 004 kill criterion 5, per trade: net pips minus the all-in cost under `cost`.

    net_i  = net_pips_i - (k_i - 1) * spread_paid_i     (spread widened by k, bid-anchored)
    bar_i  = cost.round_trip_pips(price_i) + k_i * spread_paid_i
    margin = net_i - bar_i; the criterion passes if its mean is >= 0.

    `net_pips` already carries the base round trip, so this is a cost-doubling test,
    as declared. Priced at each trade's own entry mid, as `net_pips` is.
    """
    k = np.asarray(spread_mult, dtype=float)
    s = trades["spread_paid_pips"].to_numpy()
    net = trades["net_pips"].to_numpy() - (k - 1.0) * s
    bar = np.array([cost.round_trip_pips(p) for p in trades["mid_in"].to_numpy()]) + k * s
    return pd.Series(net - bar, index=trades.index, name="margin_pips")


def stratified_compare(treat: pd.DataFrame, control: pd.DataFrame, col: str = "mid_pips",
                       strata=None, min_n: int = 2) -> dict:
    """Treat-minus-control difference within strata, weighted by the treated group's mix.

    Default strata: weekday of the (JST) date index. Declared in spec 004 *Weekday-
    matched comparison*: d_w = mean_T,w - mean_C,w; D = sum (n_T,w/n_T') d_w;
    SE^2 = sum (n_T,w/n_T')^2 (s2_T,w/n_T,w + s2_C,w/n_C,w). Strata with fewer than
    `min_n` trades in either group are dropped and listed.
    """
    def key(df):
        return pd.Series(df.index.day_of_week if strata is None else strata(df.index), index=df.index)
    a, b = treat[col].dropna(), control[col].dropna()
    ka, kb = key(a), key(b)
    used, dropped, d, var, w = [], [], [], [], []
    for s in sorted(set(ka) | set(kb)):
        xa, xb = a[ka == s], b[kb == s]
        if len(xa) < min_n or len(xb) < min_n:
            dropped.append(s)
            continue
        used.append(s)
        d.append(xa.mean() - xb.mean())
        var.append(xa.var(ddof=1) / len(xa) + xb.var(ddof=1) / len(xb))
        w.append(len(xa))
    w = np.array(w, dtype=float) / np.sum(w)
    diff = float(np.dot(w, d))
    se = float(np.sqrt(np.dot(w ** 2, var)))
    return {"diff": diff, "se": se, "t": diff / se, "strata": used, "dropped": dropped,
            "n_treat": int(sum(len(a[ka == s]) for s in used)),
            "n_control": int(sum(len(b[kb == s]) for s in used))}


def summarize(trades: pd.DataFrame, col: str = "net_pips") -> pd.DataFrame:
    """Mean, t-stat, hit rate and total, overall and per period."""
    def one(x: pd.Series) -> dict:
        x = x.dropna()
        n = len(x)
        sd = x.std(ddof=1) if n > 1 else np.nan
        return {"n": n, "mean": x.mean(), "std": sd, "t": x.mean() / (sd / np.sqrt(n)) if n > 1 and sd > 0 else np.nan,
                "hit_rate": (x > 0).mean(), "total": x.sum()}
    out = {"all": one(trades[col])}
    for name, (a, b) in PERIODS.items():
        sub = trades.loc[(trades.index >= a) & (trades.index <= b), col]
        if len(sub):
            out[name] = one(sub)
    return pd.DataFrame(out).T


def compare(treat: pd.DataFrame, control: pd.DataFrame, col: str = "mid_pips") -> dict:
    """Welch t-test: does the window behave differently on event days than on control days?"""
    a, b = treat[col].dropna(), control[col].dropna()
    t, p = stats.ttest_ind(a, b, equal_var=False)
    return {"treat_mean": a.mean(), "control_mean": b.mean(), "diff": a.mean() - b.mean(), "t": t, "p": p,
            "n_treat": len(a), "n_control": len(b)}
