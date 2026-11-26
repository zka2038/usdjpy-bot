"""Position simulator for rebalanced strategies: specs 014, 016 and 017.

A strategy here is a signed USD notional target (+ long USDJPY) set at UTC rebalance
times: weekly for 014/016 (Mon 08:00 JST = Sun 23:00 UTC), daily or finer once spec 017's
overlays scale it. The position is carried between rebalances, marked at mid, financed
on every 17:00 New York roll it is held through (`costs.roll_times`), and charged costs
only when it trades. Not an event study: `events.window_trades` does not apply.

Accounting at rebalance k, for the position p held over (t_{k-1}, t_k]:
  price P&L  = p * (mid_k - mid_{k-1}) / mid_k                          USD
  financing  = |p| * per-night carry net of the skim, at the rates published
               before each roll in [t_{k-1}, t_k) (`rates.asof`)          USD
  trade cost = |dp| * (half spread + slippage) / mid_k + commission(|dp|)  USD
A round trip at a flat price therefore costs exactly what `events.window_trades`
charges a 1-trade window: (spread + CostModel.round_trip_pips) pips on the notional.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import HOLDOUT_START
from .costs import PIP, CostModel, roll_times
from .rates import asof

HOLDOUT_UTC = pd.Timestamp(HOLDOUT_START, tz="UTC")


def quotes_from_mid(mid: pd.Series, spread_pips: float) -> pd.DataFrame:
    """Bid/ask around a mid-only price (e.g. the H.10 noon rate) with an assumed spread.
    State the spread: it is an assumption, not a measurement."""
    half = spread_pips * PIP / 2
    m = mid.astype("float64")
    return pd.DataFrame({"bid": m - half, "ask": m + half}, index=mid.index)


def on_schedule(target: pd.Series, times) -> pd.Series:
    """Carry targets set at their own times onto a schedule: each time takes the newest
    target set at or before it (NaN before the first). Use it to put a weekly signal on
    the daily grid that spec 017's overlays scale."""
    t = pd.DatetimeIndex(times)
    s = target.sort_index()
    pos = s.index.searchsorted(t, side="right") - 1
    vals = np.where(pos >= 0, s.to_numpy(dtype=float)[np.clip(pos, 0, None)], np.nan)
    return pd.Series(vals, index=t, name=target.name)


def apply_multiplier(target: pd.Series, mult: pd.Series, sides: str = "long") -> pd.Series:
    """target * mult on long targets ('long', spec 017's O1-O4), short ones ('short') or
    all ('both'). `mult` must cover every target time: a missing multiplier raises
    rather than defaulting to 1."""
    m = mult.reindex(target.index)
    if m.isna().any():
        raise ValueError(f"no multiplier for {int(m.isna().sum())} target times")
    pick = {"long": target > 0, "short": target < 0, "both": pd.Series(True, index=target.index)}[sides]
    return target.where(~pick, target * m)


