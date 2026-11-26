"""Task 6 volatility model against known answers on synthetic data: realised variance is
unbiased for the integrated variance (with gaps), HAR recovers known coefficients and
never looks ahead, EWMA never looks ahead, the minute-of-week baseline recovers a known
intraday pattern on the clock it is keyed to, and the mid-versus-bid trap is real."""
import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from usdjpy import vol  # noqa: E402
from usdjpy.datasets import _with_synthetic_ask  # noqa: E402

UTC = "UTC"


def ts(s):
    return pd.Timestamp(s, tz=UTC)


# ------------------------------------------------------------------ trading days

@pytest.mark.parametrize("t, day", [
    ("2024-03-08 21:59", "2024-03-08"),   # Fri 16:59 EST
    ("2024-03-10 21:00", "2024-03-11"),   # Sun 17:00 EDT: Monday's session (DST began that day)
    ("2024-07-10 20:59", "2024-07-10"),   # 16:59 EDT
    ("2024-07-10 21:00", "2024-07-11"),   # 17:00 EDT
    ("2024-07-11 01:00", "2024-07-11"),   # Tokyo morning belongs to that NY date
])
def test_trading_day_boundary_is_17_new_york(t, day):
    assert vol.trading_day(pd.DatetimeIndex([ts(t)]))[0] == pd.Timestamp(day)


# ------------------------------------------------------------------ realised variance

def fx_minutes(start, end):
    """Every minute the FX market is open: Sunday 17:00 to Friday 17:00 New York."""
    idx = pd.date_range(start, end, freq="1min", tz=UTC, inclusive="left")
    ny = idx.tz_convert("America/New_York")
    closed = ((ny.day_of_week == 4) & (ny.hour >= 17)) | (ny.day_of_week == 5) | \
             ((ny.day_of_week == 6) & (ny.hour < 17))
    return idx[~closed]


def bm_prices(idx, daily_var_by_day, rng, base=150.0):
    """Log-price Brownian motion whose per-minute variance is the trading day's variance / 1440."""
    day = vol.trading_day(idx)
    v = daily_var_by_day.reindex(day).to_numpy() / 1440
    lp = np.log(base) + np.cumsum(rng.standard_normal(len(idx)) * np.sqrt(v))
    return pd.Series(np.exp(lp), index=idx)


def _rv_case(rng, drop=0.0, cut_hours=0):
    idx = fx_minutes("2024-01-07 22:00", "2024-12-27 22:00")      # Sun 17:00 EST .. Fri 17:00 EST
    days = vol.trading_day(idx).unique()
    true = pd.Series(np.exp(rng.normal(np.log(4e-5), 0.5, len(days))), index=days)
    p = bm_prices(idx, true, rng)
    if drop:
        p = p[rng.random(len(p)) >= drop]
    if cut_hours:
        start = vol.trading_day(p.index)
        first = pd.Series(p.index, index=p.index).groupby(start).transform("min")
        p = p[(p.index - pd.DatetimeIndex(first)) >= pd.Timedelta(hours=cut_hours)]
    return vol.realized_variance(p), true


def test_rv_is_unbiased_for_integrated_variance():
    rv, true = _rv_case(np.random.default_rng(1))
    ratio = (rv["rv"] / true.reindex(rv.index)).dropna()
    assert len(ratio) > 240
    assert ratio.mean() == pytest.approx(1.0, abs=0.02)
    assert rv["coverage"].median() == pytest.approx(1.0, abs=0.01)


def test_rv_unbiased_with_interior_gaps():
    rv, true = _rv_case(np.random.default_rng(2), drop=0.3)   # 30% of minutes missing at random
    ratio = (rv["rv"] / true.reindex(rv.index)).dropna()
    assert ratio.mean() == pytest.approx(1.0, abs=0.02)


def test_rv_drops_days_missing_their_start():
    rv, true = _rv_case(np.random.default_rng(3), cut_hours=6)  # first quarter of every day gone
    assert rv["coverage"].max() <= 0.76
    assert rv["rv"].isna().all()                                # below the 0.8 rule
    ratio = (rv["rv_raw"] / true.reindex(rv.index)).dropna()
    assert ratio.mean() == pytest.approx(0.75, abs=0.03)       # the variance it could not see


