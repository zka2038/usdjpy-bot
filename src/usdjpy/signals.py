"""Daily-signal machinery for spec 003 (rate-path revision).

`events.py` handles fixed-clock-time window trades. Spec 003 is a different object:
a daily signal tested by predictive regression, so it needs its own harness.

THE ONE RULE THAT MATTERS HERE. Regressing FX returns on a rates signal with plain
OLS is unusable: when the regressor's volatility co-moves with the return's
volatility -- which US rates and USDJPY do -- the naive t rejects on 77.3% of pure
nulls (simulated, GARCH(1,1) a=.08 b=.90, 20y daily, shared vol loading 0.6).
White HC errors restore the size to 5.7% and then destroy the power: 9.7% at
rho=0.05. Standardising BOTH sides by conditional volatility fixes both at once --
size 3.7%, power 100% at rho=0.05 -- and drops the HC/naive SE ratio from 6.68 to
1.00.

Mechanism: when the signal is largest exactly when the noise is largest, OLS
over-weights the least informative observations. Dividing through by conditional
vol equalises information per observation. It is GLS in effect.

So `predictive_regression` reports t_hc, t_naive and their ratio, and the study
script must standardise first. A large HC/naive ratio on the *standardised* series
means the standardisation failed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def ewma_vol(returns: pd.Series, lam: float = 0.94) -> pd.Series:
    """EWMA conditional volatility, using only information up to t-1 at each point."""
    r = returns.astype(float)
    v = np.empty(len(r))
    v[0] = r.var()
    rv = r.values
    for t in range(1, len(r)):
        v[t] = lam * v[t - 1] + (1 - lam) * rv[t - 1] ** 2
    return pd.Series(np.sqrt(v), index=r.index, name="vol")


def expanding_z(s: pd.Series, min_obs: int = 252) -> pd.Series:
    """Z-score using only data up to and including t. No look-ahead."""
    m = s.expanding(min_periods=min_obs).mean()
    sd = s.expanding(min_periods=min_obs).std()
    return ((s - m) / sd).rename(s.name)


def build_spread(us2y: pd.Series, jgb2y: pd.Series, decision_tz_note: str = "00:00 UTC") -> pd.DataFrame:
    """US-minus-Japan 2y spread, correctly lagged across the date line.

    Treasury's curve for date T publishes after the US close on T, so it is NOT
    knowable in Tokyo on T -> lag the US leg one business day.
    MOF publishes the JGB curve for T in the JST evening, BEFORE the US session of
    the same calendar date -> no lag on the JGB leg.

    A matched-date spread mixes two information sets and is not a tradeable signal.
    """
    us = us2y.astype(float).sort_index()
    jp = jgb2y.astype(float).sort_index()
    idx = us.index.union(jp.index)
    us_l = us.reindex(idx).ffill().shift(1)          # the one-business-day lag
    jp_l = jp.reindex(idx).ffill()
    out = pd.DataFrame({"us2y": us_l, "jgb2y": jp_l})
    out["spread"] = out["us2y"] - out["jgb2y"]
    # staleness, so Golden Week / year-end gaps can be dropped rather than smeared
    out["us_stale"] = _stale_days(us.reindex(idx))
    out["jp_stale"] = _stale_days(jp.reindex(idx))
    out.attrs["decision_timestamp"] = decision_tz_note
    return out


def _stale_days(s: pd.Series) -> pd.Series:
    seen = s.notna()
    grp = seen.cumsum()
    return seen.groupby(grp).cumcount().where(grp > 0, np.nan)


def rate_path_signal(spread: pd.Series, fx_vol: pd.Series, n: int = 5,
                     min_obs: int = 252) -> pd.Series:
    """Spec 003 signal: n-day CHANGE in the spread, vol-standardised, then z-scored.

    The level is contemporaneous with USDJPY and not tradeable; the change is the
    hypothesis. Pre-declared n = 5 business days.
    """
    raw = spread.diff(n)
    scaled = raw / (fx_vol.reindex(raw.index) / fx_vol.mean())
    return expanding_z(scaled, min_obs=min_obs).rename(f"signal_n{n}")


def forward_return(px: pd.Series, h: int, vol: pd.Series | None = None) -> pd.Series:
    """h-period forward log return, optionally divided by conditional vol at t."""
    fwd = np.log(px.shift(-h) / px)
    if vol is not None:
        fwd = fwd / vol.reindex(fwd.index)
    return fwd.rename(f"fwd{h}")


def predictive_regression(x: pd.Series, y: pd.Series, h: int,
                          non_overlapping: bool = True) -> dict:
    """Regress y on x with White HC0 errors. Returns rho, both t-stats, and the ratio.

    non_overlapping: take every h-th observation, so blocks do not share data. More
    conservative than Newey-West on overlapping windows and needs no bandwidth choice.
    """
    df = pd.concat([x.rename("x"), y.rename("y")], axis=1).dropna()
    if non_overlapping and h > 1:
        df = df.iloc[::h]
    if len(df) < 50:
        return {"n": len(df), "rho": np.nan, "t_hc": np.nan, "t_naive": np.nan,
                "se_ratio": np.nan, "beta": np.nan}
    xv = df["x"].values - df["x"].mean()
    yv = df["y"].values - df["y"].mean()
    n = len(xv)
    sxx = np.dot(xv, xv)
    beta = np.dot(xv, yv) / sxx
    resid = yv - beta * xv
    se_naive = np.sqrt(np.sum(resid ** 2) / (n - 2) / sxx)
    se_hc = np.sqrt(np.sum(xv ** 2 * resid ** 2) / sxx ** 2)
    rho = float(np.corrcoef(xv, yv)[0, 1])
    return {"n": n, "rho": rho, "beta": float(beta),
            "t_hc": float(beta / se_hc), "t_naive": float(beta / se_naive),
            "se_ratio": float(se_hc / se_naive)}


def implied_sharpe(rho: float, h: int) -> float:
    """Annualised Sharpe implied by a signal-return correlation at horizon h."""
    return float(rho * np.sqrt(252 / h))


# ------------------------------------------------------------------ harness check

def synthetic_check(true_rho: float = 0.05, T: int = 5040, share: float = 0.6,
                    seed: int = 0) -> dict:
    """Build a series with a KNOWN predictive link and confirm the harness finds it.

    Spec 003 requires this before any null from the real data is trusted. During
    calibration a simulator that built the correlation between x_t and y_t, then
    regressed y_{t+1} on x_t, produced power = size in every cell -- an apparent
    null from a harness containing no signal at all. Same error class as pairing a
    noon FX snapshot with a US close.

    Returns the regression on raw and standardised specifications. The standardised
    t_hc should be large and the se_ratio near 1.
    """
    rng = np.random.default_rng(seed)
    e = rng.standard_normal(T + 1)
    vol = np.empty(T + 1)
    vol[0] = 1.0
    for t in range(1, T + 1):
        vol[t] = np.sqrt(1e-5 + 0.08 * (vol[t - 1] * e[t - 1]) ** 2 + 0.90 * vol[t - 1] ** 2)
    sig_vol = share * vol + (1 - share) * vol.mean()
    xr = sig_vol * rng.standard_normal(T + 1)
    xs = (xr - xr.mean()) / xr.std()
    eps = vol * rng.standard_normal(T + 1)
    eps = eps / eps.std()
    y = np.empty(T + 1)
    y[0] = eps[0]
    y[1:] = true_rho * xs[:-1] + np.sqrt(max(0.0, 1 - true_rho ** 2)) * eps[1:]   # x_t -> y_{t+1}

    idx = pd.RangeIndex(T)
    X = pd.Series(xs[:-1], index=idx)
    Y = pd.Series(y[1:], index=idx)
    V = pd.Series(vol[:-1], index=idx)
    raw = predictive_regression(X, Y, 1)
    std = predictive_regression((X / V - (X / V).mean()) / (X / V).std(), Y / V, 1)
    return {"true_rho": true_rho, "raw": raw, "standardised": std,
             "passes": abs(std["t_hc"]) > 3 and std["se_ratio"] < 2.0}
