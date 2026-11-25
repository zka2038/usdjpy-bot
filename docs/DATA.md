# Data catalogue

Seeded 2026-11-24. All timestamps in processed files are **UTC**. Prices are USDJPY in JPY.
`data/` is git-ignored except `data/calendars/` and `data/README.md`; rebuild the rest with
`python scripts/build_github_data.py` (GitHub mirrors) and `python scripts/fetch_official.py` (official hosts).

Load everything through `usdjpy.datasets` — it handles sources, synthetic ask, and release lags.

**This file is the catalogue.** `data/README.md` used to carry a second copy of
every table below, and the two drifted: the HistData "Complete" claim was
corrected here and not there, while `dgs2.csv` and `jgbcme_all.csv` were
catalogued there and not here, so each file held one true fact and one stale one.
`data/README.md` now points here. Record provenance in this file only.

## Prices

| File | Coverage | Content | Source | Notes |
|---|---|---|---|---|
| `bars_1min/histdata_bid_2015_2025.parquet` | 2015-01 → 2025-04 | 1-min BID OHLC | HistData.com M1 via github.com/yukkiya/usd-jpy-data | **NOT complete**, despite claiming "Complete (~372k min/yr)" here until 2026-11-25: spec 005 found up to ~60% of minutes missing between 08:00 and 24:00 UTC from Feb to Jul 2023 (62 decision days lost in 2023 alone), which is where spec 004's 23:00 UTC prefix entry sits. Verify a year before relying on it. Timestamps are NY local time *with* DST (not fixed EST as HistData documents) — verified by weekly-open time and lag-0 match vs Dukascopy & Eightcap. |
| `bars_1min/dukascopy_bid_2007_2023.parquet` | 2007-01 → 2023-03 | 1-min BID OHLC + Dukascopy volume | Dukascopy export via github.com/EPSOFT/Database-Currency-Pair | **Gappy**: 2007–10 ≈ 85% complete; 2011–18 only 40–65%; **2020 missing**; 2023 ends 31 Mar. Use for 2007–2014 only. Volume = Dukascopy liquidity, not market volume. |
| `bars_1min/eightcap_bidask_2024_2026.parquet` | 2024-06-19 → 2026-06-05 | 1-min bid/ask close, bid OHLC, mean spread, tick count | Eightcap MT5 raw-spread account via github.com/rForex/ForexEightcapUSDJPYi_{2024,2025,2026} | **Real bid/ask.** Server time = NY + 7h (verified: spread spike at 17:00 NY rollover). Covers 2026-04-30 intervention. |
| `ticks/eightcap/USDJPY_YYYYMM.parquet` | same | every quote update, bid/ask as int (price × 1000) | same | ~45M ticks. `datasets.load_ticks("202504")` returns JPY prices. |
| `quarantine/getdata_2026_sample.parquet` | 2026-03 → 2026-09 | 1-min OHLC | getdata-finance GitHub sample | **Do not use.** Returns match (ρ=0.96) but levels drift ±50–150 pips vs two independent sources. |

**Cross-checks run:** Dukascopy vs HistData (2017, 2021) and HistData vs Eightcap (2024–25): lag 0,
median level difference 0.0–0.2 pips. Intervention days land where reported (e.g. 2024-04-29
−331 pips by 04:34 UTC / 13:34 JST; 2024-07-11 −340 pips by 13:07 UTC right after US CPI).

**Spread profile (Eightcap, median pips by JST hour):** ~0.23–0.30 all session hours, 0.33–0.36
around 08:00–09:00, ~5.0 in the 06:00 hour alone (NY rollover), decaying to ~0.60 at 07:00 and ~0.36 by 08:00. Retail IBKR spreads will differ — log your own.

**Not obtained (blocked from the seeding environment):** Dukascopy tick data 2003→now
(`scripts/download.py`), HistData 2000–2014 and 2025-05→now (`fetch_official.py --histdata`),
TrueFX, CME 6J futures volume (paid: Databento/CME DataMine).

## Positioning

| File | Coverage | Content | Source |
|---|---|---|---|
| `positioning/cot_jpy_tff_weekly.csv` | 2010-01-05 → 2026-11-17 | CFTC Traders in Financial Futures, JPY: dealer / asset manager / leveraged funds / other, long-short-net, % OI | github.com/ForexiaPro/cot-data (auto-updated weekly from CFTC) |
| `positioning/cot_jpy_legacy_weekly.csv` | same | Legacy report: non-commercial / commercial / non-reportable | same |

