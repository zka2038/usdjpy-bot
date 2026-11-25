"""Download Dukascopy bid/ask history to lossless monthly parquet (resumable).

    python scripts/fetch_dukascopy.py m1                  # 1-min bid+ask candles, 2003-05 -> yesterday  (~1-1.5 h)
    python scripts/fetch_dukascopy.py ticks               # every tick, bid+ask                          (~10-20 h)
    python scripts/fetch_dukascopy.py both                # m1 first, then ticks
    python scripts/fetch_dukascopy.py ticks --start 2007-01-01 --end 2024-12-31
    python scripts/fetch_dukascopy.py status              # coverage per year from the manifests

Safe to interrupt (Ctrl-C) and re-run: finished months are skipped, the month in flight is
re-fetched, months still in progress ('partial') are refreshed. Each month is written
atomically with a .json manifest beside it (status, counts, gaps, checks).

Output: data/dukascopy/{SYMBOL}/{m1,ticks}/{YYYY}/... - see docs/DATA.md. Prices are stored as
Dukascopy's integer points (USDJPY: value x 0.001 = JPY); usdjpy.datasets converts on load.

Holdout: this downloads through yesterday, i.e. past HOLDOUT_START. Downloading is fine;
using post-holdout data in any study must be declared in its spec (see CLAUDE.md).

Disk: m1 ~0.3 GB, ticks ~3-4 GB for 2003-2026. --raw-cache keeps Dukascopy's original
.bi5 files too (about the same again) so a rebuild never re-downloads.
"""
import argparse
import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from usdjpy.config import DATA_DIR, SYMBOL  # noqa: E402
from usdjpy.dukascopy_store import EARLIEST, download, status  # noqa: E402

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument("what", choices=["m1", "ticks", "both", "status"])
p.add_argument("--symbol", default=SYMBOL)
p.add_argument("--start", type=dt.date.fromisoformat, default=None, help="default: earliest available")
p.add_argument("--end", type=dt.date.fromisoformat, default=None, help="default: yesterday (UTC)")
p.add_argument("--out", type=pathlib.Path, default=pathlib.Path(DATA_DIR) / "dukascopy")
p.add_argument("--workers", type=int, default=2, help="parallel connections (default 2)")
p.add_argument("--rate", type=float, default=4.0,
               help="max requests/second; halves automatically when Dukascopy pushes back (default 4)")
p.add_argument("--all-hours", action="store_true", help="also request weekend hours (normally skipped)")
p.add_argument("--overwrite", action="store_true", help="re-download months already marked complete")
p.add_argument("--raw-cache", type=pathlib.Path, default=None, help="keep original .bi5 files in this folder")
a = p.parse_args()

if a.what == "status":
    s = status(a.symbol, a.out)
    print("No manifests yet." if s.empty else s.to_string())
    sys.exit(0)

start = a.start or EARLIEST.get(a.symbol, dt.date(2003, 5, 4))
end = a.end or (dt.datetime.utcnow().date() - dt.timedelta(days=1))
print(f"{a.symbol} {a.what}: {start} -> {end}  -> {a.out / a.symbol}")
print(f"workers {a.workers}, max {a.rate}/s, weekend hours {'fetched' if a.all_hours else 'skipped (audited)'}")

failed = 0
try:
    for kind in (["m1", "ticks"] if a.what == "both" else [a.what]):
        mans = download(kind, a.symbol, start, end, a.out, workers=a.workers, rate=a.rate,
                        all_hours=a.all_hours, overwrite=a.overwrite, raw_cache=a.raw_cache)
        bad = [m for m in mans if m["status"] == "failed"]
        failed += len(bad)
        for m in bad:
            print(f"  FAILED {kind} {m['month']}: {m['errors'][:3]}")
except KeyboardInterrupt:
    print("\nInterrupted. Re-run the same command to resume; finished months are kept.")
    sys.exit(130)

with pd.option_context("display.width", 140):
    print(status(a.symbol, a.out).to_string())
if failed:
    print(f"\n{failed} month(s) failed - re-run the same command to retry them.")
    sys.exit(1)
