# Spec 011: US Treasury auction cycle

**Author:** Haru · **Date:** 2026-11-24 · **Status:** idea

## Hypothesis
Primary dealers have to bid at every Treasury auction, and investors who plan to buy want a
concession. Both sell duration ahead of the 13:00 ET bid deadline, so yields rise into the auction and
fall back afterwards as that hedging unwinds. USDJPY co-moves with US yields, so it should drift up
before the deadline and down after it. The mechanism is documented. The question is whether the yen
leg is bigger than costs.

## Evidence
- NY Fed SR1188 ([PDF](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr1188.pdf)),
  Jun 1991 – Jul 2024, on-the-run 2/3/5/7/10/30y: yields rise **0.36–0.63bp over the 180 min before**
  the 13:00 ET close, then fall **0.32–0.75bp over the 180 min after**. Strongest in 2007–2014
  (0.9–1.7bp); since 2015 **less than half** that size.
- Krohn ([BoC SWP 2025-29](https://www.bankofcanada.ca/2025/11/staff-working-paper-2025-29/)): a 1-s.d.
  rise in auction demand depreciates the USD by ~2bp vs the G9, JPY included, and the effect persists.
- Somogyi et al. (FRBSF): the secular decline in US and G10 long yields is concentrated in auction
  windows (~22% of the sample).
- No study measures USDJPY around auctions. Translated through USDJPY's yield beta, the expected move
  is low single-digit pips, about the cost bar. Expect a null. It is worth running because ≈240
  events in 2015–2024 give a fast answer. **Confirmatory** (windows come from SR1188), so t ≥ 2.

## Rules (exact, no discretion)
- Days: 10y and 30y coupon auction days (including reopenings), plus refunding-week 3y auctions (Feb,
  May, Aug, Nov). Control: other US business days, excluding FOMC decision days and auction days.
- Leg 1 (pre-auction): **long 10:00 → 12:58 ET**. UTC 15:00–17:58 (EST) / 14:00–16:58 (EDT); JST
  00:00–02:58 / 23:00–01:58.
- Leg 2 (post-auction): **short 13:01 → 16:00 ET**. UTC 18:01–21:00 / 17:01–20:00; JST 03:01–06:00 /
  02:01–05:00.
- Stop: none (fixed windows).
- Filters / skip conditions: skip FOMC decision days (14:00 ET statement falls in leg 2); skip MOF
  intervention days.
- Size: USD 100k.
- Diagnostic: estimate USDJPY's daily beta to ΔDGS10 on 2015–2024 to translate SR1188's bp into pips.

## Data needed
- **Missing:** `data/calendars/ust_auctions.csv` (auction date, term, reopening flag) from TreasuryDirect
  historical auction data (free). When-issued yields, needed for a "tail" variant, are paid and are
  out of scope. This is Tier 0c.
- `datasets.load_minute('histdata')` 2015–2024; `datasets.load_minute('eightcap')` 2024-06 → 2024-12
  for real spreads at 10:00 and 16:00 ET; `datasets.fomc()`; `datasets.macro_daily()` (DGS10).

## Kill criteria (decided BEFORE testing)
Confirmatory, so t ≥ 2. Applied per leg. Reject that leg if any of:
- Auction-minus-control `events.compare` difference t < 2, or of the wrong sign;
- Mean net pips ≤ 0 under base costs, or ≤ 0 under `PESSIMISTIC`;
- Effect absent in 2022+ (≈70 events, so the template criterion applies).
A clean null closes the idea. Record it in the ledger and do not iterate on auction subsets.

## Parameters
Windows fixed by SR1188. Variants (three): (1) 10y + 30y only, (2) adding refunding-week 3y,
(3) legs 1 and 2 chained as one round trip (reverse at 13:01 ET).

## Implementation notes
`window_trades` fits directly, with `tz="America/New_York"`: `window_trades(bars, auction_days,
"10:00", "12:58", +1)` and `("13:01", "16:00", -1)`, the same on control days, then `events.compare`.
DST is handled by the tz argument.

## Results
_Pending._
