"""Volatility model (Tier 0b): realised variance, HAR-RV forecasts, EWMA, minute-of-week
profiles, and vol-target sizing. Infrastructure for specs 007, 014 and 017; it tests
nothing. Every forecast and baseline uses only data strictly before the time it is
used at.

PRICE SERIES: use the BID (`bars["bid"]`), never the mid. Bid-only sources (Dukascopy,
HistData) carry a synthetic ask keyed on the hour (`datasets._with_synthetic_ask`), so
their mid steps by half the spread change at each hour boundary. Measured on HistData
2015-2024 (`scripts/vol_model_check.py`): 2.34 pips at 05:59 JST and 2.20 at 06:59 JST,
every day, around the ~5-pip rollover hour; under 0.12 pips anywhere else. Those steps
never traded. Two such steps add about 0.2% to a median day's RV (computed, not
measured), and because they recur in the same minute-of-week cell, a seasonally
normalised shock rule (spec 007, which says "mid") absorbs them into its baseline and so
HIDES real shocks at those two minutes rather than inventing new ones: at 05:59 JST a 5x
rule on a Tokyo-clock baseline fires on 0.9% of days on the mid against 5.7% on the bid.
The bid is the observed series in every source, Eightcap included, and has neither problem.

Trading day: 17:00 New York to 17:00 New York, labelled by the New York date it ends on
(the FX convention, and the boundary `costs.roll_times` charges financing on). The
Sunday-evening reopen begins Monday's day. No return crosses a day boundary.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ROLL_TZ = "America/New_York"
DAYS_PER_YEAR = 260          # FX weekdays: what a 17:00-NY trading day counts
HAR_LAGS = (1, 5, 22)        # spec 017 O2


# ------------------------------------------------------------------ realised variance

def trading_day(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Trading-day label (naive NY date) of each UTC timestamp: the session ending at the
    next 17:00 New York. 16:59 NY belongs to that date, 17:00 NY to the next one."""
    ny = pd.DatetimeIndex(index).tz_convert(ROLL_TZ)
    d = ny.tz_localize(None).normalize()
    return d + pd.to_timedelta((ny.hour >= 17).astype(int), unit="D")


def realized_variance(price: pd.Series, freq: str = "5min", min_coverage: float = 0.8) -> pd.DataFrame:
    """Daily realised variance from one price series (the bid; see the module note).

    Sampling: the last price in each `freq` interval of each trading day (previous-tick).
    Returns are taken between consecutive sampled intervals of the same day, across any
    empty intervals between them: for a diffusion, squared increments over any partition
    sum to the integrated variance in expectation, so interior gaps add noise, not bias.
    Gaps at a day's start or end lose variance outright, hence the coverage rule.

    Returns per trading day: `rv` (sum of squared log returns; NaN if coverage is below
    `min_coverage`), `rv_raw` (the same, before the rule), `n_returns`, `coverage`
    (share of the day's `freq` intervals with a price; a full day has 24h / freq), and
    `weekday` (of the label). Weekend labels never appear: Saturday and Sunday sessions
    do not exist.
    """
    p = price.dropna().astype(float)
    p = p[p > 0]
    lp = np.log(p)
    day = trading_day(lp.index)
    bucket = lp.index.floor(freq)
    s = lp.groupby([day, bucket]).last()
    s.index.names = ["day", "bucket"]
    r = s.groupby(level="day").diff()
    out = pd.DataFrame({
        "rv_raw": (r ** 2).groupby(level="day").sum(min_count=1),
        "n_returns": r.notna().groupby(level="day").sum(),
        "n_buckets": s.groupby(level="day").size(),
    })
    out = out[out.index.day_of_week < 5]          # stray bars after Friday 17:00 NY
    full = pd.Timedelta("24h") / pd.Timedelta(freq)
    out["coverage"] = out["n_buckets"] / full
    out["rv"] = out["rv_raw"].where(out["coverage"] >= min_coverage)
    out["weekday"] = out.index.day_of_week
    out.index.name = "day"
    return out[["rv", "rv_raw", "n_returns", "coverage", "weekday"]]


