"""Rebuild data/ from free GitHub-hosted mirrors (what was used to seed the repo on 2026-11-24).

    python scripts/build_github_data.py            # everything (~2.5 GB download, ~0.5 GB on disk)
    python scripts/build_github_data.py --skip-ticks

Needs: git, pandas, pyarrow. Raw downloads go to a temp dir and are deleted afterwards.
Sources and caveats: docs/DATA.md.
"""
import argparse
import glob
import os
import pathlib
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
D = ROOT / "data"
RAW = "https://raw.githubusercontent.com"
GH = "https://github.com"


def get(url: str, dest: pathlib.Path) -> pathlib.Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest)
    return dest


def positioning_and_macro(tmp: pathlib.Path) -> None:
    (D / "positioning").mkdir(parents=True, exist_ok=True)
    (D / "macro").mkdir(parents=True, exist_ok=True)
    get(f"{RAW}/ForexiaPro/cot-data/main/data/legacy/JPY.csv", D / "positioning/cot_jpy_legacy_weekly.csv")
    get(f"{RAW}/ForexiaPro/cot-data/main/data/tff/JPY.csv", D / "positioning/cot_jpy_tff_weekly.csv")
    base = f"{RAW}/gourujeevan-cpu/japan-jgb-yield-regression/main/data/raw"
    fr = None
    for s in ["DEXJPUS", "DGS10", "DGS20", "DGS30", "VIXCLS", "NIKKEI225"]:
        x = pd.read_csv(get(f"{base}/{s}.csv", tmp / f"{s}.csv"), parse_dates=["observation_date"], index_col=0, na_values=["."])
        fr = x if fr is None else fr.join(x, how="outer")
    fr.index.name = "date"
    fr.to_csv(D / "macro/fred_daily_2000_2026H1.csv")
    j = pd.read_csv(get(f"{base}/jgb_yields.csv", tmp / "jgb.csv"), skiprows=1, na_values=["-"])
    j["Date"] = pd.to_datetime(j["Date"], format="%Y/%m/%d")
    j.rename(columns={"Date": "date"}).to_csv(D / "macro/mof_jgb_yields_daily_1974_2026.csv", index=False)
    c = pd.read_csv(get(f"{base}/boj_call_rate.csv", tmp / "call.csv"), skiprows=7, header=None,
                    names=["month", "call_rate_eom", "call_rate_avg"])
    c[c.month.astype(str).str.match(r"^\d{4}/\d{2}$")].to_csv(D / "macro/boj_call_rate_monthly_1985_2026.csv", index=False)
    fx = pd.read_csv(get(f"{RAW}/datasets/exchange-rates/main/data/daily.csv", tmp / "fx.csv"), parse_dates=["Date"])
    jp = fx[fx.Country == "Japan"].set_index("Date")["Exchange rate"].rename("JPY_per_USD")
    jp.index.name = "date"
    jp.to_csv(D / "macro/fred_h10_usdjpy_daily_1971_2026.csv")
    get(f"{RAW}/datasets/finance-vix/main/data/vix-daily.csv", D / "macro/vix_daily_1990_2026.csv")


