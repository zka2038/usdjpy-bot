"""scripts/fetch_status.py: progress from file names and mtimes only, never contents."""
import datetime as dt
import importlib.util
import os
import pathlib
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(name):
    sp = importlib.util.spec_from_file_location(name.replace(".py", ""), ROOT / "scripts" / name)
    mod = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(mod)
    return mod


def _tree(tmp_path, days, mtime):
    """A tree whose day files are NOT parquet: any attempt to read one would fail."""
    root = tmp_path / "tokyo_hours"
    for d in days:
        p = root / "USDJPY" / str(d.year) / f"{d}.parquet"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"not a parquet file")
        os.utime(p, (mtime, mtime))
    (root / "USDJPY" / "2023" / "._2023-02-01.parquet").write_bytes(b"AppleDouble")   # must be skipped
    (root / "fetch.log").write_text("stage 1 complete\n  HTTP 429 on https://x; waiting 30s\n"
                                    "--- restarted 2026-11-26 14:48 UTC ---\n--- restarted 2026-11-26 19:20 UTC ---\n")
    (root / "fetch.pid").write_text("999999\n")      # no such process
    return root


def test_progress_and_pace_from_names_and_mtimes_only(tmp_path):
    fs = _load("fetch_status.py")
    fetcher = fs._load_fetcher()
    a, b, days, _ = fetcher.STAGES["1"]
    stage1 = [d for d, _n in fetcher.missing_days(a, b, days, out_dir=tmp_path / "none")]
    now = time.time()
    root = _tree(tmp_path, stage1[:10], now - 600)          # 10 stage-1 days, written 10 min ago

    files = fs.day_files(root)
    assert len(files) == 10 and all(isinstance(d, dt.date) for d, _ in files)

    st = fs.stage_progress(fetcher, root)
    s1 = next(s for s in st if s["stage"] == "1")
    assert s1["days"] - s1["days_left"] == 10
    assert s1["reqs"] - s1["reqs_left"] == sum(s1["plan"][d] for d in stage1[:10])

    d1, r1 = fs.pace(st, files, 1, now)
    assert d1 == 10 and r1 == s1["reqs"] - s1["reqs_left"]
    assert fs.pace(st, files, 1 / 12, now) == (0, 0)        # nothing in the last 5 minutes

    text = fs.render(root, 5, color=False)                  # the whole report, on unreadable files
    assert "NOT RUNNING" in text and "process restarts recorded in the whole log: 2" in text
    assert "stage 1 |" in text and "total   |" in text


def test_bar_and_tree_lookup(tmp_path):
    fs = _load("fetch_status.py")
    assert fs.bar(0, 10, 10) == " " * 10 and fs.bar(10, 10, 10) == "█" * 10
    assert len(fs.bar(3, 7, 20)) == 20
    assert fs.find_tree(str(tmp_path)) == tmp_path
