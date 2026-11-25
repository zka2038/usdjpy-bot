"""Audit the Eightcap spread profile that datasets.py uses for the synthetic ask.

    python scripts/spread_profile_audit.py

WHY. docs/DATA.md states ~0.33-0.36 pips at 08:00-09:00 JST and ~5.0 pips at
06:00-07:00 JST (the 17:00 NY rollover). But the spec 004 run reports a median
assumed spread of 0.600 pips at the 08:00 JST prefix entry -- 1.7x the catalogue
figure. One of the two is wrong, and it moves the prefix all-in cost by 0.25
pips, which is 16% of the gross effect being measured.

PRIME SUSPECT: timezone. The catalogue says the Eightcap server runs at NY + 7h.
`datasets.load_minute("eightcap")` uses `e.index` as-is with no conversion, and
`_hourly_spread_profile()` then does `.tz_convert("Asia/Tokyo")`. If the stored
index is server time rather than UTC, every hour bucket is displaced by 7-9h.

THE DECISIVE TEST. 17:00 NY = 22:00 UTC (EST) = 07:00 JST next day. So the
rollover spike MUST sit at JST hour 6-7. Wherever this script finds the spike is
where the index actually is.
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from usdjpy.config import DATA_DIR  # noqa: E402

PATH = DATA_DIR / "bars_1min" / "eightcap_bidask_2024_2026.parquet"
if not PATH.exists():
    raise SystemExit(f"not found: {PATH}")

e = pd.read_parquet(PATH)
print("=" * 78)
print("1. FILE AND INDEX")
print("=" * 78)
print(f"  path     {PATH}")
print(f"  rows     {len(e):,}")
print(f"  columns  {list(e.columns)}")
print(f"  index    dtype={e.index.dtype}  tz={getattr(e.index, 'tz', None)}")
print(f"  range    {e.index.min()}  ->  {e.index.max()}")

col = "spread_mean" if "spread_mean" in e.columns else None
if col is None:
    cands = [c for c in e.columns if "spread" in c.lower()]
    if not cands:
        raise SystemExit(f"no spread column; have {list(e.columns)}")
    col = cands[0]
    print(f"  !! 'spread_mean' absent; using '{col}'")
s = pd.to_numeric(e[col], errors="coerce").dropna()

print()
print("=" * 78)
print("2. UNITS")
print("=" * 78)
q = s.quantile([0.01, 0.25, 0.5, 0.75, 0.99])
print(f"  {col} quantiles (raw): " + ", ".join(f"{p:.0%}={v:.6f}" for p, v in q.items()))
med = float(s.median())
if med < 0.01:
    unit, to_pips = "JPY price units", 1 / 0.01
elif med < 5:
    unit, to_pips = "already pips", 1.0
else:
    unit, to_pips = "points (1/1000 JPY)?", 0.1
print(f"  median {med:.6f}  ->  interpreted as {unit}; x{to_pips:g} gives pips")
print(f"  median in pips: {med*to_pips:.3f}")
print(f"  NOTE: window_trades computes (ask-bid)/PIP, and _with_synthetic_ask does")
print(f"        ask = bid + profile_value. So the profile MUST be in JPY, not pips.")
if med > 0.01:
    print(f"  !! median {med:.4f} is too large for JPY -> ask = bid + {med:.4f} would")
    print(f"     imply a {med/0.01:.1f}-pip spread. CHECK the unit in the parquet.")

print()
print("=" * 78)
print("3. WHERE IS THE ROLLOVER SPIKE?  (decides the timezone question)")
print("=" * 78)
idx = e.index
if getattr(idx, "tz", None) is None:
    print("  index is tz-NAIVE. _hourly_spread_profile() calls .tz_convert('Asia/Tokyo'),")
    print("  which RAISES on a naive index -- so either the loader localises first")
    print("  somewhere, or the fallback 0.3 pips was silently used. Testing both readings.")
    readings = [("assume stored = UTC", idx.tz_localize("UTC")),
                ("assume stored = server (NY+7h = UTC+2)", idx.tz_localize("Etc/GMT-2"))]
else:
    readings = [("index as stored", idx)]

for label, i2 in readings:
    jst = i2.tz_convert("Asia/Tokyo")
    prof = s.groupby(jst.hour).median() * to_pips
    prof = prof.reindex(range(24))
    spike = int(prof.idxmax())
    print(f"\n  --- {label} ---")
    print("   JST hr " + " ".join(f"{h:>5}" for h in range(24)))
    print("   pips   " + " ".join(("  n/a" if np.isnan(v) else f"{v:5.2f}") for v in prof.values))
    print(f"   spike at JST hour {spike} ({prof.max():.2f} pips)"
          f"   {'<-- CORRECT (expect 6-7)' if spike in (6, 7) else '<-- WRONG, expected 6-7'}")
    print(f"   hour 8  = {prof.get(8, float('nan')):.3f} pips   (catalogue claims 0.33-0.36)")
    print(f"   hour 9  = {prof.get(9, float('nan')):.3f} pips")
    print(f"   hour 10 = {prof.get(10, float('nan')):.3f} pips")
    print(f"   all-hour median = {float(np.nanmedian(prof.values)):.3f} pips"
          f"   (catalogue claims 0.23-0.30)")
    if spike not in (6, 7):
        shift = (7 - spike) % 24
        print(f"   => index appears displaced; shifting +{shift}h would put the spike at 7.")

print()
print("=" * 78)
print("4. WHAT THE SPEC 004 RUN ACTUALLY USED")
print("=" * 78)
try:
    from usdjpy.datasets import _hourly_spread_profile
    p = _hourly_spread_profile()
    print("  _hourly_spread_profile() returned:")
    print("   hour " + " ".join(f"{h:>7}" for h in range(0, 12)))
    print("   val  " + " ".join(f"{p.get(h, float('nan')):7.4f}" for h in range(0, 12)))
    print("   hour " + " ".join(f"{h:>7}" for h in range(12, 24)))
    print("   val  " + " ".join(f"{p.get(h, float('nan')):7.4f}" for h in range(12, 24)))
    print(f"\n  value at hour 8 = {p.get(8, float('nan')):.4f}")
    print(f"  in pips          = {p.get(8, float('nan'))/0.01:.3f}")
    print(f"  spec 004 prefix reported a 0.600-pip median at the 08:00 JST entry.")
    v8 = p.get(8, float("nan")) / 0.01
    if abs(v8 - 0.600) < 0.05:
        print("  -> MATCHES. The 0.600 figure is the hour-8 profile value, so the")
        print("     discrepancy is between the PROFILE and docs/DATA.md, not a bug")
        print("     in the study. Re-derive the catalogue line.")
    else:
        print(f"  -> DOES NOT MATCH ({v8:.3f} vs 0.600). Something between the profile")
        print("     and window_trades is altering the spread; trace _with_synthetic_ask.")
    print(f"\n  FALLBACK_SPREAD is 0.003 (0.3 pips). If the profile had silently")
    print(f"  fallen back, every hour would read exactly 0.0030 -- check above.")
except Exception as ex:
    print(f"  could not call _hourly_spread_profile(): {type(ex).__name__}: {ex}")
    print("  If this raised on tz_convert, the naive-index path above is the answer.")

print()
print("=" * 78)
print("""VERDICT GUIDE

  spike at JST 6-7      -> timezone is right; the catalogue line is simply wrong
                           and 0.600 pips at hour 8 is the real assumption.
  spike anywhere else   -> the index is displaced, every hour bucket is
                           mislabelled, and BOTH the catalogue and the spec 004
                           cost figures are wrong. Fix the loader, re-run 004.
  every hour = 0.0030   -> the Eightcap read failed and FALLBACK_SPREAD was used
                           silently. Every cost figure in the project is then the
                           flat 0.3-pip default, including at the rollover hour
                           where the truth is ~17x that.""")
