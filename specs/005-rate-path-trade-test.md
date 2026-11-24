# Spec 005: Rate-path revision, trade simulation (H3)

**Author:** Haru (drafted with Claude) · **Date:** 2026-11-24 · **Status:** rejected

> **Relation to spec 003.** This was written and run without knowledge of `specs/003-rate-path-revision.md`,
> which tests the same hypothesis the way `Research/Strategy/Hypothesis Review H1 to H3.md` §6
> recommends: a volatility-standardised predictive regression first, trade rules only if it
> passes. This spec instead simulates trades directly, with Newey–West errors on raw pips, under
> its own kill criteria. It does **not** replace spec 003. Spec 003's parameters were fixed
> before these results existed, so it can still be run as written, but it must not be changed
> in response to anything here. The raw-pips slope diagnostic below (t +2.19) uses Newey–West
> errors, which per the review's simulation keep the false-positive rate near nominal but give an
> unstandardised test little power and weight it towards volatile periods. Treat it as
> descriptive; spec 003's standardised regression is the proper test of that question.

## Hypothesis
USDJPY is priced off the expected US–Japan policy-rate path, which the 2-year yield spread
summarises. When that path is revised, FX traders under-react: macro and real-money accounts
rebalance over days, not minutes, so USDJPY keeps drifting in the direction of a recent spread
change (V1, V2). Separately, when USDJPY strays far from the level its recent relationship with
the spread implies, it tends to drift back (V3). The counterparty is slow-moving real money
re-hedging to a new rate outlook, not a dated flow.

## Evidence
From `Research/Strategy/Initial Strategy Survey.md`, section H3:
- The spread–USDJPY link is strong but **contemporaneous** (one-month correlation of US 2y/10y
  swaps with USDJPY ~96%, MNI) and **unstable** (12-week correlation with the 10y spread averaged
  +0.43 before Oct 2025, −0.07 after, MUFG). Levels are not a tradeable signal.
- Predictive evidence exists only at multi-quarter horizons (pooled differential coefficient
  2.17 at t+1 quarter, decaying to −0.04 by t+10; NBER WP 14473).
- One dated, unverified conditional statistic: when the US–Japan 2y spread compressed ≥15bp over
  five sessions, USDJPY fell in every instance, averaging −3.92% (Investing.com, 23 Nov 2026;
  no sample size or period stated).
- No published backtest of either the change or the residual form. This is a test, not a replication.

## Rules (exact, no discretion)
**Decision time:** 00:00 UTC (09:00 JST) on every weekday. Entries and exits are market orders
at that time: buy at the ask, sell at the bid of the last 1-minute quote at or before it.

