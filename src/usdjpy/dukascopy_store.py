"""Robust, resumable Dukascopy downloader that writes lossless monthly parquet.

Two datasets per symbol, both from Dukascopy's public datafeed (prices in UTC):

  ticks  one LZMA .bi5 file per HOUR:  {SYM}/{Y}/{MM0}/{DD}/{HH}h_ticks.bi5
         20-byte records: uint32 ms-in-hour, uint32 ask, uint32 bid, float32 ask_vol, float32 bid_vol
  m1     one LZMA .bi5 file per DAY and side:  {SYM}/{Y}/{MM0}/{DD}/{BID|ASK}_candles_min_1.bi5
         24-byte records: uint32 sec-in-day, uint32 open, uint32 close, uint32 low, uint32 high, float32 vol
         (field order is verified on every file - see `_candle_order`)

MM0 is the ZERO-based month (00 = January). Prices are integers in units of POINT
(USDJPY: 0.001 JPY) and are stored exactly as delivered - nothing is converted to float.

Output (one file + one manifest per month, written atomically):
  {out}/{SYM}/ticks/{YYYY}/{SYM}_ticks_{YYYYMM}.parquet   index ts (UTC, ns); bid, ask int32; bid_vol, ask_vol float32
  {out}/{SYM}/m1/{YYYY}/{SYM}_m1_{YYYYMM}.parquet         index ts (UTC, minute open); bid_o/h/l/c, ask_o/h/l/c int32;
                                                           bid_vol, ask_vol float32
  each with a sibling .json manifest: status (complete | partial | failed), counts, gaps, checks.

A month is "complete" only when every scheduled file downloaded and validated AND the month
lies wholly in the past (ends >= 2 days before today, UTC). Anything else is "partial" and is
re-fetched on the next run, so re-running the same command is always safe.

Volumes are Dukascopy's own liquidity figures, not market volume.
"""
from __future__ import annotations

import concurrent.futures as cf
import dataclasses
import datetime as dt
import json
import lzma
import os
import pathlib
import random
import socket
import threading
import time
from collections import Counter
from typing import Callable, Iterable

import numpy as np
import pandas as pd
import requests

DATAFEED = "https://datafeed.dukascopy.com/datafeed"
POINT = {"USDJPY": 1e-3, "EURJPY": 1e-3, "GBPJPY": 1e-3, "AUDJPY": 1e-3, "CHFJPY": 1e-3,
         "CADJPY": 1e-3, "NZDJPY": 1e-3, "EURUSD": 1e-5, "GBPUSD": 1e-5, "AUDUSD": 1e-5}
# First data Dukascopy serves for USDJPY (ticks and minute candles), UTC.
EARLIEST = {"USDJPY": dt.date(2003, 5, 4)}
# Plausibility band for prices, in the instrument's own units. Catches wrong scaling or decoding.
PRICE_BAND = {"USDJPY": (50.0, 300.0)}
# Crossed quotes (ask < bid) above this share of ticks/minutes fail validation.
MAX_CROSSED = 0.01

TICK_REC = np.dtype([("ms", ">u4"), ("ask", ">u4"), ("bid", ">u4"), ("ask_vol", ">f4"), ("bid_vol", ">f4")])
CANDLE_REC = np.dtype([("sec", ">u4"), ("a", ">u4"), ("b", ">u4"), ("c", ">u4"), ("d", ">u4"), ("vol", ">f4")])
SCHEMA_VERSION = 1


STOP = threading.Event()  # set on Ctrl-C so sleeping workers wake up and exit at once


class Stopped(RuntimeError):
    """Raised inside workers once STOP is set."""


def _sleep(seconds: float) -> None:
    if seconds > 0 and STOP.wait(seconds):
        raise Stopped()
    if STOP.is_set():
        raise Stopped()


def root_cause(e: BaseException) -> str:
    """Innermost exception in a requests/urllib3 chain, e.g. 'ConnectionResetError: [Errno 54] ...'."""
    seen, cur = set(), e
    while True:
        nxt = getattr(cur, "reason", None) or cur.__cause__ or cur.__context__
        if nxt is None or id(nxt) in seen or not isinstance(nxt, BaseException):
            break
        seen.add(id(cur))
        cur = nxt
    return f"{type(cur).__name__}: {cur}"


class FetchError(RuntimeError):
    """A file could not be downloaded or decoded after all retries."""


class ValidationError(RuntimeError):
    """Downloaded data failed a sanity check (wrong scaling, field order, crossed quotes...)."""


# ----------------------------------------------------------------------------------------------
# Schedules: which files to request
# ----------------------------------------------------------------------------------------------

def tick_url(sym: str, hour: dt.datetime) -> str:
    return f"{DATAFEED}/{sym}/{hour.year}/{hour.month - 1:02d}/{hour.day:02d}/{hour.hour:02d}h_ticks.bi5"


