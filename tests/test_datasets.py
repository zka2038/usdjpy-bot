"""HistData DST correction: scripts/histdata_alignment_check.py found that from 2019
HistData's raw clock changes on EU DST dates, so in the US/EU mismatch weeks the
bar labelled T carries the true T+60 price. These tests rebuild that bug on a
synthetic series with a known answer and require the loader fix to undo it exactly.
"""
import sys
import pathlib

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from usdjpy.datasets import fix_histdata_dst, us_eu_dst_mismatch_windows  # noqa: E402

T = pd.Timestamp


def test_mismatch_windows_2019():
    (sa, sb), (aa, ab) = us_eu_dst_mismatch_windows([2019])
    assert sa == T("2019-03-10 07:00", tz="UTC")   # US: 2nd Sunday of March, 02:00 EST
    assert sb == T("2019-03-31 01:00", tz="UTC")   # EU: last Sunday of March, 01:00 UTC
    assert aa == T("2019-10-27 01:00", tz="UTC")   # EU: last Sunday of October
    assert ab == T("2019-11-03 06:00", tz="UTC")   # US: 1st Sunday of November, 02:00 EDT


@pytest.mark.parametrize("year", range(2015, 2027))
def test_mismatch_windows_match_tz_database(year):
    """The US/EU change instants agree with the tz database, every year."""
    def changes(tz):
        h = pd.date_range(f"{year}-01-01", f"{year}-12-31 23:00", freq="h", tz="UTC")
        off = h.tz_convert(tz).map(lambda t: t.utcoffset())
        return list(h[1:][np.asarray(off[1:] != off[:-1])])
    us, eu = changes("America/New_York"), changes("Europe/London")
    (sa, sb), (aa, ab) = us_eu_dst_mismatch_windows([year])
    assert (sa, ab) == (us[0], us[1])
    assert (sb, aa) == (eu[0], eu[1])
    for a, b in ((sa, sb), (aa, ab)):           # both edges in the weekend close
        assert a.day_of_week == 6 and b.day_of_week == 6 and b.hour < 21


def _true_bars(start, end):
    """Weekday minute bars, market closed Fri 21:00 UTC to Sun 21:00 UTC, with a
    price that encodes its own true timestamp so any misplacement is visible."""
    idx = pd.date_range(start, end, freq="min", tz="UTC", inclusive="left")
    dow, h = idx.day_of_week, idx.hour
    closed = (dow == 5) | ((dow == 4) & (h >= 21)) | ((dow == 6) & (h < 21))
    idx = idx[~closed]
    return pd.Series(100 + (idx.asi8 // 60_000_000_000 % 100_000) / 1000, index=idx)


def _with_eu_clock_bug(true):
    """What the stored parquet holds: inside a mismatch window from 2019, the label
    is one hour early (the bar labelled T is the true T+60 bar)."""
    win = us_eu_dst_mismatch_windows(range(2019, true.index[-1].year + 1))
    m = np.any([(true.index >= a) & (true.index < b) for a, b in win], axis=0)
    return pd.Series(true.to_numpy(), index=true.index.where(~m, true.index - pd.Timedelta("60min"))).sort_index()


@pytest.mark.parametrize("start,end", [("2019-03-01", "2019-04-08"), ("2023-10-20", "2023-11-12"),
                                       ("2018-03-01", "2018-04-08")])
def test_fix_recovers_true_timestamps(start, end):
    true = _true_bars(start, end)
    stored = _with_eu_clock_bug(true) if start >= "2019" else true
    fixed = fix_histdata_dst(stored)
    pd.testing.assert_series_equal(fixed, true, check_freq=False)


def test_fix_leaves_pre_2019_and_ordinary_weeks_alone():
    s = _true_bars("2018-03-05", "2018-03-30")
    pd.testing.assert_series_equal(fix_histdata_dst(s), s)
    s = _true_bars("2021-06-01", "2021-06-20")
    pd.testing.assert_series_equal(fix_histdata_dst(s), s)


def test_fix_moves_a_tokyo_entry_bar_by_one_hour():
    """The case that matters to spec 004: the bar stored at 21:59 UTC on Sunday
    2022-03-13 (inside the window) is the true 22:59 bar, the 08:00 JST entry quote."""
    idx = pd.DatetimeIndex([T("2022-03-13 21:59", tz="UTC"), T("2022-04-03 21:59", tz="UTC")])
    out = fix_histdata_dst(pd.Series([1.0, 2.0], index=idx))
    assert list(out.index) == [T("2022-03-13 22:59", tz="UTC"), T("2022-04-03 21:59", tz="UTC")]


def test_fix_works_on_frames():
    idx = pd.DatetimeIndex([T("2020-03-09 00:00", tz="UTC")])
    out = fix_histdata_dst(pd.DataFrame({"close": [1.0]}, index=idx))
    assert out.index[0] == T("2020-03-09 01:00", tz="UTC")
