# Spec 007: No-news 1-minute shock fade

**Author:** Haru · **Date:** 2026-11-24 · **Status:** idea

## Hypothesis
A very large 1-minute move with no scheduled news is usually a liquidity event, not information: a
large market order, or a cascade of price-contingent stop-loss orders, hits a thin book. The traders who
must act are stop-loss holders and margin-called leveraged accounts, and their orders carry no
information. Liquidity providers then lean against the overshoot and price partly reverts within an
hour. The yen-specific danger is that the largest "no-news" moves of 2022–2026 were interventions,
rate checks and BoJ leaks, which *continue*. The exclusion list matters more than the threshold.

## Evidence
- Xiao, Yin & Zhao (J. Financial Research 2020), equity ETFs: 57% of intraday jumps have no associated
  news, and **no-news jumps are followed by significant reversals for at least 60 minutes**
  ([vLex](https://law-journals-books.vlex.com/vid/jumps-news-and-subsequent-855590156)). Not FX.
- Only FX trading evidence: a jump-cluster study on 8 USD pairs, 5-min data, **1 Mar – 6 Jun 2013**
  (Bayes WP 08-2014): very short and regime-specific.
- FX jump detection is "extremely sensitive" to sampling frequency and test choice
  ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9563180)). FX volatility is strongly periodic intraday
  (St. Louis Fed WP 2012-008), so without minute-of-week normalisation "shocks" just pick out 08:30 ET
  and 09:55 JST.
- Osler (NY Fed SR150): large stop-losses cluster near round numbers, a mechanism for cascades.
- No USDJPY-specific result exists. **Exploratory** (thresholds are our own).

## Rules (exact, no discretion)
- Days: all bars 2015-01-01 → 2024-12-31 outside the exclusions below.
- Shock: r = 1-min mid log return. s_m = median |r| at the same minute-of-week over the previous 60
  trading days. Shock if |r| > 5 × s_m.
- Entry: against the shock at the **close of the next bar** (one-bar delay), at bid/ask. No new entry
  while a position is open.
- Exit (three variants): time exit after 15, 30 or 60 minutes. Stop: 1.5 × |shock size| beyond entry,
  checked on bar highs/lows (from the notes' proposed design).
- Filters / skip conditions (until the release calendar, Tier 0c, exists):
  - ±5 min around 08:30, 10:00 and 14:00 ET on every weekday (13:30/12:30, 15:00/14:00 and
    19:00/18:00 UTC, EST/EDT; 22:30/21:30, 00:00/23:00 and 04:00/03:00 JST).
  - 08:25–08:55 JST (23:25–23:55 UTC, Japanese data); 09:50–10:00 JST (00:50–01:00 UTC, Tokyo fix).
  - BoJ decision days 11:00–16:00 JST (02:00–07:00 UTC); FOMC days after 14:00 ET.
  - MOF intervention days and T+1; rate-check days.
  - 16:55–17:10 ET (21:55–22:10 / 20:55–21:10 UTC; 06:55–07:10 / 05:55–06:10 JST).
  - Mondays before 09:00 JST (00:00 UTC).
  - Once 0c exists, add ±5 min around every timed release in it.
- Twin test (separate ledger entry): shocks *inside* the news windows above, traded **with** the shock,
  same exits. Hypothesis: these continue.
- Size: USD 100k.

## Data needed
- `datasets.load_minute('histdata')` 2015–2024; `datasets.fomc()`, `datasets.boj()`,
  `datasets.interventions()`.
- `datasets.load_minute('eightcap')` + `datasets.load_ticks('YYYYMM')` for 2024-06 → 2024-12 to check
  real spreads and next-bar fills at shock minutes. Synthetic HistData spreads (hourly median) will
  **understate** cost at shock minutes.
- Missing: US release calendar (`data/calendars/us_releases.csv`, from BLS/BEA schedules) and
  rate-check dates (`data/calendars/rate_checks.csv`, by hand; e.g. 2026-01-23, which is in the holdout).
- Loader gap: `load_minute` returns bar close only. Stops need bid high/low (present in the HistData and
  Eightcap parquet files), so extend the loader.

## Kill criteria (decided BEFORE testing)
Exploratory, so the bar is t ≥ 3. Reject if any of:
- Mean net pips ≤ 0 under base costs (2015–2024), or t < 3 for the chosen variant;
- Mean has a different sign in 2015–2019 and 2020–2024;
- Mean net ≤ 0 under `PESSIMISTIC`;
- Fails against a placebo: the same fade at random non-shock minutes matched by minute-of-week must
  earn less (difference t ≥ 2);
- On 2024-06 → 2024-12 Eightcap data, the mean real entry spread at shock+1 bars is more than 2× the
  synthetic spread *and* the result turns ≤ 0 when re-costed with measured spreads.
Also report the result with the top 1% of trades by |P&L| removed (no decision, a robustness check).

## Parameters
k = 5, lookback = 60 days, entry delay = 1 bar, stop = 1.5 × shock, exits 15/30/60 min (the three
variants). Do not tune k on the full sample.

## Implementation notes
Path-dependent (detection, stop), so `window_trades` does not fit. Write a vectorised shock scanner
plus a per-trade bar loop over the next ≤60 bars with bid/ask high/low, then validate fills on Eightcap
ticks (a limit or stop counts as filled only if price trades through by ≥ 1 tick). In Eightcap-period
runs, record the spread z-score at entry for the spec 017 spread filter.

## Results
_Pending._
