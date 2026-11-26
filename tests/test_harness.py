"""Task 5 harness gaps, each against a known answer on synthetic data: financing rolls,
the timestamp-based trade helper, MAE, summarize periods, bid OHLC in load_minute, the
H.10 loader, and the rebalance simulator."""
import datetime as dt
import math
import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from usdjpy import datasets, portfolio  # noqa: E402
from usdjpy.costs import PIP, PESSIMISTIC, CostModel, roll_times  # noqa: E402
from usdjpy.events import (PERIODS, PERIODS_2015_2024, at_local, summarize,  # noqa: E402
                           timestamp_trades, window_trades)

UTC = "UTC"


def ts(s):
    return pd.Timestamp(s, tz=UTC)


def rate_frame(value, start="2000-01-01"):
    """A constant rate in the usdjpy.rates format, published long before any test date."""
    t = pd.DatetimeIndex([pd.Timestamp(start)])
    return pd.DataFrame({"value": [float(value)], "available_at": t.tz_localize(UTC)}, index=t)


def flat_bars(start, end, mid=150.0, spread=0.004, ohlc=False):
    idx = pd.date_range(start, end, freq="1min", tz=UTC)
    m = np.full(len(idx), mid)
    df = pd.DataFrame({"bid": m - spread / 2, "ask": m + spread / 2}, index=idx)
    if ohlc:
        df["bid_open"] = df["bid_high"] = df["bid_low"] = df["bid"]
    return df


# ------------------------------------------------------------------ rolls (financing nights)

@pytest.mark.parametrize("a, b, n", [
    ("2024-05-09 23:00", "2024-05-10 02:00", 0),    # spec 004's Tokyo morning: no night
    ("2024-01-10 21:50", "2024-01-11 21:50", 1),    # 16:50 -> 16:50 ET, EST
    ("2024-07-10 20:50", "2024-07-11 20:50", 1),    # same, EDT
    ("2024-05-10 20:50", "2024-05-13 20:50", 3),    # Fri 16:50 ET -> Mon 16:50 ET: weekend is 3
    ("2024-05-12 23:00", "2024-05-13 07:00", 0),    # spec 006 exit A: Mon 08:00 -> 16:00 JST
])
def test_roll_counts(a, b, n):
    assert len(roll_times(ts(a), ts(b))) == n


def test_rolls_stay_at_17_new_york_across_dst():
    # Sat 9 Mar -> Tue 12 Mar 2024: US clocks change on Sun 10 Mar
    r = roll_times(ts("2024-03-09 12:00"), ts("2024-03-12 12:00"))
    assert list(r) == [ts("2024-03-09 22:00"), ts("2024-03-10 21:00"), ts("2024-03-11 21:00")]


def test_roll_at_entry_counts_at_exit_does_not():
    roll = ts("2024-01-10 22:00")   # 17:00 EST
    assert len(roll_times(roll, roll + pd.Timedelta("1h"))) == 1
    assert len(roll_times(roll - pd.Timedelta("1h"), roll)) == 0


# ------------------------------------------------------------------ at_local

def test_at_local_et_across_dst_and_offsets():
    d = pd.DatetimeIndex(["2024-01-12", "2024-07-12"])           # Fridays
    assert list(at_local(d, "16:50", "America/New_York")) == [ts("2024-01-12 21:50"), ts("2024-07-12 20:50")]
    t3 = at_local(d, "16:50", "America/New_York", pd.offsets.BDay(3))
    assert list(t3.tz_convert("America/New_York").day_name()) == ["Wednesday", "Wednesday"]
    thu = at_local(pd.DatetimeIndex(["2024-05-13"]), "16:50", "America/New_York", pd.offsets.Week(weekday=3))
    assert thu[0] == ts("2024-05-16 20:50")
    assert at_local(pd.DatetimeIndex(["2024-05-13"]), "08:00", "Asia/Tokyo")[0] == ts("2024-05-12 23:00")


def test_at_local_refuses_a_time_that_does_not_exist():
    with pytest.raises(Exception):
        at_local(pd.DatetimeIndex(["2024-03-10"]), "02:30", "America/New_York")


# ------------------------------------------------------------------ timestamp_trades

