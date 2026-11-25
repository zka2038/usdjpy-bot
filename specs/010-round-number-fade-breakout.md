# Spec 010: Round-number fade and breakout vs placebo levels

**Author:** Haru · **Date:** 2026-11-24 · **Status:** idea

## Hypothesis
Dealers hold clients' conditional orders. Take-profits cluster *at* round numbers and stop-losses
*just beyond* them. When price reaches a figure, the dealer has to fill the take-profits, which brakes
the move and produces more reversals. When price crosses it, the stops trigger as market orders,
pushing price further. The flow is price-contingent and non-informative, and the dealer is obliged to
execute it.

## Evidence
- Osler ([J. Finance 2003](https://ideas.repec.org/a/bla/jfinan/v58y2003i5p1791-1819.html); NY Fed SR125):
  ~9,700 stop-loss and take-profit orders at one bank, Sep 1999 – Apr 2000, incl. USDJPY. About 10% of
  conditional orders sit at rates ending in 00. Executed take-profits cluster at 00 (9.9% vs 3.8% for
  stops, value-weighted), and stop-loss buys cluster just above figures (14.3% in [01,10] vs 6.9% in [90,99]).
- Osler ([NY Fed SR150](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr150.pdf)),
  minute Reuters quotes, Jan 1996 – Apr 1998, NY hours 09:00–16:00, vs 10,000 bootstrap sets of
  arbitrary levels:
  - **Reversal:** USDJPY reverses at 00/50 levels **60.1% of the time vs 57.3%** at arbitrary levels.
    Significant for < 30 min, stronger in the NY afternoon, robust to excluding intervention months.
  - **Continuation:** after a crossing, the 15-min move is 6.89 vs 5.98 (hundredths of a %); USDJPY moves
    **1.3bp further** after crossing than after reversing. The two-hour significance is printed as both
    0.017 and 0.145 (internal inconsistency).
- Weaknesses: in-sample data that predates algorithmic liquidity provision; no post-2005 replication
  found; edges are ~1–2× the 1.1-pip cost. Treated as **confirmatory** (levels and windows come from
  Osler), so t ≥ 2, but the trade parameters (offsets, stops, targets) are the report's design.

## Rules (exact, no discretion)
- Levels L: every XXX.00 and every XXX.50, tested **separately**. Placebo: 1,000 sets, each a uniform
  random offset o ∈ [0.10, 0.40] applied as XXX.00 + o and XXX.50 + o (never within 10 pips of a
  figure or half-figure).
- Arming: a level is armed after mid has been ≥ 15 pips away from it; the first approach after arming
  is the only one traded.
- Fade: on the first approach within 1.5 pips of L from below, place a sell limit at L − 1 pip; stop
  L + 5 pips; target 5 pips below entry; time stop 30 min. Mirror from above (buy limit L + 1, stop
  L − 5).
- Breakout: from below, buy stop-entry at L + 2 pips; stop at L − 3 pips; exit after 60 min (variant
  B60) or 120 min (B120). Mirror from above.
- Hours: 09:00–02:00 JST (00:00–17:00 UTC). Subset reported separately: NY afternoon 12:00–16:00 ET
  (17:00–21:00 / 16:00–20:00 UTC; 02:00–06:00 / 01:00–05:00 JST).
- Filters / skip conditions: no entries ±15 min around 08:30, 10:00 and 14:00 ET, 08:50 JST
  (23:50 UTC) and 09:55 JST (00:55 UTC); none on BoJ decision days 11:00–16:00 JST; none on MOF
  intervention days.
- Fills: a limit fills only if the bid (sell) or ask (buy) trades through it by ≥ 1 tick.
- Size: USD 100k.
- Statistic: mean net pips at round levels **minus** the placebo distribution; bootstrap p = share of
  placebo sets with mean ≥ the round-level mean.

## Data needed
- `datasets.load_minute('histdata')` 2015–2024, extended to return bid high/low (the parquet has OHLC;
  the loader returns close only).
- `datasets.load_minute('eightcap')` and `datasets.load_ticks('YYYYMM')`, 2024-06 → 2024-12, to
  validate the bar-based fill model; `datasets.load_minute('dukascopy')` 2007–2014 as a robustness check.
- `datasets.fomc()`, `datasets.boj()`, `datasets.interventions()`. US release calendar (Tier 0c) to
  replace the fixed-time exclusion once built.

## Kill criteria (decided BEFORE testing)
Confirmatory, so t ≥ 2. Applied to each of fade-00, fade-50, breakout-00 and breakout-50. Reject that
rule if any of:
- Round-minus-placebo bootstrap p ≥ 0.05 (≈ t < 2);
- Mean net pips ≤ 0 under base costs, or ≤ 0 under `PESSIMISTIC`;
- Effect absent in 2022+ (events are plentiful, so the template criterion applies);
- Tick-validated P&L on 2024-06 → 2024-12 is < 50% of the bar-based P&L for the same trades. In that
  case the bar results are void, and the rule is retested with tick fills only.
If every standalone rule fails but the round-minus-placebo difference is significant, keep the result
as a **modifier** for other specs (no targets just beyond a figure, no stops just beyond one).

## Parameters
Approach band 1.5, arming distance 15, limit offset 1, fade stop 5 / target 5 / time 30 min, breakout
offset 2, stop 3, hold 60/120 min. All fixed in advance. Variants: B60, B120 and the NY-afternoon
subset (three).

## Implementation notes
Touch-triggered with stops and targets, so this needs a bar-loop simulator using bid/ask high/low. If
stop and target fall in the same bar, assume the stop filled first. `window_trades` does not fit.
Validate on Eightcap ticks before reading any number. This is a natural point to start the
NautilusTrader layer (README Layer 2).

## Results
_Pending._
