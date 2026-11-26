"""Event-study harness for fixed-time-window trades.

A "window trade" enters at a clock time and exits at a later clock time on a set of dates.
Times are given in a named timezone (default JST) and converted to UTC, so Tokyo-fix rules
are written exactly as a Japanese trader would say them. `timestamp_trades` takes explicit
UTC entry and exit times instead (build them with `at_local`), for multi-day and
ET-anchored holds.

Fills: long = buy at ask, sell at bid; short = sell at bid, buy at ask. Then costs.py on top,
and financing for every 17:00 New York roll the position is held through.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
from scipy import stats

from .config import HOLDOUT_START
from .costs import PIP, CostModel, roll_times
from .rates import asof

PERIODS = {"2005-2014": ("2005-01-01", "2014-12-31"), "2015-2021": ("2015-01-01", "2021-12-31"),
           "2022+": ("2022-01-01", "2100-01-01")}
# The 2015-19 / 2020-24 halves that specs 006-018 split on. Beside PERIODS, not
# replacing it: spec 004's tables are on PERIODS.
PERIODS_2015_2024 = {"2015-2019": ("2015-01-01", "2019-12-31"), "2020-2024": ("2020-01-01", "2024-12-31")}


def quote_at(bars: pd.DataFrame, ts: pd.Timestamp, tolerance: str = "5min") -> pd.Series | None:
    """Last 1-min bar at or before ts (bar labelled t covers [t, t+1min), so we use the bar ending by ts)."""
    pos = bars.index.searchsorted(ts - pd.Timedelta("1min"), side="right") - 1
    if pos < 0:
        return None
    row = bars.iloc[pos]
    if ts - bars.index[pos] > pd.Timedelta(tolerance) + pd.Timedelta("1min"):
        return None  # stale: no quote close enough to ts
    return row


HOLDOUT_UTC = pd.Timestamp(HOLDOUT_START, tz="UTC")


def at_local(dates, hhmm: str, tz: str, offset=None) -> pd.DatetimeIndex:
    """UTC instants of clock time `hhmm` in `tz` on each of `dates` (calendar dates in
    `tz`), each date first moved by `offset` if one is given: a pandas DateOffset or
    Timedelta such as `pd.offsets.BDay(3)` (T+3 weekdays; use CustomBusinessDay for a
    holiday calendar), `pd.offsets.Week(weekday=3)` (the next Thursday) or
    `pd.Timedelta(days=28)`. Built on local dates, so 16:50 ET stays 16:50 ET across
    DST. A clock time that does not exist, or repeats, in `tz` raises."""
    d = pd.DatetimeIndex(dates)
    if d.tz is not None:
        d = d.tz_localize(None)
    d = d.normalize()
    if offset is not None:
        d = pd.DatetimeIndex([x + offset for x in d]).normalize()
    t = dt.time.fromisoformat(hhmm)
    local = d + pd.Timedelta(hours=t.hour, minutes=t.minute)
    return local.tz_localize(tz, ambiguous="raise", nonexistent="raise").tz_convert("UTC")


def _trade_row(bars: pd.DataFrame, d: pd.Timestamp, ts_in: pd.Timestamp, ts_out: pd.Timestamp,
               side: int, cost: CostModel, rates) -> dict | None:
    """One trade's fills, P&L and spread columns, or None if either leg has no quote.
    Shared by window_trades and timestamp_trades, so fills are defined once."""
    q_in, q_out = quote_at(bars, ts_in), quote_at(bars, ts_out)
    if q_in is None or q_out is None:
        return None
    if side > 0:
        px_in, px_out = q_in["ask"], q_out["bid"]
    else:
        px_in, px_out = q_in["bid"], q_out["ask"]
    mid_in, mid_out = (q_in["bid"] + q_in["ask"]) / 2, (q_out["bid"] + q_out["ask"]) / 2
    gross = side * (px_out - px_in) / PIP
    s_in, s_out = (q_in["ask"] - q_in["bid"]) / PIP, (q_out["ask"] - q_out["bid"]) / PIP
    rolls = roll_times(ts_in, ts_out)
    fin = _financing_pips(side, mid_in, rolls, rates, cost, ts_in)
    return {
        "date": d.normalize(), "entry_utc": ts_in, "exit_utc": ts_out,
        "mid_pips": side * (mid_out - mid_in) / PIP,
        "after_spread_pips": gross,
        "net_pips": gross - cost.round_trip_pips(px_in) + fin,
        "spread_in_pips": s_in,
        # Columns below were added 2026-11-25 and change none of the above.
        "spread_out_pips": s_out,
        # Spread paid relative to the BID path, which is the observed series for
        # bid-only sources: a long buys bid+s at entry, a short buys bid+s at exit.
        # Scale this, not spread_in_pips, when widening spreads for a short.
        "spread_paid_pips": s_in if side > 0 else s_out,
        "mid_in": mid_in,
        "source": q_in.get("source", None),
        # Added 2026-11-26 (Task 5). 0 / 0.0 / NaN for every window that holds no
        # night on bars without bid high/low, which is every trade specs 001-004 make.
        "nights": len(rolls),
        "financing_pips": fin,
        "mae_pips": _mae_pips(bars, ts_in, ts_out, side, q_in["bid"]),
    }


def _financing_pips(side: int, price: float, rolls: pd.DatetimeIndex, rates, cost: CostModel,
                    ts_in: pd.Timestamp) -> float:
    """Carry net of the broker skim over the 17:00 New York rolls held, each night at the
    rates published before that roll (`rates.asof`), priced at the entry mid. Raises
    rather than charge nothing."""
    if len(rolls) == 0:
        return 0.0
    if rates is None:
        raise ValueError(
            f"the trade entered {ts_in} is held through {len(rolls)} 17:00 New York roll(s) but "
            "no rates were given. Overnight spot pays the financing skim (CLAUDE.md); pass "
            "rates=(usd_frame, jpy_frame) in the usdjpy.rates format.")
    usd = asof(rates[0], rolls)["value"].to_numpy(dtype=float)
    jpy = asof(rates[1], rolls)["value"].to_numpy(dtype=float)
    if np.isnan(usd).any() or np.isnan(jpy).any():
        raise ValueError(f"no rate published before a roll of the trade entered {ts_in}")
    return float(np.sum(cost.financing_pips(side, price, usd, jpy, 1.0)))


def _mae_pips(bars: pd.DataFrame, ts_in: pd.Timestamp, ts_out: pd.Timestamp, side: int,
              bid_in: float) -> float:
    """Worst bid excursion against the position while it is held, in pips from the entry
    bid (negative = adverse), over the bars labelled ts_in .. ts_out - 1min: the entry
    fills on the close of bar ts_in - 1min and the exit on the close of bar ts_out - 1min.
    Needs bars from `load_minute(..., ohlc=True)`; NaN otherwise. Bid-anchored, like
    spread_paid_pips: a short's adverse fill is at the ask, one spread worse."""
    if "bid_low" not in bars.columns or "bid_high" not in bars.columns:
        return float("nan")
    i = bars.index.searchsorted(ts_in)
    j = bars.index.searchsorted(ts_out - pd.Timedelta("1min"), side="right")
    if j <= i:
        return float("nan")
    worst = bars["bid_low"].iloc[i:j].min() if side > 0 else bars["bid_high"].iloc[i:j].max()
    return float(side * (worst - bid_in) / PIP)


