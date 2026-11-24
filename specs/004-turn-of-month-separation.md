# Spec 004: turn-of-month separation

**Author:** bzk · **Date:** 2026-11-24 · **Status:** testing

**This spec exists to resolve a confound in spec 001, not to find a new effect.**
Read §5 of `Research/Strategy/Hypothesis Review H1 to H3.md` first.

## Hypothesis

`calendars.gotobi_days()` returns the 5th, 10th, 15th, 20th, 25th **and the last
business day of the month** (月末). Spec 001's treatment group therefore bundles two
distinct mechanisms:

- **Gotobi proper:** Japanese corporates settle trade invoices on multiples of 5,
  generating importer USD demand into the Tokyo 09:55 fix.
- **Month-end:** a different and larger set of forced flows — fund NAV
  rebalancing, index tracking, custodian hedge resets, corporate book-closing —
  concentrated on the last business day.

The published fix-spike frequencies say the one that is *not* Gotobi is the
stronger:

```
relative spike frequency, Tokyo 09:55 JST fix
  month-end  0.538
  Friday     0.301
  5th/10th   0.276
  all days   0.247
```

So if spec 001 shows an effect, it cannot be attributed to the importer-settlement
mechanism it claims. **H0 for this spec: the effect in spec 001's treatment group is
the same on Gotobi-excluding-month-end days as on month-end days.** Rejecting it
means spec 001's stated mechanism is wrong even if its numbers are right.

Direction: month-end shows a larger effect than Gotobi-excluding-month-end, and
the latter may be indistinguishable from ordinary business days.

## Evidence

- Ito & Yamada (NBER WP 22820), EBS tick 2006–2013 plus bank fixing rates
  1999–2013: the spike frequencies above; Tokyo 09:55 spike dummy t = 42.5 versus
  **−1.01 (t = −27.8) for the London fix in USDJPY** — in this pair Tokyo is the
  dominant fixing event, not London.
- Same source, decay: BTMU fixing max-gap +2.47bp before November 2008 → **−0.79bp
  after**; spike frequency 0.643 (2008) → 0.121 (2013). Any effect found should be
  checked for being a pre-2008 artefact.
- Ito & Yamada (NBER WP 23327): a pre-reform end-of-month fix reversal strategy was
  profitable **including in USDJPY**, and strengthened post-reform at the 15-minute
  horizon, while intra-month trading was unprofitable in both periods. This is the
  closest thing to a direct prior, and it points at month-end rather than Gotobi.
- The gross size in the original Gotobi work is ~**1.8bp over fifteen years**,
  described as "slightly above bid-ask cost", with no t-statistic reported. Do not
  expect a large effect.
- **H2a (fiscal year-end, 31 March) is NOT specced**: n = 20 in 20 years gives an
  MDE of 198 pips, which would be an effect visible to every participant in the
  market. Dead on arrival, recorded so it is not revisited.

## Rules (exact, no discretion)

Three mutually exclusive date groups, all on Japanese business days:

- **A — month-end:** last business day of the month (`calendars.gotobi_days` minus
  the multiples-of-5 set; equivalently a month-end helper)
- **B — Gotobi proper:** 5th/10th/15th/20th/25th rolled back, **excluding** any that
  is also the last business day of the month
- **C — control:** `jp_business_days` minus A minus B

Windows, both taken unchanged from spec 001 so the comparison is apples-to-apples:

| Rule | Side | Entry (JST) | Exit (JST) | Entry (GMT) | Exit (GMT) |
|---|---|---|---|---|---|
| prefix | long | 08:00 | 09:55 | 23:00 | 00:55 |
| postfix | short | 09:55 | 11:00 | 00:55 | 02:00 |

- Order type: market at the stated minute, via `events.window_trades`
- Stop: none (window trades, held minutes)
- Filters: `events.quote_at` staleness tolerance; skip Japanese bank holidays
  (handled by `calendars`); `allow_holdout=False`
- Size: ≥ USD 100k notional

**Test.** For each rule, run A, B and C through `events.window_trades`, then:
- `events.summarize` on `net_pips` under `CostModel()` and `PESSIMISTIC`
- `events.compare(A, C)` and `events.compare(B, C)` on `mid_pips`
- **`events.compare(A, B)` — this is the actual test of the spec**
- `stats.clustered_t` is **not** needed: A and B dates are separated by construction
- Report `stats.min_detectable_pips` next to every null

## Data needed

USDJPY 1-min bid/ask via `usdjpy.dukascopy` from `DATA_DIR` — the same data spec 001
already uses. **No new data required**, which is why this is the cheaper of the two
live specs.

## Kill criteria (decided BEFORE testing)

1. Mean net pips ≤ 0 under base costs on pre-holdout data for every group, or
2. `|t| < 2.5` on the A-versus-B comparison (two rules × one comparison, plus the
   A/C and B/C checks: ~6 tests, so the threshold is raised from 2), or
3. Effect present pre-2008 and absent in `2015-2021` and `2022+` (`events.PERIODS`)
   — i.e. it decayed with the fix reforms, or
4. Fails under `PESSIMISTIC` costs, or
5. **Tradeability bar, separate from significance:** net pips per trade below
   `PESSIMISTIC` all-in cost (~1.84 pips at 159) does not proceed to Layer 2, even
   if significant.

## Parameters

Zero new. Entry and exit times are inherited unchanged from spec 001 precisely so
that no tuning enters through this spec. The only new thing is the date partition,
which is calendar-determined rather than chosen.

## Power

20 years pre-holdout, 3-day window equivalent, sd of the window move 173 pips:

| Group | Obs/yr | n (20y) | MDE at 80% |
|---|---|---|---|
| A month-end | 12 | 240 | 31 pips |
| B Gotobi proper | ~48 | ~960 | 16 pips |
| A vs B difference | — | — | ~35 pips |

Well-powered against the published effect sizes, which is the opposite of H1's
position. The risk here is not low power but multiple testing across calendar
patterns — a minimal grid on one pair is 50–60 near-independent tests, which
expects 2–3 nominal 5% hits by chance. Hence the raised threshold and the fixed,
inherited windows.

## Outcome to expect

The most likely result is that **both** A and B are indistinguishable from C on
post-2008 data, because the fix-pricing behaviour that generated the original
effect decayed after November 2008 and again after the February 2015 reform. If so,
spec 001 should be re-run on the A/B partition and its conclusion restated: the
mechanism it names is not separable from a stronger one it does not name, and
neither survives in current data.

That is a useful result. It retires a family rather than a parameter.

## Results

<to be filled in: link to `results/`, the A/B/C summary tables, the three
comparisons, MDE alongside each null, and the decision>
