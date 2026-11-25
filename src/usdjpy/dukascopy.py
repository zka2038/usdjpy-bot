"""Download and parse Dukascopy tick data (free bid/ask quotes, UTC timestamps).

Dukascopy serves one LZMA-compressed .bi5 file per symbol per hour:
    https://datafeed.dukascopy.com/datafeed/USDJPY/2024/00/05/13h_ticks.bi5
Note the month is ZERO-based (00 = January).

Each record is 20 bytes, big-endian:
    uint32 ms since start of hour, uint32 ask, uint32 bid, float32 ask_vol, float32 bid_vol
Prices are integers scaled by 1/POINT (USDJPY: 1 unit = 0.001 JPY).
Volumes are Dukascopy's own liquidity figures, NOT market volume.
"""
from __future__ import annotations

import datetime as dt
import json
import lzma
import pathlib
import time

import numpy as np
import pandas as pd
import requests

BASE_URL = "https://datafeed.dukascopy.com/datafeed/{sym}/{y}/{m:02d}/{d:02d}/{h:02d}h_ticks.bi5"
POINT = {"USDJPY": 1e-3, "EURJPY": 1e-3, "EURUSD": 1e-5, "GBPUSD": 1e-5}
RECORD = np.dtype([("ms", ">u4"), ("ask", ">u4"), ("bid", ">u4"), ("ask_vol", ">f4"), ("bid_vol", ">f4")])
COLUMNS = ["bid", "ask", "bid_vol", "ask_vol"]


def parse_bi5(payload: bytes, hour_start: pd.Timestamp, point: float) -> pd.DataFrame:
    """Decode one hourly .bi5 payload into a tick DataFrame indexed by UTC timestamp."""
    if not payload:
        return _empty()
    raw = lzma.decompress(payload)
    arr = np.frombuffer(raw, dtype=RECORD)
    idx = hour_start + pd.to_timedelta(arr["ms"].astype(np.int64), unit="ms")
    return pd.DataFrame(
        {
            "bid": arr["bid"].astype(np.float64) * point,
            "ask": arr["ask"].astype(np.float64) * point,
            "bid_vol": arr["bid_vol"].astype(np.float64),
            "ask_vol": arr["ask_vol"].astype(np.float64),
        },
        index=pd.DatetimeIndex(idx, name="ts"),
    )


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNS, index=pd.DatetimeIndex([], tz="UTC", name="ts"), dtype=float)


_last_request = 0.0


def _backoff(attempt: int, retry_after: str | None) -> float:
    """Seconds to wait after a throttled or failed request: Retry-After if given, else 30s doubling to 10 min."""
    if retry_after and retry_after.isdigit():
        return float(retry_after)
    return min(600.0, 30.0 * 2**attempt)


def fetch_hour(sym: str, hour_start: pd.Timestamp, session: requests.Session, retries: int = 8,
               pause: float = 0.0) -> pd.DataFrame:
    """One hour of ticks. `pause` is the minimum gap in seconds between successive requests.

    The datafeed rate-limits with 429/503 and dropped connections, so those back off
    for minutes rather than seconds (worst case ~45 min before giving up).
    """
    global _last_request
    url = BASE_URL.format(sym=sym, y=hour_start.year, m=hour_start.month - 1, d=hour_start.day, h=hour_start.hour)
    for attempt in range(retries):
        time.sleep(max(0.0, _last_request + pause - time.monotonic()))
        _last_request = time.monotonic()
        try:
            r = session.get(url, timeout=30)
        except requests.RequestException as e:
            wait = _backoff(attempt, None)
            print(f"  {type(e).__name__} on {url}; waiting {wait:.0f}s", flush=True)
            time.sleep(wait)
            continue
        if r.status_code == 200:
            return parse_bi5(r.content, hour_start, POINT[sym])
        if r.status_code == 404:
            return _empty()
        wait = _backoff(attempt, r.headers.get("Retry-After"))
        print(f"  HTTP {r.status_code} on {url}; waiting {wait:.0f}s", flush=True)
        time.sleep(wait)
    raise RuntimeError(f"Failed to download {url}")


def fetch_day(sym: str, day: dt.date, session: requests.Session | None = None,
              hours: tuple[int, ...] | None = None, pause: float = 0.0) -> pd.DataFrame:
    """One UTC day of ticks. `hours` restricts which UTC hours are fetched."""
    if hours is not None and not all(0 <= h < 24 for h in hours):
        raise ValueError(f"hours must be UTC hours 0-23, got {hours}")
    session = session or requests.Session()
    start = pd.Timestamp(day, tz="UTC")
    want = range(24) if hours is None else sorted(set(hours))
    frames = [fetch_hour(sym, start + pd.Timedelta(hours=h), session, pause=pause) for h in want]
    frames = [f for f in frames if len(f)]
    return pd.concat(frames).sort_index() if frames else _empty()


# Tokyo-morning window used by specs 001 and 004 (08:00-11:00 JST = 23:00-02:00 UTC),
# padded either side so events.quote_at has quotes to find at the window edges.
# Hour 0 also covers spec 003's 00:00 UTC decision timestamp, so one hours-limited
# download serves both specs.
TOKYO_MORNING_HOURS = (22, 23, 0, 1, 2)

