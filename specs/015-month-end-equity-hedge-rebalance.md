# Spec 015: Month-end London-fix equity-hedge rebalancing

**Author:** Claude (research 2026-11-24) · **Date:** 2026-11-24 · **Status:** idea

## Hypothesis
Funds that hedge the currency risk of foreign equity holdings reset their hedges at the month-end
London 4pm fix. If Japanese equities (in USD) outperformed during the month, foreign holders of Japanese
stocks are now under-hedged and must **sell JPY** in the hour before the fix (USDJPY up). If US equities
outperformed, the flow runs the other way. The flow is mandated by benchmark hedge ratios and happens
at a known time. For the yen the net sign is ambiguous: Japanese investors hedging *foreign* assets
trade in the opposite direction.

## Evidence
- Melvin & Prins (J. Financial Markets 22, 2015; [EconPapers](https://econpapers.repec.org/RePEc:eee:finmar:v:22:y:2015:i:c:p:50-72)),
  ten G10 currencies, Apr 2004 – Dec 2012 (in-sample): a 10% month-to-date equity outperformance
  predicts **~14bp of that currency's depreciation from 15:00 to 16:00 London on the last trading day**
  (coefficient 0.0142, R² 0.03). Equity return measured from day 1 to the second-to-last day. No
  trading P&L reported.
- JPY detail: non-bank month-end JPY flow is 1.87× normal (1% level), but the **JPY interaction term is
  insignificant (p = 0.17)**, plausibly because the two hedger groups offset.
- Evans (MPRA 81583, 2004–2013): pre-fix 1-min moves beyond the 95th percentile on ~62% of JPY/USD
  month-ends, yet a JPY/USD fix-*reversal* strategy lost money after costs at every horizon. That
  result concerns fading the fix, a different trade.
- The Feb 2015 reform widened the fix to 5 minutes, and the FCA found reversals insignificant after it
  (USDJPY not in sample). BIS Bulletin 123: hedge ratios shift by regime (equity funds raised USD hedge
  ratios after Apr 2025), which can change the sign.
- 12 events a year, so expect years of data. The earlier report's verdict: "a small side test".

## Rules (exact, no discretion)
- Days: last UK business day of each month (`usdjpy.calendars.last_business_days(..., "UK")`).
- Signal: D = MTD return of Nikkei 225 in USD (NIKKEI225 / USDJPY) − MTD S&P 500 return, both from the
  last close of the previous month to the close of the **second-to-last** business day.
- Entry: if D > +3% go **long** USDJPY; if D < −3% go **short**; at **15:00 London**: GMT months
  15:00 UTC / 00:00 JST (next day); BST months 14:00 UTC / 23:00 JST. Market order.
- Exit: 16:00 London (16:00 / 15:00 UTC; 01:00 / 00:00 JST). UK DST (last Sunday Mar → last Sunday Oct)
  is what matters here, not US DST.
- Stop: none (one-hour window).
- Filters / skip conditions: skip if the day is a MOF intervention day.
- Size: USD 100k.
- Primary statistical test (no threshold): regress the 15:00→16:00 London mid return on D across
  **all** month-ends. Placebo: the same regression on the 5 business days before each month-end.

## Data needed
- **Scriptable:** S&P 500 (FRED SP500 via `scripts/fetch_official.py`; check history length, which may
  need a free alternative source for pre-2016 closes).
- In repo: NIKKEI225 and DEXJPUS in `datasets.macro_daily()` (to 2026-06). TOPIX, used in the earlier
  report, is **missing**; Nikkei 225 is a price-weighted proxy (TOPIX daily is free from JPX/Stooq if
  wanted as a robustness check).
- Bars: `datasets.load_minute('dukascopy')` 2007–2014 (gappy), `datasets.load_minute('histdata')`
  2015–2024.

## Kill criteria (decided BEFORE testing)
Predicted sign is positive (Japan outperforming → USDJPY up). Reject if any of:
- All-month-end regression slope has the wrong sign or t < 2 over 2007–2024 (confirmatory:
  mechanism and window from Melvin & Prins);
- Slope does not exceed the placebo-day slope (difference t < 2);
- The ±3% trading rule has mean net pips ≤ 0 under base costs or under `PESSIMISTIC`, 2015–2024;
- The trading rule's sign differs between 2015–2019 and 2020–2024 (rare-event variant).
Report 2007–2012 (Melvin–Prins sample) separately from 2013–2024 (post-publication).

## Parameters
Threshold 3%, window 15:00–16:00 London. Variants (three): (A) 3%, exit 16:00; (B) 3%, exit 15:57
London, before the post-2015 5-minute fixing window; (C) 5% threshold, exit 16:00.

## Implementation notes
`window_trades` fits: `window_trades(bars, long_days, "15:00", "16:00", +1, tz="Europe/London")` and
the same for short days. `quote_at` fills the 16:00 exit from the last bar ending by 16:00 (the 15:59
bar), which sits inside the post-2015 fixing window. Variant B avoids it. The regression is a few lines
of pandas on `mid_pips`.

## Results
_Pending._