def window_trades(bars: pd.DataFrame, dates, entry: str, exit: str, side: int,
                  cost: CostModel = CostModel(), tz: str = "Asia/Tokyo",
                  allow_holdout: bool = False, rates=None) -> pd.DataFrame:
    """Simulate one window trade per date.

    dates: calendar dates in `tz` (e.g. gotobi days in JST)
    entry/exit: "HH:MM" in `tz`; if exit <= entry the exit is on the next day
    side: +1 long USDJPY, -1 short
    rates: (usd, jpy) frames in the `usdjpy.rates` format. Required only if a window is
        held through a 17:00 New York roll, which then pays financing in net_pips.

    Without allow_holdout, a date on or after HOLDOUT_START is skipped, and so is a
    trade whose exit falls on or after HOLDOUT_START 00:00 UTC. Before 2026-11-26 only
    the date was checked, so a window rolling past New Year 2025 read holdout bars.
    For multi-day or differently anchored holds use timestamp_trades.
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
        if not allow_holdout and ts_out >= HOLDOUT_UTC:
            continue
        row = _trade_row(bars, d, ts_in, ts_out, side, cost, rates)
        if row is not None:
            rows.append(row)
    return pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame()


def timestamp_trades(bars: pd.DataFrame, entries, exits, side, cost: CostModel = CostModel(),
                     dates=None, rates=None, allow_holdout: bool = False) -> pd.DataFrame:
    """One trade per (entry, exit) pair of UTC timestamps, for holds window_trades cannot
    express: multi-day, ET-anchored, or exiting on a later weekday. Build the timestamps
    with `at_local`. Same fills, quote tolerance and columns as window_trades, plus `side`.

    side: +1 / -1, or one per trade.
    dates: index labels (e.g. the signal date); default the entry's UTC date.
    rates: (usd, jpy) frames in the `usdjpy.rates` format, required as soon as any trade
        is held through a 17:00 New York roll. Financing is charged per roll at the rates
        published before it, at the entry mid, and is included in net_pips.
    Without allow_holdout, a trade labelled, entering or exiting on or after
    HOLDOUT_START (00:00 UTC for the timestamps) is skipped.
    """
    ent = pd.DatetimeIndex(entries).tz_convert("UTC")
    ext = pd.DatetimeIndex(exits).tz_convert("UTC")
    if len(ent) != len(ext):
        raise ValueError("entries and exits differ in length")
    if (ext <= ent).any():
        raise ValueError("every exit must be after its entry")
    sides = np.broadcast_to(np.asarray(side), (len(ent),))
    if not np.isin(sides, (1, -1)).all():
        raise ValueError("side must be +1 or -1")
    labels = ent.tz_localize(None).normalize() if dates is None else pd.DatetimeIndex(dates)
    if labels.tz is not None:
        labels = labels.tz_localize(None)
    if len(labels) != len(ent):
        raise ValueError("dates and entries differ in length")
    rows = []
    for d, a, b, s in zip(labels, ent, ext, sides):
        if not allow_holdout and (d >= pd.Timestamp(HOLDOUT_START) or a >= HOLDOUT_UTC or b >= HOLDOUT_UTC):
            continue
        row = _trade_row(bars, d, a, b, int(s), cost, rates)
        if row is not None:
            row["side"] = int(s)
            rows.append(row)
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


def summarize(trades: pd.DataFrame, col: str = "net_pips", periods: dict | None = None) -> pd.DataFrame:
    """Mean, t-stat, hit rate and total, overall and per period: `periods` (default
    PERIODS; PERIODS_2015_2024 for the 2015-19 / 2020-24 split), as inclusive calendar
    dates compared with the trades' date index."""
    def one(x: pd.Series) -> dict:
        x = x.dropna()
        n = len(x)
        sd = x.std(ddof=1) if n > 1 else np.nan
        return {"n": n, "mean": x.mean(), "std": sd, "t": x.mean() / (sd / np.sqrt(n)) if n > 1 and sd > 0 else np.nan,
                "hit_rate": (x > 0).mean(), "total": x.sum()}
    out = {"all": one(trades[col])}
    for name, (a, b) in (PERIODS if periods is None else periods).items():
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
