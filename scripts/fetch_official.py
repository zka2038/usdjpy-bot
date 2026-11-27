"""Fetch official sources directly (run on your own machine; these hosts were unreachable when the
repo was seeded). Each source is independent: a failure is reported and the rest continue.

    python scripts/fetch_official.py              # FRED, MOF, CFTC
    python scripts/fetch_official.py --histdata   # + HistData 1-min 2000-2014 and 2025-05 onward (pip install histdata)
    python scripts/fetch_official.py --no-official --histdata-pairs eurjpy,gbpjpy,audjpy,eurusd,gbpusd,audusd
        # spec 019: HistData 1-min for other pairs, 2007-2024 only, built to data/bars_1min/.
        # Refuses to run until the Dukascopy gap-fill fetch has logged "stage 3 complete".

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
    """HistData.com 1-min. Timestamps are NY local WITH DST (see docs/DATA.md) - localize to America/New_York."""
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


PAIR_YEARS = range(2007, 2025)   # spec 019: pre-holdout only; holdout years are not downloaded


def dukascopy_fetch_done() -> tuple[bool, str]:
    """True unless a Dukascopy gap-fill fetch exists whose log does not yet end in
    `stage 3 complete`. Looks for data/tokyo_hours here and in parent directories, as
    scripts/fetch_status.py does, so it finds the main checkout's tree from a worktree."""
    for base in (ROOT, *ROOT.parents):
        log = base / "data" / "tokyo_hours" / "fetch.log"
        if log.exists():
            lines = log.read_text(errors="replace").splitlines()[-20:]
            done = any("stage 3 complete" in x for x in lines)
            return done, str(log)
    return True, "no data/tokyo_hours/fetch.log found"


def histdata_pairs(pairs: list[str]) -> None:
    """Spec 019's pairs: yearly HistData MetaTrader M1 zips for 2007-2024, built into
    data/bars_1min/histdata_<pair>_bid_2007_2024.parquet (bid OHLC, UTC; NY local with DST,
    no EU-date correction: spec 019's Step 0 decides that). Raw zips stay in
    data/official/histdata/<pair>/."""
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from usdjpy.config import HOLDOUT_START
    from usdjpy.datasets import histdata_pair_path, read_histdata_mt_csv

    done, where = dukascopy_fetch_done()
    if not done:
        raise SystemExit(
            f"Refusing: the Dukascopy gap-fill fetch is not complete ({where}). No other fetch "
            "runs until it logs 'stage 3 complete' (user's instruction, 2026-11-27).")
    if max(PAIR_YEARS) >= pd.Timestamp(HOLDOUT_START).year:
        raise SystemExit("PAIR_YEARS reaches the holdout; spec 019 downloads pre-holdout years only")
    try:
        from histdata import download_hist_data as dl
        from histdata.api import Platform as P, TimeFrame as TF
    except ImportError:
        raise SystemExit("pip install histdata")
    for pair in pairs:
        pair = pair.lower()
        print(f"HistData {pair}")
        dest = OUT / "histdata" / pair
        dest.mkdir(parents=True, exist_ok=True)
        parts = []
        for y in PAIR_YEARS:
            zips = sorted(dest.glob(f"*{pair.upper()}*{y}*.zip"))
            if not zips:
                try:
                    dl(year=str(y), pair=pair, platform=P.META_TRADER, time_frame=TF.ONE_MINUTE,
                       output_directory=str(dest))
                except Exception as e:  # noqa: BLE001
                    print(f"  FAIL {y}: {e}")
                    continue
                zips = sorted(dest.glob(f"*{pair.upper()}*{y}*.zip"))
            for z in zips:
                with zipfile.ZipFile(z) as zf:
                    for name in zf.namelist():
                        if name.lower().endswith(".csv"):
                            parts.append(read_histdata_mt_csv(zf.open(name)))
            print(f"  ok  {y}")
        if not parts:
            print(f"  no data for {pair}")
            continue
        bars = pd.concat(parts).sort_index()
        bars = bars[~bars.index.duplicated(keep="last")]
        bars = bars[bars.index < pd.Timestamp(HOLDOUT_START, tz="UTC")]
        out = histdata_pair_path(pair)
        out.parent.mkdir(parents=True, exist_ok=True)
        bars.to_parquet(out, compression="zstd")
        print(f"  built {out.name}: {len(bars):,} bars {bars.index[0]} .. {bars.index[-1]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--histdata", action="store_true")
    ap.add_argument("--histdata-pairs", default=None,
                    help="comma-separated pairs other than usdjpy, 2007-2024 only (spec 019)")
    ap.add_argument("--no-official", action="store_true", help="skip FRED, MOF and CFTC")
    a = ap.parse_args()
    if a.histdata_pairs:   # checked first, so a refusal happens before any other request
        done, where = dukascopy_fetch_done()
        if not done:
            raise SystemExit(f"Refusing: the Dukascopy gap-fill fetch is not complete ({where}).")
    if not a.no_official:
        fred()
        mof()
        cftc()
    if a.histdata:
        histdata()
    if a.histdata_pairs:
        histdata_pairs([x.strip() for x in a.histdata_pairs.split(",") if x.strip()])
