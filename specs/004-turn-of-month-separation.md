# Spec 004: turn-of-month separation

**Author:** bzk · **Date:** 2026-11-24 · **Status:** effect confirmed (t +3.47 / +3.34 net, 83% / 80% power, as run after the 2026-11-25 HistData DST fix; was t +3.15 / +3.11, 74% / 73%); separation unanswerable; tradeability blocked on spread; gap fill declared 2026-11-25, figures to be re-derived (see *Gap fill*)

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

As run, the spec used `datasets.load_minute("combined")`, which drops 194 prefix and
128 postfix B trades for lack of a quote (193 prefix before the 2026-11-25 HistData DST
fix; see *Results*). The *Gap fill* section below declares how
they are restored from `data/tokyo_hours/`.

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

**Evaluation note on criterion 5 (2026-11-25; the criterion is unchanged; no filled
data had been viewed).** "~1.84 pips at 159" was an estimate of the quantity the
criterion defines, not the criterion itself, and it was wrong twice: it used the
pre-fix hour-7 spread, and it applied the long leg's entry spread to both legs. The
*Results* section later substituted 1.60 after results had been seen; that
substitution is withdrawn. From this date criterion 5 is evaluated as written, per
trade:
- **Bar for trade i** = `PESSIMISTIC.round_trip_pips(price_i)` + the spread trade i
  actually pays: the entry spread for the long prefix leg, the exit spread for the
  short postfix leg (bid-anchored fills: a long buys bid + s at entry, a short buys
  bid + s at exit). Priced at the trade's own price, as `net_pips` already is.
- **Margin** = mean over trades of `net_pips_i − bar_i`. Criterion 5 passes if the
  margin is ≥ 0. Read literally, that requires gross to cover base plus pessimistic
  costs, about 2.2× base: a cost-doubling test.
- **The governing column is *measured*** (see *Gap fill*). Until it exists, criterion
  5 is **pending**; the *as run*, *era* and *era ×2* columns are assumptions.
- **Reported beside it, not governing** (standard net-of-cost measures): the
  one-sided 95% lower bound of the margin, with any pass or fail within one standard
  error labelled "not resolved"; net mean and t under `PESSIMISTIC` (criterion 4);
  break-even round-trip cost (mean `mid_pips`) in pips and bp; and a bp view at 159,
  so the effect and the costs are compared at today's price.

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
(pre-holdout), after the execution-hour fix to `_with_synthetic_ask`, and **re-run the
same day after the HistData DST fix** (`datasets.fix_histdata_dst`; see *Second bug*
below). Every table shows the corrected figure first and the pre-fix one beside it.
The pre-fix trade CSVs are kept in `results/archive/004_as_run_pre_dst_fix/`, and
`scripts/004_spread_sensitivity.py --results-dir` on that folder reproduces every
pre-fix number below. Day counts:
A 234, B 1159, C 3357, A/B overlap 0. Month-end is 234 of spec 001's 1393
treatment days = **17%**.

### The clean test — mid_pips, no cost assumption

| Test | prefix_long | postfix_short | MDE @ t=2.5 (prefix / postfix) | verdict |
|---|---|---|---|---|
| A vs C | −0.08 (t −0.05); was −0.23 (t −0.13) | +2.00 (t +1.16); was +1.87 (t +1.09) | 5.85 / 5.74p | null, **uninformative** |
| **B vs C** | **+2.465 (t +3.28)**; was +2.275 (t +3.04) | **+1.630 (t +2.80)**; was +1.513 (t +2.62) | 2.51 / 1.95p | **DIFFERENT** |
| A vs B | −2.55 (t −1.39); was −2.50 (t −1.37) | +0.37 (t +0.21); was +0.36 (t +0.20) | 6.15 / 5.90p | null, **uninformative** |

The MDE column is now at the declared t=2.5 bar. It previously read 4.8–4.9, 2.09 / 1.61
and 5.1 / 4.9 pips, which were computed at t=1.96 (`004_spread_sensitivity.py` hard-coded
2.80 standard errors); the corrected pre-fix values are 5.83 / 5.72, 2.50 / 1.93 and
6.11 / 5.88. No verdict changes.