def annualise(daily_var, days_per_year: float = DAYS_PER_YEAR):
    """Daily variance -> annualised volatility, sqrt(days_per_year * var)."""
    return np.sqrt(np.asarray(daily_var, dtype=float) * days_per_year)


# ------------------------------------------------------------------ HAR-RV

def weekday_series(rv: pd.Series) -> pd.Series:
    """`rv` on every weekday between its first and last day, NaN where absent, so that a
    day with no bars at all counts as missing instead of silently shortening a window."""
    idx = pd.DatetimeIndex(rv.index)
    return rv.astype(float).reindex(pd.bdate_range(idx.min(), idx.max()))


def har_design(rv: pd.Series, lags=HAR_LAGS, min_frac: float = 0.8) -> pd.DataFrame:
    """HAR regressors at each day t: the mean RV over the last k trading days for each k
    in `lags` (k = 1 is RV_t itself), over the trading-day series, needing at least
    ceil(min_frac * k) valid days in each window. Pass a `weekday_series`."""
    rv = rv.astype(float)
    cols = {}
    for k in lags:
        cols[f"rv_{k}"] = rv.rolling(k, min_periods=max(1, int(np.ceil(min_frac * k)))).mean()
    return pd.DataFrame(cols, index=rv.index)


def har_target(rv: pd.Series, horizon: int = 1, min_frac: float = 0.8) -> pd.Series:
    """Mean RV over trading days t+1 .. t+horizon (the direct multi-step target)."""
    fwd = rv.astype(float)[::-1].rolling(horizon, min_periods=max(1, int(np.ceil(min_frac * horizon)))).mean()[::-1]
    return fwd.shift(-1).rename(f"rv_next_{horizon}")


def har_forecast(rv: pd.Series, horizon: int = 1, lags=HAR_LAGS, min_train: int = 250,
                 refit_every: int = 1) -> pd.DataFrame:
    """Out-of-sample HAR-RV forecast of mean daily RV over the next `horizon` trading days,
    made at the end of each day t from data up to t only.

    The model at t is OLS (levels, with intercept) on rows s whose target is fully
    observed by t, i.e. s + horizon <= t: for horizon 5 the newest training row is five
    days back. Expanding window, refitted every `refit_every` days, first forecast once
    `min_train` rows exist. Forecasts are floored at the smallest training target, since
    a levels HAR can go negative. Returns `forecast` (daily variance), `vol_ann`
    (annualised), and the coefficients used (`b0`, `b_<k>`), indexed by forecast day t
    over every weekday (`weekday_series`).
    """
    rv = weekday_series(rv)
    X = har_design(rv, lags)
    y = har_target(rv, horizon)
    pos = np.arange(len(rv))
    rows, coef, floor = [], None, np.nan
    Xv, yv = X.to_numpy(), y.to_numpy()
    ok = ~np.isnan(Xv).any(axis=1) & ~np.isnan(yv)
    for t in range(len(rv)):
        train = ok & (pos + horizon <= t)
        if train.sum() < min_train or np.isnan(Xv[t]).any():
            rows.append([np.nan] * (2 + len(lags)))
            continue
        if coef is None or t % refit_every == 0:
            A = np.column_stack([np.ones(train.sum()), Xv[train]])
            coef, *_ = np.linalg.lstsq(A, yv[train], rcond=None)
            floor = float(yv[train].min())
        f = max(float(coef[0] + Xv[t] @ coef[1:]), floor)
        rows.append([f, *coef])
    out = pd.DataFrame(rows, index=rv.index, columns=["forecast", "b0", *[f"b_{k}" for k in lags]])
    out.insert(1, "vol_ann", annualise(out["forecast"].to_numpy()))
    return out


