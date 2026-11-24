"""Download Dukascopy USDJPY ticks.

    python scripts/download.py 2015-01-01 2024-12-31
    python scripts/download.py 2025-01-01 2026-11-20   # holdout period, download but don't look

Roughly 20-60 MB of parquet per year. Re-running skips days already downloaded.
"""
import argparse
import datetime as dt
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from usdjpy.config import DATA_DIR, SYMBOL  # noqa: E402
from usdjpy.dukascopy import download_range  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("start", type=dt.date.fromisoformat)
p.add_argument("end", type=dt.date.fromisoformat)
p.add_argument("--symbol", default=SYMBOL)
p.add_argument("--overwrite", action="store_true")
a = p.parse_args()
download_range(a.symbol, a.start, a.end, DATA_DIR, overwrite=a.overwrite)
