"""Is histdata_bid_2015_2025.parquet aligned to UTC, in US summer and at DST changes?

HistData's raw stamps are New York local time. If they were converted with DST
(America/New_York), summer and winter both land on true UTC. If they were converted
with a fixed +5 h (the first committed version of build_github_data.py did this),
every EDT bar is labelled one hour late.

Method: shift the HistData index by -60, 0 and +60 minutes, join it to an
independent bid source on common minutes and take the absolute difference of bid
closes. The offset with the smallest difference is the one that aligns the two.
Reported month by month split by NY DST regime, by DST transition week, day by
day, and by Sunday reopen hour (17:00 New York at every FX venue: 21:00 UTC under
EDT, 22:00 under EST).

References:
  dukascopy_bid_2007_2023.parquet   2015-01 .. 2023-03 (gappy). Raw export stamps
                                    carry explicit GMT offsets, so no DST guess.
  eightcap_bidask_2024_2026.parquet 2024-06-19 .. 2024-12-31. Capped at HOLDOUT_START:
                                    this check spends no post-holdout data.

Offset sign: the HistData bar labelled T is compared with the reference bar at
T + offset. Offset +60 is best where the HistData label T carries the true T+60
price.

Finding (2026-11-25): full months align at 0, but from 2019 the weeks between the
US and EU DST changes align at +60: HistData's raw clock follows EU DST dates.
`datasets.fix_histdata_dst` corrects it in the loader. This script reports the file
as stored, then re-runs on the corrected series, which must show no dates off.

Where no reference exists (2020, Nov 2023, Mar 2024), each US/EU mismatch window is
also checked without one: the Sunday reopen label hour, and the lag that best
aligns the window's intraday |return| profile with the same window's profile in
2015-2018, which the reference comparison shows to be correctly stamped.

    python scripts/histdata_alignment_check.py
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from usdjpy.config import DATA_DIR, HOLDOUT_START, RESULTS_DIR  # noqa: E402
from usdjpy.datasets import HISTDATA_EU_DST_FROM, fix_histdata_dst, us_eu_dst_mismatch_windows  # noqa: E402

BARS = DATA_DIR / "bars_1min"
OFFSETS = (-60, 0, 60)
PIP = 0.01


def is_edt(idx: pd.DatetimeIndex) -> np.ndarray:
    """True where New York is on daylight time at that UTC instant (offset -4 h)."""
    ny = idx.tz_convert("America/New_York")
    off = (ny.tz_localize(None) - idx.tz_convert("UTC").tz_localize(None)) / pd.Timedelta(hours=1)
    return np.asarray(off == -4)


def in_windows(ts: pd.DatetimeIndex, windows) -> np.ndarray:
    return np.any([(ts >= a) & (ts < b) for a, b in windows], axis=0)


def compare(hd: pd.Series, ref: pd.Series, offset_min: int) -> pd.DataFrame:
    """Absolute bid difference in pips on common minutes, HistData bar T vs ref bar T + offset.
    Indexed by the reference timestamp."""
    shifted = pd.Series(hd.to_numpy(), index=hd.index + pd.Timedelta(minutes=offset_min))
    j = pd.concat({"hd": shifted, "ref": ref}, axis=1, join="inner").dropna()
    return pd.DataFrame({"absdiff": (j.hd - j.ref).abs() / PIP}, index=j.index)


def _best(t: pd.DataFrame) -> np.ndarray:
    """Offset with the smallest median; an offset with no overlap (NaN) never wins."""
    med = t[[f"median_{o:+d}" for o in OFFSETS]].to_numpy()
    return np.array(OFFSETS)[np.nanargmin(np.where(np.isnan(med), np.inf, med), axis=1)]


def monthly_table(hd: pd.Series, ref: pd.Series, ref_name: str) -> pd.DataFrame:
    rows = []
    for off in OFFSETS:
        d = compare(hd, ref, off)
        d["month"] = d.index.strftime("%Y-%m")
        d["regime"] = np.where(is_edt(d.index), "EDT", "EST")
        g = d.groupby(["month", "regime"])["absdiff"].agg(["median", "mean", "count"])
        g.columns = [f"{c}_{off:+d}" for c in g.columns]
        rows.append(g)
    t = pd.concat(rows, axis=1).fillna({f"count_{o:+d}": 0 for o in OFFSETS})
    t["best_offset"] = _best(t)
    t["reference"] = ref_name
    return t.reset_index()


def days_off(hd: pd.Series, ref: pd.Series, ref_name: str) -> pd.DataFrame:
    """Every UTC date (>= 60 common minutes) whose best offset is not 0. Month cells
    can hide a one-week misalignment inside an otherwise aligned month."""
    m = {off: compare(hd, ref, off).absdiff for off in OFFSETS}
    d = pd.DataFrame({f"median_{o:+d}": s.groupby(s.index.date).median() for o, s in m.items()})
    d["count_+0"] = m[0].groupby(m[0].index.date).size()
    d = d[d["count_+0"] >= 60].copy()
    d["best_offset"] = _best(d)
    d["reference"] = ref_name
    d.index.name = "date_utc"
    return d[d.best_offset != 0].reset_index()


def transition_weeks(hd: pd.Series, ref: pd.Series, ref_name: str) -> pd.DataFrame:
    """The 7 days either side of each US DST change."""
    lo, hi = max(hd.index[0], ref.index[0]), min(hd.index[-1], ref.index[-1])
    out = []
    for y in range(lo.year, hi.year + 1):
        tz = pd.date_range(f"{y}-01-01", f"{y}-12-31 23:00", freq="h", tz="America/New_York")
        flips = tz[1:][is_edt(tz[1:]) != is_edt(tz[:-1])]
        for f in flips:
            for side, a, b in (("before", f - pd.Timedelta(days=7), f), ("after", f, f + pd.Timedelta(days=7))):
                r = ref[(ref.index >= a) & (ref.index < b)]
                if len(r) == 0:
                    continue
                h = hd[(hd.index >= a - pd.Timedelta(hours=2)) & (hd.index < b + pd.Timedelta(hours=2))]
                rec = {"change_utc": str(f.tz_convert("UTC")), "side": side, "reference": ref_name}
                for off in OFFSETS:
                    d = compare(h, r, off)
                    rec[f"median_{off:+d}"] = d.absdiff.median() if len(d) else np.nan
                    rec[f"count_{off:+d}"] = len(d)
                out.append(rec)
    t = pd.DataFrame(out)
    t["best_offset"] = _best(t)
    return t


def reopen_hours(s: pd.Series, name: str) -> pd.DataFrame:
    """UTC hour of the first bar after each Sunday weekend gap, by NY DST regime."""
    idx = s.index
    gaps = idx[1:][np.diff(idx.asi8) > 24 * 3600 * 10**9]
    gaps = gaps[gaps.day_of_week == 6]
    df = pd.DataFrame({"hour": gaps.hour, "regime": np.where(is_edt(gaps), "EDT", "EST")})
    t = df.groupby(["regime", "hour"]).size().unstack(fill_value=0)
    t.index = [f"{name} {r}" for r in t.index]
    return t


def _abs_ret_profile(s: pd.Series) -> np.ndarray:
    """Mean |1-min return| by UTC minute of day, consecutive minutes only, smoothed
    with a 15-minute circular moving average."""
    idx = s.index
    ok = np.diff(idx.asi8) == 60 * 10**9
    r = np.abs(np.diff(s.to_numpy()))[ok]
    mod = (idx[1:][ok].hour * 60 + idx[1:][ok].minute).to_numpy()
    prof = pd.Series(r).groupby(mod).mean().reindex(range(1440)).interpolate(limit_direction="both").to_numpy()
    k = 15
    return np.convolve(np.r_[prof[-k:], prof, prof[:k]], np.ones(k) / k, mode="same")[k:-k]


def reference_free(hd: pd.Series, last_year: int) -> pd.DataFrame:
    """Per US/EU mismatch window: the Sunday reopen label hour (21 if aligned, 20 if
    labels are an hour early), and the lag that best aligns the window's intraday
    |return| profile with the same-season windows of 2015-2018. Lag +60 means the
    label T looks like true T+60."""
    seasons = {"spring": 0, "autumn": 1}
    clean = us_eu_dst_mismatch_windows(range(2015, HISTDATA_EU_DST_FROM))
    refs = {}
    for name, k in seasons.items():
        parts = [hd[(hd.index >= a) & (hd.index < b)] for a, b in clean[k::2]]
        refs[name] = np.mean([_abs_ret_profile(p) for p in parts if len(p) > 1000], axis=0)
    out = []
    windows = us_eu_dst_mismatch_windows(range(2015, last_year + 1))
    for i, (a, b) in enumerate(windows):
        season = "spring" if i % 2 == 0 else "autumn"
        s = hd[(hd.index >= a) & (hd.index < b)]
        if len(s) < 1000:
            continue
        prof = _abs_ret_profile(s)
        corr = {lag: np.corrcoef(prof, np.roll(refs[season], -lag))[0, 1] for lag in OFFSETS}
        gaps = s.index[1:][np.diff(s.index.asi8) > 24 * 3600 * 10**9]
        out.append({"window_start": str(a.date()), "window_end": str(b.date()), "season": season,
                    "bars": len(s), "reopen_label_hours": ",".join(str(h) for h in gaps.hour),
                    **{f"corr_{o:+d}": round(c, 3) for o, c in corr.items()},
                    "best_lag": max(corr, key=corr.get)})
    return pd.DataFrame(out)


def run(hd: pd.Series, du: pd.Series, ec: pd.Series) -> dict:
    off = pd.concat([days_off(hd, du, "dukascopy"), days_off(hd, ec, "eightcap")], ignore_index=True)
    win = us_eu_dst_mismatch_windows(range(hd.index[0].year, hd.index[-1].year + 1))
    days = pd.DatetimeIndex(pd.to_datetime(off.date_utc)).tz_localize("UTC")
    # a UTC date is "in" a window if any of its trading hours are; test at 12:00 and 23:00
    off["in_us_eu_mismatch"] = (in_windows(days + pd.Timedelta("12h"), win)
                                | in_windows(days + pd.Timedelta("23h"), win)) if len(off) else []
    return {
        "monthly": pd.concat([monthly_table(hd, du, "dukascopy"), monthly_table(hd, ec, "eightcap")],
                             ignore_index=True),
        "transitions": pd.concat([transition_weeks(hd, du, "dukascopy"), transition_weeks(hd, ec, "eightcap")],
                                 ignore_index=True),
        "days_off": off,
        "reopen": pd.concat([reopen_hours(hd, "histdata"), reopen_hours(du, "dukascopy"),
                             reopen_hours(ec, "eightcap")]).fillna(0).astype(int),
        "reference_free": reference_free(hd, hd.index[-1].year),
    }


def report(r: dict, label: str, full: bool) -> None:
    print(f"\n{'#' * 78}\n# {label}\n{'#' * 78}")
    m = r["monthly"]
    if full:
        mcols = ["reference", "month", "regime", "count_+0", "median_-60", "median_+0", "median_+60", "best_offset"]
        print("== Monthly (abs bid difference, pips; median over common minutes) ==")
        print(m[mcols].round(3).to_string(index=False))
        print("\n== DST transition weeks ==")
        tcols = ["reference", "change_utc", "side", "count_+0", "median_-60", "median_+0", "median_+60", "best_offset"]
        print(r["transitions"][tcols].round(3).to_string(index=False))
    print("\n== Best offset by reference and regime: number of month-regime cells ==")
    print(m.groupby(["reference", "regime"])["best_offset"].value_counts().unstack(fill_value=0))
    print("\n== Pooled by regime (median of monthly medians) ==")
    print(m.groupby(["reference", "regime"])[[f"median_{o:+d}" for o in OFFSETS]].median().round(3))
    print("\n== Sunday reopen hour (UTC), count of weeks ==")
    print(r["reopen"].to_string())
    print("\n== Mismatch windows without a reference: reopen label hour and |return|-profile lag ==")
    print(r["reference_free"].to_string(index=False))
    off = r["days_off"]
    print(f"\nmonth-regime cells with best offset != 0: {(m.best_offset != 0).sum()} of {len(m)}")
    print(f"transition half-weeks with best offset != 0: {(r['transitions'].best_offset != 0).sum()} "
          f"of {len(r['transitions'])}")
    print("== UTC dates with best offset != 0 (>= 60 common minutes) ==")
    if len(off):
        for (ref, y), g in off.groupby(["reference", pd.to_datetime(off.date_utc).dt.year]):
            print(f"{ref:9s} {y}: {len(g):2d} days, offsets {sorted(set(g.best_offset))}, "
                  f"{int(g.in_us_eu_mismatch.sum())} inside a US/EU DST mismatch window: "
                  f"{g.date_utc.min()} .. {g.date_utc.max()}")
    print(f"total {len(off)} dates off, {int(off.in_us_eu_mismatch.sum()) if len(off) else 0} "
          f"inside a US/EU mismatch window")


def main() -> None:
    cap = pd.Timestamp(HOLDOUT_START, tz="UTC")
    raw = pd.read_parquet(BARS / "histdata_bid_2015_2025.parquet")["close"].astype("float64")
    raw = raw[raw.index < cap]
    du = pd.read_parquet(BARS / "dukascopy_bid_2007_2023.parquet")["close"].astype("float64")
    du = du[du.index >= raw.index[0]]
    ec = pd.read_parquet(BARS / "eightcap_bidask_2024_2026.parquet")["bid"].astype("float64")
    ec = ec[ec.index < cap]
    fixed = fix_histdata_dst(raw)

    RESULTS_DIR.mkdir(exist_ok=True)
    pd.set_option("display.width", 200, "display.max_rows", 400)
    for tag, series, full in (("stored", raw, True), ("corrected", fixed, False)):
        r = run(series, du, ec)
        for k in ("monthly", "transitions", "days_off", "reference_free"):
            r[k].to_csv(RESULTS_DIR / f"histdata_alignment_{tag}_{k}.csv", index=False)
        report(r, f"histdata_bid_2015_2025.parquet {tag.upper()}"
               + (" (datasets.fix_histdata_dst applied)" if tag == "corrected" else " (as on disk)"), full)


if __name__ == "__main__":
    main()