**Spread s(D)** = US 2y − JGB 2y in basis points, each leg taken as the latest value
**published before** the decision time (the survey's "timestamp trap two"):
- US 2y: FRED `DGS2` for date T counts as published at 18:00 New York time on T (Treasury
  releases its par curve after the US close). At 00:00 UTC on D the newest usable value is D−1.
- JGB 2y: MOF curve for Japanese date T counts as published at 18:00 JST on T. At 09:00 JST on D
  the newest usable value is D−1.
- If either leg is more than 5 calendar days old (long holidays), no new trade that day.

**Variants** (exactly three; no others will be run before this spec's decision):
- **V1 Change.** x = s(D) − s(D−5 decision days). Long USDJPY if x > 0, short if x < 0. A trade is
  opened every decision day and held 5 decision days (overlapping positions).
- **V2 Big move.** Same x. Open a trade in the direction of x when |x| ≥ 15bp. Hold 5 decision
  days. No new V2 trade while one is open (non-overlapping events).
- **V3 Residual.** On each D, regress log(mid) on s over the previous 252 decision days (D−252
  to D−1, using only values known at each of those decision times). Residual
  e = log(mid(D)) − fit(s(D)); z = e / std(window residuals). Short USDJPY if z ≥ 1, long if
  z ≤ −1, else no trade. Hold 10 decision days (overlapping positions).

**Size:** USD 100k per trade.

**Costs:** `usdjpy.costs.CostModel` (bid/ask fills, IBKR commission, slippage) plus
**financing**: a long USDJPY position earns (US rate − Japan rate) and a short pays it, using
the effective Fed funds rate (FRED `DFF`) and the BoJ uncollateralised overnight call rate
(monthly average), known at entry, over the calendar days held (act/360). IBKR keeps a skim on
both sides of a cash FX position (USD credit at benchmark − 0.5%, JPY debit at benchmark + 1.5%),
modelled as **2.0% a year** of notional against every position, **2.5%** under `PESSIMISTIC`.

**Sample:** 2007-01 to 2024-12, from the combined seeded 1-minute data. Trades whose exit falls on
or after `HOLDOUT_START` (2025-01-01) are dropped.

## Data needed
- USDJPY 1-minute bid/ask: `data/bars_1min` via `usdjpy.datasets.load_minute("combined")`.
  Before 2024-06 the ask is synthetic (bid + typical 2024–26 spread for that hour).
- FRED `DGS2`, `DFF`: `data/official/fred_daily.csv` (`scripts/fetch_official.py`).
- MOF JGB 2y: `data/macro/mof_jgb_yields_daily_1974_2026.csv`.
- BoJ call rate: `data/macro/boj_call_rate_monthly_1985_2026.csv`.

## Kill criteria (decided BEFORE testing)
Each variant is judged on its own, on pre-holdout trades. It is rejected if any holds:
1. Mean net pips per trade ≤ 0 under base costs, including financing.
2. Newey–West t-stat of the mean net pips < 3.0, with lag = holding period in days (the
   survey's bar, stricter than spec 001's 2.0 because three variants are tested).
3. Mean net pips per trade ≤ 0 in 2022–2024.
4. Mean net pips ≤ 0 or Newey–West t < 3.0 under `PESSIMISTIC` costs.
5. **Drift control:** after subtracting the sample's average 5-day (V3: 10-day) mid-price move,
   signed by each trade's side, the mean is ≤ 0 or its Newey–West t < 2.0. USDJPY rose from ~120
   to ~157 over 2007–2024, so a rule that is long most of the time can look good on drift alone.

Not run here, and required before any variant moves on: deflated Sharpe ratio and probability of
backtest overfitting (survey: DSR > 0.95, PBO < 0.05).

## Parameters
Lookback n = 5 days (V1, V2); threshold 15bp (V2, from the quoted statistic); fair-value window
252 days and entry |z| ≥ 1 (V3); holds 5 / 5 / 10 days; decision time 00:00 UTC; staleness limit
5 days; financing skim 2.0% (2.5% pessimistic). None will be tuned on this sample.

## Results
Run 2026-11-24 with `python scripts/h3_rate_study.py` (combined data, 2007-01 to 2024-12,
3,976 decision days with a quote and a spread). Files: `results/h3_summary.csv`,
`results/h3_verdict.csv`, `results/h3_V{1,2,3}_trades.csv`, `results/h3_signals.csv`.

| | V1 Change | V2 Big move | V3 Residual |
|---|---|---|---|
| Trades | 3,911 | 175 | 1,613 |
| Share long | 51% | 50% | 63% |
| Mean net pips, base | −0.73 | +7.16 | −0.54 |
| Newey–West t, base | −0.19 | +0.47 | −0.04 |
| Mean net pips, pessimistic | −2.38 | +5.42 | −3.26 |
| 2022–2024 mean net pips | +12.32 | +20.71 | −39.02 |
| Net minus drift, NW t | −0.22 | +0.48 | −0.21 |
| Mean financing per trade | −5.10 | −6.56 | −10.33 |
| Kill criteria failed | 1, 2, 4, 5 | 2, 4, 5 | all five |

**Decision: all three variants rejected.** None comes close to the t ≥ 3.0 bar. Sub-periods
flip sign (V1: +4.6 / −10.2 / +12.3; V3: +53.9 / −11.0 / −39.0 pips), which is what noise looks
like.

Diagnostics (not kill criteria): regressing the raw 5-day mid move on the 5-day spread change
gives +0.96 pips per bp, Newey–West t +2.19. So there is a faint same-direction drift, but it is
small next to costs: financing alone (mostly IBKR's 2% skim) takes about 5 pips from every
5-day trade. The 10-day move on V3's fair-value z has slope −6.67 pips per z, t −0.90: no
mean reversion to speak of. V2 fires mostly in rate-volatile regimes (2008: 33 events; 2022–24:
83) and almost never at the zero bound (2010–2021: 33 events in 12 years).

Data notes: decision days without a quote are skipped, not filled. That is 35–128 a year in
2007–2014 (gaps in the Dukascopy mirror) and **62 in 2023: the HistData 2023 file is missing up
to ~60% of minutes between 08:00 and 24:00 UTC from February to July**, contrary to
`docs/DATA.md`. Before mid-2024 the ask is synthetic. Neither is large enough to change the decision.

Not tried, and not to be tried on this sample without a new spec: other lookbacks, thresholds,
holding periods or decision times; futures (6J/MJY) instead of spot, which would avoid the
financing skim but not the lack of significance.
