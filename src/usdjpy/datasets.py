"""Loaders for everything in data/. See docs/DATA.md for provenance and caveats.

All price loaders return 1-minute bars indexed by UTC timestamp with at least `bid` and `ask`
columns (bar close), which is what usdjpy.events.window_trades expects.

BID-only sources get a synthetic ask: bid + the median Eightcap spread for that JST hour
(2024-26 raw-spread account, ~0.25 pips most hours, ~5 pips at the 17:00 NY rollover).
Historical spreads were wider (esp. 2007-2012), so always also check PESSIMISTIC costs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import DATA_DIR

BARS = DATA_DIR / "bars_1min"
FALLBACK_SPREAD = 0.003  # 0.3 pips


def _hourly_spread_profile(allow_fallback: bool = False) -> pd.Series:
    """Median Eightcap spread by JST hour. Raises if the source file is absent.

    The fallback is a flat 0.3 pips, which is within 0.06 pips of the real hour-8
    value and therefore indistinguishable from a correct result in any output it
    reaches. Every cost number in the repo depends on this profile, so a missing
    file must fail loudly rather than quietly produce plausible figures.
    """
    path = BARS / "eightcap_bidask_2024_2026.parquet"
    if not path.exists():
        if not allow_fallback:
            raise FileNotFoundError(
                f"No spread profile: {path} is missing.\n"
                "Every synthetic ask, and so every cost figure, depends on it. The flat "
                f"{FALLBACK_SPREAD * 100:.1f}-pip fallback is close enough to the real "
                "profile to look correct while being wrong, so it is not used by default.\n"
                "Fetch the file, or pass allow_fallback=True if you are deliberately "
                "running without real spreads."
            )
        return pd.Series(FALLBACK_SPREAD, index=range(24))
    s = pd.read_parquet(path, columns=["spread_mean"])["spread_mean"]
    prof = s.groupby(s.index.tz_convert("Asia/Tokyo").hour).median()
    return prof.reindex(range(24)).fillna(FALLBACK_SPREAD)


def _with_synthetic_ask(bid: pd.Series, source: str, exec_lag: str = "1min") -> pd.DataFrame:
    """Attach a synthetic ask keyed on the EXECUTION hour, not the bar's own hour.

    `events.quote_at(ts)` fills on the bar at `ts - 1min`, so the bar labelled T is
    the fill for a trade at T + 1min and must carry the spread prevailing then.
    Keying on the bar's own hour charged spec 004's 08:00 JST entry the hour-7
    spread (0.600 pips, still decaying from the 06:00 NY rollover spike) instead of
    hour 8 (0.360) - 0.24 pips a trade on a 1.8-pip effect. `exec_lag` must track
    `quote_at`'s offset; if that changes, change this.
    """
    prof = _hourly_spread_profile()
    exec_hour = (bid.index + pd.Timedelta(exec_lag)).tz_convert("Asia/Tokyo").hour
    spread = prof.reindex(exec_hour).to_numpy()
    return pd.DataFrame({"bid": bid.astype("float64"), "ask": bid.to_numpy() + spread, "spread": spread,
                         "source": source}, index=bid.index)


HISTDATA_EU_DST_FROM = 2019


def us_eu_dst_mismatch_windows(years) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """UTC spans in which US and EU clocks disagree, one pair per year:
    US spring change (2nd Sunday of March, 07:00 UTC) to EU spring change (last
    Sunday of March, 01:00 UTC), and EU autumn change (last Sunday of October,
    01:00 UTC) to US autumn change (1st Sunday of November, 06:00 UTC). Every
    boundary falls inside the FX weekend close."""
    def sundays(y, m):
        d = pd.date_range(f"{y}-{m:02d}-01", periods=31, freq="D", tz="UTC")
        return d[(d.month == m) & (d.day_of_week == 6)]
    out = []
    for y in years:
        out.append((sundays(y, 3)[1] + pd.Timedelta("7h"), sundays(y, 3)[-1] + pd.Timedelta("1h")))
        out.append((sundays(y, 10)[-1] + pd.Timedelta("1h"), sundays(y, 11)[0] + pd.Timedelta("6h")))
    return out


def fix_histdata_dst(s: pd.Series | pd.DataFrame) -> pd.Series | pd.DataFrame:
    """Shift HistData bars +60 min inside the US/EU DST mismatch weeks from 2019 on.

    The parquet was built by localising HistData's raw stamps to America/New_York.
    That is right everywhere except here: from 2019 HistData's raw clock changes on
    EU DST dates, so in the weeks between the US and EU changes the bar labelled T
    carries the true T+60 price. Found by scripts/histdata_alignment_check.py: 75
    dates against Dukascopy (2019, 2021-2023) and Eightcap (2024), all of them in a
    mismatch window, all at +60; 2015-2018 have none. 2020, Nov 2023 and Mar 2024
    have no second source and were checked on the reopen hour and intraday
    volatility profile instead (same script). Windows start and end in the weekend
    close, so the shift cannot collide with an unshifted bar.

    Guard against double correction: a file with the EU-clock error reopens on the
    Sundays inside these windows labelled 20:xx UTC (true 21:00), a correct file at
    21:xx. If the Sunday reopens inside the windows are mostly at 21:00 or later, the
    file has already been corrected (e.g. rebuilt), and shifting would break it, so
    this raises instead. Re-run scripts/histdata_alignment_check.py after any rebuild.
    """
    idx = s.index
    years = range(max(idx[0].year, HISTDATA_EU_DST_FROM), idx[-1].year + 1)
    windows = us_eu_dst_mismatch_windows(years)
    mask = np.zeros(len(idx), dtype=bool)
    for a, b in windows:
        mask |= (idx >= a) & (idx < b)
    if len(idx) > 1:
        reopen = idx[1:][(((idx[1:] - idx[:-1]) > pd.Timedelta("24h"))) & mask[1:]]
        reopen = reopen[reopen.day_of_week == 6]
        if len(reopen) and np.mean(reopen.hour >= 21) > 0.5:
            raise AssertionError(
                f"HistData bars already look DST-correct: {int(np.sum(reopen.hour >= 21))} of "
                f"{len(reopen)} Sunday reopens inside the US/EU mismatch windows are at 21:00 UTC "
                "or later, not 20:xx. fix_histdata_dst would shift them an hour late. Was the "
                "file rebuilt? Re-run scripts/histdata_alignment_check.py.")
    new = idx.where(~mask, idx + pd.Timedelta(minutes=60))
    out = s.copy()
    out.index = new
    out = out.sort_index()
    if out.index.has_duplicates:
        raise AssertionError("HistData DST shift produced duplicate timestamps")
    return out


def load_minute(source: str = "combined") -> pd.DataFrame:
    """1-min bars. source: 'dukascopy' (2007-2023, gappy), 'histdata' (2015-2025-04; gappy Feb-Jul 2023, DST-corrected),
    'eightcap' (2024-06 to 2026-06, real bid/ask), or 'combined' (best available per period)."""
    if source == "dukascopy":
        return _with_synthetic_ask(pd.read_parquet(BARS / "dukascopy_bid_2007_2023.parquet")["close"], "dukascopy")
    if source == "histdata":
        bid = fix_histdata_dst(pd.read_parquet(BARS / "histdata_bid_2015_2025.parquet")["close"])
        return _with_synthetic_ask(bid, "histdata")
    if source == "eightcap":
        e = pd.read_parquet(BARS / "eightcap_bidask_2024_2026.parquet")
        return pd.DataFrame({"bid": e["bid"].astype("float64"), "ask": e["ask"].astype("float64"),
                             "spread": e["spread_mean"].astype("float64"), "source": "eightcap"}, index=e.index)
    if source == "combined":
        du, hd, ec = load_minute("dukascopy"), load_minute("histdata"), load_minute("eightcap")
        ec_start = ec.index[0]
        parts = [du[du.index < hd.index[0]], hd[hd.index < ec_start], ec]
        return pd.concat(parts).sort_index()
    raise ValueError(source)


def load_ticks(month: str) -> pd.DataFrame:
    """Eightcap ticks for 'YYYYMM' (2024-06 .. 2026-06), prices in JPY."""
    t = pd.read_parquet(DATA_DIR / "ticks" / "eightcap" / f"USDJPY_{month}.parquet")
    return t / 1000.0


def interventions() -> pd.DataFrame:
    """MOF intervention days (Japan date). Positive `usd_bn_jpy` = MOF bought USD (yen-weakening)."""
    df = pd.read_csv(DATA_DIR / "calendars" / "mof_intervention_transcribed.csv", parse_dates=["date"])
    df = df[df.pair == "USD/JPY"].copy()
    sign = df.mof_side.map({"buy_usd_sell_jpy": 1, "sell_usd_buy_jpy": -1})
    df["jpy_tn"] = df.amount_oku_yen / 1e4 * sign
    return df.set_index("date")


def fomc() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "calendars" / "fomc_decisions.csv", parse_dates=["decision_date"]).set_index("decision_date")


def boj() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "calendars" / "boj_mpm.csv", parse_dates=["start_date", "decision_date"]).set_index("decision_date")


def cot(report: str = "tff") -> pd.DataFrame:
    """Weekly CFTC JPY futures positioning (as of Tuesday; published Friday 15:30 ET).
    Use `available_from` (the release Friday) for anything trading on it."""
    df = pd.read_csv(DATA_DIR / "positioning" / f"cot_jpy_{report}_weekly.csv", parse_dates=["date"]).set_index("date")
    df["available_from"] = df.index + pd.Timedelta(days=3)
    return df


def macro_daily() -> pd.DataFrame:
    """FRED mirror (DEXJPUS, DGS10/20/30, VIXCLS, NIKKEI225; 2000 to mid-2026) + MOF JGB 2y/10y."""
    f = pd.read_csv(DATA_DIR / "macro" / "fred_daily_2000_2026H1.csv", parse_dates=["date"]).set_index("date")
    j = pd.read_csv(DATA_DIR / "macro" / "mof_jgb_yields_daily_1974_2026.csv", parse_dates=["date"]).set_index("date")
    return f.join(j[["2Y", "10Y"]].rename(columns={"2Y": "JGB2Y", "10Y": "JGB10Y"}), how="outer")
