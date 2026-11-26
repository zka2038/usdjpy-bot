"""Spec 004: A / B / C by weekday, and the Friday decomposition. DESCRIPTIVE ONLY.

    python scripts/004_weekday_breakdown.py

Why: Gotobi dates on a weekend roll back to Friday, so B is 44% Fridays against 11%
in C, and non-Gotobi Fridays move on their own in the prefix window. The declared
weekday-matched comparison (spec 004, declared 2026-11-25) is the test; this script
shows where the unmatched difference comes from. It governs nothing, declares no new
hypothesis, and a "Friday Tokyo-morning effect" may not be traded or tested as a rule
without its own spec (CLAUDE.md, trial budget). Many cells are small: read every mean
beside its MDE at the t=2.5 bar.

Reads results/004_*.csv (mid_pips: cost-free) and recomputes the calendar.
"""
import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import norm  # noqa: E402

from usdjpy.calendars import GOTOBI_DAYS, jp_business_days  # noqa: E402
from usdjpy.config import RESULTS_DIR  # noqa: E402
from usdjpy.events import stratified_compare  # noqa: E402

MDE_MULT = 2.5 + norm.ppf(0.80)
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri"]
LEGS = ("prefix_long", "postfix_short")


def load(leg, g):
    return pd.read_csv(RESULTS_DIR / f"004_{leg}_{g}.csv", parse_dates=["date"]).set_index("date")["mid_pips"]


def cell(x: pd.Series) -> str:
    n = len(x)
    if n < 2:
        return f"{'n<2':>24}"
    se = x.std(ddof=1) / np.sqrt(n)
    return f"{x.mean():+6.2f} t{x.mean() / se:+5.1f} n{n:<4} M{MDE_MULT * se:4.1f}"


def diff(a: pd.Series, b: pd.Series) -> str:
    if len(a) < 2 or len(b) < 2:
        return f"{'-':>22}"
    se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    d = a.mean() - b.mean()
    return f"{d:+6.2f} t{d / se:+5.1f} M{MDE_MULT * se:4.1f}"


def b_origin(dates: pd.DatetimeIndex) -> pd.Series:
    """For each B day, how its date arose: 'dated' (the 5th/10th/... itself is a
    business day), 'rolled_weekend' (the nominal date fell on Sat/Sun) or
    'rolled_holiday' (a weekday holiday). Mirrors calendars.gotobi_days' roll-back."""
    start, end = dates.min().date().replace(day=1), dates.max().date()
    # Pad the business-day set back past the first nominal date, or the roll-back
    # walks off its start (calendars.gotobi_days had the same bug until 2026-11-25).
    bdays = set(d.date() for d in jp_business_days(start - dt.timedelta(days=15), end))
    origin = {}
    for m in pd.date_range(pd.Timestamp(start).replace(day=1), end, freq="MS"):
        for day in GOTOBI_DAYS:
            nom = dt.date(m.year, m.month, day)
            d = nom
            while d not in bdays:
                d -= dt.timedelta(days=1)
            kind = "dated" if d == nom else ("rolled_weekend" if nom.weekday() >= 5 else "rolled_holiday")
            origin.setdefault(pd.Timestamp(d), kind)
    return pd.Series([origin.get(d, "unknown") for d in dates], index=dates)


def before_break(dates: pd.DatetimeIndex) -> pd.Series:
    """True where a holiday lies between this day and the next JP business day:
    Mon-Thu with the next business day 2+ calendar days away, or Fri with it 4+
    days away (a long weekend). An ordinary Fri->Mon gap is not a break.
    Note: a Gotobi date that falls inside a break rolls back onto the day before
    it, so many pre-break days are B (or A), not C, by construction."""
    bd = jp_business_days(dates.min().date(), dates.max().date() + dt.timedelta(days=15))
    pos = bd.searchsorted(dates, side="right")
    gap = np.asarray((bd[np.minimum(pos, len(bd) - 1)] - dates).days)
    fri = np.asarray(dates.day_of_week == 4)
    return pd.Series(np.where(fri, gap >= 4, gap >= 2), index=dates)


def main() -> None:
    for leg in LEGS:
        A, B, C = (load(leg, g) for g in ("A_month_end", "B_gotobi_proper", "C_control"))
        print("=" * 110)
        print(f"{leg}: mid_pips (cost-free). Cell = mean, t vs 0, n, M = MDE at t=2.5")
        print("=" * 110)
        print(f"{'':6}{'A month-end':>26}{'B gotobi-proper':>26}{'C control':>26}   {'B - C same weekday':>22}")
        for k, name in enumerate(DOW):
            a, b, c = (x[x.index.day_of_week == k] for x in (A, B, C))
            print(f"{name:6}{cell(a):>26}{cell(b):>26}{cell(c):>26}   {diff(b, c):>22}")
        print(f"{'all':6}{cell(A):>26}{cell(B):>26}{cell(C):>26}   {diff(B, C):>22}")
        share = {g: f"{(x.index.day_of_week == 4).mean():.0%}" for g, x in (("A", A), ("B", B), ("C", C))}
        print(f"Friday share: {share}")

        for lbl, (x, y) in (("A vs C", (A, C)), ("B vs C", (B, C)), ("A vs B", (A, B))):
            u = diff(x, y)
            m = stratified_compare(x.to_frame(), y.to_frame())
            print(f"  {lbl}: unmatched {u}   weekday-matched {m['diff']:+6.2f} t{m['t']:+5.1f} "
                  f"M{MDE_MULT * m['se']:4.1f}")

        org = b_origin(B.index)
        print("\nB by how its date arose (all weekdays):")
        for kind in ("dated", "rolled_weekend", "rolled_holiday", "unknown"):
            x = B[org == kind]
            if len(x):
                print(f"  {kind:<16}{cell(x):>26}   Fri share {(x.index.day_of_week == 4).mean():.0%}")

        lb = before_break(C.index)
        lbb = before_break(B.index)
        fri_c = C.index.day_of_week == 4
        fri_b = B.index.day_of_week == 4
        rows = [
            ("B Fri, dated (5th/10th/.. is a Fri)", B[(B.index.day_of_week == 4) & (org == "dated")]),
            ("B Fri, rolled from weekend", B[(B.index.day_of_week == 4) & (org == "rolled_weekend")]),
            ("B Fri, rolled from holiday", B[(B.index.day_of_week == 4) & (org == "rolled_holiday")]),
            ("A Fri (month-end on a Fri)", A[A.index.day_of_week == 4]),
            ("C Fri, ordinary weekend ahead", C[fri_c & ~lb]),
            ("C Fri, long weekend ahead", C[fri_c & lb]),
            ("C Mon-Thu, holiday ahead", C[~fri_c & lb]),
            ("C Mon-Thu, ordinary", C[~fri_c & ~lb]),
            ("B Mon-Thu, holiday ahead", B[~fri_b & lbb]),
            ("B Mon-Thu, ordinary", B[~fri_b & ~lbb]),
            ("B Fri, long weekend ahead", B[fri_b & lbb]),
        ]
        ref = C[~fri_c & ~lb]
        print("\nFriday and pre-break decomposition (diff vs C Mon-Thu ordinary):")
        for lbl, x in rows:
            print(f"  {lbl:<34}{cell(x):>26}   {diff(x, ref):>22}")
        print()


if __name__ == "__main__":
    main()
