import datetime as dt
import lzma
import struct
import sys
import pathlib

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from usdjpy.calendars import gotobi_days  # noqa: E402
from usdjpy.costs import CostModel  # noqa: E402
from usdjpy.dukascopy import parse_bi5, ticks_to_minute_bars  # noqa: E402
from usdjpy.events import quote_at, window_trades  # noqa: E402


def test_gotobi_rolls_back_over_weekend_and_holiday():
    days = set(d.date() for d in gotobi_days(dt.date(2024, 5, 1), dt.date(2024, 5, 31)))
    # 2024-05-05 is Sunday + Children's Day; 3-6 May are holidays -> roll back to Thu 2 May
    assert dt.date(2024, 5, 2) in days
    assert dt.date(2024, 5, 10) in days          # Friday, ordinary
    assert dt.date(2024, 5, 24) in days          # 25th is Saturday -> Fri 24th
    assert dt.date(2024, 5, 31) in days          # month-end Friday
    assert dt.date(2024, 5, 5) not in days


def test_commission_minimum_and_pips():
    small, big = CostModel(notional_usd=25_000), CostModel(notional_usd=100_000)
    assert small.commission_usd() == 2.0          # minimum binds
    assert big.commission_usd() == 2.0            # 100k * 0.2bp = $2 exactly
    assert CostModel(notional_usd=1_000_000).commission_usd() == pytest.approx(20.0)
    # at 150, $100k: 1 pip = $6.67, so $2 = 0.3 pips
    assert big.commission_pips(150.0) == pytest.approx(0.3)


def test_parse_bi5_roundtrip():
    recs = [(0, 150_123, 150_120, 1.5, 2.0), (61_000, 150_130, 150_126, 1.0, 1.0)]
    raw = b"".join(struct.pack(">3I2f", *r) for r in recs)
    hour = pd.Timestamp("2024-01-05 13:00", tz="UTC")
    ticks = parse_bi5(lzma.compress(raw, format=lzma.FORMAT_ALONE), hour, 1e-3)
    assert ticks["bid"].iloc[0] == pytest.approx(150.120)
    assert ticks["ask"].iloc[1] == pytest.approx(150.130)
    assert ticks.index[1] == hour + pd.Timedelta(seconds=61)
    bars = ticks_to_minute_bars(ticks)
    assert len(bars) == 2


def _synthetic_bars(drift_on: set, start="2024-05-01", end="2024-05-31"):
    """1-min bars where price rises 10 pips between 08:00 and 09:55 JST on `drift_on` dates."""
    idx = pd.date_range(start, end, freq="1min", tz="UTC")
    mid = np.full(len(idx), 150.0)
    jst = idx.tz_convert("Asia/Tokyo")
    for d in drift_on:
        mask = (jst.date == d) & (jst.time >= dt.time(8, 0)) & (jst.time < dt.time(9, 55))
        if mask.any():
            mid[mask] += np.linspace(0, 0.10, mask.sum())
            after = (jst.date == d) & (jst.time >= dt.time(9, 55))
            mid[after] += 0.10
    return pd.DataFrame({"bid": mid - 0.001, "ask": mid + 0.001, "n_ticks": 10, "spread": 0.002}, index=idx)


def test_window_trade_detects_injected_drift():
    gd = gotobi_days(dt.date(2024, 5, 1), dt.date(2024, 5, 30))
    bars = _synthetic_bars({d.date() for d in gd})
    tr = window_trades(bars, gd, "08:00", "09:55", +1, CostModel(), allow_holdout=True)
    assert len(tr) == len(gd)
    assert tr["mid_pips"].mean() == pytest.approx(10.0, abs=0.2)
    # spread 0.2 pips + 2*(0.3 commission + 0.1 slippage) ≈ 1.0 pip cost
    assert tr["net_pips"].mean() == pytest.approx(9.0, abs=0.3)


def test_holdout_excluded_by_default():
    gd = gotobi_days(dt.date(2025, 1, 1), dt.date(2025, 1, 31))
    bars = _synthetic_bars(set(), "2025-01-01", "2025-01-31")
    assert window_trades(bars, gd, "08:00", "09:55", +1).empty


def test_quote_at_rejects_stale():
    idx = pd.date_range("2024-01-05 00:00", periods=3, freq="1min", tz="UTC")
    bars = pd.DataFrame({"bid": [1.0, 2.0, 3.0], "ask": [1.0, 2.0, 3.0]}, index=idx)
    assert quote_at(bars, pd.Timestamp("2024-01-05 00:02", tz="UTC"))["bid"] == 2.0
    assert quote_at(bars, pd.Timestamp("2024-01-05 01:00", tz="UTC")) is None


