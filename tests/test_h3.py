import sys
import pathlib

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from usdjpy.costs import CostModel  # noqa: E402
from usdjpy.horizon import newey_west_t, quotes_at, simulate  # noqa: E402
from usdjpy.rates import _stamp, asof  # noqa: E402


def _series(dates, values):
    return pd.Series(values, index=pd.to_datetime(dates))


def test_us_yield_used_only_after_new_york_evening():
    us = _stamp(_series(["2024-03-04", "2024-03-05"], [4.50, 4.60]), "18:00", "America/New_York")
    t = pd.DatetimeIndex(["2024-03-05 00:00", "2024-03-05 22:30", "2024-03-05 23:30", "2024-03-06 00:00"], tz="UTC")
    got = asof(us, t)
    # 03-05 value is published 18:00 EST = 23:00 UTC on 03-05: not usable at 00:00 or 22:30 UTC that day
    assert list(got["value_date"].dt.strftime("%m-%d")) == ["03-04", "03-04", "03-05", "03-05"]


def test_jgb_same_day_not_usable_at_tokyo_morning():
    jgb = _stamp(_series(["2024-03-05", "2024-03-06"], [0.18, 0.19]), "18:00", "Asia/Tokyo")
    t = pd.DatetimeIndex(["2024-03-06 00:00", "2024-03-06 09:30"], tz="UTC")  # 09:00 JST, 18:30 JST
    got = asof(jgb, t)
    assert list(got["value"]) == [0.18, 0.19]


def test_boj_average_stamped_when_the_months_last_final_print_exists(tmp_path, monkeypatch):
    from usdjpy import rates
    f = tmp_path / "boj.csv"
    f.write_text("month,call_rate_eom,call_rate_avg\n2019/04,-0.05,-0.06\n2024/05,0.07,0.08\n2024/12,0.23,0.24\n")
    monkeypatch.setattr(rates, "BOJ_FILE", f)
    b = rates.boj_call_rate()
    # first JP business day of the next month, 10:00 JST: Golden Week 2019, a Saturday 1st,
    # and New Year (banks shut 31 Dec - 3 Jan, then a weekend)
    assert list(b["available_at"]) == [pd.Timestamp(s, tz="UTC") for s in
                                       ("2019-05-07 01:00", "2024-06-03 01:00", "2025-01-06 01:00")]
    got = asof(b, pd.DatetimeIndex(["2025-01-06 00:00", "2025-01-06 01:30"], tz="UTC"))
    assert list(got["value"]) == [0.08, 0.24]


def test_stale_values_dropped():
    us = _stamp(_series(["2024-01-02"], [4.3]), "18:00", "America/New_York")
    got = asof(us, pd.DatetimeIndex(["2024-01-04 00:00", "2024-01-12 00:00"], tz="UTC"), max_age_days=5)
    assert got["value"].iloc[0] == 4.3 and np.isnan(got["value"].iloc[1])


def test_newey_west_lag0_is_plain_t():
    x = np.random.default_rng(0).normal(0.3, 1, 500)
    plain = x.mean() / (x.std(ddof=0) / np.sqrt(len(x)))
    assert newey_west_t(x, 0) == pytest.approx(plain)
    # positively autocorrelated series: NW t must be smaller than the naive one
    y = pd.Series(x).rolling(5).sum().dropna().to_numpy()
    assert abs(newey_west_t(y, 5)) < abs(newey_west_t(y, 0))


def test_financing_sign_and_skim():
    c = CostModel(financing_skim_pct=2.0)
    # 4% vs 0%, long, 9 days at 150: (4 - 2)% * 150 * 9/360 / 0.01 = 7.5 pips
    assert c.financing_pips(+1, 150.0, 4.0, 0.0, 9) == pytest.approx(7.5)
    assert c.financing_pips(-1, 150.0, 4.0, 0.0, 9) == pytest.approx(-22.5)


def test_simulate_fills_and_exit_day():
    times = pd.bdate_range("2024-01-01", periods=8, tz="UTC")
    bars = pd.DataFrame({"bid": np.arange(8) + 150.00, "ask": np.arange(8) + 150.01},
                        index=times - pd.Timedelta("1min"))
    q = quotes_at(bars, times)
    side = pd.Series([1, 0, -1, 0, 0, 0, 0, 0], index=times)
    zero = pd.Series(0.0, index=times)
    tr = simulate(q, side, hold=2, cost=CostModel(financing_skim_pct=0), usd_rate=zero, jpy_rate=zero)
    assert list(tr["side"]) == [1, -1]
    assert tr["exit_utc"].iloc[0] == times[2]
    assert tr["after_spread_pips"].iloc[0] == pytest.approx((152.00 - 150.01) / 0.01)
    assert tr["after_spread_pips"].iloc[1] == pytest.approx(-(154.01 - 152.00) / 0.01)