def candle_url(sym: str, day: dt.date, side: str) -> str:
    return f"{DATAFEED}/{sym}/{day.year}/{day.month - 1:02d}/{day.day:02d}/{side}_candles_min_1.bi5"


def is_weekend_hour(hour: dt.datetime) -> bool:
    """True for UTC hours when spot FX is closed: Fri 22:00 -> Sun 20:00 (conservative both sides).

    The weekly close is 21:00 UTC (US summer) or 22:00 (winter) on Friday and the reopen
    21:00/22:00 on Sunday, so Friday hours <= 21 and Sunday hours >= 20 are always fetched.
    """
    wd = hour.weekday()
    return wd == 5 or (wd == 4 and hour.hour >= 22) or (wd == 6 and hour.hour < 20)


def month_hours(year: int, month: int, start: dt.date, end: dt.date, all_hours: bool) -> tuple[list, list]:
    """(scheduled hours, skipped weekend hours) for one month, clipped to [start, end]."""
    first = max(dt.date(year, month, 1), start)
    last = min((pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)).date(), end)
    hours, skipped = [], []
    for day in pd.date_range(first, last, freq="D"):
        for h in range(24):
            ts = dt.datetime(day.year, day.month, day.day, h)
            (skipped if (not all_hours and is_weekend_hour(ts)) else hours).append(ts)
    return hours, skipped


def month_days(year: int, month: int, start: dt.date, end: dt.date) -> list[dt.date]:
    """Days to request minute candles for (Saturdays skipped: no trading)."""
    first = max(dt.date(year, month, 1), start)
    last = min((pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)).date(), end)
    return [d.date() for d in pd.date_range(first, last, freq="D") if d.weekday() != 5]


def months(start: dt.date, end: dt.date) -> list[tuple[int, int]]:
    return [(m.year, m.month) for m in pd.date_range(pd.Timestamp(start).replace(day=1), end, freq="MS")]


# ----------------------------------------------------------------------------------------------
# Decoding
# ----------------------------------------------------------------------------------------------

def _decompress(payload: bytes, rec: np.dtype) -> np.ndarray:
    if not payload:
        return np.empty(0, dtype=rec)
    raw = lzma.decompress(payload)
    if len(raw) % rec.itemsize:
        raise FetchError(f"decoded length {len(raw)} is not a multiple of {rec.itemsize}")
    return np.frombuffer(raw, dtype=rec)


def decode_ticks(payload: bytes, hour: dt.datetime) -> pd.DataFrame:
    """Lossless decode of one hourly tick file. Prices stay as integer points."""
    arr = _decompress(payload, TICK_REC)
    base = pd.Timestamp(hour, tz="UTC")
    idx = base + pd.to_timedelta(arr["ms"].astype(np.int64), unit="ms")
    if len(arr) and int(arr["ms"].max()) >= 3_600_000:
        raise ValidationError(f"tick offset beyond the hour in {hour}")
    return pd.DataFrame({"bid": arr["bid"].astype(np.int32), "ask": arr["ask"].astype(np.int32),
                         "bid_vol": arr["bid_vol"].astype(np.float32), "ask_vol": arr["ask_vol"].astype(np.float32)},
                        index=pd.DatetimeIndex(idx, name="ts").as_unit("ns"))


def _candle_order(arr: np.ndarray) -> tuple[str, str, str, str]:
    """Map the four price fields to (open, high, low, close), checked on the data itself.

    Dukascopy documents candles as open, close, low, high. We verify instead of trusting it:
    the right assignment satisfies low <= min(open, close) and high >= max(open, close) on
    essentially every bar; a wrong one fails on most bars that moved.
    """
    live = arr[arr["vol"] > 0]
    if len(live) == 0:
        return ("a", "d", "c", "b")  # documented order; nothing to verify against
    candidates = {("a", "d", "c", "b"): "open,close,low,high (documented)",
                  ("a", "b", "c", "d"): "open,high,low,close"}
    for o, h, l, c in candidates:
        ok = ((live[l] <= np.minimum(live[o], live[c])) & (live[h] >= np.maximum(live[o], live[c]))).mean()
        if ok >= 0.999:
            return (o, h, l, c)
    raise ValidationError("candle fields fit neither open,close,low,high nor open,high,low,close")