def test_download_tree_refuses_to_mix_full_and_partial(tmp_path):
    from usdjpy.dukascopy import TOKYO_MORNING_HOURS, _claim_tree, download_range

    # Pre-manifest tree with files (like data/USDJPY/) counts as full-day.
    legacy = tmp_path / "full" / "USDJPY" / "2003"
    legacy.mkdir(parents=True)
    pd.DataFrame({"bid": [1.0]}).to_parquet(legacy / "2003-05-05.parquet")
    with pytest.raises(ValueError, match="full-day"):
        download_range("USDJPY", dt.date(2003, 5, 6), dt.date(2003, 5, 6),
                       tmp_path / "full", hours=TOKYO_MORNING_HOURS)
    assert not (tmp_path / "full" / "USDJPY" / "_hours.json").exists()

    # Fresh tree is claimed by its first writer; a mismatch is refused either way.
    tokyo = tmp_path / "tokyo" / "USDJPY"
    _claim_tree(tokyo, TOKYO_MORNING_HOURS)
    _claim_tree(tokyo, (0, 1, 22, 23))             # same set, any order
    with pytest.raises(ValueError):
        _claim_tree(tokyo, None)
    with pytest.raises(ValueError):
        _claim_tree(tokyo, (0, 1))


def test_download_trims_closed_hours_and_honours_days(tmp_path, monkeypatch):
    from usdjpy import dukascopy
    calls = []
    monkeypatch.setattr(dukascopy, "fetch_day",
                        lambda sym, day, session, hours, pause: calls.append((day, hours)) or dukascopy._empty())
    # Thu 2023-01-05 .. Mon 2023-01-09
    n = dukascopy.download_range("USDJPY", dt.date(2023, 1, 5), dt.date(2023, 1, 9), tmp_path,
                                 hours=dukascopy.TOKYO_MORNING_HOURS)
    assert calls == [(dt.date(2023, 1, 5), (0, 1, 22, 23)), (dt.date(2023, 1, 6), (0, 1)),
                     (dt.date(2023, 1, 8), (22, 23)), (dt.date(2023, 1, 9), (0, 1, 22, 23))]
    assert n == 12
    calls.clear()
    dukascopy.download_range("USDJPY", dt.date(2023, 1, 10), dt.date(2023, 1, 12), tmp_path,
                             hours=dukascopy.TOKYO_MORNING_HOURS, days={dt.date(2023, 1, 11)})
    assert [d for d, _ in calls] == [dt.date(2023, 1, 11)]


def test_fetch_day_rejects_bad_hours():
    from usdjpy.dukascopy import fetch_day
    with pytest.raises(ValueError):
        fetch_day("USDJPY", dt.date(2024, 1, 2), hours=(23, 24))


def _digest(idx):
    import hashlib
    return len(idx), hashlib.sha1(",".join(idx.strftime("%Y-%m-%d")).encode()).hexdigest()[:12]


def test_gotobi_days_unchanged_for_month_start_ranges():
    """Output pinned to the pre-fix implementation (2026-11-25) on the ranges the studies use."""
    assert _digest(gotobi_days(dt.date(2007, 1, 1), dt.date(2024, 12, 31))) == (1291, "32901c57566b")
    assert _digest(gotobi_days(dt.date(2015, 1, 1), dt.date(2024, 12, 31))) == (717, "c536f8eb7394")
    assert _digest(gotobi_days(dt.date(2007, 1, 1), dt.date(2026, 6, 5))) == (1393, "48e6884dc2d2")


@pytest.mark.parametrize("start", [dt.date(2007, 1, 31), dt.date(2015, 3, 28), dt.date(2023, 12, 30),
                                   dt.date(2019, 5, 6)])
def test_gotobi_days_late_month_start(start):
    """Used to loop until the date overflowed when start was late in a month. Any start
    must give the month-start result clipped to start."""
    end = dt.date(start.year + 1, 6, 30)
    full = gotobi_days(dt.date(start.year, start.month, 1), end)
    assert list(gotobi_days(start, end)) == list(full[full >= pd.Timestamp(start)])


def test_turn_of_month_groups_partition():
    from usdjpy.calendars import jp_business_days, turn_of_month_groups
    g = turn_of_month_groups(dt.date(2007, 1, 1), dt.date(2024, 12, 31))
    a, b, c = g["A_month_end"], g["B_gotobi_proper"], g["C_control"]
    assert len(a.intersection(b)) == len(a.intersection(c)) == len(b.intersection(c)) == 0
    assert len(a) + len(b) + len(c) == len(jp_business_days(dt.date(2007, 1, 1), dt.date(2024, 12, 31)))
    assert (len(a), len(b)) == (216, 1075)