def test_rv_has_no_weekend_labels_and_no_cross_day_returns():
    idx = fx_minutes("2024-05-05 21:00", "2024-05-11 00:00")
    p = pd.Series(150.0, index=idx)
    p[p.index >= ts("2024-05-07 21:00")] = 151.0     # a jump exactly at a day boundary (17:00 EDT)
    rv = vol.realized_variance(p)
    assert (rv["weekday"] < 5).all()
    assert (rv["rv_raw"] == 0).all()                   # the boundary jump is in no day's RV


# ------------------------------------------------------------------ HAR

TRUE_B = np.array([2e-6, 0.35, 0.30, 0.25])   # b0, b1, b5, b22


def simulate_har(n, rng, s=0.3):
    rv = np.full(n, 2e-5)
    for t in range(22, n - 1):
        m = TRUE_B[0] + TRUE_B[1] * rv[t] + TRUE_B[2] * rv[t - 4:t + 1].mean() + TRUE_B[3] * rv[t - 21:t + 1].mean()
        rv[t + 1] = m * np.exp(s * rng.standard_normal() - s * s / 2)
    return pd.Series(rv, index=pd.bdate_range("2000-01-03", periods=n))


def test_har_recovers_known_coefficients():
    rv = simulate_har(8000, np.random.default_rng(4))
    f = vol.har_forecast(rv, horizon=1, refit_every=500)
    last = f.dropna().iloc[-1]
    assert last[["b_1", "b_5", "b_22"]].to_numpy() == pytest.approx(TRUE_B[1:], abs=0.06)


@pytest.mark.parametrize("h", [1, 5])
def test_har_never_looks_ahead(h):
    rv = simulate_har(700, np.random.default_rng(5))
    full = vol.har_forecast(rv, horizon=h, min_train=300)
    T = 600
    cut = rv.copy()
    cut.iloc[T + 1:] = cut.iloc[T + 1:] * 50             # wreck everything after day T
    pert = vol.har_forecast(cut, horizon=h, min_train=300)
    pd.testing.assert_series_equal(full["forecast"].iloc[:T + 1], pert["forecast"].iloc[:T + 1])
    assert full["forecast"].iloc[:T + 1].notna().sum() > 200


def test_har_counts_absent_days_as_missing():
    rv = simulate_har(400, np.random.default_rng(6))
    f = vol.har_forecast(rv.drop(rv.index[350]), min_train=200)
    assert pd.Timestamp(rv.index[350]) in f.index and np.isnan(f.loc[rv.index[350], "forecast"])


# ------------------------------------------------------------------ EWMA

def test_ewma_recursion_seed_and_no_look_ahead():
    rng = np.random.default_rng(7)
    r = pd.Series(rng.standard_normal(300) * 0.01)
    e = vol.ewma_variance(r, lam=0.94, seed_obs=20)
    assert e.iloc[:19].isna().all()
    v = np.mean(r.iloc[:20] ** 2)
    assert e.iloc[19] == pytest.approx(v)
    for t in range(20, 25):
        v = 0.94 * v + 0.06 * r.iloc[t] ** 2
        assert e.iloc[t] == pytest.approx(v)
    r2 = r.copy()
    r2.iloc[200:] *= 100
    pd.testing.assert_series_equal(e.iloc[:200], vol.ewma_variance(r2, lam=0.94).iloc[:200])
    assert vol.ewma_variance(r, com=60).iloc[100] == pytest.approx(
        vol.ewma_variance(r, lam=60 / 61).iloc[100])
    with pytest.raises(ValueError):
        vol.ewma_variance(r)


def test_past_only_seed_for_signals_ewma_vol_and_stats_ewma_standardise():
    """Both seed from past returns only (fixed 2026-11-26); before, v[0] was the variance
    of the whole series. Known answer: the measured spec 003 variant B."""
    from usdjpy.signals import ewma_vol
    from usdjpy.stats import ewma_standardise, ewma_variance_past, hurst_dfa
    rng = np.random.default_rng(9)
    r = rng.standard_normal(400) * 0.01
    v = ewma_variance_past(r, 0.94)
    assert np.isnan(v[0]) and v[1] == pytest.approx(r[0] ** 2) and v[20] == pytest.approx(np.mean(r[:20] ** 2))
    assert v[21] == pytest.approx(0.94 * v[20] + 0.06 * r[20] ** 2)
    r2 = r.copy()
    r2[300:] *= 100                                       # nothing at or after 300 may move v[:301]
    np.testing.assert_array_equal(v[:301], ewma_variance_past(r2, 0.94)[:301])
    s = pd.Series(r, index=pd.bdate_range("2007-01-02", periods=400))
    pd.testing.assert_series_equal(ewma_vol(s), pd.Series(np.sqrt(v), index=s.index, name="vol"))
    z = ewma_standardise(r)
    assert len(z) == len(r) - 1
    raw = r[1:] / np.sqrt(v[1:])
    np.testing.assert_allclose(z, raw - raw.mean())
    assert hurst_dfa(ewma_standardise(rng.standard_normal(4000))) == pytest.approx(0.5, abs=0.08)