# ------------------------------------------------------------------ EWMA

def ewma_variance(returns: pd.Series, lam: float | None = None, com: float | None = None,
                  seed_obs: int = 20) -> pd.Series:
    """EWMA variance forecast for t+1 from returns up to t, with no look-ahead.

    lam directly (spec 017: 0.94), or a centre of mass (spec 014: 60 days, lam = com/(1+com)).
    Seeded with the mean square of the first `seed_obs` returns and NaN until then.
    (`signals.ewma_vol` is indexed differently, v_t from returns up to t-1, and warms up
    on an expanding mean instead: `stats.ewma_variance_past`.) Missing returns leave the
    variance unchanged.
    """
    if (lam is None) == (com is None):
        raise ValueError("give exactly one of lam, com")
    lam = com / (1 + com) if lam is None else lam
    r = returns.astype(float).to_numpy()
    out = np.full(len(r), np.nan)
    seen = np.flatnonzero(~np.isnan(r))
    if len(seen) < seed_obs:
        return pd.Series(out, index=returns.index, name="ewma_var")
    start = seen[seed_obs - 1]
    v = float(np.mean(r[seen[:seed_obs]] ** 2))
    out[start] = v
    for t in range(start + 1, len(r)):
        if not np.isnan(r[t]):
            v = lam * v + (1 - lam) * r[t] ** 2
        out[t] = v
    return pd.Series(out, index=returns.index, name="ewma_var")


# ------------------------------------------------------------------ minute-of-week profile

CLOCKS = ("hybrid", "utc", "Asia/Tokyo", "America/New_York", "jst_nydst")
# The hybrid clock's New York band, in New York minutes of the day: London open (03:00 ET)
# through US data, the London fix and the 17:00 rollover. Fixed 2026-11-26 before measuring.
HYBRID_NY_BAND = (3 * 60, 17 * 60 + 10)


def minute_of_week_key(index: pd.DatetimeIndex, clock: str) -> np.ndarray:
    """Cell key of each timestamp: minute of the week (0 = Monday 00:00) on `clock`.
    REQUIRED, with no default: every choice costs something, so a spec declares it.

    - 'hybrid' (**chosen by the user 2026-11-26 for minute-of-week work, spec 007's s_m
      included**): each minute on the clock of the market that drives it. 03:00-17:10
      New York time (`HYBRID_NY_BAND`) is keyed in New York time, everything else in
      JST, in two separate key spaces (ET keys 0-10079, JST keys 10080+). A JST key
      shifted by the US offset into one space instead collides at the band edges (420
      keys in an EDT week hold two market states). Tokyo and New York events both stay
      in their own cells through every US DST change; only the JST cells at the band
      edges (06:10-07:10 and 16:00-17:00 JST) are in the band part of the year and
      restart. Measured on HistData 2015-2024 (`scripts/vol_model_check.py`): 96.1% of
      minutes have a baseline; in the 4 weeks after a US change the Thursday 08:30 ET and
      09:55 JST minutes show 5.1% / 3.5% |r| > 5x baseline, as the matching single clock
      does. London follows EU DST: its events sit an hour off for ~4 weeks a year.
    - 'Asia/Tokyo', 'America/New_York', 'utc': one clock. Events fixed on that clock are
      crisp; events on another clock change cell at each US (or EU) DST change and are
      measured against the wrong history for up to 12 weeks (Tokyo clock: 30.8% of
      Thursday 08:30 ET minutes over 5x baseline in the 4 weeks after a change; New York
      clock: 18.8% of 09:55 JST minutes).
    - 'jst_nydst': JST minute-of-week split by whether New York is on daylight time
      (CLAUDE.md trap 7). Both crisp, but every cell restarts after each US DST change:
      66.4% of minutes have a baseline, none in the 4 weeks after a change.
    """
    idx = pd.DatetimeIndex(index)
    if clock not in CLOCKS:
        raise ValueError(f"clock must be one of {CLOCKS}")
    if clock == "hybrid":
        et, jst = idx.tz_convert(ROLL_TZ), idx.tz_convert("Asia/Tokyo")
        et_m = et.hour.to_numpy() * 60 + et.minute.to_numpy()
        in_ny = (et_m >= HYBRID_NY_BAND[0]) & (et_m < HYBRID_NY_BAND[1])
        k_et = et.day_of_week.to_numpy() * 1440 + et_m
        k_jst = 10080 + jst.day_of_week.to_numpy() * 1440 + jst.hour.to_numpy() * 60 + jst.minute.to_numpy()
        return np.where(in_ny, k_et, k_jst)
    local = idx.tz_convert("UTC" if clock == "utc" else ("Asia/Tokyo" if clock == "jst_nydst" else clock))
    key = local.day_of_week.to_numpy() * 1440 + local.hour.to_numpy() * 60 + local.minute.to_numpy()
    if clock == "jst_nydst":
        offset = idx.tz_convert(ROLL_TZ).tz_localize(None) - idx.tz_convert("UTC").tz_localize(None)
        key = key + 10080 * (offset == pd.Timedelta(hours=-4)).astype(int)    # EDT
    return np.asarray(key)


