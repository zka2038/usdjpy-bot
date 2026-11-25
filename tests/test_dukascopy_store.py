"""Offline tests for usdjpy.dukascopy_store: a fake Dukascopy server, no network."""
import datetime as dt
import json
import lzma
import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from usdjpy import dukascopy_store as ds  # noqa: E402


def bi5(records: np.ndarray) -> bytes:
    return lzma.compress(records.tobytes(), format=lzma.FORMAT_ALONE)


def tick_payload(n=5, base=150_000, spread=3):
    r = np.zeros(n, dtype=ds.TICK_REC)
    r["ms"] = np.arange(n) * 1000
    r["bid"] = base + np.arange(n)
    r["ask"] = r["bid"] + spread
    r["bid_vol"], r["ask_vol"] = 1.5, 2.0
    return bi5(r)


def candle_payload(day_minutes=1440, live=range(0, 1440, 2), base=150_000, side_offset=0):
    """Documented order open, close, low, high; every other minute live, the rest flat zero-volume."""
    r = np.zeros(day_minutes, dtype=ds.CANDLE_REC)
    r["sec"] = np.arange(day_minutes) * 60
    o = base + side_offset + (np.arange(day_minutes) % 7)
    c = o + 2
    r["a"], r["b"], r["c"], r["d"] = o, c, o - 3, c + 4   # open, close, low, high
    vol = np.zeros(day_minutes, dtype=np.float32)
    vol[list(live)] = 3.0
    r["vol"] = vol
    return bi5(r)


class Resp:
    def __init__(self, code, content=b""):
        self.status_code, self.content = code, content


class FakeSession:
    """Serves ticks for weekday hours, candles for weekdays; can inject failures."""

    def __init__(self, fail_urls=(), flaky=None, weekend_ticks=False):
        self.calls, self.fail_urls, self.flaky, self.weekend_ticks = [], set(fail_urls), dict(flaky or {}), weekend_ticks
        self.headers = {}

    def get(self, url, timeout=None):
        self.calls.append(url)
        if url in self.fail_urls:
            return Resp(503)
        if self.flaky.get(url, 0) > 0:
            self.flaky[url] -= 1
            return Resp(429)
        parts = url.split("/datafeed/")[1].split("/")
        sym, y, m0, d, name = parts[0], int(parts[1]), int(parts[2]), int(parts[3]), parts[4]
        day = dt.date(y, m0 + 1, d)
        if name.endswith("h_ticks.bi5"):
            h = dt.datetime(y, m0 + 1, d, int(name[:2]))
            if ds.is_weekend_hour(h) and not self.weekend_ticks:
                return Resp(200, b"")
            return Resp(200, tick_payload())
        if "candles_min_1" in name:
            if day.weekday() == 5:
                return Resp(404)
            return Resp(200, candle_payload(side_offset=0 if name.startswith("BID") else 3))
        return Resp(404)


def make_fetcher(session):
    return ds.Fetcher(ds.AdaptiveRate(1e6), retries=3, session_factory=lambda: session)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(ds.time, "sleep", lambda s: None)


TODAY = dt.date(2026, 11, 25)


def test_urls_use_zero_based_month():
    assert ds.tick_url("USDJPY", dt.datetime(2024, 1, 5, 13)).endswith("USDJPY/2024/00/05/13h_ticks.bi5")
    assert ds.candle_url("USDJPY", dt.date(2024, 12, 31), "ASK").endswith("USDJPY/2024/11/31/ASK_candles_min_1.bi5")


