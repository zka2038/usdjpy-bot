"""Download Dukascopy USDJPY ticks.

    python scripts/download.py 2015-01-01 2024-12-31
    python scripts/download.py 2010-01-01 2024-12-31 --tokyo-hours
    python scripts/download.py 2025-01-01 2026-11-20   # holdout period, download but don't look

Roughly 20-60 MB of parquet per year for a full day. Re-running skips days already
downloaded.

--tokyo-hours fetches only UTC hours 22, 23, 0 and 1 while the market is open,
which covers specs 001 and 004 (08:00-11:00 JST) and spec 003's 00:00 UTC decision
time: ~15,600 requests instead of ~112,700 for 2010-2024. The datafeed rate-limits
hard; pass --pause 30. For spec 004's staged gap fill use download_gap_fill.py.

A windowed download is NOT interchangeable with a full one and `load_minute_bars`
cannot tell them apart, so --tokyo-hours writes to a SEPARATE tree
(DATA_DIR/tokyo_hours) rather than mixing partial days into DATA_DIR. Point
--out-dir somewhere else if you want, but do not aim it at a full-day tree.
"""
import argparse
import datetime as dt
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from usdjpy.config import DATA_DIR, SYMBOL  # noqa: E402
from usdjpy.dukascopy import TOKYO_MORNING_HOURS, download_range, market_open_hours  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("start", type=dt.date.fromisoformat)
p.add_argument("end", type=dt.date.fromisoformat)
p.add_argument("--symbol", default=SYMBOL)
p.add_argument("--overwrite", action="store_true")
p.add_argument("--tokyo-hours", action="store_true",
               help=f"fetch only UTC hours {TOKYO_MORNING_HOURS} into a separate tree")
p.add_argument("--out-dir", default=None,
               help="override the destination (default: DATA_DIR, or DATA_DIR/tokyo_hours "
                    "with --tokyo-hours)")
p.add_argument("--pause", type=float, default=0.0,
               help="minimum seconds between requests; the datafeed rate-limits (HTTP 429)")
a = p.parse_args()

hours = TOKYO_MORNING_HOURS if a.tokyo_hours else None
if a.out_dir is not None:
    out_dir = pathlib.Path(a.out_dir)
elif a.tokyo_hours:
    out_dir = pathlib.Path(DATA_DIR) / "tokyo_hours"
else:
    out_dir = pathlib.Path(DATA_DIR)

if a.tokyo_hours and out_dir.resolve() == pathlib.Path(DATA_DIR).resolve():
    raise SystemExit(
        "Refusing to write a windowed download into the full-day tree.\n"
        f"  {out_dir}\n"
        "Partial days are indistinguishable from complete ones once written. "
        "Drop --out-dir to use DATA_DIR/tokyo_hours, or name a different directory."
    )

days = [d.date() for d in __import__("pandas").date_range(a.start, a.end, freq="D") if d.weekday() != 5]
n_req = sum(24 if hours is None else len(market_open_hours(d, hours)) for d in days)
print(f"{a.symbol}  {a.start} -> {a.end}  ({len(days):,} non-Saturday days)")
print(f"hours: {'ALL 24' if hours is None else str(hours)}   requests: ~{n_req:,}")
print(f"dest:  {out_dir}")
download_range(a.symbol, a.start, a.end, out_dir, overwrite=a.overwrite, hours=hours,
               pause=a.pause)