Positions are as of **Tuesday**, released **Friday 15:30 ET**. Use `available_from` from
`datasets.cot()` to avoid look-ahead. Verify against CFTC with `fetch_official.py` (TFF zips).

## Macro

| File | Coverage | Content | Source |
|---|---|---|---|
| `macro/fred_daily_2000_2026H1.csv` | 2000-01 → 2026-06 | DEXJPUS, DGS10/20/30, VIXCLS, NIKKEI225 | FRED, via github.com/gourujeevan-cpu/japan-jgb-yield-regression |
| `macro/fred_h10_usdjpy_daily_1971_2026.csv` | 1971-01 → 2026-11-20 | Fed H.10 noon NY USDJPY | FRED via github.com/datasets/exchange-rates |
| `macro/mof_jgb_yields_daily_1974_2026.csv` | 1974-09 → 2026-05 | MOF JGB yield curve 1y–40y | MOF jgbcm_all.csv via same GitHub repo |
| `dgs2.csv` | 2005-01 → 2026-11-24 | UST 2y CMT, FRED `DGS2` layout (`observation_date,DGS2`) | **Treasury** daily par-curve CSV, "2 Yr" column, per year 2005–2026 (FRED timed out from the seeding environment; same underlying series). At `DATA_DIR` root, not under `macro/`, because `rate_path_study.py` expects it there. Fetched 2026-11-24 for spec 003. |
| `jgbcme_all.csv` | 1974-09 → 2026-10-30 | MOF JGB curve 1Y–40Y, English edition | mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv (the URL in `rate_path_study.py` had 404'd). 2Y matches `macro/mof_jgb_yields…` exactly on 5,238 overlapping days. At `DATA_DIR` root, not under `macro/`. Fetched 2026-11-24. |
| `macro/boj_call_rate_monthly_1985_2026.csv` | 1985-07 → 2026-05 | Uncollateralised O/N call rate (EOM, avg) | BoJ time-series via same repo |
| `macro/vix_daily_1990_2026.csv` | 1990 → 2026-09 | VIX OHLC | CBOE via github.com/datasets/finance-vix |

**Missing: US 2-year yield (DGS2)** — needed for the rate-differential signal. `fetch_official.py` pulls
it with DFF, SOFR, broad dollar and others into `data/official/fred_daily.csv`.

## Calendars (tracked in git)

| File | Coverage | Source |
|---|---|---|
| `calendars/fomc_decisions.csv` | 2007 → 2027 (2027 tentative), incl. unscheduled calls; SEP flag | federalreserve.gov fomccalendars.htm + fomchistoricalYYYY.htm |
| `calendars/boj_mpm.csv` | 2010 → 2027 (start + decision day) | boj.or.jp mpmsche_minu past.htm + index.htm |
| `calendars/mof_intervention_transcribed.csv` | 1991-05 → 2026-08-03 | MOF foreign_exchange_intervention_operations.csv |

The intervention file was **transcribed through a web reader**, not downloaded byte-for-byte. Totals
check out against MOF's published figures (e.g. 2026-04-28→05-27 = ¥11.735tn; 2026-07-30→08-03 =
¥15.40tn), but run `fetch_official.py` and diff against `data/official/mof_intervention_all.csv`
(Shift-JIS) before relying on pre-2010 rows. BoJ 2007–2009 meeting dates not yet included.
Gotobi days and holidays are computed in code (`usdjpy.calendars`).

**Not yet included:** US data release times (NFP, CPI). BLS publishes schedules per year; add when an
event strategy needs them.

## Official sources (run `scripts/fetch_official.py` on your machine → `data/official/`)

FRED (DGS2, DGS10, DGS3MO, DFF, SOFR, T10YIE, VIXCLS, SP500, NIKKEI225, DTWEXBGS, DEXJPUS, OECD Japan
rates) · MOF intervention (full history) · **MOF weekly portfolio flows** (week.csv, 2005→, Shift-JIS)
and monthly/by-investor flows · MOF JGB yields (all + current month) · CFTC TFF official zips 2010→ ·
optional HistData via `pip install histdata`.