def test_weekend_hours():
    assert ds.is_weekend_hour(dt.datetime(2024, 1, 6, 12))       # Saturday
    assert ds.is_weekend_hour(dt.datetime(2024, 1, 5, 22))       # Fri 22:00 UTC
    assert not ds.is_weekend_hour(dt.datetime(2024, 1, 5, 21))   # Fri 21:00 still fetched (winter close is 22:00)
    assert ds.is_weekend_hour(dt.datetime(2024, 1, 7, 19))       # Sun 19:00
    assert not ds.is_weekend_hour(dt.datetime(2024, 1, 7, 20))   # Sun 20:00 fetched (opens 21-22)
    hours, skipped = ds.month_hours(2024, 1, dt.date(2024, 1, 1), dt.date(2024, 1, 31), all_hours=False)
    assert len(hours) + len(skipped) == 31 * 24 and len(skipped) > 0


def test_decode_ticks_is_lossless_integers():
    df = ds.decode_ticks(tick_payload(), dt.datetime(2024, 1, 5, 13))
    assert df["bid"].dtype == np.int32 and df["bid"].iloc[0] == 150_000 and df["ask"].iloc[0] == 150_003
    assert df.index[1] == pd.Timestamp("2024-01-05 13:00:01", tz="UTC")


def test_candle_order_detected_and_mismatch_raises():
    df, order = ds.decode_candles(candle_payload(), dt.date(2024, 1, 5))
    assert order == "adcb"   # fields a,d,c,b -> open,high,low,close: the documented open,close,low,high layout
    assert (df["l"] <= df[["o", "c"]].min(axis=1)).all() and (df["h"] >= df[["o", "c"]].max(axis=1)).all()
    r = np.zeros(10, dtype=ds.CANDLE_REC)
    r["sec"] = np.arange(10) * 60
    r["a"], r["b"], r["c"], r["d"], r["vol"] = 100, 90, 120, 80, 1.0   # inconsistent under both orders
    with pytest.raises(ds.ValidationError):
        ds.decode_candles(bi5(r), dt.date(2024, 1, 5))


def test_m1_month_writes_bid_ask_and_drops_flats(tmp_path):
    s = FakeSession()
    man = ds.download("m1", "USDJPY", dt.date(2024, 1, 1), dt.date(2024, 1, 31), tmp_path,
                      fetcher=make_fetcher(s), today=TODAY, log=lambda m: None)[0]
    assert man["status"] == "complete" and man["errors"] == []
    df = pd.read_parquet(tmp_path / "USDJPY/m1/2024/USDJPY_m1_202401.parquet")
    weekdays = sum(1 for d in pd.date_range("2024-01-01", "2024-01-31") if d.weekday() != 5)
    assert len(df) == weekdays * 720 and man["flat_minutes_dropped"] == weekdays * 720
    assert (df["ask_c"] - df["bid_c"] == 3).all() and df["bid_c"].dtype == np.int32
    loaded = ds.load_m1("USDJPY", tmp_path)
    assert loaded["bid_c"].iloc[0] == pytest.approx(150.002)


def test_ticks_month_complete_skip_and_resume(tmp_path):
    s = FakeSession()
    f = make_fetcher(s)
    run = lambda: ds.download("ticks", "USDJPY", dt.date(2024, 1, 1), dt.date(2024, 2, 29), tmp_path,
                              fetcher=f, today=TODAY, log=lambda m: None)
    mans = run()
    assert [m["status"] for m in mans] == ["complete", "complete"]
    jan = json.loads((tmp_path / "USDJPY/ticks/2024/USDJPY_ticks_202401.json").read_text())
    assert jan["ticks"] == jan["hours_scheduled"] * 5 and jan["checks"]["crossed_share"] == 0
    n = len(s.calls)
    assert run() == [] and len(s.calls) == n          # nothing re-downloaded


