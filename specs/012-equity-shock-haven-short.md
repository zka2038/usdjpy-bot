# Spec 012: Equity-shock haven short

**Author:** Claude (research 2026-11-24) · **Date:** 2026-11-24 · **Status:** idea

## Hypothesis
After a sharp US equity sell-off with a jump in the VIX, risk limits (VaR, margin) force leveraged
holders of yen-funded carry to cut positions, which means buying back yen over the following days.
Haven demand adds to it. So USDJPY should fall over 1–3 days after the shock. The weakness is that
this property has been unstable since 2022, and it fails when Japan itself is the epicentre.

## Evidence
- Ranaldo & Söderlind ([Rev. Finance 2010](https://econpapers.repec.org/RePEc:oup:revfin:v:14:y:2010:i:3:p:385-407)),
  1993–2008: JPY appreciates when US stocks fall, bonds rally and FX vol rises, "from a few hours to
  several days". Non-linear and strongest in crises. This is co-movement, not prediction.
- Brunnermeier, Nagel & Pedersen (NBER w14473): carry crash risk rises with the VIX. BIS Bulletin 90:
  yen-funded carry was "the hardest hit" in Aug 2024 (~¥40trn estimated going in).
- Habib & Stracca (JIE 2012): what currencies do when risk aversion is high is "hard to predict",
  with estimates imprecise and unstable.
- Regime breaks: 2022, ING said the USDJPY–equity correlation fell from ~0.35 to zero; early Nov 2026,
  no haven bid while Japanese stocks fell almost 6% (ExchangeRates.org.uk); 20 Nov 2026, a haven bid
  that reversed on Monday's Nvidia-led rally (TMGM).
- No yen-specific out-of-sample test of a VIX-conditioned rule. ≈30–60 events in 2007–2026.
  **Exploratory.**

## Rules (exact, no discretion)
- Days: trigger day T = US business day with S&P 500 close-to-close return < −2% **and** VIX close
  > 1.25 × its 20-day mean (both known by 16:50 ET).
- Entry: **short at 16:50 ET on T** (21:50 / 20:50 UTC, EST/EDT; 06:50 / 05:50 JST on T+1), market order.
- Exit (three variants): (A) 16:50 ET on T+1; (B) 16:50 ET on T+3 (US business days); (C) as B, plus a
  stop at 1 × ATR(20) of daily USDJPY ranges, checked on 1-min bars. A and B have no stop; record MAE.
- Filters / skip conditions: skip if T or T+1 is a MOF intervention day; no new trade while one is
  open (overlapping triggers are not stacked).
- Splits (reported, not used to select): Nikkei 225 return on Tokyo date T < −4% vs not; regimes
  2007–12, 2013–21, 2022–24.
- Size: USD 100k. Short USDJPY pays carry on every 17:00 ET roll (roughly 1.5–2 pips/night at an
  assumed 4% differential; use measured IBKR rates).

## Data needed
- **Scriptable:** S&P 500 closes via `scripts/fetch_official.py` → `data/official/fred_daily.csv`
  (SP500). FRED's SP500 history may be shorter than 2007–2026; check coverage and fill gaps from a
  free index-close source (e.g. Stooq) if needed.
- In repo: VIX in `data/macro/vix_daily_1990_2026.csv` / `datasets.macro_daily()` (VIXCLS); NIKKEI225
  in `datasets.macro_daily()`; `datasets.interventions()`.
- Bars: `datasets.load_minute('dukascopy')` 2007–2014 (gappy, so require both quotes),
  `datasets.load_minute('histdata')` 2015–2024.

## Kill criteria (decided BEFORE testing)
Exploratory, so t ≥ 3, with the trade list reported in full. Primary statistic: exit B, 2007–2024.
Reject if any of:
- Mean net pips (after financing) ≤ 0 under base costs, or t < 3;
- Sign differs between 2007–2014 and 2015–2024;
- Mean net ≤ 0 under `PESSIMISTIC`;
- Result is driven by one regime: mean ≤ 0 in two of the three regime buckets.
With this few events t ≥ 3 is unlikely. If the sign is consistent but t < 3, demote the rule to a
**risk input** for spec 017 (cut long exposure after such days) rather than a trade.

## Parameters
−2% S&P threshold, 1.25 × 20-day VIX ratio, entry 16:50 ET, holds 1/3 days, ATR(20) stop. Three
variants: A, B, C. No tuning of thresholds.

## Implementation notes
Exit A fits `window_trades(bars, trigger_days, "16:50", "16:50", -1, tz="America/New_York")` (exit ≤
entry rolls to the next day). B needs the multi-day timestamp helper from spec 002. C needs a bar loop
for the stop. All three need the financing term that `costs.py` lacks.

## Results
_Pending._
