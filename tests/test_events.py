"""Known-answer tests for the spec 004 review fixes of 2026-11-25: the spread a
short actually pays, kill criterion 5's per-trade margin, and the weekday-matched
comparison."""
import sys
import pathlib

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from usdjpy.costs import PESSIMISTIC, CostModel  # noqa: E402
from usdjpy.events import compare, stratified_compare, tradeability_margin, window_trades  # noqa: E402


def _bars():
    """Flat bid of 100.00; spread 0.5 pips before 01:00 UTC, 0.2 pips from 01:00."""
    idx = pd.date_range("2020-01-06 00:00", "2020-01-06 03:00", freq="min", tz="UTC")
    bid = pd.Series(100.0, index=idx)
    spread = np.where(idx.hour < 1, 0.005, 0.002)
    return pd.DataFrame({"bid": bid, "ask": bid + spread, "source": "histdata"})


@pytest.mark.parametrize("side,paid", [(+1, 0.5), (-1, 0.2)])
def test_spread_paid_is_entry_for_long_and_exit_for_short(side, paid):
    t = window_trades(_bars(), [pd.Timestamp("2020-01-06")], "00:30", "01:30", side, tz="UTC")
    row = t.iloc[0]
    assert row.spread_in_pips == pytest.approx(0.5)
    assert row.spread_out_pips == pytest.approx(0.2)
    assert row.spread_paid_pips == pytest.approx(paid)
    # bid is flat, so all the gross P&L is the spread paid, relative to the bid path
    assert row.after_spread_pips == pytest.approx(-paid)
    assert row.mid_in == pytest.approx(100.0025)
    assert row.source == "histdata"


def test_tradeability_margin_arithmetic():
    tr = pd.DataFrame({"net_pips": [3.0, 1.0], "spread_paid_pips": [0.4, 0.3], "mid_in": [110.0, 150.0]})
    m1 = tradeability_margin(tr, PESSIMISTIC)
    exp1 = [3.0 - (PESSIMISTIC.round_trip_pips(110.0) + 0.4), 1.0 - (PESSIMISTIC.round_trip_pips(150.0) + 0.3)]
    assert m1.to_numpy() == pytest.approx(exp1)
    k = np.array([2.5, 5.0])
    m2 = tradeability_margin(tr, PESSIMISTIC, k)
    exp2 = [3.0 - 1.5 * 0.4 - (PESSIMISTIC.round_trip_pips(110.0) + 2.5 * 0.4),
            1.0 - 4.0 * 0.3 - (PESSIMISTIC.round_trip_pips(150.0) + 5.0 * 0.3)]
    assert m2.to_numpy() == pytest.approx(exp2)
    # base and pessimistic differ only in slippage: 0.2 pips a side more
    assert PESSIMISTIC.round_trip_pips(159) - CostModel().round_trip_pips(159) == pytest.approx(0.4)


def _weekday_sample(n, friday_share, effect, rng):
    """Trades on business days; Friday mean +3 pips, other weekdays 0, plus `effect`."""
    days = pd.bdate_range("2007-01-01", periods=20 * n)
    fri, other = days[days.day_of_week == 4], days[days.day_of_week != 4]
    nf = int(round(n * friday_share))
    idx = fri[rng.choice(len(fri), nf, replace=False)].append(other[rng.choice(len(other), n - nf, replace=False)])
    mu = np.where(idx.day_of_week == 4, 3.0, 0.0) + effect
    return pd.DataFrame({"mid_pips": mu + rng.normal(0, 15, len(idx))}, index=idx).sort_index()


def test_matched_comparison_removes_a_weekday_confound():
    rng = np.random.default_rng(4)
    t = _weekday_sample(20_000, 0.44, 0.0, rng)
    c = _weekday_sample(60_000, 0.11, 0.0, rng)
    assert compare(t, c)["t"] > 4                       # unmatched: spurious difference
    m = stratified_compare(t, c)
    assert abs(m["t"]) < 2.5 and abs(m["diff"]) < 0.3   # matched: none
    assert m["strata"] == [0, 1, 2, 3, 4] and m["dropped"] == []


def test_matched_comparison_recovers_a_true_effect():
    rng = np.random.default_rng(5)
    t = _weekday_sample(20_000, 0.44, 1.0, rng)
    c = _weekday_sample(60_000, 0.11, 0.0, rng)
    m = stratified_compare(t, c)
    assert m["diff"] == pytest.approx(1.0, abs=0.35)
    assert m["t"] > 4


def test_matched_comparison_formula_by_hand():
    mon, fri = pd.Timestamp("2020-01-06"), pd.Timestamp("2020-01-10")
    t = pd.DataFrame({"mid_pips": [1.0, 3.0, 5.0, 7.0, 9.0]}, index=[mon, mon, fri, fri, fri])
    c = pd.DataFrame({"mid_pips": [0.0, 2.0, 4.0, 6.0]}, index=[mon, mon, fri, fri])
    m = stratified_compare(t, c)
    d_mon, d_fri = 2.0 - 1.0, 7.0 - 5.0
    w = np.array([2, 3]) / 5
    assert m["diff"] == pytest.approx(w[0] * d_mon + w[1] * d_fri)
    var = [np.var([1, 3], ddof=1) / 2 + np.var([0, 2], ddof=1) / 2,
           np.var([5, 7, 9], ddof=1) / 3 + np.var([4, 6], ddof=1) / 2]
    assert m["se"] == pytest.approx(np.sqrt(w[0] ** 2 * var[0] + w[1] ** 2 * var[1]))


def test_matched_comparison_drops_thin_strata():
    mon, tue = pd.Timestamp("2020-01-06"), pd.Timestamp("2020-01-07")
    t = pd.DataFrame({"mid_pips": [1.0, 2.0, 3.0]}, index=[mon, mon, tue])
    c = pd.DataFrame({"mid_pips": [0.0, 1.0, 0.0, 1.0]}, index=[mon, mon, tue, tue])
    m = stratified_compare(t, c)
    assert m["strata"] == [0] and m["dropped"] == [1] and m["n_treat"] == 2
