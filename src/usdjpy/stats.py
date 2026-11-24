"""Inference helpers with the heteroskedasticity and clustering corrections.

`events.summarize()` reports a naive t = mean / (sd / sqrt(n)). That is fine for
genuinely independent window trades. It is NOT fine in two cases this project
keeps running into, and the repo's `t-stat < 2` kill criterion depends on it:

1. CLUSTERED EVENTS. MOF intervention days arrive in runs of 2-3 consecutive
   days. Pre-holdout there are 7 operation days but only 4 independent episodes.
   Treating them as 7 overstates t by sqrt(7/4) = 1.32x; on the full 13-day /
   5-cluster sample, by 1.61x. Use `clustered_t`.

2. AUTOCORRELATION ESTIMATES on a return series. The textbook 1/sqrt(T) standard
   error is badly anti-conservative under volatility clustering. Validated by
   simulation on GARCH(1,1) (alpha=.08, beta=.90):
     - the "variance inflation" form is INCONSISTENT: size rose from 27% at
       T=2000 to 47% at T=5000
     - the direct HC sandwich below is sized at 4.7% and collapses to 1/sqrt(T)
       on homoskedastic data (ratio 0.999)
     - on realistic FX vol dynamics it is 4.9-7.4x the textbook SE
   Use `acf_se_hc`.

Also here: `variance_ratio` with the heteroskedasticity-robust z. The textbook
homoskedastic variance-ratio test rejected on 79.5% of pure GARCH random walks
in simulation (T=4000, 400 paths) -- it declares a random walk mean-reverting
four times in five. The robust version is sized at 4.2% against a nominal 5%.

And `min_detectable_pips`, which should be reported next to every null on a
small event sample, so a null can be read as "the study cannot see an effect
this size" rather than "no effect exists".
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm

from .costs import PIP

EULER_MASCHERONI = 0.5772156649015329


# ------------------------------------------------------------ clustered events

def cluster_ids(dates, max_gap_days: int = 4) -> np.ndarray:
    """Group dates into episodes: a new cluster starts after a gap > max_gap_days.

    MOF operations run on consecutive or near-consecutive business days, so the
    default treats anything within 4 calendar days as the same episode.
    """
    d = pd.DatetimeIndex(pd.to_datetime(sorted(dates)))
    if len(d) == 0:
        return np.array([], dtype=int)
    gaps = np.diff(d.values).astype("timedelta64[D]").astype(int)
    return np.concatenate([[0], np.cumsum(gaps > max_gap_days)])


def clustered_t(values, dates, max_gap_days: int = 4) -> dict:
    """Mean and t-stat using cluster means as the unit of observation.

    Returns both the naive and clustered t so the inflation is visible.
    """
    v = pd.Series(np.asarray(values, float), index=pd.DatetimeIndex(pd.to_datetime(dates)))
    v = v.sort_index().dropna()
    if len(v) < 2:
        return {"n": len(v), "n_clusters": len(v), "mean": v.mean() if len(v) else np.nan,
                "t_naive": np.nan, "t_clustered": np.nan, "inflation": np.nan}
    cid = cluster_ids(v.index, max_gap_days)
    cl = pd.Series(v.values).groupby(cid).mean()
    n, k = len(v), len(cl)
    sd_n = v.std(ddof=1)
    t_naive = v.mean() / (sd_n / np.sqrt(n)) if sd_n > 0 else np.nan
    sd_k = cl.std(ddof=1) if k > 1 else np.nan
    t_cl = cl.mean() / (sd_k / np.sqrt(k)) if k > 1 and sd_k > 0 else np.nan
    return {"n": n, "n_clusters": k, "mean": v.mean(), "cluster_mean": cl.mean(),
            "t_naive": t_naive, "t_clustered": t_cl,
            "inflation": (t_naive / t_cl) if (t_cl and np.isfinite(t_cl) and t_cl != 0) else np.nan}


# --------------------------------------------------------------- autocorrelation

def acf(x, nlags: int) -> np.ndarray:
    x = np.asarray(x, float)
    x = x - x.mean()
    T = len(x)
    denom = np.dot(x, x)
    return np.array([np.dot(x[:T - k], x[k:]) / denom for k in range(1, nlags + 1)])


def acf_se_hc(x, k: int) -> float:
    """Heteroskedasticity-consistent SE of rho_k. Validated size 4.7%.

        var(rho_k) = sum_t x_t^2 x_{t-k}^2 / (sum_t x_t^2)^2
    """
    x = np.asarray(x, float)
    x = x - x.mean()
    return float(np.sqrt(np.sum(x[k:] ** 2 * x[:-k] ** 2) / np.sum(x ** 2) ** 2))


def acf_table(x, nlags: int = 10) -> pd.DataFrame:
    """Autocorrelations with HC standard errors, naive t shown for contrast."""
    x = np.asarray(x, float)
    rho = acf(x, nlags)
    naive = 1.0 / np.sqrt(len(x))
    rows = []
    for k in range(1, nlags + 1):
        se = acf_se_hc(x, k)
        rows.append({"lag": k, "rho": rho[k - 1], "se_hc": se, "se_ratio": se / naive,
                     "t_hc": rho[k - 1] / se, "t_naive": rho[k - 1] / naive})
    return pd.DataFrame(rows).set_index("lag")


# -------------------------------------------------------------- variance ratio

def variance_ratio(r, q: int) -> tuple[float, float]:
    """Lo-MacKinlay VR with the heteroskedasticity-robust z*. Validated size 4.2%.

    VR > 1 persistent/trending, VR < 1 mean-reverting. The naive homoskedastic
    z rejects on ~80% of GARCH random walks -- do not use it.
    """
    r = np.asarray(r, float)
    T = len(r)
    mu = r.mean()
    va = np.sum((r - mu) ** 2) / (T - 1)
    cum = np.cumsum(np.insert(r, 0, 0.0))
    rq = cum[q:] - cum[:-q]
    m = q * (T - q + 1) * (1 - q / T)
    vq = np.sum((rq - q * mu) ** 2) / m
    vr = vq / va
    d = (r - mu) ** 2
    sd = np.sum(d)
    theta = 0.0
    for j in range(1, q):
        delta = T * np.sum(d[j:] * d[:-j]) / sd ** 2
        theta += (2.0 * (q - j) / q) ** 2 * delta
    z = np.sqrt(T) * (vr - 1.0) / np.sqrt(theta) if theta > 0 else np.nan
    return float(vr), float(z)


# --------------------------------------------------------------------- Hurst

def ewma_standardise(r, lam: float = 0.94) -> np.ndarray:
    """Divide by EWMA conditional vol. Required before any Hurst estimate.

    On raw GARCH returns DFA has a bias of -0.099 against a truth of 0.5;
    standardising cuts that to -0.004 and the spread by about 4x.
    """
    r = np.asarray(r, float)
    v = np.empty(len(r))
    v[0] = r.var()
    for t in range(1, len(r)):
        v[t] = lam * v[t - 1] + (1 - lam) * r[t - 1] ** 2
    s = r / np.sqrt(v)
    return s - s.mean()


def hurst_dfa(x, min_w: int = 10) -> float:
    x = np.asarray(x, float)
    y = np.cumsum(x - x.mean())
    n = len(y)
    ws = np.unique(np.logspace(np.log10(min_w), np.log10(max(min_w + 1, n // 4)), 20).astype(int))
    F = []
    for w in ws:
        ns = n // w
        if ns < 2:
            continue
        t = np.arange(w)
        res = [np.sum((y[i * w:(i + 1) * w] -
                       np.polyval(np.polyfit(t, y[i * w:(i + 1) * w], 1), t)) ** 2)
               for i in range(ns)]
        F.append((w, np.sqrt(np.sum(res) / (ns * w))))
    ws_ = np.array([f[0] for f in F], float)
    Fs = np.array([f[1] for f in F], float)
    return float(np.polyfit(np.log(ws_), np.log(Fs), 1)[0])


# ------------------------------------------------------- power / detectability

def min_detectable_pips(sd_pips: float, n: int, power: float = 0.80,
                        alpha: float = 0.05) -> float:
    """Minimum detectable mean, in pips, for a sample of n independent trades.

    Pass n = number of CLUSTERS for clustered events, not number of days.
    Report this alongside every null: a null is only informative if the MDE is
    below the effect size the literature claims.
    """
    se = sd_pips / np.sqrt(n)
    return float((norm.ppf(1 - alpha / 2) + norm.ppf(power)) * se)


def expected_max_sharpe(n_trials: int, var_sr: float) -> float:
    """False Strategy Theorem bracket (Bailey & Lopez de Prado 2014, eq. 6).

    The Sharpe the best of n_trials zero-skill strategies is expected to show.
    Reproduces the published value 2.531 at n_trials=100, var_sr=1.
    """
    g = EULER_MASCHERONI
    z = (1 - g) * norm.ppf(1 - 1 / n_trials) + g * norm.ppf(1 - 1 / (n_trials * np.e))
    return float(np.sqrt(var_sr) * z)


def deflated_sharpe(sr: float, n_obs: int, skew: float, kurt_pearson: float,
                    n_trials: int) -> dict:
    """Deflated Sharpe Ratio. Pass PEARSON kurtosis, not excess.

    Hurdle: DSR > 0.95. SR and SR_0 are per-period, matching n_obs.
    """
    var_sr = (1 + sr ** 2 / 2) / (n_obs - 1)
    sr0 = expected_max_sharpe(n_trials, var_sr) if n_trials > 1 else 0.0
    denom = np.sqrt(1 - skew * sr + (kurt_pearson - 1) / 4 * sr ** 2)
    dsr = float(norm.cdf((sr - sr0) * np.sqrt(n_obs - 1) / denom))
    return {"sr": sr, "sr_0": sr0, "dsr": dsr, "passes": dsr > 0.95}


def pips_sd_from_annual_vol(ann_vol: float, price: float, days: int) -> float:
    """Convert an annualised vol into the sd of a `days`-day move, in pips."""
    return ann_vol / np.sqrt(252) * np.sqrt(days) * price / PIP
