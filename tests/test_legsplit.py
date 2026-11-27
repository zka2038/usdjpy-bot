"""Spec 019 (yen-leg / dollar-leg split): known-answer tests on synthetic seven-pair bars.
No real data and no network. Also: the bid-only quote lookup, the HistData pair parser and
loader, the fetch guard that waits for the Dukascopy fetch, and the script's stages end to
end on synthetic bars."""
import datetime as dt
import importlib.util
import io
import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from usdjpy import datasets  # noqa: E402
from usdjpy import legsplit as L  # noqa: E402
from usdjpy.calendars import turn_of_month_groups  # noqa: E402
from usdjpy.datasets import us_eu_dst_mismatch_windows  # noqa: E402
from usdjpy.events import quote_at  # noqa: E402
from usdjpy.gapfill import quotes_at  # noqa: E402


def _load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def harness():
    return {name: (ok, detail) for name, ok, detail in L.harness_check()}


def test_harness_all_checks_pass(harness):
    for name, (ok, detail) in harness.items():
        assert ok, f"{name}: {detail}"


def test_quotes_at_bid_only_matches_quote_at():
    rng = np.random.default_rng(0)
    idx = pd.date_range("2020-01-06 00:00", periods=300, freq="min", tz="UTC")
    idx = idx[rng.random(len(idx)) > 0.3]                     # gaps, so staleness bites
    bars = pd.DataFrame({"bid": 100 + rng.normal(0, 0.01, len(idx)).cumsum()}, index=idx)
    ts = pd.DatetimeIndex(sorted(idx[0] + pd.to_timedelta(rng.integers(0, 330, 200), "min")))
    got = quotes_at(bars, ts, cols=("bid",))["bid"]
    for t, v in zip(ts, got):
        q = quote_at(bars, t)
        assert (np.isnan(v) and q is None) or v == pytest.approx(q["bid"])


def test_quotes_at_default_still_returns_bid_and_ask():
    idx = pd.date_range("2020-01-06", periods=5, freq="min", tz="UTC")
    bars = pd.DataFrame({"bid": 1.0, "ask": 2.0}, index=idx)
    out = quotes_at(bars, idx[1:])
    assert list(out.columns) == ["bid", "ask"] and (out["ask"] == 2.0).all()


def test_identity_holds_exactly_on_synthetic_bars():
    g = turn_of_month_groups(dt.date(2019, 1, 1), dt.date(2019, 6, 30))
    d = g["B_gotobi_proper"].union(g["C_control"])
    bars = L.synthetic_bars(d, seed=5)
    for w in L.WINDOWS:
        r, b = L.window_returns({p: bars[p] for p in L.PAIRS + ("USDJPY",)}, d, w)
        lg = L.legs(r, b)
        assert len(lg) == len(d)
        assert np.allclose(lg["UJ_bp"], r.loc[lg.index, "USDJPY"], atol=1e-8)
        p_true = b.loc[lg.index, "USDJPY"]
        assert np.allclose(lg["P_hat"], p_true, rtol=1e-12)
        assert np.allclose(lg["J"], lg["J_bp"] * p_true / 100)


def test_injected_yen_leg_lands_in_J_only():
    g = turn_of_month_groups(dt.date(2019, 1, 1), dt.date(2019, 12, 31))
    b = g["B_gotobi_proper"]
    bars = L.synthetic_bars(b, b, {"JPY": -2.0}, sigma_bp=0.0)   # no noise: exact
    r, bid = L.window_returns({p: bars[p] for p in L.PAIRS}, b, "prefix")
    lg = L.legs(r, bid)
    assert np.allclose(lg["J_bp"], 2.0) and np.allclose(lg["D_bp"], 0.0, atol=1e-9)
    r, bid = L.window_returns({p: bars[p] for p in L.PAIRS}, b, "postfix")
    lg = L.legs(r, bid)
    assert np.allclose(lg[["J_bp", "D_bp"]], 0.0, atol=1e-9)   # held, not reversed