def decode_candles(payload: bytes, day: dt.date) -> tuple[pd.DataFrame, str]:
    """Lossless decode of one daily minute-candle file -> (o, h, l, c int32, vol float32), field order used."""
    arr = _decompress(payload, CANDLE_REC)
    o, h, l, c = _candle_order(arr)
    if len(arr) and int(arr["sec"].max()) >= 86_400:
        raise ValidationError(f"candle offset beyond the day in {day}")
    idx = pd.Timestamp(day, tz="UTC") + pd.to_timedelta(arr["sec"].astype(np.int64), unit="s")
    df = pd.DataFrame({"o": arr[o].astype(np.int32), "h": arr[h].astype(np.int32), "l": arr[l].astype(np.int32),
                       "c": arr[c].astype(np.int32), "vol": arr["vol"].astype(np.float32)},
                      index=pd.DatetimeIndex(idx, name="ts"))
    return df, f"{o}{h}{l}{c}"


# ----------------------------------------------------------------------------------------------
# HTTP with adaptive rate limiting
# ----------------------------------------------------------------------------------------------

class AdaptiveRate:
    """Thread-safe token pacing that halves on throttling and creeps back up on success."""

    def __init__(self, rate: float, floor: float = 0.25, ceiling: float | None = None,
                 recover_every: int = 50, halve_window: float = 5.0):
        self.rate, self.floor, self.ceiling = rate, floor, ceiling or rate
        self.recover_every, self.halve_window = recover_every, halve_window
        self._next = time.monotonic()
        self._ok_streak = 0
        self._last_halve = -1e9
        self._lock = threading.Lock()
        self.throttle_events = 0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            slot = max(self._next, now)
            self._next = slot + 1.0 / self.rate
        _sleep(slot - time.monotonic())

    def success(self) -> None:
        with self._lock:
            self._ok_streak += 1
            if self._ok_streak >= self.recover_every and self.rate < self.ceiling:
                self.rate = min(self.ceiling, self.rate * 1.15)
                self._ok_streak = 0

    def throttled(self, cooldown: float) -> None:
        """One server push-back. Parallel workers usually fail together, so the rate is halved at
        most once per `halve_window` seconds - otherwise 4 simultaneous errors cut 8/s to 0.5/s."""
        with self._lock:
            self.throttle_events += 1
            self._ok_streak = 0
            now = time.monotonic()
            if now - self._last_halve >= self.halve_window:
                self.rate = max(self.floor, self.rate / 2)
                self._last_halve = now
            self._next = max(self._next, now + cooldown)


NEUTRAL_HOSTS = (("1.1.1.1", 443), ("8.8.8.8", 443), ("www.apple.com", 443))


