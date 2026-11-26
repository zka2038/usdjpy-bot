"""Spec 004 gap fill: Dukascopy bid/ask for the Tokyo morning, fetched in stages.

The options, the choice (option C) and the reasons are recorded in specs/README.md
under "Dukascopy fetch". The pre-declared use of the data is in spec 004's
"Gap fill" section. Read both before running.

    python scripts/download_gap_fill.py all --dry-run   # request counts, no network
    python scripts/download_gap_fill.py 1               # Feb-Jul 2023 HistData gap
    python scripts/download_gap_fill.py 2               # 2015-2024 spread sample
    python scripts/download_gap_fill.py 3               # 2007-2014, every weekday

Writes to DATA_DIR/tokyo_hours/USDJPY/ (UTC hours 22, 23, 0, 1; see
dukascopy.TOKYO_MORNING_HOURS). Never writes to the full-day tree. Re-running skips
days already on disk, so an interrupted stage resumes where it stopped. The datafeed
blocks bursts for hours, so the default pace is one request every 30 s, and a failed
hour pauses the run for 15 minutes instead of ending it.

Stage 2 is a sample, so the tree is deliberately sparse for 2015-2024: do not run a
study on it over that period as if it were a complete price source.
"""
import argparse
import datetime as dt
import pathlib
import sys
import time

import pandas as pd
import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from usdjpy.calendars import gotobi_days, jp_business_days  # noqa: E402
from usdjpy.config import DATA_DIR, SYMBOL  # noqa: E402
from usdjpy.dukascopy import TOKYO_MORNING_HOURS, download_range, market_open_hours  # noqa: E402

OUT_DIR = pathlib.Path(DATA_DIR) / "tokyo_hours"
RESTART_WAIT = 900
MAX_RESTARTS = 200


def spread_sample_jst_days(start: dt.date, end: dt.date) -> list[dt.date]:
    """Stage 2's sample: in each month, the first Gotobi-proper (B) day and the first
    control (C) day, partitioned exactly as scripts/turn_of_month_study.py does.
    Fixed by calendar, not chosen."""
    jp = jp_business_days(start, end)
    month_end = pd.DatetimeIndex(pd.Series(jp).groupby([jp.year, jp.month]).max().values)
    b = gotobi_days(start, end).difference(month_end)
    c = jp.difference(month_end).difference(b)
    out = []
    for group in (b, c):
        firsts = pd.Series(group, index=group).groupby([group.year, group.month]).min()
        out += [d.date() for d in firsts]
    return sorted(out)


def utc_days_for(jst_days: list[dt.date]) -> set[dt.date]:
    """A JST morning 08:00-11:00 spans the previous UTC date (hours 22-23) and its own
    (hours 0-1), so each JST day needs two UTC files."""
    return {d - dt.timedelta(days=k) for d in jst_days for k in (0, 1)}


# Each stage: (UTC start, UTC end, UTC days or None for every day in range, purpose).
STAGES = {
    "1": (dt.date(2023, 1, 31), dt.date(2023, 7, 31), None,
          "HistData's Feb-Jul 2023 gap at the 23:00 UTC entry: restores 14 spec 004 prefix trades (13 before the HistData DST fix)"),
    "2": (dt.date(2014, 12, 31), dt.date(2024, 12, 31),
          utc_days_for(spread_sample_jst_days(dt.date(2015, 1, 1), dt.date(2024, 12, 31))),
          "measured spread for the HistData era: first B and first C day of each month"),
    "3": (dt.date(2006, 12, 31), dt.date(2014, 12, 31), None,
          "real bid/ask for 2007-2014, every weekday: restores 176 prefix and 125 postfix trades"),
}


def missing_days(start, end, days, out_dir=None) -> list[tuple[dt.date, int]]:
    """(UTC day, requests) for every day in the stage not yet on disk. A day's file is
    written only once all its market-open hours are fetched; an hour the datafeed
    answers with 404 is stored empty and counts as fetched."""
    root = pathlib.Path(out_dir) if out_dir is not None else OUT_DIR
    out = []
    for d in pd.date_range(start, end, freq="D"):
        d = d.date()
        if d.weekday() == 5 or (days is not None and d not in days):
            continue
        n = len(market_open_hours(d, TOKYO_MORNING_HOURS))
        if n and not (root / SYMBOL / f"{d.year}" / f"{d}.parquet").exists():
            out.append((d, n))
    return out


def planned(start, end, days, out_dir=None):
    """(files, requests) still to fetch: days already on disk cost nothing."""
    m = missing_days(start, end, days, out_dir)
    return len(m), sum(n for _, n in m)


def run(stage: str, pause: float) -> None:
    start, end, days, why = STAGES[stage]
    for attempt in range(MAX_RESTARTS):
        try:
            download_range(SYMBOL, start, end, OUT_DIR, hours=TOKYO_MORNING_HOURS, pause=pause, days=days)
            print(f"stage {stage} complete", flush=True)
            return
        except (RuntimeError, requests.RequestException) as e:
            print(f"stage {stage}: {e}; resuming in {RESTART_WAIT}s ({attempt + 1}/{MAX_RESTARTS})", flush=True)
            time.sleep(RESTART_WAIT)
    raise SystemExit(f"stage {stage} gave up after {MAX_RESTARTS} restarts")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=[*STAGES, "all"])
    ap.add_argument("--pause", type=float, default=30.0, help="minimum seconds between requests")
    ap.add_argument("--dry-run", action="store_true", help="print what is left to fetch and exit")
    a = ap.parse_args()
    stages = list(STAGES) if a.stage == "all" else [a.stage]
    total = 0
    for s in stages:
        start, end, days, why = STAGES[s]
        files, reqs = planned(start, end, days)
        total += reqs
        print(f"stage {s}: {start} -> {end}  {files:,} files, {reqs:,} requests "
              f"(~{reqs * a.pause / 3600:.1f} h at {a.pause:g}s)\n  {why}")
    print(f"dest: {OUT_DIR}   hours: {TOKYO_MORNING_HOURS}   total {total:,} requests")
    if not a.dry_run:
        for s in stages:
            run(s, a.pause)