def simulate(quotes: pd.DataFrame, target_usd: pd.Series, cost: CostModel = CostModel(),
             rates=None, min_trade_usd: float = 100_000, capital_usd: float | None = None,
             allow_holdout: bool = False) -> pd.DataFrame:
    """Carry a position between rebalances and account for it in USD.

    quotes: bid/ask at each UTC rebalance time (`horizon.quotes_at` on 1-min bars, or
        `quotes_from_mid`). Times without a quote are skipped: no trade, and the position
        is marked from the last quoted time to the next.
    target_usd: signed USD notional wanted at each time (NaN = no instruction, hold).
    rates: (usd, jpy) frames in the `usdjpy.rates` format; required once a non-zero
        position is held through a 17:00 New York roll.
    min_trade_usd: trade only if |target - position| >= this or the sign changes (spec 014;
        0 counts as a sign, so going flat or opening from flat always trades).
    capital_usd: if given, adds `ret` = net_usd / capital_usd.
    Without allow_holdout, times on or after HOLDOUT_START 00:00 UTC are dropped. The last
    position is left open, marked at the last time kept; `attrs["open_position_usd"]`.
    """
    q = quotes[["bid", "ask"]].astype("float64").sort_index()
    if q.index.has_duplicates:
        raise ValueError("duplicate rebalance times")
    if not allow_holdout:
        q = q[q.index < HOLDOUT_UTC]
    n_all = len(q)
    q = q[q.notna().all(axis=1)]
    skipped = n_all - len(q)
    tgt = target_usd.reindex(q.index).to_numpy(dtype=float)
    bid, ask = q["bid"].to_numpy(), q["ask"].to_numpy()
    mid = (bid + ask) / 2
    rows, pos = [], 0.0
    for k, t in enumerate(q.index):
        price_pnl = fin = 0.0
        nights = 0
        if k > 0:
            price_pnl = pos * (mid[k] - mid[k - 1]) / mid[k]
            if pos != 0:
                rolls = roll_times(q.index[k - 1], t)
                nights = len(rolls)
                fin = _financing_usd(pos, mid[k - 1], rolls, rates, cost, t)
        want = tgt[k]
        dp = 0.0 if np.isnan(want) else want - pos
        if dp != 0 and not (abs(dp) >= min_trade_usd or np.sign(want) != np.sign(pos)):
            dp = 0.0
        tc = 0.0
        if dp != 0:
            tc = abs(dp) * ((ask[k] - bid[k]) / 2 + cost.slippage_pips * PIP) / mid[k] + cost.commission_usd(dp)
        rows.append({"time": t, "target_usd": want, "position_before": pos, "trade_usd": dp,
                     "position_after": pos + dp, "mid": mid[k], "price_pnl_usd": price_pnl,
                     "nights": nights, "financing_usd": fin, "cost_usd": tc,
                     "net_usd": price_pnl + fin - tc})
        pos += dp
    out = pd.DataFrame(rows).set_index("time") if rows else pd.DataFrame()
    if capital_usd is not None and len(out):
        out["ret"] = out["net_usd"] / capital_usd
    out.attrs.update(skipped_no_quote=skipped, open_position_usd=pos)
    return out


def _financing_usd(pos: float, price: float, rolls: pd.DatetimeIndex, rates, cost: CostModel,
                   t: pd.Timestamp) -> float:
    if len(rolls) == 0:
        return 0.0
    if rates is None:
        raise ValueError(f"a position of {pos:,.0f} USD is held through {len(rolls)} 17:00 New York "
                         f"roll(s) before {t} but no rates were given (CLAUDE.md: cost financing).")
    usd = asof(rates[0], rolls)["value"].to_numpy(dtype=float)
    jpy = asof(rates[1], rolls)["value"].to_numpy(dtype=float)
    if np.isnan(usd).any() or np.isnan(jpy).any():
        raise ValueError(f"no rate published before a roll ending {t}")
    pips = np.sum(cost.financing_pips(int(np.sign(pos)), price, usd, jpy, 1.0))
    return float(abs(pos) * pips * PIP / price)


def summary(returns: pd.Series, periods_per_year: float = 52) -> dict:
    """The statistics specs 014/016/017 decide on, from per-period returns (or USD).

    Returns are summed, not compounded: the simulator trades a fixed capital, so equity
    is the running sum. Max drawdown is the largest fall of that sum from its running
    peak, counting the start (0) as a peak. CVaR(5%) is the mean of the worst
    ceil(5% of n) periods. Resample to weeks first where a spec asks for weekly figures.
    """
    x = pd.Series(returns).dropna().astype(float)
    n = len(x)
    if n == 0:
        return {"n": 0}
    sd = x.std(ddof=1) if n > 1 else np.nan
    eq = np.concatenate([[0.0], x.cumsum().to_numpy()])
    dd = np.maximum.accumulate(eq) - eq
    k = int(np.ceil(0.05 * n))
    ann = x.mean() * periods_per_year
    mdd = float(dd.max())
    return {"n": n, "mean": x.mean(), "sd": sd,
            "sharpe_ann": x.mean() / sd * np.sqrt(periods_per_year) if n > 1 and sd > 0 else np.nan,
            "skew": float(x.skew()) if n > 2 else np.nan, "total": x.sum(), "max_drawdown": mdd,
            "worst": x.min(), "cvar_5": float(np.sort(x.to_numpy())[:k].mean()),
            "ann_return_over_mdd": ann / mdd if mdd > 0 else np.nan}
