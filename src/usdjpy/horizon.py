"""Multi-day (1-10 day) trades at a fixed daily decision time, with financing.

Same fill conventions as usdjpy.events (buy at ask, sell at bid, then CostModel on top), plus
carry for the calendar days held. Overlapping trades are allowed; their statistics use
Newey-West standard errors so the overlap doesn't inflate t-stats.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import HOLDOUT_START
from .costs import PIP, CostModel

PERIODS = {"2007-2014": ("2007-01-01", "2014-12-31"), "2015-2021": ("2015-01-01", "2021-12-31"),
           "2022-2024": ("2022-01-01", "2024-12-31")}


def decision_times(start, end, hour_utc: int = 0) -> pd.DatetimeIndex:
    """Every weekday (Mon-Fri, UTC calendar) at hour_utc."""
    days = pd.bdate_range(start, end, tz="UTC")
    return days + pd.Timedelta(hours=hour_utc)


def quotes_at(bars: pd.DataFrame, times: pd.DatetimeIndex, tolerance: str = "5min") -> pd.DataFrame:
    """Bid/ask/mid at each time from the last 1-min bar closing by then (as usdjpy.events.quote_at).

    Times with no bar within `tolerance` get NaN (market closed or data gap).
    """
    idx = bars.index
    pos = idx.searchsorted(times - pd.Timedelta("1min"), side="right") - 1
    ok = pos >= 0
    bar_t = idx[np.clip(pos, 0, None)]  # both indexes are tz-aware UTC
    fresh = ok & ((times - bar_t) <= pd.Timedelta(tolerance) + pd.Timedelta("1min"))
    out = pd.DataFrame(index=times, columns=["bid", "ask"], dtype="float64")
    sel = np.clip(pos, 0, None)[fresh]
    out.loc[fresh, "bid"] = bars["bid"].to_numpy()[sel]
    out.loc[fresh, "ask"] = bars["ask"].to_numpy()[sel]
    out["mid"] = (out["bid"] + out["ask"]) / 2
    return out


def simulate(quotes: pd.DataFrame, side: pd.Series, hold: int, cost: CostModel,
             usd_rate: pd.Series, jpy_rate: pd.Series, overlap: bool = True,
             allow_holdout: bool = False) -> pd.DataFrame:
    """One trade per decision time where side is +1/-1, exiting `hold` tradeable decision times later.

    quotes: output of quotes_at; rows with NaN mid are not tradeable and are skipped when counting.
    side: +1 long USDJPY, -1 short, 0/NaN no trade (indexed like quotes).
    usd_rate, jpy_rate: % rates known at each decision time (for financing).
    overlap=False: no new trade until the open one has exited.
    """
    q = quotes.dropna(subset=["mid"])
    times = q.index
    sides = side.reindex(times).fillna(0).to_numpy()
    usd, jpy = usd_rate.reindex(times).to_numpy(), jpy_rate.reindex(times).to_numpy()
    bid, ask, mid = q["bid"].to_numpy(), q["ask"].to_numpy(), q["mid"].to_numpy()
    rows, busy_until = [], -1
    for i in range(len(times) - hold):
        s = int(sides[i])
        if s == 0 or (not overlap and i < busy_until):
            continue
        j = i + hold
        if not allow_holdout and times[j] >= pd.Timestamp(HOLDOUT_START, tz="UTC"):
            break
        if np.isnan(usd[i]) or np.isnan(jpy[i]):
            continue
        px_in, px_out = (ask[i], bid[j]) if s > 0 else (bid[i], ask[j])
        days = (times[j] - times[i]).total_seconds() / 86400
        gross = s * (px_out - px_in) / PIP
        fin = cost.financing_pips(s, mid[i], usd[i], jpy[i], days)
        rows.append({"entry_utc": times[i], "exit_utc": times[j], "side": s, "days_held": days,
                     "mid_pips": s * (mid[j] - mid[i]) / PIP, "after_spread_pips": gross,
                     "financing_pips": fin, "net_pips": gross - cost.round_trip_pips(px_in) + fin})
        busy_until = j
    return pd.DataFrame(rows)


def mean_moves(quotes: pd.DataFrame, hold: int, allow_holdout: bool = False) -> float:
    """Average `hold`-day mid move in pips over all tradeable decision times (the drift to beat)."""
    q = quotes.dropna(subset=["mid"])
    move = (q["mid"].shift(-hold) - q["mid"]) / PIP
    exit_t = pd.Series(q.index, index=q.index).shift(-hold)
    keep = exit_t.notna() & (allow_holdout | (exit_t < pd.Timestamp(HOLDOUT_START, tz="UTC")))
    return float(move[keep].mean())


def newey_west_t(x, lag: int) -> float:
    """t-stat of the mean of x (in time order) with a Bartlett-kernel Newey-West standard error."""
    x = np.asarray(pd.Series(x).dropna(), dtype="float64")
    n = len(x)
    if n < 3:
        return float("nan")
    e = x - x.mean()
    var = e @ e / n
    for k in range(1, min(lag, n - 1) + 1):
        var += 2 * (1 - k / (lag + 1)) * (e[k:] @ e[:-k]) / n
    return float(x.mean() / np.sqrt(var / n)) if var > 0 else float("nan")


def newey_west_slope(y, x, lag: int) -> tuple[float, float]:
    """OLS slope of y on x (with intercept) and its Newey-West t-stat."""
    d = pd.DataFrame({"y": y, "x": x}).dropna()
    X = np.column_stack([np.ones(len(d)), d["x"].to_numpy()])
    yv = d["y"].to_numpy()
    XtX_inv = np.linalg.inv(X.T @ X)
    b = XtX_inv @ X.T @ yv
    u = yv - X @ b
    g = X * u[:, None]
    S = g.T @ g
    for k in range(1, lag + 1):
        G = g[k:].T @ g[:-k]
        S += (1 - k / (lag + 1)) * (G + G.T)
    V = XtX_inv @ S @ XtX_inv
    return float(b[1]), float(b[1] / np.sqrt(V[1, 1]))


def summarize(trades: pd.DataFrame, lag: int, col: str = "net_pips") -> pd.DataFrame:
    """n, mean, Newey-West t, hit rate and total, overall and per period."""
    def one(x: pd.Series) -> dict:
        return {"n": len(x), "mean": x.mean(), "nw_t": newey_west_t(x, lag), "hit_rate": (x > 0).mean(),
                "total": x.sum()}
    if trades.empty:
        return pd.DataFrame()
    t = trades.set_index("entry_utc")
    out = {"all": one(t[col])}
    for name, (a, b) in PERIODS.items():
        sub = t.loc[a:b, col]
        if len(sub):
            out[name] = one(sub)
    return pd.DataFrame(out).T