def test_window_returns_drop_holdout_and_missing_quotes():
    d = pd.DatetimeIndex(["2024-12-30", "2025-01-06"])
    bars = L.synthetic_bars(d, seed=1)
    bars["EURJPY"] = bars["EURJPY"][bars["EURJPY"].index < pd.Timestamp("2024-12-29 23:30", tz="UTC")]
    r, _ = L.window_returns({p: bars[p] for p in L.PAIRS}, d, "prefix")
    assert list(r.index) == [pd.Timestamp("2024-12-30")]          # 2025 date never read
    assert np.isnan(r.loc["2024-12-30", "EURJPY"])
    assert L.legs(r, _).empty                                    # a day needs all six pairs


def test_step0_non_dst_misalignment_is_not_the_declared_case():
    bars, alld, _ = L._synthetic_groups(21, noise_bp=0.2, years=(2019,))
    span = [(pd.Timestamp("2019-06-01", tz="UTC"), pd.Timestamp("2019-07-01", tz="UTC"))]
    faulty = {k: (L.shift_in_windows(v, span, -60) if k in L.PAIRS else v) for k, v in bars.items()}
    s0 = L.step0(faulty, alld)
    assert not s0["passed"] and not s0["dst_only"]
    assert any("2019-06" in f for f in s0["failures"])


def test_step0_dst_fault_before_2019_is_not_the_declared_case():
    bars, alld, _ = L._synthetic_groups(22, noise_bp=0.2, years=(2017,))
    win = [us_eu_dst_mismatch_windows([2017])[0]]
    faulty = {k: (L.shift_in_windows(v, win, -60) if k in L.PAIRS else v) for k, v in bars.items()}
    s0 = L.step0(faulty, alld)
    assert not s0["passed"] and not s0["dst_only"]


def test_step0_median_threshold_fails_on_noisy_identity():
    bars, alld, _ = L._synthetic_groups(23, noise_bp=3.0, years=(2019,))
    s0 = L.step0(bars, alld)
    assert not s0["passed"] and any("median" in f for f in s0["failures"])


def test_matched_se_from_control_matches_stratified_compare_under_null():
    from usdjpy.events import stratified_compare
    _, _, g = L._synthetic_groups(31)
    for w in L.WINDOWS:
        counts = pd.Series(g[w]["B"].index.day_of_week).value_counts().sort_index()
        se_c = L.matched_se_from_control(g[w]["C"]["J"], counts)
        se_true = stratified_compare(g[w]["B"], g[w]["C"], col="J")["se"]
        assert se_c == pytest.approx(se_true, rel=0.25)


def test_stage1_uses_no_treated_outcomes():
    """Stage 1 must give the same table whatever B's returns are."""
    _, _, g1 = L._synthetic_groups(41)
    _, _, g2 = L._synthetic_groups(41, {"JPY": -5.0})          # same seed, B days moved
    bd = {w: g1[w]["B"].index for w in L.WINDOWS}
    t1 = L.stage1({w: g1[w]["C"] for w in L.WINDOWS}, bd)
    t2 = L.stage1({w: g2[w]["C"] for w in L.WINDOWS}, bd)
    pd.testing.assert_frame_equal(t1, t2)
    assert {"power_s1", "power_s0.5", "mde"} <= set(t1.columns)
    assert (t1["power_s1"] >= t1["power_s0.5"]).all()


def _tab(p_t, p_diff, p_mde, s2_t):
    rows = {"P": {"t": p_t, "diff_pips": p_diff, "mde": p_mde},
            "S2": {"t": s2_t, "diff_pips": 0.0, "mde": 1.0}}
    return pd.DataFrame(rows).T


@pytest.mark.parametrize("p_t,p_diff,p_mde,s2_t,expect", [
    (3.0, 2.0, 1.0, 0.0, ["2"]),
    (-3.0, -2.0, 1.0, 0.0, ["5"]),
    (-0.5, -0.3, 1.2, 0.0, ["3"]),
    (-0.5, -0.3, 2.0, 0.0, ["6"]),          # P <= 0 but MDE above 1.56: not a contradiction
    (0.5, 0.3, 1.2, 3.0, ["4"]),
    (-0.5, -0.3, 1.2, 3.0, ["3", "4"]),     # both can hold
    (1.0, 0.6, 1.2, 1.0, ["6"]),
])
def test_readings(p_t, p_diff, p_mde, s2_t, expect):
    got = [r.split(":")[0] for r in L.readings(_tab(p_t, p_diff, p_mde, s2_t))]
    assert got == expect