def _tcp(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _retry_after_seconds(r) -> float | None:
    """Seconds from a Retry-After header (delta-seconds or HTTP date), if the server sent one."""
    v = (getattr(r, "headers", None) or {}).get("Retry-After")
    if not v:
        return None
    try:
        return max(0.0, float(v))
    except ValueError:
        try:
            from email.utils import parsedate_to_datetime
            return max(0.0, (parsedate_to_datetime(v) - dt.datetime.now(dt.timezone.utc)).total_seconds())
        except (TypeError, ValueError):
            return None


def _retry_after_note(r) -> str:
    sec = _retry_after_seconds(r)
    return "" if sec is None else f", Retry-After {sec:.0f}s"


def internet_up(timeout: float = 5.0) -> bool:
    """Is the machine online at all? Probes neutral hosts, NOT Dukascopy: when Dukascopy refuses or
    drops our connections that is server push-back (slow down), not an outage (pause)."""
    return any(_tcp(h, p, timeout) for h, p in NEUTRAL_HOSTS)


class OnlineGate:
    """Shared pause for all workers while the machine is offline (Wi-Fi drop, sleep, VPN flap)."""

    def __init__(self, check: Callable[[], bool] = internet_up, poll: float = 30.0,
                 log: Callable[[str], None] = print):
        self.check, self.poll, self.log = check, poll, log
        self._lock = threading.Lock()
        self.pauses = 0
        self.paused_seconds = 0.0
        self._resumed_at = -1e9
        self.grace = 60.0  # errors this soon after a resume were in flight during the outage

    def wait_until_online(self) -> bool:
        """Block while offline. Returns True if we were offline (so the failed attempt is free)."""
        with self._lock:  # one worker probes; the others queue here and pass straight through after
            if self.check():
                return time.monotonic() - self._resumed_at < self.grace
            self.pauses += 1
            t0 = time.monotonic()
            self.log(f"  offline - pausing all workers, checking every {self.poll:.0f}s ...")
            while not self.check():
                _sleep(self.poll)
            dt_ = time.monotonic() - t0
            self.paused_seconds += dt_
            self._resumed_at = time.monotonic()
            self.log(f"  back online after {dt_ / 60:.1f} min - resuming")
            return True


@dataclasses.dataclass
class Fetcher:
    """GET with retries, exponential backoff + jitter, and a shared adaptive rate."""

    rate: AdaptiveRate
    retries: int = 8
    timeout: tuple[float, float] = (10.0, 30.0)
    raw_cache: pathlib.Path | None = None
    session_factory: Callable[[], requests.Session] = requests.Session
    gate: OnlineGate | None = None
    _local: threading.local = dataclasses.field(default_factory=threading.local)
    requests_made: int = 0
    cache_hits: int = 0
    failures: Counter = dataclasses.field(default_factory=Counter)
    max_offline_rounds: int = 1000
    max_rate_limited_rounds: int = 40   # ~40 escalating waits (up to 10 min each) before giving up on a file
    # Dukascopy drops/refuses connections when we go too fast. Escalating cooldown, reset on success.
    pushback_cooldown: float = 30.0
    pushback_max: float = 600.0
    log: Callable[[str], None] = print
    _pushback_level: int = 0
    _pushback_until: float = -1e9
    _ok_since_pushback: int = 0
    _pb_lock: threading.Lock = dataclasses.field(default_factory=threading.Lock)

    def _session(self) -> requests.Session:
        s = getattr(self._local, "s", None)
        if s is None:
            s = self._local.s = self.session_factory()
            if hasattr(s, "headers"):
                s.headers.update({"User-Agent": "usdjpy-bot research downloader (python-requests)"})
        return s

    def _cache_path(self, url: str) -> pathlib.Path | None:
        return None if self.raw_cache is None else self.raw_cache / url.split("/datafeed/", 1)[1]

    def get(self, url: str, decode: Callable[[bytes], object]):
        """Return decode(payload). 404 / empty body means 'no data' -> decode(b'')."""
        cp = self._cache_path(url)
        if cp is not None and cp.exists():
            self.cache_hits += 1
            return decode(cp.read_bytes())
        last, attempt, offline_rounds, limited_rounds = None, 0, 0, 0
        while attempt < self.retries:
            self.rate.wait()
            try:
                r = self._session().get(url, timeout=self.timeout)
                self.requests_made += 1
            except requests.RequestException as e:  # timeouts, resets, DNS, offline
                kind = type(e).__name__
                last = f"{kind}: {root_cause(e)}"
                if (isinstance(e, requests.ConnectionError) and self.gate is not None
                        and offline_rounds < self.max_offline_rounds and self.gate.wait_until_online()):
                    offline_rounds += 1      # we were offline: free retry, no slowdown
                    continue
                self.failures[kind] += 1
                if isinstance(e, requests.ConnectionError):   # online, but Dukascopy cut us off
                    self._pushback(detail=root_cause(e))
                else:
                    self._backoff(attempt, throttle=True)
                attempt += 1
                continue
            if r.status_code == 404:
                self._succeeded()
                return decode(b"")
            if r.status_code == 200:
                try:
                    out = decode(r.content)
                except (lzma.LZMAError, FetchError) as e:  # truncated/corrupt transfer: retry
                    last = f"decode: {e}"
                    self.failures["corrupt payload"] += 1
                    self._backoff(attempt, throttle=False)
                    attempt += 1
                    continue
                self._succeeded()
                if cp is not None and r.content:
                    cp.parent.mkdir(parents=True, exist_ok=True)
                    tmp = cp.with_suffix(cp.suffix + ".tmp")
                    tmp.write_bytes(r.content)
                    os.replace(tmp, cp)
                return out
            last = f"HTTP {r.status_code}"
            self.failures[last] += 1
            if r.status_code == 429 and limited_rounds < self.max_rate_limited_rounds:
                # Too Many Requests is about us, not this file: wait it out, don't spend retries.
                limited_rounds += 1
                self._pushback(detail=f"HTTP 429 Too Many Requests{_retry_after_note(r)}",
                               min_wait=_retry_after_seconds(r))
                continue
            self._backoff(attempt, throttle=r.status_code in (403, 429) or r.status_code >= 500)
            attempt += 1
        raise FetchError(f"{url}: gave up after {self.retries} attempts ({last})")

    def _succeeded(self) -> None:
        self.rate.success()
        self._ok_since_pushback += 1
        if self._ok_since_pushback >= 50:
            self._pushback_level = 0

    def _pushback(self, detail: str = "", min_wait: float | None = None) -> None:
        """Connection refused/reset while the internet is fine: Dukascopy is limiting us.

        Escalates at most once per cooldown: parallel workers usually fail together, and
        counting each of them separately jumped 30 s straight to 120 s on the first real run."""
        with self._pb_lock:
            self._ok_since_pushback = 0
            now = time.monotonic()
            if now >= self._pushback_until:
                wait = min(self.pushback_max, self.pushback_cooldown * 2 ** self._pushback_level)
                if min_wait:
                    wait = max(wait, min(min_wait, 3600.0))
                self._pushback_level += 1
                self._pushback_until = now + wait
                self.rate.throttled(cooldown=wait)
                self.log(f"  Dukascopy is limiting us (internet OK) - backing off {wait:.0f}s, "
                         f"rate now {self.rate.rate:.1f}/s\n    cause: {detail[:200]}")
            remaining = self._pushback_until - now
        _sleep(max(0.0, remaining) * (0.9 + 0.2 * random.random()))

    def _backoff(self, attempt: int, throttle: bool) -> None:
        delay = min(120.0, 2.0 ** attempt) * (0.5 + random.random())
        if throttle:
            self.rate.throttled(cooldown=delay)
        _sleep(delay)


# ----------------------------------------------------------------------------------------------
# Month jobs
# ----------------------------------------------------------------------------------------------

def _paths(out: pathlib.Path, sym: str, kind: str, year: int, month: int) -> tuple[pathlib.Path, pathlib.Path]:
    stem = out / sym / kind / f"{year}" / f"{sym}_{kind}_{year}{month:02d}"
    return stem.with_suffix(".parquet"), stem.with_suffix(".json")


def read_manifest(path: pathlib.Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _write_atomic(df: pd.DataFrame, pq: pathlib.Path, manifest: dict, mf: pathlib.Path) -> None:
    pq.parent.mkdir(parents=True, exist_ok=True)
    tmp = pq.with_suffix(".parquet.tmp")
    df.to_parquet(tmp, compression="zstd")
    back = pd.read_parquet(tmp)  # read-back check before the file replaces anything
    same = (len(back) == len(df) and list(back.columns) == list(df.columns)
            and np.array_equal(back.index.as_unit("ns").asi8, df.index.as_unit("ns").asi8)
            and all(np.array_equal(back[c].to_numpy(), df[c].to_numpy(), equal_nan=df[c].dtype.kind == "f")
                    for c in df.columns))
    if not same:
        tmp.unlink(missing_ok=True)
        raise ValidationError(f"read-back mismatch writing {pq}")
    os.replace(tmp, pq)
    manifest["bytes"] = pq.stat().st_size
    mtmp = mf.with_suffix(".json.tmp")
    mtmp.write_text(json.dumps(manifest, indent=1, default=str))
    os.replace(mtmp, mf)


def _write_failed(mf: pathlib.Path, manifest: dict) -> None:
    mf.parent.mkdir(parents=True, exist_ok=True)
    manifest["status"] = "failed"
    mf.write_text(json.dumps(manifest, indent=1, default=str))


def _finalised(year: int, month: int, today: dt.date) -> bool:
    month_end = (pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)).date()
    return month_end <= today - dt.timedelta(days=2)


def _month_status(sym: str, year: int, month: int, start: dt.date, end: dt.date, today: dt.date) -> str:
    """'complete' only if the request covered the whole month (or began at the first data Dukascopy has)
    and the month is safely in the past. A month clipped by --start/--end stays 'partial', so a later
    run with a wider range fills it instead of skipping it."""
    m_start, m_end = dt.date(year, month, 1), manifest_end(year, month)
    covers_start = start <= m_start or start == EARLIEST.get(sym)
    return "complete" if covers_start and end >= m_end and _finalised(year, month, today) else "partial"


def _check_prices(sym: str, bid: np.ndarray, ask: np.ndarray, what: str) -> dict:
    lo, hi = PRICE_BAND.get(sym, (0.0, np.inf))
    point = POINT[sym]
    if len(bid) == 0:
        return {"crossed_share": 0.0}
    pmin, pmax = float(min(bid.min(), ask.min())) * point, float(max(bid.max(), ask.max())) * point
    if pmin < lo or pmax > hi:
        raise ValidationError(f"{what}: prices {pmin:.3f}-{pmax:.3f} outside plausible band {lo}-{hi} "
                              f"(wrong POINT scaling or corrupt decode)")
    crossed = float((ask < bid).mean())
    if crossed > MAX_CROSSED:
        raise ValidationError(f"{what}: {crossed:.1%} of quotes have ask < bid")
    return {"price_min": round(pmin, 3), "price_max": round(pmax, 3), "crossed_share": round(crossed, 6)}


def _parallel(fetcher: Fetcher, jobs: list, workers: int) -> tuple[dict, list]:
    """Run (key, url, decode) jobs; return ({key: result}, [errors]). Never raises for one bad file."""
    results, errors = {}, []
    ex = cf.ThreadPoolExecutor(max_workers=workers)
    try:
        futs = {ex.submit(fetcher.get, url, dec): key for key, url, dec in jobs}
        for f in cf.as_completed(futs):
            try:
                results[futs[f]] = f.result()
            except (FetchError, ValidationError) as e:
                errors.append(f"{futs[f]}: {e}")
            except Stopped:
                pass
    except KeyboardInterrupt:
        STOP.set()                      # wake every sleeping worker so they exit now
        ex.shutdown(wait=True, cancel_futures=True)
        raise
    ex.shutdown(wait=True)
    if STOP.is_set():
        raise KeyboardInterrupt
    return results, errors


def fetch_tick_month(sym: str, year: int, month: int, start: dt.date, end: dt.date, out: pathlib.Path,
                     fetcher: Fetcher, workers: int, all_hours: bool, today: dt.date,
                     audit_skipped: int = 2) -> dict:
    pq, mf = _paths(out, sym, "ticks", year, month)
    hours, skipped = month_hours(year, month, start, end, all_hours)
    manifest = {"schema": SCHEMA_VERSION, "symbol": sym, "kind": "ticks", "month": f"{year}-{month:02d}",
                "range": [str(max(dt.date(year, month, 1), start)), str(min(end, (pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)).date()))],
                "hours_scheduled": len(hours), "hours_skipped_weekend": len(skipped), "point": POINT[sym],
                "price_unit": "integer points (price = value * point)", "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    # Weekend skip is an assumption: verify it on a few skipped hours every month.
    audit = random.Random(f"{sym}{year}{month}").sample(skipped, min(audit_skipped, len(skipped)))
    jobs = [(h, tick_url(sym, h), (lambda p, h=h: decode_ticks(p, h))) for h in hours + audit]
    res, errors = _parallel(fetcher, jobs, workers)
    leaked = [str(h) for h in audit if h in res and len(res[h])]
    if leaked:
        errors.append(f"weekend hours that were assumed closed contain ticks: {leaked}. "
                      f"Re-run with --all-hours.")
    manifest["errors"] = errors
    if errors:
        _write_failed(mf, manifest)
        return manifest
    try:
        return _finish_ticks(sym, year, month, start, end, today, hours, res, manifest, pq, mf)
    except ValidationError as e:
        manifest["errors"] = [str(e)]
        _write_failed(mf, manifest)
        return manifest


def _finish_ticks(sym, year, month, start, end, today, hours, res, manifest, pq, mf) -> dict:
    frames = [res[h] for h in hours if len(res[h])]
    df = (pd.concat(frames) if frames else decode_ticks(b"", dt.datetime(year, month, 1))).sort_index(kind="stable")
    empty_hours = [h for h in hours if len(res[h]) == 0]
    # Empty weekday trading hours are gaps worth knowing about (holidays explain some).
    weekday_gaps = [str(h) for h in empty_hours if h.weekday() < 5 and not is_weekend_hour(h)]
    manifest.update({"ticks": int(len(df)), "hours_with_data": len(hours) - len(empty_hours),
                     "weekday_hours_empty": len(weekday_gaps), "weekday_hours_empty_sample": weekday_gaps[:20],
                     "checks": _check_prices(sym, df["bid"].to_numpy(), df["ask"].to_numpy(), f"ticks {year}-{month:02d}"),
                     "status": _month_status(sym, year, month, start, end, today)})
    _write_atomic(df, pq, manifest, mf)
    return manifest


def manifest_end(year: int, month: int) -> dt.date:
    return (pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)).date()


