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
| `bars_1min/histdata_bid_2015_2025.parquet` | 2015-01 → 2025-04 | 1-min BID OHLC | HistData.com M1 via github.com/yukkiya/usd-jpy-data | **NOT complete**, despite claiming "Complete (~372k min/yr)" here until 2026-11-25: spec 005 found up to ~60% of minutes missing between 08:00 and 24:00 UTC from Feb to Jul 2023 (62 decision days lost in 2023 alone), which is where spec 004's 23:00 UTC prefix entry sits. Verify a year before relying on it. Timestamps are NY local time *with* DST (not fixed EST as HistData documents), **except that from 2019 HistData's raw clock changes on EU DST dates**: in the weeks where US and EU clocks disagree (2nd Sunday of March to last Sunday of March; last Sunday of October to 1st Sunday of November) the stored bar labelled T holds the true T+60 price. **Corrected in the loader** by `datasets.fix_histdata_dst` (2026-11-25); read the file through `load_minute`, never directly. Evidence, from `scripts/histdata_alignment_check.py` (pre-holdout only): every full EDT and EST month aligns at offset 0 against Dukascopy 2015-01..2023-03 (93 month-regime cells) and Eightcap 2024-06..2024-12 (7), so US summer itself is right; 75 dates align at +60, all inside a mismatch window, in 2019, 2021-23 (Dukascopy) and 2024 (Eightcap); 2015-2018 have none. 2020, Nov 2023 and Mar 2024 have no reference and were checked on the Sunday reopen label (20:00 UTC instead of 21:00) and the intraday |return| profile (best lag +60 in every 2019-2024 window, 0 in every 2015-2018 one), and against the Fed H.10 noon rate, an independent 12:00 New York print (every 2019-2024 window closest at +60, March 2020 3.9 pips against 13.8 as stored). After correction: 0 dates off, every window at lag 0. Mar 2025 is post-holdout and corrected by the same rule unchecked. The file on disk (mtime 2026-11-24 21:47) predates every committed version of `build_github_data.py`, so whether the EU-date switch is in HistData's raw stamps or in the uncommitted conversion that built this file is unverified. The fix is applied unconditionally: **after any rebuild, re-run the check script before trusting the fix**, since a file built differently could be shifted twice. |
| `bars_1min/dukascopy_bid_2007_2023.parquet` | 2007-01 → 2023-03 | 1-min BID OHLC + Dukascopy volume | Dukascopy export via github.com/EPSOFT/Database-Currency-Pair | **Gappy**: 2007–10 ≈ 85% complete; 2011–18 only 40–65%; **2020 missing**; 2023 ends 31 Mar. Use for 2007–2014 only. Volume = Dukascopy liquidity, not market volume. |
| `bars_1min/eightcap_bidask_2024_2026.parquet` | 2024-06-19 → 2026-06-05 | 1-min bid/ask close, bid OHLC, mean spread, tick count | Eightcap MT5 raw-spread account via github.com/rForex/ForexEightcapUSDJPYi_{2024,2025,2026} | **Real bid/ask.** Server time = NY + 7h (verified: spread spike at 17:00 NY rollover). Covers 2026-04-30 intervention. |
| `ticks/eightcap/USDJPY_YYYYMM.parquet` | same | every quote update, bid/ask as int (price × 1000) | same | ~45M ticks. `datasets.load_ticks("202504")` returns JPY prices. |
| `tokyo_hours/USDJPY/YYYY/YYYY-MM-DD.parquet` | being fetched from 2026-11-25 | Dukascopy ticks (bid, ask, volumes), **UTC hours 22, 23, 0, 1 only**, market hours only | datafeed.dukascopy.com via `scripts/download_gap_fill.py` | Spec 004 gap fill, option C in `specs/README.md` *Dukascopy fetch*. Stage 1: Feb–Jul 2023. Stage 2: a **sample** of 2015–2024 (first B and first C day of each month), so sparse there; a spread source, not a price source. Stage 3: every weekday 2007–2014. `_hours.json` records the hours; never mix with a full-day tree. |
| `USDJPY/YYYY/YYYY-MM-DD.parquet` | 15 days of 2003 | Dukascopy ticks, full day | `scripts/download.py` | Partial full-day download from 2026-11. Do not add hours-limited files (`_claim_tree` refuses). |
| `quarantine/getdata_2026_sample.parquet` | 2026-03 → 2026-09 | 1-min OHLC | getdata-finance GitHub sample | **Do not use.** Returns match (ρ=0.96) but levels drift ±50–150 pips vs two independent sources. |