def test_failed_hour_marks_month_failed_and_retries_next_run(tmp_path):
    bad = ds.tick_url("USDJPY", dt.datetime(2024, 1, 10, 3))
    s = FakeSession(fail_urls={bad})
    man = ds.download("ticks", "USDJPY", dt.date(2024, 1, 1), dt.date(2024, 1, 31), tmp_path,
                      fetcher=make_fetcher(s), today=TODAY, log=lambda m: None)[0]
    assert man["status"] == "failed" and bad in man["errors"][0]
    assert not (tmp_path / "USDJPY/ticks/2024/USDJPY_ticks_202401.parquet").exists()
    s.fail_urls.clear()
    man2 = ds.download("ticks", "USDJPY", dt.date(2024, 1, 1), dt.date(2024, 1, 31), tmp_path,
                       fetcher=make_fetcher(s), today=TODAY, log=lambda m: None)[0]
    assert man2["status"] == "complete"


def test_throttling_backs_off_then_succeeds(tmp_path):
    url = ds.tick_url("USDJPY", dt.datetime(2024, 1, 10, 3))
    s = FakeSession(flaky={url: 2})
    f = make_fetcher(s)
    ds.download("ticks", "USDJPY", dt.date(2024, 1, 10), dt.date(2024, 1, 10), tmp_path,
                fetcher=f, today=TODAY, log=lambda m: None)
    assert f.rate.throttle_events == 2 and f.rate.rate < 1e6


def test_weekend_leak_fails_month(tmp_path):
    s = FakeSession(weekend_ticks=True)
    man = ds.download("ticks", "USDJPY", dt.date(2024, 1, 1), dt.date(2024, 1, 31), tmp_path,
                      fetcher=make_fetcher(s), today=TODAY, log=lambda m: None)[0]
    assert man["status"] == "failed" and "--all-hours" in man["errors"][0]


def test_partial_months(tmp_path):
    # current month, and a month clipped by --start, must stay 'partial' so later runs fill them
    s = FakeSession()
    cur = ds.download("m1", "USDJPY", dt.date(2026, 11, 2), dt.date(2026, 11, 24), tmp_path,
                      fetcher=make_fetcher(s), today=TODAY, log=lambda m: None)[0]
    clipped = ds.download("m1", "USDJPY", dt.date(2024, 3, 15), dt.date(2024, 3, 31), tmp_path,
                          fetcher=make_fetcher(s), today=TODAY, log=lambda m: None)[0]
    assert cur["status"] == "partial" and clipped["status"] == "partial"
    again = ds.download("m1", "USDJPY", dt.date(2024, 3, 1), dt.date(2024, 3, 31), tmp_path,
                        fetcher=make_fetcher(s), today=TODAY, log=lambda m: None)
    assert again[0]["status"] == "complete"


def test_price_band_catches_bad_scaling(tmp_path, monkeypatch):
    monkeypatch.setitem(ds.POINT, "USDJPY", 1e-2)      # pretend we mis-scaled by 10x -> ~1500 JPY
    man = ds.download("ticks", "USDJPY", dt.date(2024, 1, 10), dt.date(2024, 1, 10), tmp_path,
                      fetcher=make_fetcher(FakeSession()), today=TODAY, log=lambda m: None)[0]
    assert man["status"] == "failed" and "plausible band" in man["errors"][0]


def test_raw_cache_avoids_redownload(tmp_path):
    s = FakeSession()
    f = make_fetcher(s)
    f.raw_cache = tmp_path / "raw"
    kw = dict(fetcher=f, today=TODAY, log=lambda m: None, overwrite=True)
    ds.download("m1", "USDJPY", dt.date(2024, 1, 1), dt.date(2024, 1, 31), tmp_path, **kw)
    n = len(s.calls)
    ds.download("m1", "USDJPY", dt.date(2024, 1, 1), dt.date(2024, 1, 31), tmp_path, **kw)
    assert len(s.calls) == n and f.cache_hits > 0


def test_status_table(tmp_path):
    ds.download("m1", "USDJPY", dt.date(2024, 1, 1), dt.date(2024, 2, 29), tmp_path,
                fetcher=make_fetcher(FakeSession()), today=TODAY, log=lambda m: None)
    st = ds.status("USDJPY", tmp_path)
    assert st.loc[("m1", 2024), "complete"] == 2
