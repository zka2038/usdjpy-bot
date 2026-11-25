# Spec 017: Risk overlays for trend/carry (VIX, vol targeting, holidays, post-intervention, blackouts)

**Author:** Claude (research 2026-11-24) · **Date:** 2026-11-24 · **Status:** idea

## Hypothesis
Long USDJPY (spec 014 in the current regime) is short crash risk. Its losses come when the parties
that must trade are VaR-limited carry holders unwinding (VIX spikes), the MOF intervening (near 160,
often on Japanese holidays or Friday NY afternoons), or thin holiday liquidity. Cutting exposure when
those risks are high should shrink drawdowns more than returns. These overlays are **judged on
drawdown and tails, not on return**.

## Evidence
- Moreira & Muir (JF 2017): volatility-managed portfolios raise Sharpe in sample, including for FX
  carry (one NBER fragment suggests the carry alpha is specification-sensitive). Cederburg et al.
  (2020, via [arXiv 2603.03213](https://arxiv.org/pdf/2603.03213)): the gains "generally do not
  survive" real-time out-of-sample tests; the equity Sharpe gain shrinks to 0.488 vs 0.471. So the
  robust benefit is tail control.
- BNP (NBER w14473): carry crash risk rises with the VIX. Ranaldo & Söderlind: the yen rises when FX
  volatility jumps. FX vol is autocorrelated and forecastable (St. Louis Fed WP 2012-008).
- Holidays: no directional effect (yen up in 52.8% of 178 JP-holiday Tokyo sessions, 2007–2019; GW 11
  down / 9 up, 1999–2018; ZAi FX), but GW ranges average **2.15 yen**. There were yen-surge panics in
  four straight GWs 2008–2011 (Monex) and the 3 Jan 2019 flash crash had a 3.04-yen range.
- Intervention: T+0 averages −1.2% with a ~3.1% range, then no directional bias and contracting ranges
  over T+1…T+6 (FOREX.com, small sample, snippet figures). Interventions fell on a JP holiday
  (29 Apr 2024) and a Friday (31 Jul 2026). About eight yen-buying days fall inside the bar data.
- No yen-specific out-of-sample test of any of these overlays exists.

## Rules (exact, no discretion)
Base = spec 014 core (unfiltered) weights. O1–O4 multiply the **long** USDJPY weight only; each is
tested alone and then all together.
- **O1 VIX regime** (daily, applied at 16:50 ET; 21:50 / 20:50 UTC; 06:50 / 05:50 JST):
  - ×1 if VIX < 20 and below its 50-day MA; ×0.5 if 20 ≤ VIX < 30, or if VIX < 20 but above its 50-day MA;
  - ×0 if VIX ≥ 30 or VIX rose > 4 points that day. After ×0, stay flat until VIX has closed below its
    20-day MA for 5 consecutive days.
- **O2 Vol targeting:** replace 014's sizing with w = s × min(2, 8% / σ̂), where σ̂ is a HAR-RV
  forecast (5-min RV; daily/weekly/monthly lags; fitted on past data only). Alternative σ̂: EWMA
  λ = 0.94. Rebalance weekly (Mon 08:00 JST / Sun 23:00 UTC).
- **O3 Holidays/GW:** when spot > 158, ×0.5 from the last Tokyo close before a JP bank holiday
  (15:00 JST, 06:00 UTC) to the first post-holiday 09:00 JST (00:00 UTC). Level-free variant: ×0.5 over
  every JP holiday, which gives a larger sample.
- **O4 Post-intervention:** after any MOF yen-buying day T: no new directional entries (any spec)
  from T+1 to T+6 JP business days. Size any long above the last intervention-day high so that a 5%
  gap loses at most a pre-declared USD amount R.
- **O5 Intraday entry blackouts** (applies to specs 007, 010 and any passing intraday spec):
  - no new entries on BoJ decision days 11:00–16:00 JST (02:00–07:00 UTC);
  - none 08:25–08:45 ET on release days (13:25–13:45 / 12:25–12:45 UTC; 22:25–22:45 / 21:25–21:45 JST);
  - none 13:55–15:00 ET on FOMC days (18:55–20:00 / 17:55–19:00 UTC; 03:55–05:00 / 02:55–04:00 JST);
  - none 16:55–17:10 ET (rollover);
  - skip entries for 5 min when the spread z-score vs its minute-of-week median exceeds 3 (Eightcap/live only);
  - on JP holidays use 1.5× normal intraday stop distance (design choice; not from a source);
  - size intraday trades on T+0 of an intervention by min(1, ATR20 / T+0 range).
- Size: as base spec; overlays only scale down.

## Data needed
- In repo: VIX (`data/macro/vix_daily_1990_2026.csv`); `datasets.interventions()` (to 2026-08-03);
  `usdjpy.calendars.jp_bank_holidays`; `datasets.boj()`, `datasets.fomc()`; Eightcap bid/ask for spread z.
- O2 needs Tier 0b (HAR-RV from `datasets.load_minute('histdata')`). RV is reliable only from 2015
  (Dukascopy 2011–2018 is 40–65% complete), so O2 is testable 2016–2024.
- O5 needs the US release calendar (Tier 0c, **missing**). Spot > 158 occurs pre-holdout only in 2024,
  so O3/O4 have very few pre-holdout episodes.

## Kill criteria (decided BEFORE testing)
Applies to O1–O3, each vs base, separately in 2007–2015 and 2016–2024 (O2: 2016–2020 and 2021–2024).
An overlay is **rejected** unless, in both halves:
- Max drawdown falls by ≥ 20% (relative); **and**
- The worst-week loss or weekly CVaR(5%) improves; **and**
- Return / max drawdown does not fall.
Sharpe change is reported but does not decide (Cederburg caveat).
O4 and O5 are rare-event risk rules. They are adopted on prior unless they make the available
episodes *worse* (more loss in aggregate across the listed intervention/blackout episodes, reported one by one).

## Parameters
O1: 20/30 levels, 50/20-day MAs, +4-point jump, 5-day re-entry. O2: 8% target, cap 2, HAR lags 1/5/22.
O3: 158 level. O4: 6-day window, 5% gap, R. O5: window edges, z > 3, 1.5× stop. No tuning: these are
the report's values or stated design choices.

## Implementation notes
O1–O4 are weight multipliers in the spec 014 weekly/daily simulator, so they need daily (not only
weekly) adjustment for O1 and O3. O5 is an entry mask passed to the bar-loop simulators of specs
007/006. Build the HAR model once (Tier 0b) and reuse it for sizing everywhere.

## Results
_Pending._
