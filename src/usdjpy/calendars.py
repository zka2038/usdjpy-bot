"""Trading calendars: Japanese business days, gotobi (五十日) days, month-ends.

Gotobi convention: the 5th, 10th, 15th, 20th, 25th and the last business day of the
month (月末). If a date falls on a weekend or Japanese bank holiday it rolls BACK to
the previous business day. Japanese banks are also closed 31 Dec - 3 Jan.
"""
from __future__ import annotations

import datetime as dt

import holidays
import pandas as pd

GOTOBI_DAYS = (5, 10, 15, 20, 25)


def jp_bank_holidays(start: dt.date, end: dt.date) -> set[dt.date]:
    years = range(start.year, end.year + 1)
    hols = set(holidays.Japan(years=years).keys())
    for y in years:
        hols |= {dt.date(y, 12, 31), dt.date(y, 1, 1), dt.date(y, 1, 2), dt.date(y, 1, 3)}
    return hols


def jp_business_days(start: dt.date, end: dt.date) -> pd.DatetimeIndex:
    hols = jp_bank_holidays(start, end)
    days = pd.bdate_range(start, end)
    return days[~days.normalize().isin(pd.DatetimeIndex(sorted(hols)))]


def _roll_back(d: dt.date, bdays: set[dt.date]) -> dt.date:
    while d not in bdays:
        d -= dt.timedelta(days=1)
    return d


def gotobi_days(start: dt.date, end: dt.date) -> pd.DatetimeIndex:
    """Gotobi dates (JST calendar dates) between start and end, inclusive."""
    pad_start = start - dt.timedelta(days=15)  # so roll-backs near `start` resolve
    bdays = set(d.date() for d in jp_business_days(pad_start, end))
    out = set()
    for month in pd.date_range(pd.Timestamp(start).replace(day=1), end, freq="MS"):
        for day in GOTOBI_DAYS:
            out.add(_roll_back(dt.date(month.year, month.month, day), bdays))
        month_end = (month + pd.offsets.MonthEnd(0)).date()
        out.add(_roll_back(month_end, bdays))
    return pd.DatetimeIndex(sorted(d for d in out if start <= d <= end))


def last_business_days(start: dt.date, end: dt.date, country: str = "UK") -> pd.DatetimeIndex:
    """Last business day of each month for a holiday calendar (UK for the London 4pm fix)."""
    years = range(start.year, end.year + 1)
    hols = pd.DatetimeIndex(sorted(holidays.country_holidays(country, years=years).keys()))
    days = pd.bdate_range(start, end)
    days = days[~days.isin(hols)]
    return pd.DatetimeIndex(pd.Series(days).groupby([days.year, days.month]).max().values)
