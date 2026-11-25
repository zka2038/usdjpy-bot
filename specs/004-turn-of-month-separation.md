# Spec 004: turn-of-month separation

**Author:** bzk · **Date:** 2026-11-24 · **Status:** undecidable (declared test unanswerable; effect below its own MDE; numbers pending re-run)

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

**Corrected.** An earlier draft of this section computed the MDE on a 3-day window
and concluded the spec was well-powered. The inherited windows are 115 and 65
*minutes*. On the correct scaling the headline test is underpowered.

Window standard deviations, √time from a 100-pip daily sd (a floor, since the
Tokyo morning is an active session):

| Window | Minutes | sd |
|---|---|---|
| prefix 08:00–09:55 JST | 115 | 28.3 pips |
| postfix 09:55–11:00 JST | 65 | 21.3 pips |

Published Gotobi effect: ~1.8bp of notional = **2.86 pips** at 159.

MDE at 80% power, 15 years pre-holdout, on the 115-minute window:

| Group | n | MDE | vs the 2.86-pip effect |
|---|---|---|---|
| B Gotobi proper | 895 | 2.65 pips | 0.9× — **marginally powered** |
| A month-end | 180 | 5.91 pips | 2.1× too insensitive |
| **A vs B (the spec 004 test)** | — | **6.47 pips** | **2.3× too insensitive** |

So B alone can just about see the published effect, while **the A-versus-B
separation cannot.** A null on the A/B comparison is therefore weak evidence that
the two mechanisms behave alike — not evidence that they do. Record the realised
MDE from the trade standard deviations alongside every comparison; the script does
this, and the runtime numbers supersede these √time estimates.

What this does *not* undermine: the A/C and B/C comparisons, where n is larger and
the question is whether either group differs from ordinary days at all. If both
are null against C, the separation question is moot.

Multiple testing remains the second risk — a minimal calendar grid on one pair is
50–60 near-independent tests, expecting 2–3 nominal 5% hits by chance. Hence the
raised threshold and the windows inherited unchanged from spec 001.

### Scale of the confound, quantified

Month-end is **17% of spec 001's treatment group** (180 of 1,075 days over
2010–2024). Weighting by the published spike-frequency ratio (0.538/0.276 = 1.95)
puts month-end at roughly **28% of spec 001's measured effect while being 17% of
its days**. That is enough to break attribution to the importer-settlement
mechanism; it is not enough to say spec 001 is "really" a month-end result. State
it at that strength and no stronger.

## Outcome to expect

The most likely result is that **both** A and B are indistinguishable from C on
post-2008 data, because the fix-pricing behaviour that generated the original
effect decayed after November 2008 and again after the February 2015 reform. If so,
spec 001 should be re-run on the A/B partition and its conclusion restated: the
mechanism it names is not separable from a stronger one it does not name, and
neither survives in current data.

That is a useful result. It retires a family rather than a parameter.

## Results

Run 2026-11-25 on `datasets.load_minute("combined")`, 2007-01-31 to 2024-12-30
(pre-holdout), after the execution-hour fix to `_with_synthetic_ask`. Day counts:
A 234, B 1159, C 3357, A/B overlap 0. Month-end is 234 of spec 001's 1393
treatment days = **17%**.

### The clean test — mid_pips, no cost assumption

| Test | prefix_long | postfix_short | MDE | verdict |
|---|---|---|---|---|
| A vs C | −0.23 (t −0.13) | +1.87 (t +1.09) | 4.8–4.9p | null, **uninformative** |
| **B vs C** | **+2.275 (t +3.04)** | **+1.513 (t +2.62)** | 2.09 / 1.61p | **DIFFERENT** |
| A vs B | −2.50 (t −1.37) | +0.36 (t +0.20) | 5.1 / 4.9p | null, **uninformative** |

**The hypothesis is refuted, and in the opposite direction.** This spec predicted
month-end would dominate and Gotobi-proper would be indistinguishable from
control. The data says Gotobi-proper differs from control in both rules, same
sign, with MDE **below** the published 2.86-pip effect — an informative positive.
Month-end shows nothing, but at MDE 1.7× the effect we cannot *see* it, which is
not the same as it contributing nothing.

**So spec 001's stated mechanism survives.** The effect lives in importer
settlement days, not month-end rebalancing. Its conclusion was not a month-end
artefact.

**The separation test itself fails on power**, exactly as this spec's corrected
power section predicted (MDE 1.8× the effect). Kill criterion 2 is therefore not
decisive either way: we did not reject A=B, and we could not have.

That reasoning stands, but the status line drawn from it did not. This spec was
marked "passed" on the strength of B-vs-C, which is not the comparison it
nominated as its test — line 85 names `compare(A, B)`. B-vs-C restates spec 001's
own claim on a subset of its days and cannot separate the two mechanisms, which
was this spec's entire purpose. The honest verdict is **undecidable**: the
question it set out to answer needs roughly 2.3× the month-end sample, and 234
pre-holdout month-end days is all 18 years provides.

### Period stability (net pips, base costs)

| rule | 2005–2014 | 2015–2021 | 2022+ |
|---|---|---|---|
| B prefix | +2.53 (t +2.10, n=302) | +2.21 (t +2.84, n=414) | +0.87 (t +0.46, n=166) |
| B postfix | +1.84 (t +2.36, n=353) | +0.72 (t +1.07, n=415) | +2.96 (t +1.98, n=179) |