def fetch_m1_month(sym: str, year: int, month: int, start: dt.date, end: dt.date, out: pathlib.Path,
                   fetcher: Fetcher, workers: int, today: dt.date) -> dict:
    pq, mf = _paths(out, sym, "m1", year, month)
    days = month_days(year, month, start, end)
    manifest = {"schema": SCHEMA_VERSION, "symbol": sym, "kind": "m1", "month": f"{year}-{month:02d}",
                "days_scheduled": len(days), "point": POINT[sym],
                "price_unit": "integer points (price = value * point)", "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    jobs = [((d, side), candle_url(sym, d, side), (lambda p, d=d: decode_candles(p, d)))
            for d in days for side in ("BID", "ASK")]
    res, errors = _parallel(fetcher, jobs, workers)
    manifest["errors"] = errors
    if errors:
        _write_failed(mf, manifest)
        return manifest
    try:
        return _finish_m1(sym, year, month, start, end, today, days, res, manifest, pq, mf)
    except ValidationError as e:
        manifest["errors"] = [str(e)]
        _write_failed(mf, manifest)
        return manifest


def _finish_m1(sym, year, month, start, end, today, days, res, manifest, pq, mf) -> dict:
    orders, parts = set(), []
    for d in days:
        (b, ob), (a, oa) = res[(d, "BID")], res[(d, "ASK")]
        orders.update({ob, oa})
        if len(b) == 0 and len(a) == 0:
            continue
        j = b.add_prefix("bid_").join(a.add_prefix("ask_"), how="outer")
        parts.append(j)
    cols = ["bid_o", "bid_h", "bid_l", "bid_c", "ask_o", "ask_h", "ask_l", "ask_c", "bid_vol", "ask_vol"]
    if parts:
        df = pd.concat(parts).sort_index()
        # Dukascopy fills idle minutes with flat zero-volume candles; drop minutes with no ticks on either side.
        live = (df["bid_vol"].fillna(0) > 0) | (df["ask_vol"].fillna(0) > 0)
        flat_dropped = int((~live).sum())
        df = df[live]
        one_sided = df[cols[:8]].isna().any(axis=1)
        if one_sided.mean() > 0.001:
            raise ValidationError(f"m1 {year}-{month:02d}: {one_sided.mean():.2%} of live minutes have only one side")
        manifest["one_sided_minutes_dropped"] = int(one_sided.sum())
        df = df[~one_sided].astype({c: "int32" for c in cols[:8]} | {c: "float32" for c in cols[8:]})[cols]
    else:
        df = pd.DataFrame({c: pd.Series(dtype="int32" if i < 8 else "float32") for i, c in enumerate(cols)},
                          index=pd.DatetimeIndex([], tz="UTC", name="ts").as_unit("ns"))
        flat_dropped = 0
    per_day = df.groupby(df.index.date).size() if len(df) else pd.Series(dtype=int)
    manifest.update({"minutes": int(len(df)), "flat_minutes_dropped": flat_dropped,
                     "days_with_data": int(len(per_day)), "candle_field_order": sorted(orders),
                     "checks": _check_prices(sym, df["bid_c"].to_numpy() if len(df) else np.array([]),
                                             df["ask_c"].to_numpy() if len(df) else np.array([]), f"m1 {year}-{month:02d}"),
                     "status": _month_status(sym, year, month, start, end, today)})
    _write_atomic(df, pq, manifest, mf)
    return manifest


