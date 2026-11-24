"""Spec 001 (gotobi) results as one self-contained HTML page.

    python scripts/gotobi_report.py                 # -> results/gotobi_report.html
    python scripts/gotobi_report.py --source histdata

Reruns the same rules as scripts/gotobi_study.py, then embeds every trade, the summary
statistics, d3 and all styling into a single file that opens offline in any browser.
"""
import argparse
import datetime as dt
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

from usdjpy.calendars import gotobi_days, jp_business_days  # noqa: E402
from usdjpy.config import RESULTS_DIR  # noqa: E402
from usdjpy.costs import PESSIMISTIC, CostModel  # noqa: E402
from usdjpy.datasets import load_minute  # noqa: E402
from usdjpy.events import compare, quote_at, summarize, window_trades  # noqa: E402

TEMPLATES = pathlib.Path(__file__).resolve().parent / "templates"
RULES = {"1a": ("08:00", "09:55", +1), "1b": ("09:55", "11:00", -1)}


def num(x):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), 4)


def run(source: str) -> tuple[dict, str]:
    bars = load_minute(source)
    start, end = bars.index[0].date(), bars.index[-1].date()
    gotobi = gotobi_days(start, end)
    control = jp_business_days(start, end).difference(gotobi)
    trades, summary = [], []
    for rule, (t_in, t_out, side) in RULES.items():
        res = {}
        for days_name, days in (("gotobi", gotobi), ("control", control)):
            base = window_trades(bars, days, t_in, t_out, side, CostModel())
            pess = window_trades(bars, days, t_in, t_out, side, PESSIMISTIC)
            res[days_name] = base
            for d, r in base.iterrows():
                q = quote_at(bars, r["entry_utc"])
                trades.append({"date": d.strftime("%Y-%m-%d"), "rule": rule, "days": days_name,
                               "price_source": q["source"] if "source" in q else source,
                               "mid_pips": num(r["mid_pips"]), "net_pips": num(r["net_pips"]),
                               "net_pips_pessimistic": num(pess.loc[d, "net_pips"]),
                               "entry_spread_pips": num(r["spread_in_pips"])})
            for cost_name, tr in (("base", base), ("pessimistic", pess)):
                if days_name == "control" and cost_name == "pessimistic":
                    continue
                for period, s in summarize(tr, "net_pips").iterrows():
                    summary.append({"rule": rule, "days": days_name, "costs": cost_name, "period": period,
                                    "n": int(s["n"]), "mean_net_pips": num(s["mean"]), "std": num(s["std"]),
                                    "t": num(s["t"]), "hit_rate": num(s["hit_rate"]), "total_pips": num(s["total"])})
        c = compare(res["gotobi"], res["control"])
        summary.append({"rule": rule, "days": "gotobi vs control", "costs": "none (mid)", "period": "all",
                        "n": int(c["n_treat"]), "mean_net_pips": num(c["diff"]), "std": None, "t": num(c["t"]),
                        "hit_rate": None, "total_pips": None, "p_value": num(c["p"]),
                        "gotobi_mean_mid": num(c["treat_mean"]), "control_mean_mid": num(c["control_mean"]),
                        "n_control": int(c["n_control"])})
    note = f"price data: {source}, {start} to {end}; 2025+ holdout excluded"
    return {"trades": trades, "summary": summary}, note


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="combined", help="combined | histdata | dukascopy | eightcap")
    ap.add_argument("--out", type=pathlib.Path, default=RESULTS_DIR / "gotobi_report.html")
    a = ap.parse_args()

    data, note = run(a.source)
    # "</" inside an inline <script> would end it early; JSON allows the escaped form.
    data_js = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    html = (TEMPLATES / "gotobi_report.html").read_text()
    html = (html.replace("__D3__", (TEMPLATES / "vendor" / "d3-7.9.0.min.js").read_text())
                .replace("__DATA__", data_js)
                .replace("__GENERATED__", dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
                .replace("__INPUT__", note))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(html)
    print(f"Wrote {a.out} ({a.out.stat().st_size / 1e6:.1f} MB, {len(data['trades'])} trades)")


if __name__ == "__main__":
    main()
