"""Status of the spec 004 gap-fill fetch (scripts/download_gap_fill.py), for a terminal.

    python scripts/fetch_status.py                 # one snapshot
    python scripts/fetch_status.py --watch 60      # refresh every 60 s (Ctrl-C to stop)
    python scripts/fetch_status.py --lines 25      # more of the log
    python scripts/fetch_status.py --tree-root "/Volumes/bzk Drive/usdjpy-bot/data/tokyo_hours"

Shows: whether the fetch process is alive (and caffeinate, and the Mac's power source),
a progress bar per stage and overall, the recent pace and an ETA, the most recent days
written, recent HTTP 429 / connection errors / restarts, and the tail of fetch.log.

BLINDING: it never opens a day file. Spec 004's gap fill is declared before the fetched
data is seen, so this script uses day files' NAMES and modification times only (metadata,
not contents; HANDOFF-2026-11-26-next-session.md), plus fetch.log and fetch.pid, which
the fetch itself writes for monitoring. Day totals come from the same plan the fetch uses
(`download_gap_fill.STAGES`), so they cannot drift from it.

By default it looks for data/tokyo_hours in this repo and then in each parent directory,
so it finds the main checkout's tree when run from a worktree under .claude/worktrees/
(where data/tokyo_hours is deliberately not linked). Python: the repo's venv.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "src"))

from usdjpy.config import SYMBOL  # noqa: E402

PROBLEMS = re.compile(r"HTTP 429|ConnectionError|ConnectTimeout|Timeout|Failed to download|resuming in|restarted|Traceback|gave up")


def _load_fetcher():
    sp = importlib.util.spec_from_file_location("download_gap_fill", HERE / "download_gap_fill.py")
    mod = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(mod)
    return mod


def find_tree(explicit: str | None) -> pathlib.Path:
    if explicit:
        return pathlib.Path(explicit).expanduser()
    for base in [HERE.parents[0], *HERE.parents[0].parents]:
        cand = base / "data" / "tokyo_hours"
        if (cand / "fetch.log").exists() or (cand / SYMBOL).is_dir():
            return cand
    raise SystemExit("No data/tokyo_hours found here or in a parent directory; pass --tree-root.")


def stage_progress(fetcher, root: pathlib.Path) -> list[dict]:
    """Per stage: planned days and requests, and what is still missing (file names only)."""
    out = []
    empty = root / "__no_such_dir__"
    for name, (a, b, days, why) in fetcher.STAGES.items():
        plan = fetcher.missing_days(a, b, days, out_dir=empty)          # every day: nothing on disk there
        left = fetcher.missing_days(a, b, days, out_dir=root)
        out.append({"stage": name, "why": why, "plan": dict(plan),
                    "days": len(plan), "days_left": len(left),
                    "reqs": sum(n for _, n in plan), "reqs_left": sum(n for _, n in left)})
    return out


def day_files(root: pathlib.Path) -> list[tuple[dt.date, float]]:
    """(UTC day, mtime) of every day file, from names and stat() only, never contents."""
    out = []
    for p in (root / SYMBOL).glob("*/*.parquet"):
        if p.name.startswith("._"):
            continue
        try:
            d = dt.date.fromisoformat(p.stem)
        except ValueError:
            continue
        out.append((d, p.stat().st_mtime))
    return sorted(out, key=lambda x: x[1])


def pace(stages: list[dict], files: list[tuple[dt.date, float]], hours: float, now: float) -> tuple[int, int]:
    """(days, requests) written in the last `hours`, by file modification time."""
    reqs_of = {}
    for s in stages:
        reqs_of.update(s["plan"])
    recent = [d for d, m in files if now - m <= hours * 3600]
    return len(recent), sum(reqs_of.get(d, 0) for d in recent)


def bar(done: int, total: int, width: int) -> str:
    frac = 0.0 if total == 0 else done / total
    full = int(frac * width)
    part = " ▏▎▍▌▋▊▉"[int((frac * width - full) * 8)] if full < width else ""
    return "█" * full + part + " " * (width - full - len(part))


def process_info(root: pathlib.Path) -> dict:
    info = {"pid": None, "alive": False, "etime": "", "caffeinate": False, "power": ""}
    try:
        info["pid"] = int((root / "fetch.pid").read_text().split()[0])
        os.kill(info["pid"], 0)
        info["alive"] = True
    except (OSError, ValueError, IndexError):
        pass
    if info["alive"]:
        r = subprocess.run(["ps", "-p", str(info["pid"]), "-o", "etime="], capture_output=True, text=True)
        info["etime"] = r.stdout.strip()
    r = subprocess.run(["pgrep", "-f", "caffeinate.*download_gap_fill"], capture_output=True, text=True)
    info["caffeinate"] = bool(r.stdout.strip())
    if shutil.which("pmset"):
        r = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True)
        src = re.search(r"'([^']+)'", r.stdout)
        pct = re.search(r"(\d+)%", r.stdout)
        info["power"] = (src.group(1) if src else "") + (f", {pct.group(1)}%" if pct else "")
    return info


def tail(path: pathlib.Path, n: int) -> list[str]:
    if not path.exists():
        return []
    with open(path, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - 200_000))
        lines = f.read().decode("utf-8", "replace").splitlines()
    return lines[-n:]


def fmt_h(hours: float) -> str:
    if hours != hours or hours == float("inf"):
        return "n/a"
    return f"{hours / 24:.1f} d ({hours:.0f} h)" if hours >= 48 else f"{hours:.1f} h"


def render(root: pathlib.Path, n_lines: int, color: bool) -> str:
    c = (lambda code, s: f"\033[{code}m{s}\033[0m") if color else (lambda code, s: s)
    fetcher = _load_fetcher()
    now = time.time()
    stages = stage_progress(fetcher, root)
    files = day_files(root)
    proc = process_info(root)
    width = max(20, min(50, shutil.get_terminal_size((100, 20)).columns - 50))
    out = [c("1", f"Gap-fill fetch  {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC") + f"   tree: {root}"]

    if proc["alive"]:
        line = c("32", f"ALIVE  pid {proc['pid']}, up {proc['etime']}")
    else:
        line = c("31;1", f"NOT RUNNING  (pid file says {proc['pid']}); restart: HANDOFF-2026-11-26-remaining.md §2")
    line += "   caffeinate " + (c("32", "on") if proc["caffeinate"] else c("33", "off"))
    if proc["power"]:
        on_batt = "Battery" in proc["power"]
        line += "   power: " + (c("33;1", proc["power"] + "  (plug in: sleep kills the fetch)") if on_batt else proc["power"])
    out.append(line)
    log_lines = tail(root / "fetch.log", 400)
    if any("stage 3 complete" in s for s in log_lines[-5:]):
        out.append(c("32;1", "FETCH COMPLETE: tell the user before running scripts/004_gap_fill_analysis.py"))
    out.append("")

    tot_r = sum(s["reqs"] for s in stages)
    tot_left = sum(s["reqs_left"] for s in stages)
    for s in stages:
        done = s["days"] - s["days_left"]
        state = c("32", "done") if s["days_left"] == 0 else f"{s['days_left']:,} days / {s['reqs_left']:,} requests left"
        out.append(f"stage {s['stage']} |{bar(done, s['days'], width)}| {done:>5,}/{s['days']:<5,} days  {state}")
    out.append(f"total   |{bar(tot_r - tot_left, tot_r, width)}| {100 * (tot_r - tot_left) / max(1, tot_r):5.1f}% of "
               f"{tot_r:,} requests, {tot_left:,} left")
    out.append("")

    d1, r1 = pace(stages, files, 1, now)
    d6, r6 = pace(stages, files, 6, now)
    full = 3600 / 30                               # the fetch's ceiling: one request per 30 s
    out.append(f"pace: last 1 h {d1} days / {r1} requests;  last 6 h {d6} days / {r6} requests "
               f"({r6 / 6:.0f}/h);  ceiling {full:.0f} requests/h")
    eta_full = tot_left / full
    eta_6 = tot_left / (r6 / 6) if r6 else float("inf")
    out.append(f"ETA:  at full pace {fmt_h(eta_full)};  at the last 6 h pace {fmt_h(eta_6)}")
    if files:
        last_m = files[-1][1]
        age = (now - last_m) / 60
        warn = c("33", f"  (no new day for {age:.0f} min: rate-limited or stalled?)") if age > 15 else ""
        out.append(f"last day written {dt.datetime.fromtimestamp(last_m, dt.timezone.utc):%H:%M} UTC, "
                   f"{age:.0f} min ago{warn}")
        recent = ", ".join(f"{d}" for d, _ in files[-6:])
        out.append(f"recent days: {recent}")
    out.append("")

    window = log_lines[-200:]
    n429 = sum("HTTP 429" in s for s in window)
    nconn = sum(bool(re.search(r"ConnectionError|ConnectTimeout|Timeout", s)) for s in window)
    nrest = sum("resuming in" in s for s in window)
    log_path = root / "fetch.log"
    n_proc = log_path.read_text(errors="replace").count("--- restarted") if log_path.exists() else 0
    out.append(f"last 200 log lines: {n429} HTTP 429, {nconn} connection errors, {nrest} stage restarts; "
               f"process restarts recorded in the whole log: {n_proc}")
    out.append(c("1", f"fetch.log, last {n_lines} lines:"))
    for s in log_lines[-n_lines:]:
        out.append("  " + (c("33", s) if PROBLEMS.search(s) else s))
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description="Status of the spec 004 gap-fill fetch (file names and the log only).")
    ap.add_argument("--tree-root", default=None, help="data/tokyo_hours (default: found from this repo upwards)")
    ap.add_argument("--lines", type=int, default=12, help="log lines to show")
    ap.add_argument("--watch", type=float, default=0, help="refresh every N seconds")
    ap.add_argument("--no-color", action="store_true")
    a = ap.parse_args()
    root = find_tree(a.tree_root)
    color = sys.stdout.isatty() and not a.no_color
    if not a.watch:
        print(render(root, a.lines, color))
        return
    try:
        while True:
            text = render(root, a.lines, color)
            print("\033[2J\033[H" + text if color else text + "\n" + "-" * 60, flush=True)
            time.sleep(a.watch)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
