"""Fetch official sources directly (run on your own machine; these hosts were unreachable when the
repo was seeded). Each source is independent: a failure is reported and the rest continue.

    python scripts/fetch_official.py              # FRED, MOF, CFTC
    python scripts/fetch_official.py --histdata   # + HistData 1-min 2000-2014 and 2025-05 onward (pip install histdata)

Dukascopy tick data (bid/ask, 2003-now) is separate and large:
    python scripts/download.py 2010-01-01 2026-11-20
"""
import argparse
import datetime as dt
import io
import pathlib
import zipfile

import pandas as pd
import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "official"
UA = {"User-Agent": "Mozilla/5.0 (research; usdjpy-bot)"}
S = requests.Session()
S.headers.update(UA)

FRED = {
    "DEXJPUS": "USDJPY noon NY (H.10)", "DGS2": "UST 2y", "DGS10": "UST 10y", "DGS3MO": "UST 3m",
    "DFF": "Fed funds effective", "SOFR": "SOFR", "T10YIE": "10y breakeven", "VIXCLS": "VIX",
    "SP500": "S&P 500", "NIKKEI225": "Nikkei 225", "DTWEXBGS": "Broad USD index",
    "IRLTLT01JPM156N": "Japan 10y (OECD, monthly)", "IR3TIB01JPM156N": "Japan 3m interbank (OECD, monthly)",
}
MOF = {
    "mof_intervention_all.csv": "https://www.mof.go.jp/policy/international_policy/reference/feio/foreign_exchange_intervention_operations.csv",
    "mof_portfolio_flows_weekly.csv": "https://www.mof.go.jp/policy/international_policy/reference/itn_transactions_in_securities/week.csv",
    "mof_portfolio_flows_monthly.csv": "https://www.mof.go.jp/policy/international_policy/reference/itn_transactions_in_securities/montha1.csv",
    "mof_portfolio_flows_by_investor_monthly.csv": "https://www.mof.go.jp/policy/international_policy/reference/itn_transactions_in_securities/monthb1.csv",
    "mof_jgb_yields_all.csv": "https://www.mof.go.jp/jgbs/reference/interest_rate/historical/jgbcm_all.csv",
    "mof_jgb_yields_current_month.csv": "https://www.mof.go.jp/jgbs/reference/interest_rate/jgbcm.csv",
}


def save(name: str, content: bytes) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_bytes(content)
    print(f"  ok  {name} ({len(content) / 1e3:.0f} kB)")


def fred() -> None:
    print("FRED")
    frames = []
    for sid in FRED:
        try:
            r = S.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}", timeout=60)
            r.raise_for_status()
            df = pd.read_csv(io.StringIO(r.text), index_col=0, parse_dates=True, na_values=["."])
            frames.append(df)
            print(f"  ok  {sid}: {df.index[0].date()} -> {df.index[-1].date()}")
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL {sid}: {e}")
    if frames:
        out = pd.concat(frames, axis=1).sort_index()
        out.index.name = "date"
        OUT.mkdir(parents=True, exist_ok=True)
        out.to_csv(OUT / "fred_daily.csv")


def mof() -> None:
    print("MOF (files are Shift-JIS; read with encoding='cp932')")
    for name, url in MOF.items():
        try:
            r = S.get(url, timeout=60)
            r.raise_for_status()
            save(name, r.content)
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL {name}: {e}")


def cftc(first_year: int = 2010) -> None:
    """Official TFF (Traders in Financial Futures) for the JPY contract - use to verify the GitHub mirror."""
    print("CFTC TFF")
    rows = []
    for y in range(first_year, dt.date.today().year + 1):
        try:
            r = S.get(f"https://www.cftc.gov/files/dea/history/fut_fin_txt_{y}.zip", timeout=120)
            r.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
                df = pd.read_csv(zf.open(zf.namelist()[0]), low_memory=False)
            rows.append(df[df.iloc[:, 0].astype(str).str.contains("JAPANESE YEN", case=False)])
            print(f"  ok  {y}")
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL {y}: {e}")
    if rows:
        OUT.mkdir(parents=True, exist_ok=True)
        pd.concat(rows).to_csv(OUT / "cftc_tff_jpy_official.csv", index=False)


def histdata() -> None:
    """HistData.com 1-min (EST, no DST). Fills 2000-2014 and 2025-05 onward."""
    print("HistData")
    try:
        from histdata import download_hist_data as dl
        from histdata.api import Platform as P, TimeFrame as TF
    except ImportError:
        print("  skip: pip install histdata")
        return
    dest = OUT / "histdata"
    dest.mkdir(parents=True, exist_ok=True)
    this_year = dt.date.today().year
    for y in range(2000, 2015):
        try:
            dl(year=str(y), pair="usdjpy", platform=P.META_TRADER, time_frame=TF.ONE_MINUTE, output_directory=str(dest))
            print(f"  ok  {y}")
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL {y}: {e}")
    for y in range(2025, this_year + 1):
        for m in range(1, 13):
            if (y == 2025 and m < 5) or dt.date(y, m, 1) > dt.date.today():
                continue
            try:
                dl(year=str(y), month=str(m), pair="usdjpy", platform=P.META_TRADER, time_frame=TF.ONE_MINUTE,
                   output_directory=str(dest))
                print(f"  ok  {y}-{m:02d}")
            except Exception as e:  # noqa: BLE001
                print(f"  FAIL {y}-{m:02d}: {e}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--histdata", action="store_true")
    a = ap.parse_args()
    fred()
    mof()
    cftc()
    if a.histdata:
        histdata()