6/6 cells positive, 4/6 at |t| ≥ 1.96. Kill criterion 3 (pre-2008 only) does not
fire: the effect is present across all three periods, weakest most recently in
the prefix rule and strongest most recently in the postfix.

### Sharpe, and the two bars

| | trades/yr | sd/trade | as run | era | live (73% haircut) |
|---|---|---|---|---|---|
| prefix_long | 49 | 19.5p | **0.74** | 0.44 | 0.20 |
| postfix_short | 53 | 15.4p | **0.73** | 0.37 | 0.10 |

18-year detection bar (t=2) is 0.47; multiple-testing bar (t=3) is 0.71. The
as-run Sharpe of 0.74 clears t=3, which was the first result in this project to
do so. Under era-scaled spreads it falls to 0.44, below even detection.

**Two corrections that undercut this table.**

*The 0.74 needed code the repo did not have.* `datasets._with_synthetic_ask` kept
keying the synthetic spread on the bar's own hour until the commit that added this
paragraph; the fix existed only in a working tree. A clean clone produced prefix
+1.838 and Sharpe 0.661, not +2.068 and 0.743 — short by exactly 0.230 pips a
trade, with postfix off by 0.012, which is the trap-6 signature (0.600 − 0.360 on
the entry leg only). The 0.74 is right for correct code; it was not reproducible.
Re-run and confirm before quoting it again.

*Both legs sit below their own MDE at this spec's declared bar.* Kill criterion 2
sets the bar at |t| ≥ 2.5, but `min_detectable_pips` was called with its α=0.05
default, so every MDE printed used t=1.96 and was 19% too small:

| leg | effect (fixed) | MDE printed (t=1.96) | MDE at declared t=2.5 |
|---|---|---|---|
| prefix_long B | +2.068p | 1.837p — looks cleared | **2.192p — below floor** |
| postfix_short B | +1.561p | 1.406p — looks cleared | **1.677p — below floor** |

The prefix effect and its printed MDE agree to 0.001 pips, which is why it read
as a pass. At the bar this spec actually declared, neither leg reaches the
smallest effect the test could resolve. This is independent of the spread
question: it holds whichever spread is assumed, because a constant cost shifts
the mean and leaves the sd untouched.

Annualised vol is only **0.86%**, because exposure is ~2 hours per trade. That
makes the strategy capital-efficient and leverable; at 10× it is 6.4%/yr at 8.6%
vol. Sharpe is leverage-invariant, so the honest live expectation remains 0.20,
i.e. roughly 1.7%/yr at that leverage.

### Tradeability: undecidable, and for a stateable reason

Kill criterion 5 as written quoted a 1.84-pip bar, computed with the pre-fix
0.600 spread. With the corrected hour-8 spread the `PESSIMISTIC` all-in is
**1.236 + 0.360 = 1.60 pips**.

| | as run | era | era ×2 |
|---|---|---|---|
| prefix_long | +2.068 **passes** | +1.236 fails | +0.001 fails |
| postfix_short | +1.561 fails | +0.784 fails | −0.318 fails |

The verdict flips between columns, which is the case `004_spread_sensitivity.py`
was written to detect. **The effect (1.5–2.1 pips) is the same order as the
spread uncertainty (0.36 measured, 0.9–1.8 plausible for 2007–2024).** So "is
this tradeable" is literally the question "what was the retail spread in
2007–2024", and bid-only data cannot answer it. The admissible bid/ask slice is
2024-06-19 onward, which is 6½ pre-holdout months.

Ignore the `sig` flags on C_control under era costs (t up to −6.44). Adding
spread uniformly shifts every group down, and at n=2606 a small shift is
significant. That is arithmetic, not a finding, and is why the `mid_pips`
comparison is the test.

### Decision

- **Separation: unresolved and unresolvable at this power.** Do not claim month-end
  contributes nothing; claim only that it is invisible at n=187–193.
- **Spec 001's mechanism: upheld.** Restate its conclusion as Gotobi-proper, not
  Gotobi-including-month-end.
- **Effect: real and period-stable** on the cost-free comparison.
- **Tradeability: blocked on spread provenance, not on statistics.** Does not
  advance to Layer 2 until either (a) `scripts/download.py` supplies genuine
  Dukascopy bid/ask for 2007–2024, or (b) forward bid/ask accumulates enough
  month-ends post-2024-06 to test directly.

### Bug found and fixed during this run

`_with_synthetic_ask` keyed the synthetic spread on the source bar's JST hour.
`events.quote_at` fills on the bar at `ts − 1min`, so an 08:00 JST entry filled
on the 07:59 bar and paid hour 7 (0.600 pips, still decaying from the 06:00
rollover spike) instead of hour 8 (0.360). Costs were **overstated** by 0.24
pips per prefix trade — conservative, but it compounded through the era
multipliers, moving the prefix `era` column from +0.457 to +1.236. Fixed by
keying on the execution hour. Postfix was unaffected (09:55 fills on 09:54, both
hour 9) and its 0.326 median is unchanged, which is the control confirming the
fix was narrow.

Latent, not fixed: the profile is keyed on JST hour, but the 17:00 NY rollover
lands at 06:00 JST under EDT and 07:00 under EST, so hours 6–8 are DST-smeared.
Specs 001 and 004 trade 08:00–11:00 and are unaffected. Any spec trading JST 6–8
must key on (JST hour, NY DST flag).