**The hypothesis is refuted, and in the opposite direction.** This spec predicted
month-end would dominate and Gotobi-proper would be indistinguishable from
control. The data says Gotobi-proper differs from control in both rules, same
sign, with MDE **below** the published 2.86-pip effect — an informative positive.
Month-end shows nothing, but at an MDE about 2× the effect (at the t=2.5 bar) we cannot *see* it, which is
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
| B prefix | +2.53 (t +2.10, n=302) | +2.61 (t +3.21, n=414); was +2.21 (t +2.84) | +1.12 (t +0.59, n=165); was +0.87 (t +0.46, n=166) |
| B postfix | +1.84 (t +2.36, n=353) | +0.91 (t +1.36, n=415); was +0.72 (t +1.07) | +3.16 (t +2.09, n=179); was +2.96 (t +1.98) |

2005–2014 is unchanged: the fix touches 2019 onward only. 6/6 cells positive, 4/6 at
|t| ≥ 1.96, before and after. Kill criterion 3 (pre-2008 only) does not
fire: the effect is present across all three periods, weakest most recently in
the prefix rule and strongest most recently in the postfix.

### Sharpe, and the two bars

| | trades/yr | sd/trade | as run | era | live (73% haircut) |
|---|---|---|---|---|---|
| prefix_long | 48.9 | 19.7p | **0.817** (was 0.743) | 0.522 (was 0.444) | 0.221 (was 0.201) |
| postfix_short | 52.6 | 15.5p | **0.788** (was 0.733) | 0.424 (was 0.368) | 0.213 (was 0.198) |

18-year detection bar (t=2) is 0.47; multiple-testing bar (t=3) is 0.71. Both
as-run Sharpes clear t=3. Under era-scaled spreads prefix falls to 0.52, above
detection but below t=3, and postfix to 0.42, below detection. Before the DST
fix prefix era was 0.44, below detection.

*Correction to this table's earlier version:* postfix "live" read 0.10. Live is
as-run × 0.27, as the prefix row computed it, which gives 0.198; the 0.10 was
0.27 × the *era* Sharpe. Every figure here is now printed by
`004_spread_sensitivity.py` rather than computed by hand.

**Two corrections that undercut this table.**

*The 0.74 needed code the repo did not have.* `datasets._with_synthetic_ask` kept
keying the synthetic spread on the bar's own hour until the commit that added this
paragraph; the fix existed only in a working tree. A clean clone produced prefix
+1.838 and Sharpe 0.661, not +2.068 and 0.743 — short by exactly 0.230 pips a
trade, with postfix off by 0.012, which is the trap-6 signature (0.600 − 0.360 on
the entry leg only). The 0.74 is right for correct code; it was not reproducible.
Re-run and confirm before quoting it again. (Superseded as the headline on
2026-11-25 by the HistData DST fix: 0.743 is the correct *pre-DST-fix* figure,
reproducible from the archived CSVs; the current figure is 0.817.)

*The MDE was computed at the wrong bar, and the effect's power is ~74%, not 80%.*
Kill criterion 2 sets the bar at |t| ≥ 2.5, but `min_detectable_pips` was called
with its α=0.05 default, so every MDE printed used t=1.96 and was 19% too small.
Corrected, with the re-run's confirmed figures:

| leg | effect | sig. threshold (t=2.5) | observed t | MDE@80% | power vs this effect |
|---|---|---|---|---|---|
| prefix_long B | +2.301p | 1.659p | **+3.47** | 2.218p | **83.3%** |
| postfix_short B | +1.683p | 1.258p | **+3.34** | 1.681p | **80.1%** |
| *prefix_long B, before DST fix* | +2.068p | 1.640p | +3.15 | 2.192p | 74.3% |
| *postfix_short B, before DST fix* | +1.561p | 1.255p | +3.11 | 1.677p | 72.9% |