# ----------------------------------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------------------------------

def download(kind: str, sym: str, start: dt.date, end: dt.date, out: pathlib.Path, *, workers: int = 2,
             rate: float = 4.0, all_hours: bool = False, overwrite: bool = False,
             raw_cache: pathlib.Path | None = None, today: dt.date | None = None,
             fetcher: Fetcher | None = None, log: Callable[[str], None] = print) -> list[dict]:
    """Download `kind` ('ticks' or 'm1') month by month. Safe to interrupt and re-run."""
    STOP.clear()
    today = today or dt.datetime.now(dt.timezone.utc).date()
    start = max(start, EARLIEST.get(sym, start))
    if end < start:
        raise ValueError(f"end {end} is before start {start}")
    fetcher = fetcher or Fetcher(AdaptiveRate(rate), raw_cache=raw_cache, gate=OnlineGate(log=log), log=log)
    todo = months(start, end)
    done_before = 0
    out_manifests, t0, req0 = [], time.monotonic(), fetcher.requests_made
    fails_before = dict(fetcher.failures)
    for i, (y, m) in enumerate(todo, 1):
        pq, mf = _paths(out, sym, kind, y, m)
        prev = read_manifest(mf)
        if not overwrite and prev and prev.get("status") == "complete" and pq.exists():
            done_before += 1
            continue
        t_month = time.monotonic()
        if kind == "ticks":
            man = fetch_tick_month(sym, y, m, start, end, out, fetcher, workers, all_hours, today)
            size = f"{man.get('ticks', 0):>9,} ticks"
        elif kind == "m1":
            man = fetch_m1_month(sym, y, m, start, end, out, fetcher, workers, today)
            size = f"{man.get('minutes', 0):>7,} min"
        else:
            raise ValueError(kind)
        fails_now = dict(fetcher.failures)
        man["failed_attempts"] = {k: v - fails_before.get(k, 0) for k, v in fails_now.items() if v - fails_before.get(k, 0)}
        fails_before = fails_now
        out_manifests.append(man)
        elapsed = time.monotonic() - t0
        n_run = len(out_manifests)
        eta = elapsed / n_run * (len(todo) - i)
        status = man["status"] + (f" ({len(man['errors'])} errors)" if man.get("errors") else "")
        why = ", ".join(f"{k} x{v}" for k, v in man["failed_attempts"].items())
        log(f"{kind} {y}-{m:02d}  {status:<10} {size}  {time.monotonic() - t_month:5.0f}s  "
            f"rate {fetcher.rate.rate:4.1f}/s  throttles {fetcher.rate.throttle_events}  "
            f"[{i}/{len(todo)}, ETA {eta / 60:5.1f} min]" + (f"  retried: {why}" if why else ""))
    failed = [m for m in out_manifests if m["status"] == "failed"]
    log(f"{kind}: {len(out_manifests)} months fetched, {done_before} already complete, {len(failed)} failed; "
        f"{fetcher.requests_made - req0:,} requests, {fetcher.cache_hits:,} raw-cache hits, "
        f"{(time.monotonic() - t0) / 60:.1f} min")
    if fetcher.failures:
        log(f"{kind}: failed attempts by reason (all retried): {dict(fetcher.failures)}")
    if fetcher.gate is not None and fetcher.gate.pauses:
        log(f"{kind}: paused {fetcher.gate.pauses}x for being offline, {fetcher.gate.paused_seconds / 60:.1f} min total")
    return out_manifests