def drift_bars():
    """Mid 150 until Mon 2024-05-13 00:00 UTC, then +1 pip a minute for 60 minutes, then flat."""
    b = flat_bars("2024-05-06", "2024-05-20")
    up = np.clip((b.index - ts("2024-05-13 00:00")) / pd.Timedelta("1min"), 0, 60) * PIP
    b["bid"] += up
    b["ask"] += up
    return b


def test_timestamp_trades_matches_window_trades_on_the_same_window():
    b = drift_bars()
    w = window_trades(b, pd.DatetimeIndex(["2024-05-13"]), "08:00", "10:00", +1)
    e = at_local(pd.DatetimeIndex(["2024-05-13"]), "08:00", "Asia/Tokyo")
    x = at_local(pd.DatetimeIndex(["2024-05-13"]), "10:00", "Asia/Tokyo")
    t = timestamp_trades(b, e, x, +1, dates=pd.DatetimeIndex(["2024-05-13"]))
    pd.testing.assert_frame_equal(t.drop(columns="side"), w)
    # entry 23:00 reads bar 22:59 (150.00); exit 01:00 reads bar 00:59, 59 minutes into the drift
    assert t["mid_pips"].iloc[0] == pytest.approx(59.0)


def test_multi_day_hold_pays_financing_per_night():
    b = drift_bars()
    usd, jpy = rate_frame(5.0), rate_frame(0.0)
    e = [ts("2024-05-10 20:50")]                 # Fri 16:50 ET
    x = [ts("2024-05-15 20:50")]                 # Wed 16:50 ET: 5 nights
    cm = CostModel()
    for side in (+1, -1):
        t = timestamp_trades(b, e, x, side, cm, rates=(usd, jpy))
        r = t.iloc[0]
        expect = cm.financing_pips(side, r.mid_in, 5.0, 0.0, 5)
        assert r.nights == 5
        assert r.financing_pips == pytest.approx(expect)
        assert r.net_pips == pytest.approx(r.after_spread_pips - cm.round_trip_pips(150.0 + 0.002 * side) + expect, abs=1e-6)
    # the skim alone: 2% a year at 150 is 0.833 pips a night
    assert cm.financing_pips(+1, 150.0, 0.0, 0.0, 1) == pytest.approx(-150 * 0.02 / 360 / PIP)


def test_financing_uses_the_rate_published_before_each_roll():
    b = flat_bars("2024-05-06", "2024-05-20")
    t0 = pd.DatetimeIndex(["2000-01-01", "2024-05-14"])
    usd = pd.DataFrame({"value": [5.0, 6.0], "available_at": t0.tz_localize(UTC) + pd.Timedelta("18h")}, index=t0)
    t = timestamp_trades(b, [ts("2024-05-13 20:50")], [ts("2024-05-15 20:50")], +1,
                         CostModel(financing_skim_pct=0.0), rates=(usd, rate_frame(0.0)))
    # rolls Mon 21:00 UTC (5%, the 6% prints Tue 18:00 UTC) and Tue 21:00 UTC (6%)
    assert t["financing_pips"].iloc[0] == pytest.approx(150 * (5 + 6) / 100 / 360 / PIP)


def test_overnight_hold_without_rates_raises():
    b = flat_bars("2024-05-06", "2024-05-20")
    with pytest.raises(ValueError, match="roll"):
        timestamp_trades(b, [ts("2024-05-13 20:50")], [ts("2024-05-14 20:50")], +1)
    with pytest.raises(ValueError, match="roll"):
        window_trades(b, pd.DatetimeIndex(["2024-05-13"]), "16:50", "16:50", -1, tz="America/New_York")


def test_holdout_by_exit_time():
    b = flat_bars("2024-12-27", "2025-01-03")
    rates = (rate_frame(5.0), rate_frame(0.0))
    # labelled 2024-12-31, exits 2025-01-01: reads holdout bars, so skipped by default
    w = window_trades(b, pd.DatetimeIndex(["2024-12-31"]), "16:50", "16:50", -1, tz="America/New_York", rates=rates)
    assert w.empty
    assert len(window_trades(b, pd.DatetimeIndex(["2024-12-31"]), "16:50", "16:50", -1,
                             tz="America/New_York", rates=rates, allow_holdout=True)) == 1
    assert timestamp_trades(b, [ts("2024-12-31 10:00")], [ts("2025-01-01 00:00")], +1, rates=rates).empty