Before the DST fix both effects sat *between* the significance threshold and the
80%-power MDE: significant, with roughly 74% power against an effect of that size.
After it both are at or above the 80% MDE: prefix by 0.08 pips (83% power), postfix
by 0.002 pips (80%). A repeat 18-year sample would find each significant about four
times in five. The postfix margin is nil, so read it as "about 80%", not as a pass.

This is a statement about replication reliability, not detectability. An earlier
revision of this paragraph claimed the legs fell "below floor" and did not reach
the smallest resolvable effect; that was wrong, and conflated the 80%-power
threshold with the significance threshold. The effect is detected. What is not
settled is the separation, below.

Annualised vol is only **0.87%** (prefix; 0.86% before the DST fix), because
exposure is ~2 hours per trade. That makes the strategy capital-efficient and
leverable; at 10× it is 7.1%/yr at 8.7% vol (6.4% at 8.6% before). Sharpe is
leverage-invariant, so the honest live expectation is 0.22, i.e. roughly 1.9%/yr at
that leverage.

### Tradeability: undecidable, and for a stateable reason

Kill criterion 5 as written quoted a 1.84-pip bar, computed with the pre-fix
0.600 spread. With the corrected hour-8 spread the `PESSIMISTIC` all-in is
**1.236 + 0.360 = 1.60 pips**.

| | as run | era | era ×2 |
|---|---|---|---|
| prefix_long | +2.301 **passes** (was +2.068, passed) | +1.468 fails (was +1.236) | +0.233 fails (was +0.001) |
| postfix_short | +1.683 **passes** (was +1.561, **failed**) | +0.907 fails (was +0.784) | −0.196 fails (was −0.318) |

The DST fix moves postfix across the 1.60 bar in the as-run column, by 0.08 pips.
It changes no other cell's verdict. The verdict still flips between columns, which is the case `004_spread_sensitivity.py`
was written to detect. **The effect (1.7–2.3 pips) is the same order as the
spread uncertainty (0.36 measured, 0.9–1.8 plausible for 2007–2024).** So "is
this tradeable" is literally the question "what was the retail spread in
2007–2024", and bid-only data cannot answer it. The admissible bid/ask slice is
2024-06-19 onward, which is 6½ pre-holdout months.

Ignore the `sig` flags on C_control under era costs (t up to −6.47; −6.44 before the DST fix). Adding
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

### Second bug: HistData DST (found and fixed 2026-11-25)

