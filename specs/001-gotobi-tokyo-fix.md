# Spec 001: Gotobi / Tokyo 9:55 JST fix

**Author:** Haru · **Date:** 2026-11-24 · **Status:** results recorded 2026-11-26; 1b passes every criterion, 1a fails the 2022+ criterion under the t ≥ 2 reading. Verdict pending the user's choice of reading (see *Results*)

## Hypothesis
Japanese importers buy USD at the Tokyo bank fix (9:55 JST), and this demand is concentrated on
gotobi days (5th/10th/15th/20th/25th/month-end, rolled back to the previous business day). Banks
pre-hedge, so USDJPY tends to drift up into 9:55 and partly reverse afterwards.

## Evidence
- Ito & Yamada (NBER 2016 / J. Int. Econ. 2017, 1999–2013): predictable USD-buying imbalance at the
  fix, stronger on gotobi/month-end; long 5 min before / short 5 min after ≈ 1.8 bp/day, "slightly above" costs.
- Krohn, Mueller & Whelan (J. Finance 2024, 1999–2019): USDJPY has the largest post-Tokyo-fix
  reversal of 9 currencies; unprofitable at full quoted spread; weaker after 2014.
- Bessho, Sugimoto & Suzuki (arXiv 2023, 2018–2020): in-sample profit factors 1.5–2.6 on gotobi days.
- No published results for 2021–2026.

## Rules
- Days: gotobi days (`usdjpy.calendars.gotobi_days`). Control: other JP business days.
- 1a: long 08:00 JST (23:00 GMT prev. day) → exit 09:55 JST (00:55 GMT). Market orders.
- 1b: short 09:55 JST → exit 11:00 JST (02:00 GMT). Market orders.
- Size: USD 100k.

## Data needed
Dukascopy USDJPY ticks, 2010 onwards.

## Kill criteria
As in TEMPLATE. Additionally: gotobi must beat control days (Welch t-test p < 0.05) — otherwise
it's generic time-of-day drift, not the gotobi flow.

## Parameters
Entry time, exit time. Do NOT grid-search them on the full sample; if testing alternatives,
pre-declare at most 3 variants.

## Results

> **Recorded 2026-11-26** (housekeeping; until then this section read "_Pending._" while
> `CLAUDE.md` called the spec "upheld"). The verdict was only ever computed in
> `scripts/gotobi_report.py`'s HTML page, which is gitignored. Figures from
> `python scripts/gotobi_study.py` (`--source combined`): **current code** reproduced on a
> fresh clone of `research/remaining-work` at `81c7b13`, and **first-run code** (the
> exec-hour spread fix and HistData DST fix undone, as when this spec was first run on
> 2026-11-24). Pre-holdout trades only (2007-01 to 2024-12); the script's header day
> counts (1393 gotobi / 3357 control) run to 2026 but no post-holdout date is traded.
> Sample deviation, made at the first run and kept: *Data needed* says Dukascopy ticks
> from 2010; the run uses the `combined` seeded bars from 2007.

Net pips per trade, gotobi days (month-end included, as this spec defines them); t is
mean / (sd / √n).

| | 1a long 08:00→09:55, current | 1a first run | 1b short 09:55→11:00, current | 1b first run |
|---|---|---|---|---|
| Trades | 1,068 | 1,069 | 1,140 | 1,140 |
| Mean net, base / t | +1.853 / 2.97 | +1.399 / 2.26 | +1.744 / 3.45 | +1.608 / 3.19 |
| 2022+ (2022-24) mean / t | +1.758 / **0.97** | +1.339 / **0.74** | +3.393 / 2.45 | +3.292 / 2.40 |
| `PESSIMISTIC` mean / t | +1.453 / 2.33 | +0.999 / **1.62** | +1.344 / 2.66 | +1.208 / 2.39 |
| Gotobi − control, mid pips (Welch t, p) | +2.019 (2.82, 0.005) | +1.837 (2.57, 0.010) | +1.692 (2.89, 0.004) | +1.574 (2.72, 0.007) |

**Kill criteria** (TEMPLATE, plus Welch p < 0.05 against control days). Two readings of
"effect absent in the 2022+ period" and "fails under PESSIMISTIC":
- *t ≥ 2 within the period / under `PESSIMISTIC`*: the reading in `gotobi_report.py`'s
  template, committed with the first run (`2872408`, 2026-11-24). Whether it was fixed
  before the first results were seen is not recorded.
- *mean > 0*: the plain-text reading, as spec 005 later wrote its own 2022+ criterion.

| Criterion | 1a current | 1a first run | 1b current | 1b first run |
|---|---|---|---|---|
| Mean net > 0, base | pass | pass | pass | pass |
| t ≥ 2, base | pass | pass | pass | pass |
| 2022+, t ≥ 2 reading | **fail** | **fail** | pass | pass |
| 2022+, mean > 0 reading | pass | pass | pass | pass |
| `PESSIMISTIC`, t ≥ 2 reading | pass | **fail** | pass | pass |
| `PESSIMISTIC`, mean > 0 reading | pass | pass | pass | pass |
| Welch p < 0.05 vs control | pass | pass | pass | pass |

**Status: pending the user's decision on which reading governs.** Rule 1b passes under
both. Rule 1a passes only under the mean > 0 reading; under the report's t ≥ 2 reading
it fails the 2022+ criterion on any code (and failed `PESSIMISTIC` too on first-run
code), so "upheld" was never true of 1a on that reading.

Whatever the reading, the mechanism is **not** established: the treatment group bundles
month-end (16.7% of pre-holdout gotobi days), spec 004's A-vs-B separation is
uninformative, and spec 004's weekday-matched Gotobi-proper vs control is below its 2.5
bar. Do not restate this spec as Gotobi-proper (`HANDOFF.md` §6). These t-stats are naive
and on one pair; the Deflated Sharpe treatment and the trial count live in spec 004 and
`CLAUDE.md`.