# ------------------------------------------------------------------ minute-of-week baseline

BASE = 1e-4


@pytest.fixture(scope="module")
def seasonal():
    """1-min returns Jan-Jul 2024 (US DST begins 10 March) with sd x6 at 08:30 ET and x4 at
    09:55 JST on weekdays."""
    rng = np.random.default_rng(8)
    idx = fx_minutes("2024-01-07 22:00", "2024-07-26 21:00")
    sd = np.full(len(idx), BASE)
    et, jst = idx.tz_convert("America/New_York"), idx.tz_convert("Asia/Tokyo")
    sd[(et.hour == 8) & (et.minute == 30)] *= 6
    sd[(jst.hour == 9) & (jst.minute == 55)] *= 4
    return pd.Series(rng.standard_normal(len(idx)) * sd, index=idx).abs()


def _cell(s, clock, local_tz, hh, mm, a, b):
    base = vol.seasonal_baseline(s, clock=clock)
    loc = base.index.tz_convert(local_tz)
    m = (loc.hour == hh) & (loc.minute == mm) & (base.index >= ts(a)) & (base.index < ts(b))
    return base[m]


MED = 0.6745 * BASE     # median |N(0, BASE)|


def test_dst_split_clock_recovers_both_spikes_once_filled(seasonal):
    et = _cell(seasonal, "jst_nydst", "America/New_York", 8, 30, "2024-06-15", "2024-07-27")
    jp = _cell(seasonal, "jst_nydst", "Asia/Tokyo", 9, 55, "2024-06-15", "2024-07-27")
    assert et.median() / MED == pytest.approx(6, rel=0.25)
    assert jp.median() / MED == pytest.approx(4, rel=0.25)


def test_utc_clock_smears_the_new_york_spike_after_dst(seasonal):
    # weeks 1-4 after 10 March: 08:30 ET has moved to 12:30 UTC, whose history is quiet
    utc = _cell(seasonal, "utc", "America/New_York", 8, 30, "2024-03-11", "2024-04-06")
    assert utc.median() / MED == pytest.approx(1, rel=0.3)        # spike measured against calm
    split = _cell(seasonal, "jst_nydst", "America/New_York", 8, 30, "2024-03-11", "2024-04-06")
    assert split.isna().all()                                      # no baseline yet, not a wrong one


def test_tokyo_clock_keeps_the_tokyo_spike_through_us_dst(seasonal):
    jp = _cell(seasonal, "Asia/Tokyo", "Asia/Tokyo", 9, 55, "2024-03-11", "2024-04-06")
    assert jp.median() / MED == pytest.approx(4, rel=0.3)


def test_hybrid_clock_recovers_both_spikes_right_after_dst(seasonal):
    """The case no other clock handles: weeks 1-4 after the US change, both events in place."""
    et = _cell(seasonal, "hybrid", "America/New_York", 8, 30, "2024-03-11", "2024-04-06")
    jp = _cell(seasonal, "hybrid", "Asia/Tokyo", 9, 55, "2024-03-11", "2024-04-06")
    assert et.median() / MED == pytest.approx(6, rel=0.3)
    assert jp.median() / MED == pytest.approx(4, rel=0.3)


@pytest.mark.parametrize("t, space", [
    ("2024-01-10 07:59", "et"),    # 02:59 EST: before the NY band -> JST key
    ("2024-01-10 08:00", "et"),    # 03:00 EST: band starts
    ("2024-01-10 22:09", "et"),    # 17:09 EST: rollover inside the band
    ("2024-01-10 22:10", "jst"),   # 17:10 EST: band ends
    ("2024-07-10 21:09", "et"),    # 17:09 EDT
    ("2024-07-10 21:10", "jst"),
    ("2024-01-11 00:55", "jst"),   # 09:55 JST, the Tokyo fix
])
def test_hybrid_band_edges(t, space):
    k = vol.minute_of_week_key(pd.DatetimeIndex([ts(t)]), "hybrid")[0]
    et_m = ts(t).tz_convert("America/New_York")
    in_band = 180 <= et_m.hour * 60 + et_m.minute < 17 * 60 + 10
    assert (k < 10080) == in_band
    if t != "2024-01-10 07:59":
        assert (k < 10080) == (space == "et")