def test_read_histdata_mt_csv_ny_local_with_dst():
    text = ("2019.07.01,19:00,1.0,1.1,0.9,1.05,0\n"      # EDT: 23:00 UTC
            "2019.01.02,19:00,2.0,2.1,1.9,2.05,0\n"      # EST: 00:00 UTC next day
            "2019.11.03,01:30,3.0,3.1,2.9,3.05,0\n")     # ambiguous: dropped
    out = datasets.read_histdata_mt_csv(io.StringIO(text))
    assert list(out.index) == [pd.Timestamp("2019-01-03 00:00", tz="UTC"),
                               pd.Timestamp("2019-07-01 23:00", tz="UTC")]
    assert list(out.columns) == ["open", "high", "low", "close"]


def test_load_histdata_bid_needs_explicit_fix_dst(tmp_path, monkeypatch):
    monkeypatch.setattr(datasets, "BARS", tmp_path)
    with pytest.raises(FileNotFoundError, match="Dukascopy"):
        datasets.load_histdata_bid("eurjpy", fix_dst=False)
    idx = pd.date_range("2016-03-14", periods=3, freq="min", tz="UTC")
    pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": [1.0, 2.0, 3.0]}, index=idx).to_parquet(
        datasets.histdata_pair_path("eurjpy"))
    with pytest.raises(TypeError):
        datasets.load_histdata_bid("eurjpy")                    # no default on purpose
    s = datasets.load_histdata_bid("eurjpy", fix_dst=False)
    assert list(s) == [1.0, 2.0, 3.0]


def test_fetch_guard_waits_for_dukascopy(tmp_path):
    fo = _load_script("fetch_official_t", ROOT / "scripts" / "fetch_official.py")
    repo = tmp_path / "repo"
    (repo / "data" / "tokyo_hours").mkdir(parents=True)
    log = repo / "data" / "tokyo_hours" / "fetch.log"
    fo.ROOT = repo
    log.write_text("stage 3\n  2008-12-08:    6048 ticks\n")
    assert fo.dukascopy_fetch_done()[0] is False
    log.write_text("  2014-12-31:    100 ticks\nstage 3 complete\n")
    assert fo.dukascopy_fetch_done()[0] is True
    with pytest.raises(SystemExit):
        log.write_text("running\n")
        fo.histdata_pairs(["eurjpy"])
    assert max(fo.PAIR_YEARS) < 2025


def test_script_stages_end_to_end_on_synthetic_bars(tmp_path, monkeypatch, capsys):
    s = _load_script("split019_t", ROOT / "scripts" / "019_yen_dollar_split.py")
    g = turn_of_month_groups(dt.date(2019, 1, 1), dt.date(2020, 12, 31))
    alld = g["A_month_end"].union(g["B_gotobi_proper"]).union(g["C_control"])
    bars = L.synthetic_bars(alld, g["B_gotobi_proper"], {"JPY": -3.0}, sigma_bp=0.3, noise_bp=0.2, seed=51)
    monkeypatch.setattr(s, "START", dt.date(2019, 1, 1))
    monkeypatch.setattr(s, "END", dt.date(2020, 12, 31))
    monkeypatch.setattr(s, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(s.L, "mof_dates", lambda: pd.DatetimeIndex([g["B_gotobi_proper"][0]]))
    s.run_step0(bars, fix_dst=False)
    s.run_stage1(bars)
    s.run_stage2(bars)
    out = capsys.readouterr().out
    assert "STEP 0 PASSED" in out and "STOP." in out and "2: named mechanism supported" in out
    for f in ("019_step0_cells_fixdst0.csv", "019_stage1_power.csv", "019_stage2_tests.csv",
              "019_stage2_descriptives.csv", "019_stage2_periods.csv", "019_stage2_tests_with_mof.csv"):
        assert (tmp_path / f).exists()
    tab = pd.read_csv(tmp_path / "019_stage2_tests.csv", index_col=0)
    n_b = len(g["B_gotobi_proper"]) - 1                      # one B day excluded as "MOF"
    assert tab.loc["P", "n_B"] == n_b