def test_side_per_trade_and_validation():
    b = drift_bars()
    e = [ts("2024-05-13 00:00"), ts("2024-05-13 00:00")]
    x = [ts("2024-05-13 01:00"), ts("2024-05-13 01:00")]
    t = timestamp_trades(b, e, x, [1, -1], dates=pd.DatetimeIndex(["2024-05-13", "2024-05-14"]))
    assert list(t["side"]) == [1, -1]
    assert t["mid_pips"].tolist() == pytest.approx([59.0, -59.0])    # exit reads bar 00:59
    with pytest.raises(ValueError):
        timestamp_trades(b, e, e, +1)


def test_mae_counts_only_bars_inside_the_hold():
    b = flat_bars("2024-05-12 12:00", "2024-05-14", ohlc=True)
    b.loc[ts("2024-05-13 00:30"), "bid_low"] -= 20 * PIP     # inside the hold
    b.loc[ts("2024-05-13 00:30"), "bid_high"] += 7 * PIP
    b.loc[ts("2024-05-13 01:00"), "bid_low"] -= 99 * PIP     # bar labelled exit: after the exit fill
    b.loc[ts("2024-05-12 23:59"), "bid_low"] -= 99 * PIP     # the entry bar itself
    long = timestamp_trades(b, [ts("2024-05-13 00:00")], [ts("2024-05-13 01:00")], +1)
    short = timestamp_trades(b, [ts("2024-05-13 00:00")], [ts("2024-05-13 01:00")], -1)
    assert long["mae_pips"].iloc[0] == pytest.approx(-20.0)
    assert short["mae_pips"].iloc[0] == pytest.approx(-7.0)
    assert np.isnan(timestamp_trades(flat_bars("2024-05-12 12:00", "2024-05-14"), [ts("2024-05-13 00:00")],
                                     [ts("2024-05-13 01:00")], +1)["mae_pips"].iloc[0])


# ------------------------------------------------------------------ summarize periods

def test_summarize_periods_default_unchanged_and_split():
    idx = pd.DatetimeIndex(["2016-03-01", "2019-12-31", "2020-01-01", "2024-12-31"])
    tr = pd.DataFrame({"net_pips": [1.0, 3.0, -1.0, -3.0]}, index=idx)
    s = summarize(tr, periods=PERIODS_2015_2024)
    assert s.loc["2015-2019", "n"] == 2 and s.loc["2015-2019", "mean"] == 2.0
    assert s.loc["2020-2024", "n"] == 2 and s.loc["2020-2024", "mean"] == -2.0
    assert list(summarize(tr).index) == ["all", *[p for p in PERIODS if p != "2005-2014"]]


# ------------------------------------------------------------------ load_minute(ohlc=True)

def _write_sources(root: pathlib.Path):
    """Tiny stand-ins for the three bar files, with distinct open/high/low/close."""
    def bid_ohlc(start, n, base):
        idx = pd.date_range(start, periods=n, freq="1min", tz=UTC, name="ts_utc")
        c = base + np.arange(n) * PIP
        return pd.DataFrame({"open": c - PIP, "high": c + 3 * PIP, "low": c - 4 * PIP, "close": c}, index=idx)
    du = bid_ohlc("2014-12-31 23:50", 20, 120.0)
    du["volume"] = 1.0
    du.to_parquet(root / "dukascopy_bid_2007_2023.parquet")
    bid_ohlc("2015-01-01 00:05", 20, 121.0).to_parquet(root / "histdata_bid_2015_2025.parquet")
    e = bid_ohlc("2015-01-01 00:20", 20, 122.0)
    e = pd.DataFrame({"bid_open": e.open, "bid_high": e.high, "bid_low": e.low, "bid": e.close,
                      "ask": e.close + 0.003, "spread_mean": 0.003, "n_ticks": 5}, index=e.index)
    e.to_parquet(root / "eightcap_bidask_2024_2026.parquet")