**Cross-checks run:** Dukascopy vs HistData (2015-01 to 2023-03, month by month and day by day) and HistData vs Eightcap
(2024-06 to 2024-12): lag 0 after `fix_histdata_dst`, median level difference 0.0–0.2 pips. Before it, the US/EU DST
mismatch weeks from 2019 sat at lag +60 (see the HistData row). `scripts/histdata_alignment_check.py` reruns all of it. Intervention days land where reported (e.g. 2024-04-29
−331 pips by 04:34 UTC / 13:34 JST; 2024-07-11 −340 pips by 13:07 UTC right after US CPI).

**Spread profile (Eightcap, median pips by JST hour):** ~0.23–0.30 all session hours, 0.33–0.36
around 08:00–09:00, ~5.0 in the 06:00 hour alone (NY rollover), decaying to ~0.60 at 07:00 and ~0.36 by 08:00. Retail IBKR spreads will differ — log your own.

**Not obtained (blocked from the seeding environment):** Dukascopy tick data 2003→now, beyond the
two trees above (`scripts/download.py`), HistData 2000–2014 and 2025-05→now (`fetch_official.py --histdata`),
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
| `macro/fred_h10_usdjpy_daily_1971_2026.csv` | 1971-01 → 2026-11-20 | Fed H.10 noon NY USDJPY | FRED via github.com/datasets/exchange-rates. Loader `datasets.h10_daily()` (drops the 572 holiday rows; stamps 12:00 New York). Identical to `DEXJPUS` in `fred_daily_2000_2026H1.csv` on all 6,635 dates that file quotes (max difference 0.0, checked 2026-11-26). |
| `macro/mof_jgb_yields_daily_1974_2026.csv` | 1974-09 → 2026-05 | MOF JGB yield curve 1y–40y | MOF jgbcm_all.csv via same GitHub repo |
| `dgs2.csv` | 2005-01 → 2026-11-24 | UST 2y CMT, FRED `DGS2` layout (`observation_date,DGS2`) | **Treasury** daily par-curve CSV, "2 Yr" column, per year 2005–2026 (FRED timed out from the seeding environment; same underlying series). At `DATA_DIR` root, not under `macro/`, because `rate_path_study.py` expects it there. Fetched 2026-11-24 for spec 003. |
| `jgbcme_all.csv` | 1974-09 → 2026-10-30 | MOF JGB curve 1Y–40Y, English edition | mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv (the URL in `rate_path_study.py` had 404'd). 2Y matches `macro/mof_jgb_yields…` exactly on 5,238 overlapping days. At `DATA_DIR` root, not under `macro/`. Fetched 2026-11-24. |
| `macro/boj_call_rate_monthly_1985_2026.csv` | 1985-07 → 2026-05 | Uncollateralised O/N call rate (EOM, avg) | BoJ time-series via same repo. Loader `rates.boj_call_rate()`: monthly average, stamped 10:00 JST on the first Japanese business day of the next month, when the BoJ publishes the month's last final daily rate ([BoJ call money data](https://www.boj.or.jp/en/statistics/market/short/mutan/index.htm): final results for the previous business day around 10:00). Until 2026-11-26 it was stamped 00:00 UTC on the 1st, a look-ahead of 1 h (median) to 145 h (Golden Week 2019); its effect is in `HANDOFF-2026-11-25-during-fetch.md` Task 5. |
| `macro/vix_daily_1990_2026.csv` | 1990 → 2026-09 | VIX OHLC | CBOE via github.com/datasets/finance-vix |

**`official/fred_daily.csv` holds DFF and DGS2 only** (fetched 2026-11-26 from fred.stlouisfed.org
`fredgraph.csv` through `fetch_official.fred()` restricted to those two series; DFF 1954-07-01 →
2026-11-24, DGS2 1976-06-01 → 2026-11-24; SHA-256 `a2559174…eba5`). Loaders `rates.fed_funds()` and
`rates.us_2y()`. FRED DGS2 equals the Treasury-sourced `dgs2.csv` on all 5,478 shared days. With it,
spec 005's published *Results* reproduce exactly once the two later loader fixes are undone (HistData
DST, exec-hour spread), so this vintage is the one spec 005 ran on. The full `fetch_official.py` run
(SOFR, VIX, SP500, the other FRED series, MOF, CFTC) has not been done and would overwrite this file
with more columns. Rows from 2025 are holdout: on disk is not use; the loaders' consumers enforce it.

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
