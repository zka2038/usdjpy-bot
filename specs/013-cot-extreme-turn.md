# Spec 013: CFTC leveraged-fund extreme + turn

**Author:** Haru · **Date:** 2026-11-24 · **Status:** idea

## Hypothesis
Leveraged funds (hedge funds, CTAs) build crowded yen shorts through carry and trend trades. Once a
record short starts to cover, stop-losses and VaR limits force further covering, and that unwind fuels
a yen rally. The signal is the *turn* from an extreme, not the extreme itself, because extremes can
persist for months. The mirror case applies to record yen longs.

## Evidence
- Brunnermeier, Nagel & Pedersen (NBER w14473): larger speculative carry positions predict more
  negative future skewness (crash risk). Moskowitz, Ooi & Pedersen: speculators follow 12-month trends.
- Practitioner episodes: "yen shorts built ahead of yen surge" (Forex.com); in the week to 8 Sep 2026
  speculators bought a net 103,000 JPY contracts and flipped net long as the yen rose 4.2% (Saxo);
  investors "were heavily short on the yen" before the Aug 2026 coordinated intervention (Russell).
- The CFTC TFF report (from Jul 2010) separates Leveraged Funds from Asset Managers. Positions are as
  of Tuesday and released Friday 15:30 ET.
- **No out-of-sample test of any JPY TFF rule exists.** The rule fires fewer than 15 times since 2010,
  so report it trade by trade. **Exploratory**, with no tuning.

## Rules (exact, no discretion)
- Days: weekly. LF_net = (LF long − LF short) / OI for CME JPY futures. Check the CSV column definitions:
  futures are quoted JPY/USD, so LF long = long yen.
- Percentile p = rank of the current LF_net within the previous 156 weekly reports (past only; first
  signal possible from 2013).
- Short-USDJPY signal: p ≤ 5th percentile in any of the last 4 reports **and** the latest weekly
  ΔLF_net ≥ +0.015 (shorts covering, +1.5% of OI). Mirror (long USDJPY): p ≥ 95th within 4 reports and
  ΔLF_net ≤ −0.015.
- Entry: at **Mon 08:00 JST (Sun 23:00 UTC)** after the Friday 15:30 ET release (20:30 / 19:30 UTC,
  EST/EDT; Sat 05:30 / 04:30 JST), market order. Use `available_from`.
- Exit: Mon 08:00 JST 28 days after entry; stop at 2 × ATR(20) (daily ranges) from entry, checked on
  1-min bars.
- Filters / skip conditions: one position at a time; no entry in T+1…T+6 after a MOF intervention
  (spec 017 rule).
- Size: USD 100k. Short USDJPY pays ~28 nights of carry (roughly 40–55 pips at the report's assumed
  1.5–2 pips/night), which is material here. Model it.

## Data needed
- In repo: `datasets.cot('tff')` (data/positioning/cot_jpy_tff_weekly.csv, 2010-01 → 2026-11-17, with
  `available_from`). Verify against the official CFTC zips from `scripts/fetch_official.py`. Holiday and
  shutdown release delays shift `available_from`; check against the CFTC schedule.
- Bars: `datasets.load_minute('histdata')` 2015–2024, `datasets.load_minute('dukascopy')` 2013–2014
  (gappy); `datasets.interventions()`.

## Kill criteria (decided BEFORE testing)
A t-stat is meaningless at fewer than 15 trades, so these pre-declared criteria replace it. Reject if any of:
- Mean net pips (after financing) ≤ 0 under base costs or under `PESSIMISTIC`;
- Fewer than 2/3 of trades are profitable;
- The result does not beat a placebo: the mean must exceed the 95th percentile of 1,000 runs with
  signal dates shifted randomly (same count, same hold, 2013–2024);
- Mean has a different sign in 2013–2018 and 2019–2024.
Even a pass makes this an **overlay input** for spec 017/014 (cut long exposure after a covering
turn), not a standalone strategy, unless the holdout adds trades of the same sign.

## Parameters
156-week window, 5th/95th percentiles, 4-week look-back, ±1.5% OI change, 28-day hold, 2 × ATR stop.
None tuned. Variants: none. If run, the legacy non-commercial net is a robustness check only.

## Implementation notes
Multi-week hold with a stop, so this needs the timestamp-based helper plus a bar loop for the stop and
nightly financing. `window_trades` does not fit. It is cheap: fewer than 15 trades.

## Results
_Pending._