@pytest.mark.parametrize("source", ["dukascopy", "histdata", "eightcap", "combined"])
def test_load_minute_ohlc_adds_bid_extremes_and_changes_nothing_else(tmp_path, monkeypatch, source):
    _write_sources(tmp_path)
    monkeypatch.setattr(datasets, "BARS", tmp_path)
    plain = datasets.load_minute(source)
    full = datasets.load_minute(source, ohlc=True)
    assert list(full.columns) == [*plain.columns, *datasets.OHLC_COLS]
    pd.testing.assert_frame_equal(full[plain.columns], plain)
    assert (full["bid_high"] - full["bid"]).round(6).eq(0.03).all()
    assert (full["bid"] - full["bid_low"]).round(6).eq(0.04).all()
    assert (full["bid"] - full["bid_open"]).round(6).eq(0.01).all()


def test_histdata_ohlc_shifted_with_the_close():
    """OHLC must move with the close inside a US/EU DST mismatch week."""
    idx = pd.date_range("2019-03-11 00:00", periods=3, freq="1min", tz=UTC)
    raw = pd.DataFrame({"open": [1.0, 2.0, 3.0], "high": [1.5, 2.5, 3.5], "low": [0.5, 1.5, 2.5],
                        "close": [1.1, 2.1, 3.1]}, index=idx)
    f = datasets.fix_histdata_dst(raw)
    assert f.index[0] == idx[0] + pd.Timedelta("60min")
    assert f.iloc[0].tolist() == raw.iloc[0].tolist()


# ------------------------------------------------------------------ h10_daily

def test_h10_daily_noon_new_york_and_holidays_dropped(tmp_path, monkeypatch):
    (tmp_path / "macro").mkdir()
    (tmp_path / "macro" / "fred_h10_usdjpy_daily_1971_2026.csv").write_text(
        "date,JPY_per_USD\n2024-01-12,145.1\n2024-01-15,\n2024-07-12,158.0\n")
    monkeypatch.setattr(datasets, "DATA_DIR", tmp_path)
    h = datasets.h10_daily()
    assert list(h.index) == [pd.Timestamp("2024-01-12"), pd.Timestamp("2024-07-12")]
    assert list(h["observed_at"]) == [ts("2024-01-12 17:00"), ts("2024-07-12 16:00")]
    assert h["rate"].tolist() == [145.1, 158.0]


# ------------------------------------------------------------------ costs

def test_commission_by_notional():
    cm = CostModel()
    assert cm.commission_usd() == 2.0                      # 100k: 2.0 by bp and by minimum
    assert cm.commission_usd(1_000_000) == pytest.approx(20.0)
    assert cm.commission_usd(-50_000) == 2.0               # minimum; sign ignored


# ------------------------------------------------------------------ portfolio

MON = pd.date_range("2024-05-05 23:00", periods=6, freq="7D", tz=UTC)   # Mon 08:00 JST


def quotes(mids, spread_pips=0.4, index=MON):
    return portfolio.quotes_from_mid(pd.Series(mids, index=index[:len(mids)], dtype=float), spread_pips)


NO_CARRY = (rate_frame(0.0), rate_frame(0.0))


def test_round_trip_at_flat_price_costs_what_window_trades_charges():
    cm = CostModel()
    q = quotes([159.0, 159.0], spread_pips=0.36)
    tgt = pd.Series([100_000.0, 0.0], index=q.index)
    r = portfolio.simulate(q, tgt, CostModel(financing_skim_pct=0.0), rates=NO_CARRY)
    # window_trades on a flat 159 with the same spread: net = -(spread + round trip) pips
    b = flat_bars("2024-05-12 23:00", "2024-05-13 03:00", mid=159.0, spread=0.0036)
    w = window_trades(b, pd.DatetimeIndex(["2024-05-13"]), "09:00", "11:00", +1, cm)
    usd_per_pip = 100_000 * PIP / 159.0
    # window_trades prices commission at the fill (the ask), the simulator at mid: 1e-5 apart
    assert r["net_usd"].sum() == pytest.approx(w["net_pips"].iloc[0] * usd_per_pip, rel=1e-5)
    assert r["net_usd"].sum() == pytest.approx(-(0.36 + cm.round_trip_pips(159.0)) * usd_per_pip, rel=1e-9)


