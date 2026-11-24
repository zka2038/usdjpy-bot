"""Interest-rate series stamped with when they became public, so signals never look ahead.

Each loader returns a DataFrame with `value` and `available_at` (UTC). `asof` then picks, for each
decision time, the newest value published strictly before it. This is the fix for the survey's
"timestamp trap two": a US yield and a JGB yield with the same date were not public at the same time.
"""
from __future__ import annotations

import pandas as pd

from .config import DATA_DIR

FRED_OFFICIAL = DATA_DIR / "official" / "fred_daily.csv"
JGB_FILE = DATA_DIR / "macro" / "mof_jgb_yields_daily_1974_2026.csv"
BOJ_FILE = DATA_DIR / "macro" / "boj_call_rate_monthly_1985_2026.csv"


def _stamp(values: pd.Series, local_time: str, tz: str) -> pd.DataFrame:
    """Value dated T (local calendar date) counts as published at `local_time` on T in `tz`."""
    values = values.dropna().astype("float64")
    t = pd.to_datetime(values.index.strftime("%Y-%m-%d") + " " + local_time)
    avail = t.tz_localize(tz).tz_convert("UTC")
    return pd.DataFrame({"value": values.to_numpy(), "available_at": avail}, index=values.index)


def _fred(series: str) -> pd.Series:
    if not FRED_OFFICIAL.exists():
        raise FileNotFoundError(f"{FRED_OFFICIAL} missing: run python scripts/fetch_official.py")
    return pd.read_csv(FRED_OFFICIAL, parse_dates=["date"], index_col="date")[series]


def us_2y() -> pd.DataFrame:
    """FRED DGS2 (%). Treasury publishes the par curve after the US close: 18:00 New York time."""
    return _stamp(_fred("DGS2"), "18:00", "America/New_York")


def jgb_2y() -> pd.DataFrame:
    """MOF JGB 2y (%). Published in the Japanese evening: 18:00 JST on the same date."""
    s = pd.read_csv(JGB_FILE, parse_dates=["date"], index_col="date")["2Y"]
    return _stamp(s, "18:00", "Asia/Tokyo")


def fed_funds() -> pd.DataFrame:
    """FRED DFF (%), effective Fed funds. Used for carry only; published the next US morning."""
    return _stamp(_fred("DFF").shift(1, freq="D"), "09:00", "America/New_York")


def boj_call_rate() -> pd.DataFrame:
    """BoJ uncollateralised overnight call rate, monthly average (%). Used for carry only.

    A month's average is known at the start of the next month; we stamp it at 00:00 UTC on the
    1st of the following month and carry it forward.
    """
    b = pd.read_csv(BOJ_FILE)
    month = pd.to_datetime(b["month"].str.replace("/", "-") + "-01")
    s = pd.Series(b["call_rate_avg"].to_numpy(), index=month + pd.offsets.MonthBegin(1))
    return _stamp(s, "00:00", "UTC")


def asof(series: pd.DataFrame, times: pd.DatetimeIndex, max_age_days: float | None = None) -> pd.DataFrame:
    """For each UTC time, the newest value published strictly before it.

    Returns columns `value`, `value_date` and `age_days` (time since that value was published).
    Values older than `max_age_days` become NaN.
    """
    src = series.sort_values("available_at")
    left = pd.DataFrame({"t": pd.DatetimeIndex(times).as_unit("ns")}).sort_values("t")
    right = pd.DataFrame({"available_at": pd.DatetimeIndex(src["available_at"]).as_unit("ns"),
                          "value": src["value"].to_numpy(), "value_date": src.index.to_numpy()})
    m = pd.merge_asof(left, right, left_on="t", right_on="available_at", allow_exact_matches=False)
    m["age_days"] = (m["t"] - m["available_at"]).dt.total_seconds() / 86400
    if max_age_days is not None:
        m.loc[m["age_days"] > max_age_days, "value"] = float("nan")
    return m.set_index("t")[["value", "value_date", "age_days"]].reindex(times)