def probe(sym: str = "USDJPY", session: requests.Session | None = None) -> list[dict]:
    """Request a few known files ONCE each (no retries, no backoff) and report exactly what happens.
    Tells a temporary IP block (everything fails) from a problem with particular dates."""
    s = session or requests.Session()
    if hasattr(s, "headers"):
        s.headers.update({"User-Agent": "usdjpy-bot research downloader (python-requests)"})
    targets = [("m1 2003-05-05 BID", candle_url(sym, dt.date(2003, 5, 5), "BID")),
               ("m1 2014-03-04 BID", candle_url(sym, dt.date(2014, 3, 4), "BID")),
               ("m1 2024-07-09 BID", candle_url(sym, dt.date(2024, 7, 9), "BID")),
               ("tick 2024-07-09 10h", tick_url(sym, dt.datetime(2024, 7, 9, 10)))]
    rows = [{"file": "internet (neutral hosts)", "result": "up" if internet_up() else "DOWN", "seconds": None}]
    for name, url in targets:
        t0 = time.monotonic()
        try:
            r = s.get(url, timeout=(10, 30))
            res = f"HTTP {r.status_code}, {len(r.content):,} bytes"
            if r.status_code != 200:
                hdr = {k: v for k, v in (getattr(r, "headers", None) or {}).items()
                       if k.lower() in ("retry-after", "x-ratelimit-limit", "x-ratelimit-remaining",
                                        "x-ratelimit-reset", "server", "cf-ray")}
                body = r.content[:120].decode("utf-8", "replace").replace("\n", " ")
                res += f"  headers {hdr}  body: {body!r}"
        except requests.RequestException as e:
            res = f"{type(e).__name__} <- {root_cause(e)}"
        rows.append({"file": name, "result": res[:400], "seconds": round(time.monotonic() - t0, 2)})
        time.sleep(2)
    return rows


