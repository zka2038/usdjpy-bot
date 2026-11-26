"""Spec 004 tradeability measures, one definition for every cost column.

Implements, per trade and per column (as run / era / era x2 / measured):
- kill criterion 4: net mean and t under `PESSIMISTIC`;
- kill criterion 5 as declared in spec 004's *evaluation note*: margin = mean of
  net_i - (PESSIMISTIC round trip at price_i + the spread trade i pays); pass if >= 0.
  The original *Gap fill* text says to judge it "under both CostModel() and
  PESSIMISTIC", so the stricter variant (net under PESSIMISTIC minus the same bar)
  is reported beside it;
- the reported-only diagnostics of spec 004 *Amendment: field standards*: a 95%
  one-sided label beside the 1-SE label, net t in every column, break-even all-in
  cost at zero / t = 2.5 / t = 1.645, break-even / base all-in, per-trade bp at each
  trade's own price, a bp-stability test, and the 159 view only when that test
  passes;
- Sharpe / power figures (which restate t) and the deflated Sharpe.

Trades need the columns events.window_trades writes since 2026-11-25 (net_pips,
mid_pips, spread_paid_pips, mid_in, source), plus s_meas for the measured column.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import kurtosis, norm, skew

from .costs import PESSIMISTIC, PIP, CostModel, era_spread_multiplier
from .events import tradeability_margin
from .stats import deflated_sharpe, max_trials_passing

BONF_T = 2.5                              # spec 004 kill criterion 2
MDE_MULT = BONF_T + norm.ppf(0.80)        # 3.342 SE: 80% power at the t=2.5 bar
Z95 = norm.ppf(0.95)
YEARS = 18                                # 2007-2024
LIVE_HAIRCUT = 0.73                       # CLAUDE.md "Two bars"
TODAY_PRICE = 159.0
BP_STABILITY_T = 1.96                     # |t| of the bp-on-price slope above which the 159 view is withheld
BASE = CostModel()
COLUMNS = ("as run", "era", "era x2", "measured")


def with_cost_columns(trades: pd.DataFrame) -> pd.DataFrame:
    """Add the era multiplier k and one net column per cost assumption.
    Spreads widen on the spread each trade pays (bid-anchored): entry for a long,
    exit for a short."""
    t = trades.copy()
    t["k"] = era_spread_multiplier(t["source"], t.index)
    s = t["spread_paid_pips"]
    t["net_as run"] = t["net_pips"]
    t["net_era"] = t["net_pips"] - (t["k"] - 1.0) * s
    t["net_era x2"] = t["net_pips"] - (2.0 * t["k"] - 1.0) * s
    if "s_meas" in t:
        t["net_measured"] = t["net_pips"] - (t["s_meas"] - s)
    return t


def mean_t(x: pd.Series) -> dict:
    x = pd.Series(x).dropna()
    n = len(x)
    sd = x.std(ddof=1) if n > 1 else np.nan
    se = sd / np.sqrt(n) if n > 1 else np.nan
    return {"n": n, "mean": x.mean(), "sd": sd, "se": se, "t": x.mean() / se if n > 1 and se > 0 else np.nan}


def _spread_for(t: pd.DataFrame, column: str) -> tuple[pd.Series, pd.Series]:
    """(net, spread paid) for a column."""
    if column == "measured":
        return t["net_measured"], t["s_meas"]
    k = {"as run": 1.0, "era": t["k"], "era x2": 2.0 * t["k"]}[column]
    return t[f"net_{column}"], k * t["spread_paid_pips"]


def labels(mean: float, se: float) -> tuple[str, str]:
    """(1-SE label, 95% one-sided label) for a margin."""
    one = "not resolved" if abs(mean) < se else ("pass" if mean >= 0 else "fail")
    lcb, ucb = mean - Z95 * se, mean + Z95 * se
    ninety_five = "pass" if lcb > 0 else ("fail" if ucb < 0 else "not resolved")
    return one, ninety_five


def criterion_5(t: pd.DataFrame, column: str) -> dict:
    net, s = _spread_for(t, column)
    frame = pd.DataFrame({"net_pips": net, "spread_paid_pips": s, "mid_in": t["mid_in"]}).dropna()
    m = tradeability_margin(frame, PESSIMISTIC)
    st = mean_t(m)
    one, n95 = labels(st["mean"], st["se"])
    pess_extra = np.array([PESSIMISTIC.round_trip_pips(p) - BASE.round_trip_pips(p) for p in frame["mid_in"]])
    strict = mean_t(m - pess_extra)
    return {"column": column, "n": st["n"], "margin": st["mean"], "se": st["se"],
            "lcb95": st["mean"] - Z95 * st["se"], "label_1se": one, "label_95": n95,
            "strict_margin": strict["mean"], "strict_label_95": labels(strict["mean"], strict["se"])[1],
            "series": m}


def criterion_4(t: pd.DataFrame, column: str = "as run") -> dict:
    net, _ = _spread_for(t, column)
    pess_extra = np.array([PESSIMISTIC.round_trip_pips(p) - BASE.round_trip_pips(p) for p in t["mid_in"]])
    return mean_t(net - pess_extra)


def break_even(t: pd.DataFrame, column: str = "as run") -> dict:
    """All-in round-trip cost at which the net mean is zero, or t falls to 2.5 / 1.645."""
    net, _ = _spread_for(t, column)
    keep = net.notna()                    # measured can be missing for some trades: same rows throughout
    st = mean_t(net[keep])
    mid = t.loc[keep, "mid_pips"].mean()
    base_all_in = mid - st["mean"]
    mid_bp = (t.loc[keep, "mid_pips"] * PIP / t.loc[keep, "mid_in"] * 1e4).mean()
    return {"zero": mid, "zero_bp": mid_bp, "t2.5": mid - BONF_T * st["se"], "t1.645": mid - Z95 * st["se"],
            "base_all_in": base_all_in, "ratio": mid / base_all_in if base_all_in > 0 else np.nan}


def bp_stats(t: pd.DataFrame, column: str = "as run") -> dict:
    net, _ = _spread_for(t, column)
    return mean_t(net * PIP / t["mid_in"] * 1e4)


def bp_stability(t: pd.DataFrame) -> dict:
    """Is the effect constant in bp across price levels? OLS of per-trade mid bp on
    entry price (HC1 SE), and mid bp by price tercile. The 159 view assumes yes."""
    y = (t["mid_pips"] * PIP / t["mid_in"] * 1e4).to_numpy()
    x = t["mid_in"].to_numpy()
    X = np.column_stack([np.ones_like(x), x])
    xtxi = np.linalg.inv(X.T @ X)
    b = xtxi @ X.T @ y
    e = y - X @ b
    n, k = X.shape
    v = xtxi @ (X.T * e ** 2) @ X @ xtxi * n / (n - k)
    t_slope = b[1] / np.sqrt(v[1, 1])
    terc = pd.qcut(x, 3, labels=["low", "mid", "high"])
    by = pd.Series(y).groupby(terc, observed=True).agg(["mean", "count"])
    return {"slope_bp_per_yen": b[1], "t_slope": t_slope, "terciles": by,
            "admissible": bool(abs(t_slope) < BP_STABILITY_T)}


def today_view(t: pd.DataFrame, column: str) -> float | None:
    """Criterion 5 margin re-priced to TODAY_PRICE: the effect scaled by price (bp
    constant), costs at today's price, spreads unchanged in pips. A forward
    projection; returns None unless bp_stability says the scaling is admissible."""
    if not bp_stability(t)["admissible"]:
        return None
    c5 = criterion_5(t, column)["series"]
    tt = t.loc[c5.index]
    p = tt["mid_in"].to_numpy()
    mid_today = tt["mid_pips"] * TODAY_PRICE / p
    shift = np.array([BASE.round_trip_pips(x) + PESSIMISTIC.round_trip_pips(x) for x in p]) \
        - (BASE.round_trip_pips(TODAY_PRICE) + PESSIMISTIC.round_trip_pips(TODAY_PRICE))
    return float((c5 + (mid_today - tt["mid_pips"]) + shift).mean())


def sharpe_power(t: pd.DataFrame, column: str = "as run") -> dict:
    """Both restate t: annual Sharpe = t/sqrt(YEARS); observed power = Phi(t - 2.5).
    Predictive replication Phi((t - 2.5)/sqrt 2) allows for estimation error."""
    net, _ = _spread_for(t, column)
    st = mean_t(net)
    per_yr = st["n"] / YEARS
    ann = st["mean"] / st["sd"] * np.sqrt(per_yr)
    return {**st, "per_trade_sr": st["mean"] / st["sd"], "annual_sharpe": ann,
            "live": ann * (1 - LIVE_HAIRCUT), "threshold": BONF_T * st["se"], "mde80": MDE_MULT * st["se"],
            "observed_power": norm.cdf(st["t"] - BONF_T),
            "predictive_replication": norm.cdf((st["t"] - BONF_T) / np.sqrt(2))}


def dsr(t: pd.DataFrame, trials: int = 5, column: str = "as run") -> dict:
    """Deflated Sharpe on the per-trade series with its own skew and Pearson kurtosis."""
    net, _ = _spread_for(t, column)
    x = net.dropna()
    sr, n = x.mean() / x.std(ddof=1), len(x)
    sk, ku = float(skew(x)), float(kurtosis(x, fisher=False))
    return {"sr": sr, "n": n, "skew": sk, "kurt": ku, "dsr": deflated_sharpe(sr, n, sk, ku, trials)["dsr"],
            "max_n": max_trials_passing(sr, n, sk, ku)}
