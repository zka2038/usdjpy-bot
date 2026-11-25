"""Is histdata_bid_2015_2025.parquet aligned to UTC in US summer as well as winter?

HistData's raw stamps are New York local time. If they were converted with DST
(America/New_York), summer and winter both land on true UTC. If they were converted
with a fixed +5 h (the first committed version of build_github_data.py did this),
every EDT bar is labelled one hour LATE, and the winter bars are right.

Method: shift the HistData index by -60, 0 and +60 minutes, join it to an
independent bid source on common minutes and take the absolute difference of bid
closes. The offset with the smallest difference is the one that aligns the two.
Reported month by month and split by the NY DST flag of the timestamp (a month that
contains a DST change has one row per regime), plus the DST transition weeks
alone, plus the Sunday reopen hour, which sits at 21:00 UTC under EDT and 22:00
under EST for every FX venue.

References:
  dukascopy_bid_2007_2023.parquet  2015-01 .. 2023-03 (gappy). Stamps carry explicit
                                   GMT offsets in the raw export, so no DST guess.
  eightcap_bidask_2024_2026.parquet 2024-06-19 .. 2024-12-31. Capped at HOLDOUT_START:
                                   this check spends no post-holdout data.

Offset sign: the HistData bar labelled T is compared with the reference bar at
T + offset. Offset -60 is best if HistData labels are an hour late.

    python scripts/histdata_alignment_check.py
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from usdjpy.config import DATA_DIR, HOLDOUT_START, RESULTS_DIR  # noqa: E402

BARS = DATA_DIR / "bars_1min"
OFFSETS = (-60, 0, 60)
PIP = 0.01


def _dst_fast(idx: pd.DatetimeIndex) -> np.ndarray:
    """True where New York is on daylight time at that UTC instant (offset -4 h = EDT)."""
    ny = idx.tz_convert("America/New_York")
    off = (ny.tz_localize(None) - idx.tz_convert("UTC").tz_localize(None)) / pd.Timedelta(hours=1)
    return np.asarray(off == -4)


def compare(hd: pd.Series, ref: pd.Series, offset_min: int) -> pd.DataFrame:
    """Absolute bid difference in pips on common minutes, HistData bar T vs ref bar T + offset.
    Indexed by the reference timestamp (true UTC if the reference is right)."""
    shifted = pd.Series(hd.to_numpy(), index=hd.index + pd.Timedelta(minutes=offset_min))
    j = pd.concat({"hd": shifted, "ref": ref}, axis=1, join="inner").dropna()
    return pd.DataFrame({"absdiff": (j.hd - j.ref).abs() / PIP}, index=j.index)


def table(hd: pd.Series, ref: pd.Series, ref_name: str) -> pd.DataFrame:
    rows = []
    for off in OFFSETS:
        d = compare(hd, ref, off)
        d["month"] = d.index.strftime("%Y-%m")
        d["regime"] = np.where(_dst_fast(d.index), "EDT", "EST")
        g = d.groupby(["month", "regime"])["absdiff"].agg(["median", "mean", "count"])
        g.columns = [f"{c}_{off:+d}" for c in g.columns]
        rows.append(g)
    t = pd.concat(rows, axis=1).fillna({f"count_{o:+d}": 0 for o in OFFSETS})
    med = t[[f"median_{o:+d}" for o in OFFSETS]].to_numpy()
    t["best_offset"] = np.array(OFFSETS)[np.nanargmin(med, axis=1)]
    t["reference"] = ref_name
    return t.reset_index()


def days_off(hd: pd.Series, ref: pd.Series, ref_name: str) -> pd.DataFrame:
    """Every UTC date whose best offset (median abs difference) is not 0. Month cells
    can hide a one-week misalignment inside an otherwise aligned month."""
    m = {off: compare(hd, ref, off).absdiff for off in OFFSETS}
    d = pd.DataFrame({f"median_{o:+d}": s.groupby(s.index.date).median() for o, s in m.items()})
    d["count_+0"] = m[0].groupby(m[0].index.date).size()
    d = d[d["count_+0"] >= 60]
    d["best_offset"] = np.array(OFFSETS)[np.nanargmin(d[[f"median_{o:+d}" for o in OFFSETS]].to_numpy(), axis=1)]
    d["reference"] = ref_name
    d.index.name = "date_utc"
    return d[d.best_offset != 0].reset_index()


def dst_mismatch_windows(years) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """UTC spans where US and EU clocks disagree: US spring change (2nd Sunday of
    March, 07:00 UTC) to EU spring change (last Sunday of March, 01:00 UTC), and EU
    autumn change (last Sunday of October, 01:00 UTC) to US autumn change (1st
    Sunday of November, 06:00 UTC)."""
    def sundays(y, m):
        d = pd.date_range(f"{y}-{m:02d}-01", periods=31, freq="D", tz="UTC")
        return d[(d.month == m) & (d.day_of_week == 6)]
    out = []
    for y in years:
        out.append((sundays(y, 3)[1] + pd.Timedelta("7h"), sundays(y, 3)[-1] + pd.Timedelta("1h")))
        out.append((sundays(y, 10)[-1] + pd.Timedelta("1h"), sundays(y, 11)[0] + pd.Timedelta("6h")))
    return out


def in_windows(ts: pd.DatetimeIndex, windows) -> np.ndarray:
    return np.any([(ts >= a) & (ts < b) for a, b in windows], axis=0)


def transition_weeks(hd: pd.Series, ref: pd.Series, ref_name: str) -> pd.DataFrame:
    """The 7 days either side of each US DST change, where ambiguous='NaT' drops the
    repeated hour under a DST-aware build."""
    lo, hi = max(hd.index[0], ref.index[0]), min(hd.index[-1], ref.index[-1])
    years = range(lo.year, hi.year + 1)
    out = []
    for y in years:
        tz = pd.date_range(f"{y}-01-01", f"{y}-12-31 23:00", freq="h", tz="America/New_York")
        flips = tz[1:][_dst_fast(tz[1:]) != _dst_fast(tz[:-1])]
        for f in flips:
            for side, a, b in (("before", f - pd.Timedelta(days=7), f), ("after", f, f + pd.Timedelta(days=7))):
                r = ref[(ref.index >= a) & (ref.index < b)]
                if len(r) == 0:
                    continue
                h = hd[(hd.index >= a - pd.Timedelta(hours=2)) & (hd.index < b + pd.Timedelta(hours=2))]
                rec = {"change_utc": f.tz_convert("UTC"), "side": side, "reference": ref_name}
                for off in OFFSETS:
                    d = compare(h, r, off)
                    rec[f"median_{off:+d}"] = d.absdiff.median() if len(d) else np.nan
                    rec[f"count_{off:+d}"] = len(d)
                med = [rec[f"median_{o:+d}"] for o in OFFSETS]
                rec["best_offset"] = OFFSETS[int(np.nanargmin(med))] if not np.all(np.isnan(med)) else np.nan
                out.append(rec)
    return pd.DataFrame(out)


def reopen_hours(s: pd.Series, name: str) -> pd.DataFrame:
    """UTC hour of the first bar after each weekend gap of > 24 h, by NY DST regime.
    Every FX venue reopens at 17:00 New York: 21:00 UTC under EDT, 22:00 under EST."""
    idx = s.index
    gaps = idx[1:][np.diff(idx.asi8) > 24 * 3600 * 10**9]
    gaps = gaps[gaps.day_of_week == 6]  # Sunday reopen only
    df = pd.DataFrame({"hour": gaps.hour, "regime": np.where(_dst_fast(gaps), "EDT", "EST")})
    t = df.groupby(["regime", "hour"]).size().unstack(fill_value=0)
    t.index = [f"{name} {r}" for r in t.index]
    return t


def main() -> None:
    hd = pd.read_parquet(BARS / "histdata_bid_2015_2025.parquet")["close"].astype("float64")
    du = pd.read_parquet(BARS / "dukascopy_bid_2007_2023.parquet")["close"].astype("float64")
    ec = pd.read_parquet(BARS / "eightcap_bidask_2024_2026.parquet")["bid"].astype("float64")
    cap = pd.Timestamp(HOLDOUT_START, tz="UTC")
    hd, ec = hd[hd.index < cap], ec[ec.index < cap]
    du = du[du.index >= hd.index[0]]

    monthly = pd.concat([table(hd, du, "dukascopy"), table(hd, ec, "eightcap")], ignore_index=True)
    trans = pd.concat([transition_weeks(hd, du, "dukascopy"), transition_weeks(hd, ec, "eightcap")],
                      ignore_index=True)
    reopen = pd.concat([reopen_hours(hd, "histdata"), reopen_hours(du[du.index >= hd.index[0]], "dukascopy"),
                        reopen_hours(ec, "eightcap")]).fillna(0).astype(int)

    off = pd.concat([days_off(hd, du, "dukascopy"), days_off(hd, ec, "eightcap")], ignore_index=True)
    win = dst_mismatch_windows(range(hd.index[0].year, hd.index[-1].year + 1))
    off["in_us_eu_mismatch"] = in_windows(pd.DatetimeIndex(pd.to_datetime(off.date_utc)).tz_localize("UTC")
                                          + pd.Timedelta("23h"), win)

    RESULTS_DIR.mkdir(exist_ok=True)
    monthly.to_csv(RESULTS_DIR / "histdata_alignment_monthly.csv", index=False)
    trans.to_csv(RESULTS_DIR / "histdata_alignment_transitions.csv", index=False)
    off.to_csv(RESULTS_DIR / "histdata_alignment_days_off.csv", index=False)

    pd.set_option("display.width", 200, "display.max_rows", 400)
    mcols = ["reference", "month", "regime", "count_+0", "median_-60", "median_+0", "median_+60", "best_offset"]
    print("== Monthly (abs bid difference, pips; median over common minutes) ==")
    print(monthly[mcols].round(3).to_string(index=False))
    print("\n== Best offset by reference and regime: number of month-regime cells ==")
    print(monthly.groupby(["reference", "regime"])["best_offset"].value_counts().unstack(fill_value=0))
    print("\n== Pooled by regime (median of monthly medians) ==")
    print(monthly.groupby(["reference", "regime"])[[f"median_{o:+d}" for o in OFFSETS]].median().round(3))
    print("\n== DST transition weeks ==")
    tcols = ["reference", "change_utc", "side", "count_+0", "median_-60", "median_+0", "median_+60", "best_offset"]
    print(trans[tcols].round(3).to_string(index=False))
    print("\n== Sunday reopen hour (UTC), count of weeks ==")
    print(reopen.to_string())
    nonzero = monthly[monthly.best_offset != 0]
    print(f"\nmonth-regime cells with best offset != 0: {len(nonzero)} of {len(monthly)}")
    print("\n== UTC dates with best offset != 0 (>= 60 common minutes) ==")
    for (ref, y), g in off.groupby(["reference", pd.to_datetime(off.date_utc).dt.year]):
        print(f"{ref:9s} {y}: {len(g):2d} days, offsets {sorted(set(g.best_offset))}, "
              f"{g.in_us_eu_mismatch.sum()} inside the US/EU DST mismatch: "
              f"{g.date_utc.min()} .. {g.date_utc.max()}")
    print(f"total {len(off)} days off, {int(off.in_us_eu_mismatch.sum())} inside a US/EU mismatch window")


if __name__ == "__main__":
    main()