def minute_bars(tmp: pathlib.Path) -> None:
    out = D / "bars_1min"
    out.mkdir(parents=True, exist_ok=True)
    cols = ["open", "high", "low", "close"]
    # Dukascopy-format export (EPSOFT), timestamps carry explicit GMT offsets
    parts = []
    for f in ["2007-2011", "2012-2015", "2016-2019", "2021-2023"]:
        z = get(f"{GH}/EPSOFT/Database-Currency-Pair/raw/main/USDJPY/1M/{f}.zip", tmp / f"ep_{f}.zip")
        with zipfile.ZipFile(z) as zf:
            for n in zf.namelist():
                df = pd.read_csv(zf.open(n))
                ts = pd.to_datetime(df["Local time"], format="%d.%m.%Y %H:%M:%S.%f GMT%z", utc=True)
                df = df.set_axis(ts).rename(columns=str.lower)[cols + ["volume"]]
                parts.append(df[df["volume"] > 0].astype("float32"))
    d = pd.concat(parts).sort_index()
    d = d[~d.index.duplicated()]
    d.index.name = "ts_utc"
    d.to_parquet(out / "dukascopy_bid_2007_2023.parquet", compression="zstd")
    # HistData MetaTrader M1: EST without DST (fixed UTC-5)
    parts = []
    names = [str(y) for y in range(2015, 2025)] + [f"2025{m:02d}" for m in range(1, 5)]
    for n in names:
        z = get(f"{GH}/yukkiya/usd-jpy-data/raw/main/HISTDATA_COM_MT_USDJPY_M1{n}.zip", tmp / f"hd_{n}.zip")
        with zipfile.ZipFile(z) as zf:
            csv = [x for x in zf.namelist() if x.endswith(".csv")][0]
            df = pd.read_csv(zf.open(csv), header=None, names=["d", "t"] + cols + ["volume"])
            ts = pd.to_datetime(df["d"] + " " + df["t"], format="%Y.%m.%d %H:%M") + pd.Timedelta(hours=5)
            parts.append(df.set_axis(ts.dt.tz_localize("UTC"))[cols].astype("float32"))
    h = pd.concat(parts).sort_index()
    h = h[~h.index.duplicated()]
    h.index.name = "ts_utc"
    h.to_parquet(out / "histdata_bid_2015_2025.parquet", compression="zstd")
    g = pd.read_csv(get(f"{RAW}/getdata-finance/usdjpy-1m-ohlcv-forex-historical-data/main/USDJPY_1m.csv", tmp / "gd.csv"))
    g.index = pd.to_datetime(g.pop("datetime"), utc=True)
    g.index.name = "ts_utc"
    g.astype("float32").round(3).to_parquet(out / "getdata_2026_sample.parquet", compression="zstd")


def eightcap_ticks(tmp: pathlib.Path) -> None:
    """MT5 tick export, broker server time = New York time + 7h (verified: spread spike at server 00:00)."""
    (D / "ticks/eightcap").mkdir(parents=True, exist_ok=True)
    for y in (2024, 2025, 2026):
        subprocess.run(["git", "clone", "-q", "--depth", "1", f"{GH}/rForex/ForexEightcapUSDJPYi_{y}.git", str(tmp / f"ec{y}")], check=True)
    months = {}
    for p in sorted(glob.glob(str(tmp / "ec20*/*.csv"))):
        months.setdefault(os.path.basename(p)[9:15], []).append(p)

    def load(p):
        df = pd.read_csv(p, sep="\t", usecols=[0, 1, 2, 3])
        df.columns = ["date", "time", "bid", "ask"]
        srv = pd.to_datetime(df.date + " " + df.time, format="%Y.%m.%d %H:%M:%S.%f")
        ny = (srv - pd.Timedelta(hours=7)).dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT")
        df.index = pd.DatetimeIndex(ny.dt.tz_convert("UTC"), name="ts_utc")
        df = df[["bid", "ask"]].ffill().dropna()
        return df[df.index.notna()]

    bars = []
    for m, ps in sorted(months.items()):
        t = pd.concat([load(p) for p in ps]).sort_index()
        t = t[t.ask >= t.bid]
        pd.DataFrame({"bid": np.rint(t.bid * 1000).astype("int32"), "ask": np.rint(t.ask * 1000).astype("int32")},
                     index=t.index).to_parquet(D / f"ticks/eightcap/USDJPY_{m}.parquet", compression="zstd")
        r = t.resample("1min")
        b = pd.DataFrame({"bid_open": r.bid.first(), "bid_high": r.bid.max(), "bid_low": r.bid.min(), "bid": r.bid.last(),
                          "ask": r.ask.last(), "spread_mean": (t.ask - t.bid).resample("1min").mean(),
                          "n_ticks": r.bid.count()}).dropna(subset=["bid"])
        bars.append(b.astype({c: "float32" for c in b.columns if c != "n_ticks"}))
        print(m, len(t), "ticks")
    B = pd.concat(bars)
    B.index.name = "ts_utc"
    B.to_parquet(D / "bars_1min/eightcap_bidask_2024_2026.parquet", compression="zstd")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-ticks", action="store_true")
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        positioning_and_macro(tmp)
        print("positioning + macro done")
        minute_bars(tmp)
        print("1-min bars done")
        if not a.skip_ticks:
            eightcap_ticks(tmp)
            print("eightcap ticks done")
    print("Calendars (data/calendars/) are tracked separately: see docs/DATA.md")