`scripts/histdata_alignment_check.py` (the handoff's task 1) found that
`histdata_bid_2015_2025.parquet` is aligned to UTC in every full US summer and winter
month, but **from 2019 HistData's raw clock changes on EU DST dates**. In the weeks
where US and EU clocks disagree, 2nd to last Sunday of March and last Sunday of
October to 1st Sunday of November, every bar labelled T held the true T+60 price. So
a 23:00 UTC entry filled at the true 00:00 price and every leg ran an hour late.
Evidence and method are in `docs/DATA.md` (HistData row). `datasets.fix_histdata_dst`
corrects it in the loader, with known-answer tests in `tests/test_datasets.py`.

Scope in this spec: 2019 to 2024-06-18, the HistData share of `combined`. 21 prefix
and 22 postfix B trades changed, plus 60 prefix and 64 postfix C trades and 6 A
trades per leg. The 2023 March window overlaps HistData's Feb–Jul 2023 gap, so the
set of days with a 22:59 quote also moved: prefix B lost 2023-03-15 and 2023-03-20
and gained 2023-03-24 (n 882 → 881; 2023 now 46 of 60), and prefix C lost two days
and gained four (2606 → 2608).

Direction: **the fix strengthened every B figure** (prefix +2.068 → +2.301 pips, t
+3.15 → +3.47; postfix +1.561 → +1.683, t +3.11 → +3.34) and flipped one verdict, the
postfix as-run tradeability cell, by 0.08 pips. The misplaced trades sampled an hour
of the wrong session rather than leaning toward the hypothesis: before the fix, C
trades in those weeks averaged −5.35 pips (prefix) and +3.54 (postfix), against near
zero elsewhere, and B trades −0.17 and +0.55.

This is the second bug in this spec found by an alignment or reproduction check
rather than by any output looking wrong. Neither produced an implausible number.

## Gap fill (declared 2026-11-25, before any filled data is seen)

The options, request counts and the choice of fetch are recorded in
[`specs/README.md`, *Dukascopy fetch*](README.md#dukascopy-fetch-options-and-decision-2026-11-25).
This section fixes how the data will be used. It is written before the data exists,
and it may not be revised after any of it has been seen.

### Why

These rules call for every pre-holdout B day, and there are 1,075. The as-run
results drop days with no quote at an execution minute:

| | Prefix | Postfix |
|---|---|---|
| As run | 882 | 947 |
| Missing in 2007–2014 (gaps in the third-party export) | 176 | 125 |
| Missing in 2023 (HistData gap, Feb–Jul, 23:00 UTC entry) | 13 | 0 |
| Missing on 25 December (unfillable) | 4 | 3 |

So the drops come from data gaps, not from the rules. Filling them restores the
declared sample and lifts the prefix leg from 74% power to about 83%, if the effect
holds at +2.068 pips. Stage 3 also gives measured bid/ask for 2007–2014. That is the
era where the spread is least known, and tradeability is blocked on it.

**This is a second look at a test whose result is known, motivated by a power
shortfall seen in that result.** That is the shape of optional stopping. The
safeguards:
- This section is written before any filled data exists.
- Rules, windows, groups and kill criteria are unchanged.
- The filled sample is the declared one, so it is not a new trial: the trial count
  used by `stats.deflated_sharpe` does not change.
- Both results are reported side by side.

**Amendment, 2026-11-25 (after the HistData DST fix; no filled data had been viewed.
The fetch was in stage 1, and nothing under `data/tokyo_hours/` had been read beyond
filenames and the fetch log).** The fix changes as-run counts that this section quotes;
it changes no rule, window, group, threshold or kill criterion:
- **As run** in this section and in *Figures to re-derive* means the as-run on the
  DST-corrected loader: prefix 881, postfix 947 B trades; 2023 prefix 46 of 60, so 14
  trades missing in 2023, not 13, and 194 in total. The pre-fix figures stay in
  *Results* and in `results/archive/004_as_run_pre_dst_fix/`.
- **Power.** On the corrected bars the as-run prefix leg already has 83% power against
  its own effect (+2.301 pips; 819 trades needed for 80%), so the power shortfall that
  motivated this fill no longer exists. The fill is kept for its other two purposes:
  measured 2007–2014 bid/ask, and restoring the declared sample.
- **Step 0, Feb–Jul 2023 part.** The question it asks, whether an hour offset appears
  after the 12 March US DST change, has been answered on existing data: in the stored
  file it does, from 12 to 24 March 2023, and `load_minute` now corrects it. Step 0
  will compare against the loader's (corrected) HistData, where no offset should appear.

### Data

`data/tokyo_hours/USDJPY/`, UTC hours 22, 23, 0 and 1, fetched by
`scripts/download_gap_fill.py` in three stages:
1. Feb–Jul 2023
2. A spread sample, 2015–2024
3. Every weekday, 2007–2014

### Step 0: source agreement, before any fill is used

The fill is spliced into series it must match. Compare the Dukascopy tree with the
as-run bars at the three execution bars (22:59, 00:54, 01:59 UTC), on every day
both quote:

- **2007–2014, against the third-party export.** Proceed only if the median absolute
  bid difference is ≤ 0.3 pips **and** the mean absolute difference is smallest at
  offset 0 among offsets of −60, 0 and +60 minutes. Otherwise stop and report. Use no
  fill until this section is amended by a dated note that says what was seen.
- **Feb–Jul 2023, against HistData,** at 00:54 and 01:59, outside the gap. Report the
  same statistics without a threshold, because HistData is a different venue. If an
  hour offset appears after the 12 March US DST change, it confirms the open
  HistData UTC-alignment question in the triage. That would affect every
  HistData-era figure, not just the fill, and is reported as its own finding.

### Filled analysis (primary for decisions from here on)

- **Bars.** Use the as-run `combined` bars unchanged wherever they produce a trade.
  For any A, B or C day whose trade the as-run drops, take **both legs** from the
  Dukascopy tree, so a level offset between sources cannot enter a trade's P&L.
  Days quoted by neither source are dropped, as before. Stage 2's sample days are
  not used for fills.
- **Costs (kill criterion 5).** Add a **measured** column beside *as run*, *era* and
  *era ×2*:
  - 2007–2014: each trade pays the Dukascopy spread at its own execution bar.
  - 2015 to 2024-06: each trade pays the median spread from the stage 2 sample at
    that execution bar, by calendar year, pooling the B and C sample days. Report
    the B-versus-C spread difference descriptively.
  - From 2024-06-19: Eightcap bid/ask, as now.

  Judge kill criterion 5 on the measured column, under both `CostModel()` and
  `PESSIMISTIC`.
- **Unchanged:** the windows, the A/B/C partition, `quote_at` tolerance,
  `allow_holdout=False`, and every kill criterion and its threshold.

### Weekday-matched comparison (declared 2026-11-25, before any filled data is seen)

**Why.** Gotobi dates that fall on a weekend roll back to Friday, so B is 44% Fridays
against 11% in C, and month-end (A) rolls back the same way. Non-Gotobi Fridays move
on their own in the prefix window. The declared unmatched comparison therefore mixes
a Gotobi contrast with a weekday contrast. Found by an independent review on
2026-11-25.

**Test.** For each comparison X vs Y in {A vs C, B vs C, A vs B}, on `mid_pips`:
- For each JST weekday w (Mon–Fri) in which both groups have at least 2 trades,
  d_w = mean(X, w) − mean(Y, w).
- D = Σ_w (n_X,w / n_X′) · d_w, where n_X′ is X's trade count over the weekdays used
  (weights are X's weekday mix: the effect on the days X actually trades).
- SE² = Σ_w (n_X,w / n_X′)² · (s²_X,w / n_X,w + s²_Y,w / n_Y,w); t = D / SE.
- Bar |t| ≥ 2.5; MDE at 3.342 SE (t = 2.5, 80% power). Dropped weekday cells are
  reported.
Implemented as `events.stratified_compare`.

**Reported** beside the declared unmatched comparison (figure 2), with *as run* and
*filled* columns. It replaces neither the declared test nor any kill criterion. If
the matched and unmatched B-vs-C disagree at the 2.5 bar, the status line says so,
and the mechanism claim ("Gotobi-proper differs from control") is read from the
matched test.

**Disclosure.** On *as run* data a weekday-dummy regression has already been seen:
B vs C prefix +1.464 (t 1.89), postfix +1.444 (t 2.36); with year dummies too, t
1.89 and 2.39. Only the filled run of this test is blind.

### Figures to re-derive

Report each with *as run* and *filled* columns side by side:
1. Day and trade counts per group and leg, including the 2023 count (now 47 of 60
   prefix).
2. The clean test: `mid_pips` A vs C, B vs C and A vs B, with t and the MDE at the
   t = 2.5 bar.
3. Period stability, net pips at base costs.
4. Sharpe: as run, era and live, plus the measured spread.
5. Power: effect, significance threshold, observed t, MDE@80%, power.
6. Tradeability, with the measured column.
7. `stats.deflated_sharpe` at the current trial count, with skew and kurtosis
   computed from the trade series rather than assumed (0 and 3).

Then update the copies of these numbers held elsewhere:
- `CLAUDE.md` *Current state* and its trial-budget paragraph (SR 0.1062, n=882,
  passes to N=8)
- `HANDOFF.md` §2
- the spec 004 row of the `specs/README.md` index

Each copy states which sample it quotes.

**If as-run and filled disagree on any kill criterion, the status line says so.**
The filled result governs, because it is the declared sample. The as-run result
stays in the record and is not overwritten.

**What the fill cannot do:**
- It cannot answer the A-vs-B separation. Month-end gains few days, and the MDE
  stays about twice the effect.
- It does not touch the holdout.
