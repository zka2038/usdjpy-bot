# Spec 019: yen-leg / dollar-leg split of the Gotobi-morning move

**Author:** bzk (drafted with Claude) · **Date:** 2026-11-27 · **Status:** idea. Declared
before any cross-pair data exists on this machine; nothing fetched, nothing run.

**This spec asks what kind of move spec 004's B-day Tokyo-morning move is, not whether
it can be traded.** It replaces the "JPY-cross breadth study" that `HANDOFF.md` §2 and
`specs/TRIAGE-006-018.md` proposed (the same rule run on EURJPY, AUDJPY and GBPJPY as
independent replications). That design was dropped on 2026-11-27, before any data, for
the reason in *Why not replication*; the user chose this one.

## Hypothesis

Spec 004 found that USDJPY rises in the Tokyo morning on Gotobi-proper days (B), against
zero and against unmatched control days, but **not against weekday-matched control** at
its 2.5 bar (figures: spec 004 *Weekday-matched comparison* and `HANDOFF.md` §2). B is 44%
Fridays against 11% in C, and non-Gotobi Fridays rise on their own. So the open question
is mechanism: settlement flow, or a weekday effect that B inherits.

The named mechanism is **Japanese importers buying USD with JPY** for invoices settled on
multiples of 5. That flow is funded in yen. Any move in USDJPY can be split exactly into
a yen leg and a dollar leg against a third currency X:

```
ln USDJPY = ln XJPY − ln XUSD          (triangular identity)
r_UJ      = r_XJ    − r_XU             (window log returns)
```

Averaging over X in {EUR, GBP, AUD}:

- **J (yen leg)** = mean over X of r_XJ. Positive = the yen weakens against the basket.
- **D (dollar leg)** = −mean over X of r_XU. Positive = the dollar strengthens against
  the basket.
- **r_UJ = J + D**, exactly, up to triangular-arbitrage and quote-timing error (checked in
  *Step 0*).

What each explanation predicts on B days, relative to weekday-matched control:

| Explanation | J (yen leg) | D (dollar leg) |
|---|---|---|
| Yen-funded settlement flow (Gotobi as named) | **> 0** | ≥ 0 (how much of a bilateral USD/JPY shock reaches the dollar leg depends on which legs market makers move; crosses are usually priced off the legs, which puts most of it in J) |
| Broad dollar demand (a weekday or global-USD effect) | ≈ 0 | > 0 |
| Broad yen selling not tied to USD | > 0 | ≈ 0 |

**H0 (primary):** the B-day yen leg equals the weekday-matched control's, in the prefix
window. Rejecting it with J > 0 means the B-day move is at least partly a yen move, which
the settlement mechanism requires and a broad-dollar explanation does not. A dollar-only
move (D > 0, J ≈ 0) would count against the named mechanism.