def seasonal_baseline(x: pd.Series, clock: str, lookback: str = "84D",
                      min_obs: int = 8, stat: str = "median") -> pd.Series:
    """For each observation, `stat` of the same minute-of-week cell over the `lookback`
    before it, strictly excluding it: spec 007's "median |r| at the same minute-of-week over
    the previous 60 trading days" is 12 weeks, at most 12 observations of a cell. NaN with
    fewer than `min_obs`. The window is calendar time, not a count, so a cell never borrows
    observations from further back: on 'jst_nydst', a US DST change leaves the new regime's
    cells empty until `min_obs` weeks have passed (`profile_coverage` shows the cost)."""
    s = x.astype(float).dropna()
    t = pd.DatetimeIndex(s.index).tz_convert("UTC").tz_localize(None)
    frame = pd.DataFrame({"v": s.to_numpy(), "k": minute_of_week_key(s.index, clock)}, index=t)
    rolled = frame.groupby("k")["v"].rolling(lookback, closed="left", min_periods=min_obs).agg(stat)
    out = rolled.droplevel(0).reindex(t)
    return pd.Series(out.to_numpy(), index=s.index, name=f"{stat}_{lookback}").reindex(x.index)


def minute_returns(price: pd.Series, max_gap: str = "1min") -> pd.Series:
    """1-minute log returns of `price` (the bid), only between bars exactly `max_gap` apart:
    a return across a data gap or the weekend is not a 1-minute return."""
    lp = np.log(price.dropna().astype(float))
    r = lp.diff()
    gap = lp.index.to_series().diff()
    return r.where(gap <= pd.Timedelta(max_gap)).rename("r")


def profile_coverage(baseline: pd.Series) -> pd.Series:
    """Share of observations with a baseline, by calendar month: shows the weeks a
    DST-split clock loses after each US change."""
    month = baseline.index.tz_convert("UTC").tz_localize(None).to_period("M")
    return baseline.notna().groupby(month).mean()


# ------------------------------------------------------------------ sizing

def vol_target_weight(signal, sigma_ann, target: float, cap: float = 2.0):
    """w = signal * min(cap, target / sigma) (spec 014: 10%, cap 2; spec 017 O2: 8%).
    NaN or non-positive sigma gives NaN, never a capped full position."""
    s = np.asarray(signal, dtype=float)
    v = np.asarray(sigma_ann, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        lev = np.where(v > 0, np.minimum(cap, target / v), np.nan)
    w = s * lev
    if isinstance(signal, pd.Series):
        return pd.Series(w, index=signal.index, name="weight")
    return w
