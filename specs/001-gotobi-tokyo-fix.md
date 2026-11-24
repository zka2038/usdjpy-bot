# Spec 001: Gotobi / Tokyo 9:55 JST fix

**Author:** Haru · **Date:** 2026-11-24 · **Status:** testing

## Hypothesis
Japanese importers buy USD at the Tokyo bank fix (9:55 JST), and this demand is concentrated on
gotobi days (5th/10th/15th/20th/25th/month-end, rolled back to the previous business day). Banks
pre-hedge, so USDJPY tends to drift up into 9:55 and partly reverse afterwards.

## Evidence
- Ito & Yamada (NBER 2016 / J. Int. Econ. 2017, 1999–2013): predictable USD-buying imbalance at the
  fix, stronger on gotobi/month-end; long 5 min before / short 5 min after ≈ 1.8 bp/day, "slightly above" costs.
- Krohn, Mueller & Whelan (J. Finance 2024, 1999–2019): USDJPY has the largest post-Tokyo-fix
  reversal of 9 currencies; unprofitable at full quoted spread; weaker after 2014.
- Bessho, Sugimoto & Suzuki (arXiv 2023, 2018–2020): in-sample profit factors 1.5–2.6 on gotobi days.
- No published results for 2021–2026.

## Rules
- Days: gotobi days (`usdjpy.calendars.gotobi_days`). Control: other JP business days.
- 1a: long 08:00 JST (23:00 GMT prev. day) → exit 09:55 JST (00:55 GMT). Market orders.
- 1b: short 09:55 JST → exit 11:00 JST (02:00 GMT). Market orders.
- Size: USD 100k.

## Data needed
Dukascopy USDJPY ticks, 2010 onwards.

## Kill criteria
As in TEMPLATE. Additionally: gotobi must beat control days (Welch t-test p < 0.05) — otherwise
it's generic time-of-day drift, not the gotobi flow.

## Parameters
Entry time, exit time. Do NOT grid-search them on the full sample; if testing alternatives,
pre-declare at most 3 variants.

## Results
_Pending._ Run `python scripts/gotobi_study.py`.