The postfix window (spec 004's reversal leg) predicts the opposite signs.

## Why not replication (recorded 2026-11-27, before any data)

The proposed breadth study treated three JPY crosses as three more samples. They are not.
By the identity above, r_XJ = r_UJ + r_XU: on a Tokyo morning when EURUSD barely moves,
EURJPY repeats USDJPY's move. The crosses share USDJPY's information, so three of them add
far less than 3× the effective sample (plausibly 1.2–1.5×; unmeasured until the data
exist), and they inherit USDJPY's Friday effect by the same arithmetic. What the crosses
*can* do is attribute the move to a leg. Hence this design.

## Evidence

- Spec 004 *Results*, *Weekday-matched comparison* and `scripts/004_weekday_breakdown.py`:
  the confound this spec addresses.
- Ito & Yamada (NBER WP 22820, 23327): the Tokyo 09:55 fix dominates USDJPY's fixing
  events; month-end spikes are more frequent than Gotobi spikes (spec 004 *Evidence*).
- Japan's imports are invoiced mostly in USD, which is why importer settlement is a
  USD/JPY flow at all. **The invoicing shares must be quoted from MOF's
  invoicing-currency statistics before the run, not from memory**; no fetch was made
  for this spec.
- No prior study of the leg split on Gotobi days is known to us. **Exploratory as to
  mechanism; confirmatory bar applied anyway.**

## Rules (exact, no discretion)

- **Dates:** spec 004's A/B/C partition (`calendars.turn_of_month_groups`), JST dates,
  pre-holdout only (`allow_holdout=False`; last date 2024-12-31).
- **Excluded:** every date in `data/calendars/mof_intervention_transcribed.csv`, any
  pair, from all groups (declared before data; the handoff for this study required it).
  An intervention is the largest possible yen-leg move and would dominate whichever group
  it falls in. Spec 004 did not exclude them, and its largest prefix trade (2011-03-18,
  +209 pips, a B day) is the G7 coordinated intervention. The run *with* them is reported
  as a diagnostic.
- **Windows:** spec 004's, unchanged. Prefix 08:00→09:55 JST, postfix 09:55→11:00 JST.
- **Prices:** 1-min **bid** closes via `events.quote_at` (fill on the bar at ts − 1 min,
  5-min staleness tolerance), for each of seven pairs: USDJPY, EURJPY, GBPJPY, AUDJPY,
  EURUSD, GBPUSD, AUDUSD. Bid, not mid: no per-pair spread profile exists, and the test is
  B minus C, so a spread profile that depends on the hour cancels. Bid-to-bid returns
  differ from mid returns only by the change in half-spread over the window.
- **Returns:** r = 10⁴ · ln(bid_exit / bid_entry), in bp. **Not side-adjusted:** positive
  always means the base currency rose.
- **Test unit: USDJPY pip equivalents**, so results compare directly with spec 004. Each
  day's J and D in bp are multiplied by P̂ / 100, where P̂ = mean over X of
  bid_XJ / bid_XU at entry: the USDJPY level the crosses imply (1 bp ≈ 1.1 pips at 110,
  1.59 at 159). P̂ is used, not USDJPY's own bid, so that J and D need no USDJPY quote.
  bp figures are reported beside the pip figures.
- **A day enters a window's J and D only if all six cross and USD pairs quote at both
  ends.** USDJPY is not needed for J or D, only for Step 0. Days lost are counted by group
  and year.
- **J, D** as defined above, equal weights over EUR, GBP and AUD.
- No trade is simulated. No cost model applies (see *Tradeability*).

## Data needed

- **HistData 1-min bid** for EURJPY, GBPJPY, AUDJPY, EURUSD, GBPUSD and AUDUSD,
  **2007–2024 only**. Holdout years are not downloaded.
- USDJPY: the existing `load_minute("combined")` bid, for Step 0 only.
- **Fetch timing (user's instruction, 2026-11-27):** not before the Dukascopy gap-fill
  fetch has logged `stage 3 complete`, so that no second fetch can draw rate-limiting or
  IP blocking onto it. After that it still needs the user's go-ahead.
- **Code needed, none written yet:**
  - a pair argument for the HistData path of `scripts/fetch_official.py`, which
    hardcodes `usdjpy`;
  - a pair-generic bid loader (the `datasets.load_minute` path without the synthetic ask,
    which is keyed on USDJPY's spread profile);
  - `scripts/019_yen_dollar_split.py`.
- **Catalogue** each file in `docs/DATA.md` when fetched, with its provenance and the Step
  0 result.

## Step 0: alignment and identity (before any J or D is computed)

HistData's clock has already been wrong once on USDJPY (`CLAUDE.md` trap 8: EU DST dates
from 2019). An hour's misalignment in one pair would put a fake yen- or dollar-leg move
into the split. The triangular identity is the check, day by day.

For each X, each window, and each pre-holdout day on which USDJPY, XJPY and XUSD all quote
at both ends: e_X = r_UJ − (r_XJ − r_XU), in bp.

- For each day, compute mean |e_X| over the X available, with the X pairs read at time
  offsets of −60, 0 and +60 minutes relative to USDJPY. That day's best offset is the one
  with the smallest value.
- **Pass if both of these hold:**
  1. In every calendar month, and separately in every US/EU DST-mismatch window
     (`datasets.us_eu_dst_mismatch_windows`), offset 0 is the best offset on a majority of
     the days checked.
  2. Over all days, the median |e_X| at offset 0 is ≤ 2 bp for each X. Bid-to-bid returns
     leave a residual of the order of a change in half-spread; a one-hour misalignment
     leaves one of the order of the hourly volatility (≈ 10 bp).
- **If a pair fails only in the DST-mismatch windows from 2019, with offset +60 there:**
  apply `datasets.fix_histdata_dst` to that pair and re-run Step 0. This is the known
  HistData fault, so correcting it is not a choice made after seeing results. Record the
  outcome in `docs/DATA.md`.
- **Any other failure: stop.** Report what was seen. Use no data until this section is
  amended by a dated note.
- Step 0 reads identity residuals only. It computes no group means of J, D or r_UJ.

## Stage 1: power, on control days only (before any B-day outcome is computed)

The trial is spent when B-day outcomes are computed (*Trial count*). Before that, the
script computes from **C days alone**:
- sd of J and D by weekday;
- v = Var(D) / Var(r_UJ), and corr(J, D);
- the matched-test SE that B's weekday counts imply (B's counts come from the calendar,
  not from outcomes).

From these it computes power for the primary test at the 2.5 bar, against spec 004's
weekday-matched prefix estimate, for yen shares s = 1 and s = 0.5.

**It then stops and reports to the user, who decides whether to spend the trial.**
`--confirm-stage2` is required to go on, and the confirmation is recorded in this spec
with its date. A low-power result is not a reason to change any rule. It is a reason to
consider not running at all.

**Scenarios declared now, from spec 004's as-run matched figures.** The prefix matched
estimate is about 1.56 pips with SE 0.82; postfix is 1.46 with SE 0.64 (derived as
t × MDE / 3.342 from spec 004's t 1.91 / 2.28 and MDE 2.73 / 2.14). These assume J and D
are uncorrelated on control days. Two warnings: the estimates are noisy and probably
inflated by selection, so these powers are upper-end; and the table is for orientation
only, because Stage 1's own figures replace it.

| Window | v = Var(D)/Var(r_UJ) | MDE of J, pips | power, s = 1 | power, s = 0.5 |
|---|---|---|---|---|
| prefix | 0.3 | 2.28 | 41% | 9% |
| prefix | 0.5 | 1.93 | 58% | 13% |
| prefix | 0.7 | 1.50 | 84% | 22% |
| postfix | 0.3 | 1.79 | 59% | 13% |
| postfix | 0.5 | 1.51 | 77% | 19% |
| postfix | 0.7 | 1.17 | 95% | 34% |

The split can **raise** power over spec 004's own matched test when the effect sits in
one leg: removing the other leg's noise shrinks the SE. It falls sharply when the effect
is split evenly.

## Stage 2: tests (after the user's confirmation)

`events.stratified_compare(treat=B, control=C, col=…)` on J and D: weekday-matched,
weights from B's weekday mix, at least 2 days per cell. Four tests:

| # | Leg | Window | Prediction under the named mechanism | Role |
|---|---|---|---|---|
| **P** | J | prefix | > 0 | **primary** |
| S1 | J | postfix | < 0 | secondary |
| S2 | D | prefix | none (≥ 0 allowed) | secondary |
| S3 | D | postfix | none | secondary |

**Bar:** |t| ≥ 2.5 for each test. That is Bonferroni over four two-sided tests at 5%
(2.498), and the same bar as spec 004. MDE at 3.342 SE is reported beside every result,
with power read as `CLAUDE.md` *Inference rules* require (predictive replication,
Φ((t − 2.5)/√2), not observed power).

**Reported, not tested (no decision rests on them):**
- unmatched B vs C (`events.compare`) for J, D and r_UJ;
- the same split for A (month-end) vs matched C. Month-end flows are plausibly global and
  dollar-side, so this is an informative contrast;
- **the Friday split:** C Fridays vs C Monday–Thursday, for J and D. This shows what kind
  of move the Friday effect is;
- each X separately (r_XJ, −r_XU);
- `events.PERIODS` sub-periods;
- the yen share J / (J + D), only where the r_UJ difference has |t| ≥ 2;
- everything above with MOF days included;
- the B-vs-C difference in each pair's entry-bar spread, where a source has one.

## Kill criteria and readings (decided BEFORE testing)

1. **Step 0 fails** (after the declared DST correction, if one applies): no result. The
   spec stops until amended.
2. **Named mechanism supported:** P has t ≥ +2.5.
3. **Named mechanism contradicted:** P's estimate is ≤ 0 **and** its MDE is at or below
   spec 004's matched prefix estimate (1.56 pips). In that case the test could have seen
   the whole effect as a yen move, and did not.
4. **Dollar-side move:** P has |t| < 2.5 and S2 has t ≥ +2.5. The B-day move is a dollar
   move, which yen-funded settlement does not predict. Record it against the mechanism in
   specs 001 and 004.
5. **P has t ≤ −2.5:** the yen strengthens on B mornings, against the mechanism.
6. **Otherwise: unresolved.** Report the MDE and power. **Spec 001 and 004's statuses are
   left unchanged.**

**Tradeability bar: not applicable, stated so it is not mistaken for an omission.** This
spec cannot license a trade. J and D are basket returns, not positions, and no costs are
modelled. A tradeable idea that comes out of it (for example a cross-pair version of spec
004) needs its own spec, its own cost model and spread profiles, and its own place in the
trial count.

## Trial count

**Spends one spec on the USDJPY 2007–2024 sample** (user's decision, 2026-11-27, with the
triage sign-off). J and D are built from crosses and USD pairs, but they partition
USDJPY's own move on the same mornings, so this is not a fresh sample.

The count rises from N = 5 to **N = 6 at Stage 2**, not at Steps 0 or 1. At N = 6, spec
004 still clears the Deflated Sharpe hurdle on both legs: its limits are N = 17 on prefix,
N = 10 without the 2011-03-18 trade, and N = 11 on postfix (`CLAUDE.md`, trial budget).
When Stage 2 runs, update the count in `CLAUDE.md` and `HANDOFF.md` §2.

## Parameters

**Zero tuned.** Every input is inherited or fixed by construction:
- spec 004's windows, partition, `quote_at` tolerance and 2.5 bar;
- the basket of EUR, GBP and AUD, chosen for HistData coverage back to 2007 and Tokyo-hour
  liquidity, with equal weights;
- the MOF exclusion, declared above;
- the Step 0 thresholds: majority best offset at 0, median |e| ≤ 2 bp, set from the size
  of a spread change against an hour of volatility.

No other basket, window or weighting is to be tried. Each would be a new spec.

## Implementation notes

- **Known answer first** (`CLAUDE.md` *Inference rules*). `scripts/019_yen_dollar_split.py
  --synthetic` must pass before the script touches real data, and the script refuses real
  data until it has. Built on synthetic seven-pair bars that satisfy the identity exactly:
  1. inject +1 bp into J on B days: P recovers it and S2 does not;
  2. inject it into D instead: S2 recovers it and P does not;
  3. on a true null, |t| ≥ 2.5 at about the nominal rate;
  4. Step 0 flags a 60-minute shift injected into one pair inside one DST-mismatch week.
- Stage 1 and Stage 2 are separate invocations. Stage 2 refuses to run without
  `--confirm-stage2`.
- Write `results/019_*.csv` per stage, and record the results here in the same commit
  as the figures they support, confirmed from a fresh clone (handoff convention).

## Outcome to expect

The likeliest outcome is **unresolved**. The weekday-matched USDJPY effect is itself below
the bar, and an even split between the legs halves the signal in each. A clear dollar-only
answer (reading 4) would be the most useful result: it would retire the settlement story
for this window at little cost. A clear yen-leg answer (reading 2) would be the first
evidence in this repo that the B-day move is a settlement flow and not a Friday effect.

## Results

_Pending. Nothing fetched; Step 0 not run._
