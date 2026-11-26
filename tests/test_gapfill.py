"""Spec 004 gap fill, on synthetic tick trees in tmp_path. No real data, no network.

Required by the during-fetch handoff: a constructed source offset that step 0 must
catch, and a gap that must be filled from the right source. Also: the tree loader,
the vectorised quote lookup, the measured-spread hierarchy of *Amendment: field
standards*, the completion gate, and the tradeability labels.
"""
import datetime as dt
import importlib.util
import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from usdjpy import gapfill as gf  # noqa: E402
from usdjpy import tradeability as tr  # noqa: E402
from usdjpy.costs import PESSIMISTIC, era_spread_multiplier  # noqa: E402
from usdjpy.datasets import _with_synthetic_ask  # noqa: E402
from usdjpy.events import quote_at, window_trades  # noqa: E402

PROFILE = pd.Series(0.003, index=range(24))   # flat 0.3-pip synthetic spread, no data file needed


def price(ts: pd.DatetimeIndex) -> np.ndarray:
    """A deterministic price that varies minute to minute, so a copy shifted by
    minutes or an hour is distinguishable from an aligned one."""
    minutes = ((ts - pd.Timestamp("2000-01-01", tz="UTC")) // pd.Timedelta("1min")).to_numpy()
    return 100 + np.sin(minutes / 37.0) * 0.5 + (minutes % 997) * 0.0005


def write_tree(root: pathlib.Path, utc_days, spread=0.004, level=0.0, shift_min=0, hours=(22, 23, 0, 1)):
    """Tick files root/USDJPY/YYYY/YYYY-MM-DD.parquet, ticks every 15 s in `hours`.
    `level` adds to the bid; `shift_min` stamps each tick shift_min minutes late."""
    for d in utc_days:
        d = pd.Timestamp(d, tz="UTC")
        idx = pd.DatetimeIndex([])
        for h in hours:
            idx = idx.append(pd.date_range(d + pd.Timedelta(hours=h), periods=240, freq="15s"))
        true_t = idx
        bid = price(true_t) + level
        sp = spread(true_t) if callable(spread) else np.full(len(idx), spread)
        df = pd.DataFrame({"bid": bid, "ask": bid + sp, "bid_vol": 1.0, "ask_vol": 1.0},
                          index=pd.DatetimeIndex(idx + pd.Timedelta(minutes=shift_min), name="ts")).sort_index()
        p = root / "USDJPY" / f"{d.year}" / f"{d.date()}.parquet"
        p.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(p)


def utc_days_for(jst_days):
    return sorted({(pd.Timestamp(d) - pd.Timedelta(days=k)).date() for d in jst_days for k in (0, 1)})


def bid_only_bars(utc_days, level=0.0, drop=()):
    """As-run style 1-min bid bars with a synthetic ask, source 'histdata'."""
    idx = pd.DatetimeIndex([])
    for d in utc_days:
        d = pd.Timestamp(d, tz="UTC")
        for h in (22, 23, 0, 1):
            idx = idx.append(pd.date_range(d + pd.Timedelta(hours=h), periods=60, freq="1min"))
    idx = idx[~idx.isin(pd.DatetimeIndex(list(drop)))].sort_values()
    bid = pd.Series(price(idx + pd.Timedelta(seconds=45)) + level, index=idx)
    return _with_synthetic_ask(bid, "histdata", profile=PROFILE)


# ------------------------------------------------------------------ loader

def test_load_tree_last_quote_and_spreads(tmp_path):
    write_tree(tmp_path, ["2009-03-09"], spread=lambda t: np.where(t.second == 45, 0.006, 0.002))
    (tmp_path / "USDJPY" / "2009" / "._2009-03-09.parquet").write_bytes(b"appledouble")
    empty = tmp_path / "USDJPY" / "2009" / "2009-03-10.parquet"
    pd.DataFrame(columns=["bid", "ask", "bid_vol", "ask_vol"], dtype=float).to_parquet(empty)
    bars = gf.load_tree(tmp_path)
    row = bars.loc[pd.Timestamp("2009-03-09 22:00", tz="UTC")]
    assert row.spread_last == pytest.approx(0.006)            # last tick of the minute is :45
    assert row.spread_mean == pytest.approx((0.002 * 3 + 0.006) / 4)
    assert row.n_ticks == 4
    assert bars.index.min() >= pd.Timestamp("2009-03-09", tz="UTC")


def test_quotes_at_matches_quote_at(tmp_path):
    bars = bid_only_bars(["2009-03-09"], drop=pd.date_range("2009-03-09 22:10", "2009-03-09 22:30", freq="1min", tz="UTC"))
    ts = pd.date_range("2009-03-09 21:55", "2009-03-10 02:10", freq="7min", tz="UTC")
    got = gf.quotes_at(bars, ts)
    for t in ts:
        q = quote_at(bars, t)
        if q is None:
            assert np.isnan(got.loc[t, "bid"])
        else:
            assert got.loc[t, "bid"] == pytest.approx(q["bid"]) and got.loc[t, "ask"] == pytest.approx(q["ask"])


# ------------------------------------------------------------------ step 0

def _step0(tmp_path, **kw):
    days = ["2009-03-09", "2009-03-10", "2009-03-11", "2009-03-12"]
    write_tree(tmp_path, days, **kw)
    tree = gf.load_tree(tmp_path)
    ref = bid_only_bars(days)["bid"]
    return gf.step0_verdict(gf.step0_table(tree["bid"], ref))


def test_step0_passes_aligned_same_venue(tmp_path):
    ok, why = _step0(tmp_path)
    assert ok, why


def test_step0_catches_an_hour_offset(tmp_path):
    ok, why = _step0(tmp_path, shift_min=60)
    assert not ok and any("smallest at offset" in w for w in why)


def test_step0_catches_a_level_offset(tmp_path):
    ok, why = _step0(tmp_path, level=0.005)                 # 0.5 pips
    assert not ok and any("median" in w for w in why)


# ------------------------------------------------------------------ fills

def test_gap_filled_from_the_tree_both_legs(tmp_path):
    """Day X lacks its entry bar in the as-run source; the tree has it, 0.5 pips
    higher. The fill must take both legs from the tree (so the level offset cancels),
    never splice one leg from each source; a day outside the fill windows is not
    filled; a day in neither source is dropped."""
    jst = pd.DatetimeIndex(["2009-03-05", "2009-03-11", "2009-03-17", "2016-03-10"])
    x, outside, neither = jst[1], jst[3], jst[2]
    entry_bar = gf.jst_to_utc([x], "08:00")[0] - pd.Timedelta("1min")
    drop = list(pd.date_range(entry_bar - pd.Timedelta("10min"), entry_bar, freq="1min"))
    for d in (neither, outside):
        e = gf.jst_to_utc([d], "08:00")[0]
        drop += list(pd.date_range(e - pd.Timedelta("10min"), e, freq="1min"))
    asrun_bars = bid_only_bars(utc_days_for(jst), drop=drop)
    write_tree(tmp_path, [d for d in utc_days_for(jst) if d not in set(utc_days_for([neither]))], level=0.005)
    tree = gf.load_tree(tmp_path)
    tree_syn = gf.synthetic_bars(tree, profile=PROFILE)
    entry, exit_, side = gf.RULES["prefix_long"]
    asrun = window_trades(asrun_bars, jst, entry, exit_, side)
    assert set(asrun.index) == {jst[0]}
    windows = [(dt.date(2006, 12, 31), dt.date(2014, 12, 31))]
    out = gf.fill_group(asrun, jst, tree_syn, windows, entry, exit_, side)
    assert set(out.index) == {jst[0], x}                     # 'outside' (2016) and 'neither' not filled
    assert out.loc[x, "filled"] and not out.loc[jst[0], "filled"]
    assert out.loc[x, "source"] == gf.TREE_SOURCE
    tree_only = window_trades(tree_syn, [x], entry, exit_, side).loc[x, "mid_pips"]
    assert out.loc[x, "mid_pips"] == pytest.approx(tree_only)
    spliced = (quote_at(asrun_bars, gf.jst_to_utc([x], "09:55")[0])["bid"]
               - quote_at(tree_syn, gf.jst_to_utc([x], "08:00")[0])["bid"]) / 0.01
    assert abs(out.loc[x, "mid_pips"] - spliced) > 0.4      # a spliced trade would carry the offset


# ------------------------------------------------------------------ measured spreads

def _bars_at(points: dict) -> pd.DataFrame:
    """Real bid/ask bars at given UTC minutes: {timestamp: spread_pips}."""
    idx = pd.DatetimeIndex(sorted(points)).tz_convert("UTC")
    bid = np.full(len(idx), 100.0)
    return pd.DataFrame({"bid": bid, "ask": bid + np.array([points[t] for t in sorted(points)]) * 0.01,
                         "source": gf.TREE_SOURCE}, index=idx)


def test_measured_spread_hierarchy():
    leg = "prefix_long"
    pay = lambda d: gf.jst_to_utc([d], "08:00")[0] - pd.Timedelta("1min")
    own_day, imp_day = pd.Timestamp("2009-03-10"), pd.Timestamp("2009-03-11")
    s2_days = [pd.Timestamp("2016-01-05"), pd.Timestamp("2016-01-07"), pd.Timestamp("2016-02-05")]
    trade_2016, ec_day = pd.Timestamp("2016-06-10"), pd.Timestamp("2024-07-10")
    cell_days = [own_day, pd.Timestamp("2009-03-12"), pd.Timestamp("2009-03-13")]
    points = {pay(own_day): 0.8, pay(cell_days[1]): 0.4, pay(cell_days[2]): 1.2,
              pay(s2_days[0]): 0.3, pay(s2_days[1]): 0.3, pay(s2_days[2]): 1.5}
    tree_real = _bars_at(points)
    days = [own_day, imp_day, trade_2016, s2_days[2], ec_day]
    trades = pd.DataFrame({"entry_utc": [gf.jst_to_utc([d], "08:00")[0] for d in days],
                           "exit_utc": [gf.jst_to_utc([d], "09:55")[0] for d in days],
                           "source": ["dukascopy", "dukascopy", "histdata", "histdata", "eightcap"],
                           "spread_paid_pips": [0.36, 0.36, 0.36, 0.36, 0.25]}, index=pd.DatetimeIndex(days))
    m = gf.measured_spreads(trades, leg, tree_real, s2_days, cell_days)
    assert (m.loc[own_day, "s_source"], m.loc[own_day, "s_meas"]) == ("own", pytest.approx(0.8))
    assert m.loc[imp_day, "s_source"] == "imputed"
    assert m.loc[imp_day, "s_meas"] == pytest.approx((0.8 + 0.4 + 1.2) / 3)        # cell MEAN for 2009
    assert m.loc[trade_2016, "s_source"] == "stage2_mean"
    assert m.loc[trade_2016, "s_meas"] == pytest.approx((0.3 + 0.3 + 1.5) / 3)     # mean, not the 0.3 median
    assert (m.loc[s2_days[2], "s_source"], m.loc[s2_days[2], "s_meas"]) == ("own", pytest.approx(1.5))
    assert (m.loc[ec_day, "s_source"], m.loc[ec_day, "s_meas"]) == ("eightcap", pytest.approx(0.25))


def test_short_leg_pays_at_its_exit_bar():
    leg = "postfix_short"
    d = pd.Timestamp("2009-03-10")
    entry_bar = gf.jst_to_utc([d], "09:55")[0] - pd.Timedelta("1min")
    exit_bar = gf.jst_to_utc([d], "11:00")[0] - pd.Timedelta("1min")
    tree_real = _bars_at({entry_bar: 0.9, exit_bar: 0.2})
    trades = pd.DataFrame({"entry_utc": [entry_bar + pd.Timedelta("1min")], "exit_utc": [exit_bar + pd.Timedelta("1min")],
                           "source": ["dukascopy"], "spread_paid_pips": [0.27]}, index=pd.DatetimeIndex([d]))
    m = gf.measured_spreads(trades, leg, tree_real, [], [d])
    assert m.loc[d, "s_meas"] == pytest.approx(0.2)


# ------------------------------------------------------------------ gate

def _load_script(name):
    sp = importlib.util.spec_from_file_location(name.replace(".py", ""), ROOT / "scripts" / name)
    mod = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(mod)
    return mod


def test_gate_refuses_until_complete_and_honours_waivers(tmp_path, monkeypatch):
    an = _load_script("004_gap_fill_analysis.py")
    stages = {"1": (dt.date(2023, 3, 6), dt.date(2023, 3, 8), None, "test")}
    monkeypatch.setattr(an.dgf, "STAGES", stages)
    write_tree(tmp_path, ["2023-03-06", "2023-03-07"])
    assert an.gate(tmp_path, {}) == {"1": [dt.date(2023, 3, 8)]}
    w = tmp_path / "waived.csv"
    w.write_text("utc_day,reason,decided_on\n2023-03-08,test day not needed,2026-11-26\n")
    assert an.gate(tmp_path, an.load_waived(str(w))) == {"1": []}


# ------------------------------------------------------------------ tradeability

def test_labels_95_is_stricter_than_1se():
    assert tr.labels(0.85, 0.663) == ("pass", "not resolved")       # spec 004 as-run prefix
    assert tr.labels(1.2, 0.5) == ("pass", "pass")
    assert tr.labels(-1.2, 0.5) == ("fail", "fail")
    assert tr.labels(0.3, 0.5) == ("not resolved", "not resolved")


def test_era_multiplier_for_tree_trades_is_by_date():
    k = era_spread_multiplier(["dukascopy_tree", "dukascopy_tree", "histdata", "eightcap", "dukascopy"],
                              pd.DatetimeIndex(["2010-01-05", "2023-03-10", "2016-01-05", "2024-07-01", "2010-01-05"]))
    assert list(k) == [5.0, 2.5, 2.5, 1.0, 5.0]


def _trades(n, mid_pips, price, spread=0.36):
    idx = pd.bdate_range("2010-01-04", periods=n)
    return pd.DataFrame({"mid_pips": mid_pips, "net_pips": mid_pips - 1.0, "spread_paid_pips": spread,
                         "mid_in": price, "source": "histdata", "s_meas": spread * 2}, index=idx)


def test_measured_column_uses_measured_spread():
    t = tr.with_cost_columns(_trades(400, np.full(400, 3.0), 110.0))
    c5 = tr.criterion_5(t, "measured")
    expected = (3.0 - 1.0 - (0.72 - 0.36)) - (PESSIMISTIC.round_trip_pips(110.0) + 0.72)
    assert c5["margin"] == pytest.approx(expected)


def test_bp_stability_withholds_the_159_view_when_effect_is_constant_in_pips():
    rng = np.random.default_rng(1)
    px = np.linspace(80, 160, 3000)
    pips_const = 3.0 + rng.normal(0, 2, 3000)                  # constant in pips: bp falls with price
    t = tr.with_cost_columns(_trades(3000, pips_const, px))
    assert not tr.bp_stability(t)["admissible"] and tr.today_view(t, "as run") is None
    bp_const = 3.0 * px / 100 + rng.normal(0, 2, 3000)         # constant in bp
    t = tr.with_cost_columns(_trades(3000, bp_const, px))
    assert tr.bp_stability(t)["admissible"] and tr.today_view(t, "as run") is not None


def test_break_even_uses_the_same_trades_for_mid_and_net():
    t = _trades(400, np.r_[np.full(200, 6.0), np.full(200, 0.0)], 110.0)
    t.loc[t.index[200:], "s_meas"] = np.nan                    # measured spread missing for half
    t = tr.with_cost_columns(t)
    be = tr.break_even(t, "measured")
    assert be["zero"] == pytest.approx(6.0)                     # mid over the measured trades only
    assert be["base_all_in"] == pytest.approx(6.0 - (5.0 - 0.36))