# Written to out_dir/SYM/ so a tree records which hours its files hold.
HOURS_MANIFEST = "_hours.json"


def _claim_tree(sym_dir: pathlib.Path, hours: tuple[int, ...] | None) -> None:
    """Refuse to mix full-day and hours-limited files in one tree.

    A tree with parquet files but no manifest predates the manifest and is treated
    as full-day, so an hours-limited download can never land in it.
    """
    want = None if hours is None else sorted(set(hours))
    manifest = sym_dir / HOURS_MANIFEST
    if manifest.exists():
        have = json.loads(manifest.read_text())["hours"]
    elif any(not f.name.startswith(".") for f in sym_dir.glob("*/*.parquet")):
        have = None
    else:
        sym_dir.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"hours": want}) + "\n")
        return
    if have != want:
        describe = lambda h: "full-day" if h is None else f"UTC hours {h}"  # noqa: E731
        raise ValueError(
            f"{sym_dir} holds {describe(have)} files; refusing to add {describe(want)} files.\n"
            f"Partial and full downloads are not interchangeable. Use a separate out_dir."
        )


def download_range(sym: str, start: dt.date, end: dt.date, out_dir: str | pathlib.Path,
                   overwrite: bool = False, hours: tuple[int, ...] | None = None,
                   pause: float = 0.0) -> None:
    """Save one parquet of ticks per UTC day to out_dir/SYM/YYYY/YYYY-MM-DD.parquet. Skips Saturdays.

    `hours`: restrict to these UTC hours. A full day is 24 sequential requests, so
    2010-2024 full-day is ~112,700 requests (3-9 hours wall clock). Passing
    TOKYO_MORNING_HOURS cuts that to ~23,500 (0.7-2 hours) and ~21% of the storage.

    A partial download is NOT interchangeable with a full one: files written with
    `hours` set contain only those hours, and `load_minute_bars` cannot tell the
    difference. Keep partial and full downloads in separate out_dir trees; this is
    enforced via HOURS_MANIFEST in out_dir/SYM/.
    """
    out_dir = pathlib.Path(out_dir)
    _claim_tree(out_dir / sym, hours)
    session = requests.Session()
    for day in pd.date_range(start, end, freq="D"):
        if day.weekday() == 5:  # Saturday: FX market closed all day UTC
            continue
        path = out_dir / sym / f"{day.year}" / f"{day.date()}.parquet"
        if path.exists() and not overwrite:
            continue
        ticks = fetch_day(sym, day.date(), session, hours=hours, pause=pause)
        path.parent.mkdir(parents=True, exist_ok=True)
        ticks.to_parquet(path)
        print(f"{day.date()}: {len(ticks):>7} ticks")


def ticks_to_minute_bars(ticks: pd.DataFrame) -> pd.DataFrame:
    """1-minute bars of bid/ask close (last quote in the minute) plus tick count and mean spread."""
    if ticks.empty:
        return pd.DataFrame(columns=["bid", "ask", "spread", "n_ticks"])
    g = ticks.resample("1min")
    bars = pd.DataFrame({"bid": g["bid"].last(), "ask": g["ask"].last(), "n_ticks": g["bid"].count()})
    bars["spread"] = (ticks["ask"] - ticks["bid"]).resample("1min").mean()
    return bars.dropna(subset=["bid"])


def load_minute_bars(sym: str, data_dir: str | pathlib.Path, cache: bool = True) -> pd.DataFrame:
    """Load all daily tick parquets for sym and return 1-min bars (cached to data_dir/bars_SYM_1min.parquet)."""
    data_dir = pathlib.Path(data_dir)
    cache_path = data_dir / f"bars_{sym}_1min.parquet"
    # Skip dotfiles: macOS writes ._* AppleDouble companions on exFAT, and
    # pathlib's glob matches them.
    files = sorted(f for f in (data_dir / sym).glob("*/*.parquet") if not f.name.startswith("."))
    if not files and not cache_path.exists():
        raise FileNotFoundError(
            f"No tick data for {sym} under {data_dir / sym}.\n"
            f"data/ is gitignored, so a fresh clone has none. Download it first:\n"
            f"  python scripts/download.py 2010-01-01 2024-12-31 --tokyo-hours\n"
            f"(--tokyo-hours fetches only 22:00-02:00 UTC: ~23,500 requests instead of\n"
            f" ~112,700, enough for specs 001, 003 and 004, and writes to\n"
            f" data/tokyo_hours/ -- pass that as data_dir. Omit it for a full day.)"
        )
    if cache and cache_path.exists() and files and cache_path.stat().st_mtime >= max(f.stat().st_mtime for f in files):
        return pd.read_parquet(cache_path)
    bars = pd.concat([ticks_to_minute_bars(pd.read_parquet(f)) for f in files]).sort_index()
    bars = bars[~bars.index.duplicated(keep="last")]
    if cache:
        bars.to_parquet(cache_path)
    return bars
