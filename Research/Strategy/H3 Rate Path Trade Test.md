# H3 Rate Path Trade Test

**Date:** 2026-11-24 · **Verdict:** all three trade variants rejected; the long side of V2 is a lead, not evidence
**Spec:** `specs/005-rate-path-trade-test.md` · **Code:** `scripts/h3_rate_study.py`, `src/usdjpy/rates.py`, `src/usdjpy/horizon.py`

> **Relation to spec 003.** This is a trade-simulation test of H3, run without knowledge of
> `specs/003-rate-path-revision.md`, which tests the same hypothesis as a volatility-standardised
> predictive regression (`Hypothesis Review H1 to H3.md` §6). It does not replace spec 003.
> Spec 003's parameters were fixed before these results existed, so it can still be run as
> written, but it must not be changed in response to anything below. No holdout data
> (2025-01-01 onward) was used: trades whose exit falls in 2025 were dropped.

## 1. Verdict

Three variants, each pre-declared in spec 005 with its own kill criteria (Newey–West t ≥ 3.0
with lag = holding period, positive under base and pessimistic costs, positive in 2022–24,
beats drift). Sample 2007-01 to 2024-12 on the combined seeded 1-minute data, 3,976 decision
days at 00:00 UTC with a quote and a spread.

| | V1 Change | V2 Big move | V3 Residual |
|---|---|---|---|
| Rule | sign of 5-day spread change, hold 5 days, daily | same, only when \|change\| ≥ 15bp, hold 5 days, one at a time | fade \|z\| ≥ 1 from a 252-day fair-value fit, hold 10 days |
| Trades | 3,911 | 175 | 1,613 |
| Mean net pips, base | −0.73 | +7.16 | −0.54 |
| Newey–West t | −0.19 | +0.47 | −0.04 |
| 2007–14 / 2015–21 / 2022–24 | +4.6 / −10.2 / +12.3 | −22.5 / +37.0 / +20.7 | +53.9 / −11.0 / −39.0 |
| Kill criteria failed | 1, 2, 4, 5 | 2, 4, 5 | all five |

None comes near t = 3. Sub-periods flip sign, which is what noise looks like. Financing, not
spread, is the cost that matters at this horizon: IBKR's ~2% a year skim on a cash FX position
takes about 5 pips from every 5-day trade, against about 1 pip of spread, commission and slippage.

## 2. V2 in detail

**Mechanism.** A 15bp move in the US–Japan 2y spread over five sessions is a meaningful revision
of the expected rate path. The bet is that real-money accounts re-hedge over days, so USDJPY
keeps moving with the spread. The threshold comes from the survey's one dated statistic: after
every ≥15bp compression USDJPY fell, by 3.92% on average (Investing.com, no sample stated).

