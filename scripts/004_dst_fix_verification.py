"""Spec 004: verify the trades the HistData DST fix changed, and say where the change came from.

    python scripts/004_dst_fix_verification.py

Spec 004's *Second bug* section quotes two things this script reproduces:
1. Every spec 004 trade (all groups, both legs) whose mid_pips the fix changed is
   recomputed on the independent Dukascopy export (explicit GMT offsets in its raw
   stamps) with the same `events.quote_at` rule and synthetic-ask profile. Where
   Dukascopy quotes both legs, the corrected trade should match it and the pre-fix
   trade should not.
2. How the B legs' change in net pips is distributed: how many trades moved, the
   largest moves, and how much of the total the three largest carry.

Needs the pre-fix trades in results/archive/004_as_run_pre_dst_fix/ and the current
ones in results/. results/ is git-ignored; on a clean clone, regenerate the archive by
running scripts/turn_of_month_study.py at commit ab147d0 (before the fix) and copying
results/004_*.csv into that folder. Reads no data/tokyo_hours/.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from usdjpy.config import RESULTS_DIR  # noqa: E402
from usdjpy.costs import PIP  # noqa: E402
from usdjpy.datasets import load_minute  # noqa: E402
from usdjpy.events import quote_at  # noqa: E402

ARCHIVE = RESULTS_DIR / "archive" / "004_as_run_pre_dst_fix"
LEGS = {"prefix_long": 1, "postfix_short": -1}
GROUPS = ("A_month_end", "B_gotobi_proper", "C_control")


def read(folder: pathlib.Path, leg: str, group: str) -> pd.DataFrame:
    p = folder / f"004_{leg}_{group}.csv"
    if not p.exists():
        raise SystemExit(f"missing {p}; see this script's docstring for how to regenerate it")
    return pd.read_csv(p, parse_dates=["date", "entry_utc", "exit_utc"]).set_index("date")


def against_dukascopy() -> pd.DataFrame:
    du = load_minute("dukascopy")
    rows = []
    for leg, side in LEGS.items():
        for g in GROUPS:
            o, n = read(ARCHIVE, leg, g), read(RESULTS_DIR, leg, g)
            common = o.index.intersection(n.index)
            changed = common[(o.loc[common, "mid_pips"] - n.loc[common, "mid_pips"]).abs() > 1e-9]
            for d in changed:
                qi, qo = quote_at(du, n.loc[d, "entry_utc"]), quote_at(du, n.loc[d, "exit_utc"])
                if qi is None or qo is None:
                    continue
                dk = side * ((qo.bid + qo.ask) / 2 - (qi.bid + qi.ask) / 2) / PIP
                rows.append({"leg": leg, "group": g, "date": d.date(), "pre_fix": o.loc[d, "mid_pips"],
                             "corrected": n.loc[d, "mid_pips"], "dukascopy": dk})
    r = pd.DataFrame(rows)
    r["err_pre_fix"] = (r.pre_fix - r.dukascopy).abs()
    r["err_corrected"] = (r.corrected - r.dukascopy).abs()
    return r


def attribution(leg: str) -> None:
    o = read(ARCHIVE, leg, "B_gotobi_proper")["net_pips"]
    n = read(RESULTS_DIR, leg, "B_gotobi_proper")["net_pips"]
    idx = o.index.union(n.index)
    d = n.reindex(idx).fillna(0) - o.reindex(idx).fillna(0)
    d = d[d.abs() > 1e-9]
    top = d.abs().sort_values(ascending=False).index[:3]
    print(f"  {leg}: {len(d)} B trades changed, added or dropped; total {d.sum():+.1f} pips "
          f"(mean {o.mean():+.3f} -> {n.mean():+.3f}); {int((d > 0).sum())} up, {int((d < 0).sum())} down")
    print("    largest: " + ", ".join(f"{i.date()} {d[i]:+.1f}" for i in d.abs().sort_values(ascending=False).index[:6]))
    print(f"    three largest carry {d[top].sum():+.1f} of {d.sum():+.1f} pips; without them the mean shift is "
          f"{d.drop(top).sum() / len(n):+.3f} pips")


def main() -> None:
    r = against_dukascopy()
    print(f"Changed trades with Dukascopy quotes on both legs: {len(r)}")
    t = r.groupby(["leg", "group"])[["err_pre_fix", "err_corrected"]].agg(["median", "max", "count"]).round(2)
    print("|mid_pips - Dukascopy mid_pips|, pips:")
    print(t.to_string())
    print(f"corrected closer than pre-fix: {(r.err_corrected < r.err_pre_fix).sum()} of {len(r)}; "
          f"max corrected error {r.err_corrected.max():.3f} pips")
    print("\nWhere the B legs' change came from (net pips):")
    for leg in LEGS:
        attribution(leg)


if __name__ == "__main__":
    main()