def test_hybrid_keys_follow_each_market_across_dst():
    winter, summer = ts("2024-01-11 13:30"), ts("2024-07-11 12:30")      # Thu 08:30 ET in EST / EDT
    k = vol.minute_of_week_key(pd.DatetimeIndex([winter, summer]), "hybrid")
    assert k[0] == k[1] < 10080
    tokyo_w, tokyo_s = ts("2024-01-11 00:55"), ts("2024-07-11 00:55")    # 09:55 JST both seasons
    k = vol.minute_of_week_key(pd.DatetimeIndex([tokyo_w, tokyo_s]), "hybrid")
    assert k[0] == k[1] >= 10080


def test_baseline_excludes_the_current_and_later_observations(seasonal):
    s = seasonal.iloc[:60000]
    b = vol.seasonal_baseline(s, clock="jst_nydst")
    t = b.dropna().index[100]
    s2 = s.copy()
    s2[s2.index >= t] *= 1000
    b2 = vol.seasonal_baseline(s2, clock="jst_nydst")
    pd.testing.assert_series_equal(b[b.index <= t], b2[b2.index <= t])


def test_baseline_window_is_twelve_weeks_of_calendar_time():
    """One cell (Monday 00:00 UTC): 10 weekly observations, a 20-week gap, then 9 more.
    After the gap the old observations are out of the 84-day window, so there is no
    baseline until 8 new ones exist; a count-based window would have borrowed the old."""
    a = pd.date_range("2024-01-01", periods=10, freq="7D", tz=UTC)
    b = pd.date_range(a[-1] + pd.Timedelta(weeks=21), periods=9, freq="7D", tz=UTC)
    s = pd.Series(1.0, index=a.append(b))
    base = vol.seasonal_baseline(s, clock="utc")
    assert base.loc[a[8]] == 1.0 and np.isnan(base.loc[a[7]])     # 8 prior obs needed
    assert base.loc[b[:8]].isna().all() and base.loc[b[8]] == 1.0


def test_minute_returns_skip_gaps():
    idx = pd.DatetimeIndex([ts("2024-05-06 00:00"), ts("2024-05-06 00:01"), ts("2024-05-06 00:05")])
    r = vol.minute_returns(pd.Series([150.0, 150.1, 150.5], index=idx))
    assert np.isnan(r.iloc[0]) and r.iloc[1] == pytest.approx(np.log(150.1 / 150)) and np.isnan(r.iloc[2])


# ------------------------------------------------------------------ the mid trap

def test_mid_of_a_bid_only_source_jumps_at_hour_boundaries():
    """A flat bid with the hour-keyed synthetic ask: the mid moves, the bid does not."""
    idx = pd.date_range("2024-05-06 20:00", "2024-05-06 23:00", freq="1min", tz=UTC)  # 05:00-08:00 JST
    prof = pd.Series(0.003, index=range(24))
    prof[6] = 0.050                                   # the rollover hour, as in the real profile
    bars = _with_synthetic_ask(pd.Series(150.0, index=idx), "histdata", profile=prof)
    mid_r = vol.minute_returns((bars["bid"] + bars["ask"]) / 2)
    bid_r = vol.minute_returns(bars["bid"])
    assert (bid_r.dropna() == 0).all()
    # log return -> pips at 150: (5.0 - 0.3) / 2 = 2.35 pips at the 07:00 JST boundary
    assert mid_r.abs().max() * 150 / 0.01 == pytest.approx(2.35, abs=0.01)


# ------------------------------------------------------------------ sizing

def test_vol_target_weight():
    s = pd.Series([1.0, -1 / 3, 1.0, 1.0, 1.0])
    sig = np.array([0.10, 0.10, 0.02, np.nan, 0.0])
    w = vol.vol_target_weight(s, sig, target=0.10, cap=2.0)
    assert w.iloc[0] == 1.0 and w.iloc[1] == pytest.approx(-1 / 3) and w.iloc[2] == 2.0
    assert np.isnan(w.iloc[3]) and np.isnan(w.iloc[4])
    assert vol.vol_target_weight(1.0, 0.16, target=0.08) == pytest.approx(0.5)


def test_annualise():
    assert vol.annualise(0.0001) == pytest.approx(np.sqrt(0.026))