**Rules.** At 00:00 UTC each weekday, spread = US 2y − JGB 2y using only values published
before that moment (normally the previous day's closes). If it moved ≥15bp versus five decision
days earlier, trade in that direction for five decision days. While a trade is open, new
signals are ignored, so 449 qualifying days produced 175 trades.

**It fires in rate-volatile regimes.** The median weekly |change| is 4.5bp; ≥15bp is roughly
the 90th percentile. 33 trades in 2008 and 83 in 2022–24, but 33 in the twelve years 2010–2021.

**Long and short are two different stories.**

| | All | Long (spread widened) | Short (spread narrowed) |
|---|---|---|---|
| Trades | 175 | 87 | 88 |
| Mean net pips | +7.2 | +38.0 | −23.4 |
| Newey–West t | 0.47 | 1.91 | −1.19 |
| Hit rate | 54% | 69% | 39% |
| Financing per trade | −6.6 | +1.0 | −14.1 |

**The cited statistic does not replicate.** After the 88 compressions of ≥15bp, USDJPY fell over
the next five days only 41% of the time, and rose 0.08% on average (median +0.46%).

**Results hinge on a few trades.** Per-trade standard deviation is 204 pips against a mean of 7.
The five largest trades by size contribute 674 of the 1,253 total pips; without them the mean is
+3.4, t 0.24. The single biggest winner was a short on 2024-07-29 at 154.15, closed at 09:00 JST
on 2024-08-05 in the carry unwind, +833 pips.

## 3. Costs of the long trades

Average per V2 long trade (87 trades, about 8 calendar days held, average price 121.8):

| Item | Pips |
|---|---|
| USDJPY mid move | +38.08 |
| Spread (buy ask, sell bid) | −0.37 |
| Commission (IBKR $2 minimum per side on $100k) | −0.49 |
| Slippage (0.1 per side) | −0.20 |
| Carry earned (US–Japan short-rate gap, 2.13% on average) | +6.38 |
| IBKR financing skim (2% a year) | −5.37 |
| **Net** | **+38.03** |

| Period | Trades | Rate gap | Financing net | Trading costs |
|---|---|---|---|---|
| 2007–2014 | 30 | 1.38% | −1.64 | −0.97 |
| 2015–2021 | 12 | 0.83% | −2.60 | −1.01 |
| 2022–2024 | 45 | 2.99% | +3.73 | −1.12 |

Carry only beats the skim when the short-rate gap is above about 2%. Shorts pay the carry on
top of the skim, which is where their −14.1 pips of financing comes from, so part of the
long/short gap is a cost effect rather than better prediction on one side. Pessimistic costs
(0.3 slippage per side, 2.5% skim) take about 1.8 more pips per trade. Before mid-2024 the ask is
synthetic (bid plus a typical 2024–26 Eightcap spread, ~0.33 pips at 09:00 JST), so true
historical spreads were probably wider, though not by enough to matter next to ±200-pip trades.

## 4. Why the long side is not evidence yet

1. **The range of plausible results includes zero.** Mean +38.0, Newey–West standard error 19.9:
   95% interval −1 to +77 pips per trade.
2. **The profit sits in one trending period.**

   | Period | Long trades | Mean mid move | Average 5-day move on any day |
   |---|---|---|---|
   | 2007–2014 | 30 | −4.9 | +0.2 |
   | 2015–2021 | 12 | +69.8 | −1.0 |
   | 2022–2024 | 45 | +58.3 | +29.3 |

   Nothing in the first eight years. Over half the trades are in 2022–24, when USDJPY rose about
   29 pips every five days regardless of signal, so roughly half that period's gain is drift.
   2015–21 has only 12 trades.
3. **It was found by splitting results after seeing them.** "Long only" is a fourth variant chosen
   in hindsight. Its t of 1.91 is below even spec 001's bar, and well below the survey's 3.0.
4. **Even if real, it is thin.** About 5 trades a year; worst trade −624 pips; worst drawdown
   −1,162 pips against +3,309 total over 18 years. Per-year return-to-risk about 0.42 before the
   survey's backtest-to-live haircut (median −73%), so about 0.1 after it.

## 5. Data notes

- Decision days without a quote within 5 minutes are skipped, not filled: 35–128 a year in
  2007–2014 (gaps in the Dukascopy mirror).
- **HistData 2023 is incomplete.** February to July is missing up to ~60% of minutes between 08:00
  and 24:00 UTC, contrary to `docs/DATA.md`, which calls the file complete. H3 lost 62 decision
  days in 2023. Spec 001's 1a rule enters at 23:00 UTC and also loses some 2023 days.
- FRED `DGS2` and `DFF` came from `scripts/fetch_official.py` (`data/official/fred_daily.csv`).
  US yields are stamped as published at 18:00 New York time, JGB yields at 18:00 JST; tests in
  `tests/test_h3.py` check that no value is used before it was public.

## 6. Open items

- **Run spec 003 as written.** It is the proper test of whether the spread change predicts
  returns at all. Do not adjust it in light of this file.
- **If the V2 long side is pursued**, write a new spec ("long USDJPY after a ≥15bp widening, hold
  5 days") and test it on data it has never touched. Pre-2007 is the clean option: `DGS2` runs
  from 1976, the MOF JGB file from 1974, and `fetch_official.py --histdata` fetches HistData 1-min
  from 2000. The 2025+ holdout would give only about 10 trades and spend the holdout.
- Fix the 2023 completeness claim in `docs/DATA.md`.
- Deflated Sharpe ratio and probability of backtest overfitting were not computed; any variant
  that later passes needs both (`stats.deflated_sharpe`).