def test_price_pnl_and_weekly_financing():
    q = quotes([150.0, 151.0, 151.0])
    tgt = pd.Series(100_000.0, index=q.index)
    cm = CostModel(slippage_pips=0.0, commission_bp=0.0, min_commission_usd=0.0)
    r = portfolio.simulate(q, tgt, cm, rates=(rate_frame(5.0), rate_frame(0.0)))
    assert r["price_pnl_usd"].iloc[1] == pytest.approx(100_000 * 1.0 / 151.0)
    assert (r["nights"].iloc[1:] == 7).all()
    # 5% - 0% - 2% skim = 3% a year on 100k, 7 nights act/360
    assert r["financing_usd"].iloc[1:].tolist() == pytest.approx([100_000 * 0.03 * 7 / 360] * 2)
    short = portfolio.simulate(q, -tgt, cm, rates=(rate_frame(5.0), rate_frame(0.0)))
    assert short["financing_usd"].iloc[1] == pytest.approx(-100_000 * 0.07 * 7 / 360)


def test_rebalance_threshold_and_sign_changes():
    q = quotes([150.0] * 6)
    tgt = pd.Series([100_000, 150_000, 250_000, np.nan, -100_000, 0.0], index=q.index)
    r = portfolio.simulate(q, tgt, rates=NO_CARRY)
    assert r["trade_usd"].tolist() == [100_000, 0, 150_000, 0, -350_000, 100_000]
    assert r["position_after"].tolist() == [100_000, 100_000, 250_000, 250_000, -100_000, 0]


def test_missing_quote_is_skipped_and_marked_through():
    q = quotes([150.0, np.nan, 152.0])
    r = portfolio.simulate(q, pd.Series(100_000.0, index=q.index), rates=(rate_frame(0.0), rate_frame(0.0)))
    assert len(r) == 2 and r.attrs["skipped_no_quote"] == 1
    assert r["price_pnl_usd"].iloc[1] == pytest.approx(100_000 * 2.0 / 152.0)
    assert r["nights"].iloc[1] == 14


def test_simulator_holdout_and_missing_rates():
    idx = pd.date_range("2024-12-22 23:00", periods=3, freq="7D", tz=UTC)    # last is 2025-01-05
    q = quotes([150.0, 150.0, 150.0], index=idx)
    r = portfolio.simulate(q, pd.Series(100_000.0, index=idx), rates=NO_CARRY)
    assert r.index.max() < ts("2025-01-01") and r.attrs["open_position_usd"] == 100_000
    with pytest.raises(ValueError, match="roll"):
        portfolio.simulate(q, pd.Series(100_000.0, index=idx))


def test_overlay_helpers():
    tgt = pd.Series([100_000.0, -100_000.0, 200_000.0], index=MON[:3])
    m = pd.Series([0.5, 0.5, 0.0], index=MON[:3])
    assert portfolio.apply_multiplier(tgt, m).tolist() == [50_000, -100_000, 0]
    assert portfolio.apply_multiplier(tgt, m, "both").tolist() == [50_000, -50_000, 0]
    with pytest.raises(ValueError):
        portfolio.apply_multiplier(tgt, m.iloc[:2])
    daily = pd.date_range(MON[0] - pd.Timedelta("1D"), MON[2], freq="1D")
    s = portfolio.on_schedule(tgt, daily)
    assert np.isnan(s.iloc[0]) and s.iloc[1] == 100_000 and s.iloc[8] == -100_000


def test_summary_known_answer():
    s = portfolio.summary(pd.Series([1.0, -2.0, 3.0, -4.0, 1.0]), periods_per_year=52)
    assert s["max_drawdown"] == 4.0          # equity 0,1,-1,2,-2,-1: peak 2 to -2
    assert s["worst"] == -4.0 and s["cvar_5"] == -4.0
    assert s["total"] == -1.0
    assert s["sharpe_ann"] == pytest.approx(-0.2 / np.std([1, -2, 3, -4, 1], ddof=1) * math.sqrt(52))
    assert s["ann_return_over_mdd"] == pytest.approx(-0.2 * 52 / 4.0)


def test_pessimistic_costs_more():
    q = quotes([150.0, 150.0])
    tgt = pd.Series([300_000.0, 0.0], index=q.index)
    base = portfolio.simulate(q, tgt, rates=NO_CARRY)["cost_usd"].sum()
    pess = portfolio.simulate(q, tgt, PESSIMISTIC, rates=NO_CARRY)["cost_usd"].sum()
    assert pess - base == pytest.approx(2 * 300_000 * 0.20 * PIP / 150.0)