def status(sym: str, out: pathlib.Path) -> pd.DataFrame:
    """Coverage summary per kind and year from the manifests."""
    rows = []
    for kind in ("m1", "ticks"):
        for mf in sorted((out / sym / kind).glob("*/*.json")):
            man = read_manifest(mf)
            if not man:
                continue
            rows.append({"kind": kind, "year": int(man["month"][:4]), "status": man.get("status"),
                         "rows": man.get("ticks", man.get("minutes", 0)), "bytes": man.get("bytes", 0),
                         "weekday_hours_empty": man.get("weekday_hours_empty", 0)})
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    g = df.groupby(["kind", "year"])
    return pd.DataFrame({"months": g.size(), "complete": g["status"].apply(lambda s: (s == "complete").sum()),
                         "partial": g["status"].apply(lambda s: (s == "partial").sum()),
                         "failed": g["status"].apply(lambda s: (s == "failed").sum()),
                         "rows": g["rows"].sum(), "MB": (g["bytes"].sum() / 1e6).round(1),
                         "empty_wkday_hours": g["weekday_hours_empty"].sum()})


# ----------------------------------------------------------------------------------------------
# Loaders
# ----------------------------------------------------------------------------------------------

def load_m1(sym: str, out: pathlib.Path, years: Iterable[int] | None = None, as_price: bool = True) -> pd.DataFrame:
    """All downloaded minute candles (bid and ask OHLC). Prices in JPY if as_price else integer points."""
    files = sorted((out / sym / "m1").glob("*/*.parquet"))
    if years is not None:
        ys = {str(y) for y in years}
        files = [f for f in files if f.parent.name in ys]
    if not files:
        raise FileNotFoundError(f"No Dukascopy m1 data under {out / sym / 'm1'}. "
                                f"Run: python scripts/fetch_dukascopy.py m1")
    df = pd.concat([pd.read_parquet(f) for f in files]).sort_index()
    if as_price:
        px = [c for c in df.columns if not c.endswith("_vol")]
        df[px] = df[px].astype("float64") * POINT[sym]
    return df


def load_tick_month(sym: str, out: pathlib.Path, year: int, month: int, as_price: bool = True) -> pd.DataFrame:
    pq, _ = _paths(out, sym, "ticks", year, month)
    df = pd.read_parquet(pq)
    if as_price:
        df[["bid", "ask"]] = df[["bid", "ask"]].astype("float64") * POINT[sym]
    return df
