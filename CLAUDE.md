# usdjpy-bot — working rules

Research → backtest → live pipeline for USDJPY, executed through IBKR. Layer 1 is
pandas event studies and predictive regressions in this repo; most ideas should die
here, cheaply. Layer 2 is NautilusTrader with bid/ask fills.

**Start with `handoffs/README.md`**: the roadmap, the priority list, and the index of
every handoff, with the read order. `handoffs/HANDOFF.md` holds the project state, the
next action, and the numbers that were wrong at some point so they are not inherited.
**Every handoff lives in `handoffs/`**, and each new one is added to that README's index
and roadmap (convention in the README). Elsewhere, handoffs are cited by file name alone,
which stays unique inside the folder.

**Read the relevant spec in `specs/` before touching any study.** Each has its kill
criteria declared before testing. Do not revise kill criteria after seeing results.

---

## Hard rules

**Holdout.** `HOLDOUT_START = 2025-01-01` in `src/usdjpy/config.py`. Nothing on or
after that date is used until a strategy has passed on earlier data and its spec is
frozen. `events.window_trades` defaults `allow_holdout=False` — leave it. Each look
spends it. If you use post-holdout data for anything, declare it in the spec and in
the research doc, and say whether it informed selection or testing.

**One cost model.** Every result goes through `costs.CostModel` (bid/ask fills +
IBKR 0.20bp, $2 min, 0.10 pips slippage/side) and must also survive `PESSIMISTIC`.
Base round trip is 0.836 pips ex-spread at 159; `PESSIMISTIC` is 1.236.

**Cost financing separately for anything held overnight.** `costs.financing_pips`.
IBKR's skim is 2.0% a year of notional in either direction (2.5% under
`PESSIMISTIC`), which is **0.883 pips per calendar day held** at 159, before the
rate differential. Five calendar days is 4.42 pips. No effect found in this repo
exceeds 2.3 pips, so **spot held at a days-to-week horizon is taxed past
everything measured here** — spec 005's three variants each gave up roughly 5
pips a trade to financing alone. Horizon is a cost question, never a power
question (see "Two bars"). Intraday holds and MJY futures avoid the skim; spot
held overnight does not. Spec 004 holds ~2 hours with zero nights and is
unaffected.

**Compare against control days, not zero.** An effect present on every day is
time-of-day drift, not the flow you hypothesised. And when the treatment rule moves
dates (a Gotobi date on a weekend rolls back to Friday), match the control on
weekday: `events.stratified_compare`. Spec 004's B is 44% Fridays against 11% in C,
and matching takes its B-vs-C t from 3.28 to 1.91.

**The trial count is a shared, depletable resource.** Every hypothesis run on
USDJPY 2007-2024 raises `stats.expected_max_sharpe` for *every* result on that
sample, retroactively. **Count specs, not legs or variants** (user decision,
2026-11-25; revisit if specs converge): five have been run. On DST-corrected bars,
with the trade series' own skew and Pearson kurtosis (`scripts/004_deflated_sharpe.py`),
spec 004 passes the Deflated Sharpe hurdle of 0.95 at N=5 on both legs (prefix
0.990, per-trade SR 0.1168, n=881; postfix 0.981, SR 0.1087, n=947), up to **N=17
on prefix and N=11 on postfix**. The prefix leg's positive skew is one trade
(2011-03-18, +209 pips); without it skew is −0.50 and the limit is **N=10**. So the
repo has **about five hypotheses of headroom** on this sample, and specs 006-018 are
thirteen: at N=18 neither leg clears (0.949 / 0.924). Run them on other pairs or
other periods, or accept that they cost spec 004 its clearance. Declare in each new
spec which sample it spends. `stats.deflated_sharpe` is the arbiter, not the t=3 bar
below, which was set without reference to any trial count. **The DSR tests the
effect against zero, not against weekday-matched control**, where spec 004 is t
+1.91 / +2.28, below its own 2.5 bar: headroom on a result whose Gotobi specificity
is not established is a ceiling, not a licence. (Superseded: "SR 0.1062, n=882,
passes to N=8, three of headroom", from before the DST fix and assuming normal
moments. Computed moments raised the prefix DSR, not lowered it as was expected.)

**The holdout cannot rescue a marginal result.** Freezing spec 004 and spending
the holdout looks like the clean way out and is not: 1.43 years to the 2026-06-05
data end is ~70 prefix trades, SE 2.355 pips against an effect of 2.301
(DST-corrected), so the expected t is 0.98 and power is **16% at alpha=0.05**, 25%
at 0.10, and lower again against weekday-matched control. It would
almost certainly return an uninformative null, and the holdout is spent once.
Check the power of a holdout test before spending it.

**Pre-declare parameters.** No grid-searching entry/exit times over the full sample.
Each tuned number spends statistical power and there is none spare — see
`Research/Strategy/Hypothesis Review H1 to H3.md` §2.

---

## Inference rules (learned the hard way; see the Review doc for the simulations)

**Compute the MDE at the test's own bar, from the sample's own SE.** Two ways
this goes wrong, both of which flatter the null. `min_detectable_pips` defaults to
`alpha=0.05` (t=1.96); if the kill criterion is |t| >= 2.5 the MDE must use that,
or it understates the bar by 19%. And SE(rho) is `se_ratio/sqrt(n)`, not
`1/sqrt(n)` — the HC sandwich is the SE the test actually uses.

**And do not read the MDE as a detectability floor.** MDE@80% is the effect that
would be found 80% of the time; the significance threshold is lower. An effect
between the two is significant in this sample and simply under-powered for
replication. Spec 004's prefix leg is +2.301 pips against a t=2.5 threshold of
1.659 and an MDE@80% of 2.218: significant at t=3.47. Quote the power, not a
verdict on whether the effect "reached" the MDE, and know what kind of power it is:
power against the *observed* effect is Φ(t − 2.5), a restatement of t, and the
annual Sharpe is t/√years. The probability that a repeat sample clears the bar,
allowing for estimation error, is Φ((t − 2.5)/√2): 75% here, not the 83% observed
power.

**Harness recovery is not power.** `signals.synthetic_check` confirms the code can
find a signal; it says nothing about whether this sample can. Spec 003's harness
recovered true rho=0.030 at `t_hc` +5.78 while the real data gave rho=0.0302 at
+1.78 — the same correlation, t 3.2x smaller, because USDJPY's errors are far
worse behaved than the synthetic DGP's. The simulation's "86% power at rho=0.05"
is what wrongly licensed calling spec 003 a well-powered null. Power claims come
from the sample's MDE, never from the calibration run.

**Report the MDE beside every null.** `stats.min_detectable_pips`. A null whose MDE
sits far above the effect size the literature claims is uninformative, not evidence
of absence. H1 was rejected because its daily MDE was 174–314 pips against a
published 17–27 pip effect — the test was impossible, not merely negative.

**Clustered events need `stats.clustered_t`, not the naive t.** Events on
consecutive dates are not independent observations. MOF interventions are 7
operation days in 4 pre-holdout episodes, so `events.summarize`'s
`mean/(sd/√n)` is optimistic by 1.32–1.47×. Applies to intervention, BOJ-meeting
clusters, and any window rule spanning adjacent days.

**Regressions of FX returns on a rates signal must be volatility-standardised.**
Plain OLS t rejects on 77.3% of pure nulls when the regressor's volatility
co-moves with the return's. White HC errors fix the size (5.7%) and then destroy
the power (9.7% at ρ=0.05). Standardising both sides by EWMA vol gives size 3.7%
and power 100%. Use `signals.predictive_regression`, which reports `t_hc`,
`t_naive` and their ratio — expect 5–7 on raw, ~1 on standardised.

**Test and estimate are different regressions.** The standardised spec has correct
size and high power: use it to TEST. The shared vol divisor inflates its
correlation 2.2–2.8×, so it is not an estimator of magnitude. The raw spec recovers
ρ almost exactly: use it to SIZE. Reading the standardised ρ as the tradeable
correlation turns a Sharpe-0.47 effect into an apparent 1.30.

**Validate the harness before trusting a null.** Build a synthetic series with a
known effect and confirm the code recovers it, and that a true null does *not*
pass. `signals.synthetic_check` does this and `scripts/rate_path_study.py` refuses
to run on real data until it passes. This is not ceremony: a calibration simulator
that paired `x_t` with a contemporaneously-correlated `y_t` returned power = size
in every cell, an apparent null from a harness with no signal in it.

**Autocorrelation SEs must be the HC sandwich**, `stats.acf_se_hc`. Not `1/√T`, and
not the variance-inflation form (inconsistent: size 27% at T=2000 → 47% at
T=5000). On FX vol dynamics the correct SE is 4.9–7.4× the textbook value.

**Variance ratios must use the robust z**, `stats.variance_ratio`. The textbook
homoskedastic test declares pure GARCH random walks mean-reverting 79.5% of the
time.

**Hurst exponents need vol-standardised returns**, `stats.ewma_standardise` first.
Raw-return DFA bias is −0.099 against a truth of 0.5.

---

## Two bars, not one

Significance and tradeability are a factor of three apart. At the published median
73% backtest-to-live Sharpe haircut:

| | Backtest SR | implied t (20y) | net @10% vol, 2 trades/wk |
|---|---|---|---|
| detection (t=2) | 0.45 | 2.0 | +0.57%/yr |
| multiple testing (t=3) | 0.67 | 3.0 | +1.16%/yr |
| live SR 0.30 | 1.11 | 4.97 | +2.35%/yr |

**Never set a kill criterion at t=2 alone.** State a tradeability bar separately.
A result can be significant and unprofitable.

**The limit:** detectable Sharpe at t=2 is `2/√(years of data)`, independent of
holding horizon — the √n and √(252/h) factors cancel exactly. Horizon is a question
about costs and capacity, never about power. Only cross-sectional breadth moves
this.

---

## Timestamp traps

All of these manufacture *positive* results from no signal.

1. **FRED `DEXJPUS` is a 12:00 ET noon snapshot, not a close.** Never pair it with
   a US equity or VIX close — the "predictor" is then observed four hours after the
   "predicted" print. Use the Dukascopy bars. Nikkei is worse: Tokyo closes ~14h
   before the US.
2. **A matched-date US-minus-Japan yield spread mixes two information sets across
   the date line.** Treasury's curve for *T* publishes after the US close on *T*;
   MOF publishes the JGB curve for *T* in the JST evening. Use
   `signals.build_spread`, which lags the US leg one business day and the JGB leg
   none, and records per-leg staleness.
3. **CFTC COT** is a Tuesday snapshot released Friday ~15:30 ET — first actionable
   bar is the following Monday, four trading days later.
4. **MOF daily intervention detail publishes quarterly** (~100 days late). Regime
   labelling only, never a contemporaneous input. Its monthly periods run ~29th to
   ~28th, not calendar months.

5. **Bid-only substitution overstates BOTH directions by exactly one spread** -
   long entry too low, short exit too low, same sign and same size. A known
   constant, correctable by adding a spread estimate, not a direction-dependent
   distortion. HistData timestamps are **NY local WITH DST**, not the fixed EST
   its own FAQ claims (verified in `docs/DATA.md`); trust the catalogue. Except
   trap 8.
6. **Synthetic spread must be keyed on the EXECUTION hour, not the bar's hour.**
   `events.quote_at(ts)` fills on the bar at `ts - 1min`, so the bar labelled T
   is the fill for a trade at T+1min. Keying on the bar's own hour overcharged
   spec 004's 08:00 JST entry by 0.24 pips - it paid hour 7 (0.600 pips, still
   decaying from the 06:00 rollover spike) instead of hour 8 (0.360). Fixed in
   `datasets._with_synthetic_ask`; `exec_lag` must track `quote_at`'s offset.
   **This trap was documented before the fix was committed.** Spec 004's published
   numbers came from a working tree that had the fix while the repo did not, so
   until this commit the repo under-stated prefix returns by 0.230 pips a trade
   and could not reproduce its own spec. If a result cannot be reproduced from a
   clean clone, the result does not exist yet.
7. **The spread profile is DST-smeared at JST hours 6-8.** The 17:00 NY rollover
   lands at 06:00 JST under EDT and 07:00 under EST. Japan has no DST, so Tokyo
   patterns are crisp and only the rollover moves. Specs 001/004 trade
   08:00-11:00 and are unaffected; anything trading JST 6-8 must key the profile
   on (JST hour, NY DST flag).
8. **From 2019 HistData's raw clock changes on EU DST dates, not US ones.** In the
   weeks where the two disagree (2nd to last Sunday of March; last Sunday of
   October to 1st Sunday of November) the stored bar labelled T held the true T+60
   price. `datasets.fix_histdata_dst` corrects it in the loader and refuses a file
   that already looks correct; read HistData only through `load_minute`, and re-run
   `scripts/histdata_alignment_check.py` after any rebuild. Month-level checks hid
   it, because the error is one week inside otherwise aligned months: check
   alignment day by day, and against an independent timestamp (the Fed H.10 noon
   rate) where no second price source exists. It moved 21 / 22 of spec 004's B
   trades and strengthened the result, mostly through three volatile days.

---

## Gotchas in this repo

- `calendars.gotobi_days()` **includes the last business day of the month**, so
  spec 001's treatment group bundles two mechanisms. Month-end is 16.7% of those
  days pre-holdout and roughly 28% of the measured effect. `specs/004` separates them.
- **Roll-back rules make calendar groups differ by weekday.** A Gotobi date on a
  weekend rolls back to Friday, and one inside a holiday break rolls back onto the
  day before it, so B is 44% Fridays and pre-closure days are B or A by
  construction (none of the 41 Mon–Thu days before a 4+ day break in 2007–2024 is
  C). Non-Gotobi Fridays have their own Tokyo-morning move. See the hard rule
  "Compare against control days, not zero" and `scripts/004_weekday_breakdown.py`.
- CME `6J`/`MJY` are quoted **USD per JPY — the inverse of spot**. One USDJPY pip
  is 0.396 MJY ticks = $0.494/contract, not one tick. MJY maintenance margin is
  $280 and settlement is **deliverable**.
- Size for gap survival, not margin. A 700-pip intervention gap is 123.6% of one
  MJY contract's maintenance margin, so margin availability is misleading as a
  sizing guide. A stop is not protection: USDJPY moved 160.17 → 156.60 in ~11
  minutes on 2024-04-29, and MOF repeatedly chooses thin-liquidity windows.
- **`docs/DATA.md` is the only data catalogue.** `data/README.md` carried a second
  copy of every table and the two drifted in opposite directions — the HistData
  "Complete" claim corrected in one, `dgs2.csv`/`jgbcme_all.csv` catalogued in the
  other — so each held one current fact and one stale one, indistinguishably.
  `data/README.md` is now a pointer. Record provenance in `docs/DATA.md` only.
  This is the third time in this repo a fact stored twice was corrected once (the
  others: the HistData DST note, located twice in the wrong file; and the
  exec-hour fix, documented in two places while existing in neither).
- `docs/DATA.md` called `histdata_bid_2015_2025.parquet` **"Complete"**. It is not.
  Spec 005 found **up to ~60% of minutes missing between 08:00 and 24:00 UTC from
  February to July 2023**. Spec 004's prefix entry is 23:00 UTC, inside that
  window; its 00:55 exit and the entire postfix leg (00:55 -> 02:00) are outside
  it. So the gap lands on the entry leg of the only surviving result and nowhere
  else. Counted on DST-corrected bars: 46 of 60 2023 prefix B days trade; the gap
  fill restores the rest.
- `data/` and `results/` are gitignored. A fresh clone has no data; symlink it or
  work in the clone that has it.

---

## Current state

| Spec | Status | Note |
|---|---|---|
| 001 gotobi / Tokyo fix | **upheld (both rules), mechanism unconfirmed** | Results recorded 2026-11-26 (spec 001 *Results*): 1a net +1.85p t 2.97, 1b +1.74p t 3.45, both beat control at p ≤ 0.005. The 2022+ criterion is read as mean > 0 (t ≥ 2 in a fifth of the sample has ~20% power); `PESSIMISTIC` as full-sample t ≥ 2. On first-run code 1a failed `PESSIMISTIC` (t 1.62). | 004 showed B differs from unmatched C, which restates 001's own claim on a subset; matched by weekday it does not clear 2.5. Its A-vs-B separation was uninformative, so month-end is NOT ruled out as a contributor. Do not restate 001 as Gotobi-proper on 004's authority |
| 002 intervention disclosure | **rejected** | real effect, 1.3 episodes/yr, SR 0.24-0.43 |
| 003 rate-path revision | **rejected below SR 0.73; undecidable 0.73-0.98** | max abs(t_hc) 1.78 vs 2.81 bar, right sign at all 4 h (restated 2026-11-26 on current loaders and a past-only EWMA seed). NOT a well-powered null: MDE SR is 0.98 against a 0.73 tradeability bar |
| 004 turn-of-month separation | **B beats zero and unmatched control; Gotobi-specific effect not established; separation unanswerable** | DST-corrected. B net of base costs vs zero: prefix +2.301p t +3.47, postfix +1.683p t +3.34. B vs unmatched C (mid): t +3.28 / +2.80; **vs weekday-matched C: t +1.91 / +2.28, below 2.5**. A-vs-B t -1.39 / +0.21, MDE ~2x the effect: month-end not ruled out. Kill criterion 4 passes; 5 pending the measured spread (gap fill running) |
| 005 rate-path trade test | **rejected** | independent H3 retest, all three variants; NW t -0.24/+0.23/-0.06 vs 3.0 bar (restated 2026-11-26 on current loaders). Financing alone took ~5 pips/trade |

Eight signal families examined, six dead. Spec 004 is the only surviving effect,
and the 2026-11-25 review narrowed it. On DST-corrected bars, B (Gotobi-proper)
Tokyo mornings beat zero net of base costs (prefix +2.301 pips, t +3.47; postfix
+1.683, t +3.34; 6/6 sub-period cells positive) and beat unmatched control days.
But B is 44% Fridays against 11% in C, non-Gotobi Fridays rise on their own, and
**matched by weekday, B vs C is t +1.91 / +2.28, below the declared 2.5 bar**. A
Tokyo-morning USD rise on B days is established; that it is Gotobi settlement
rather than a Friday or pre-closure effect is not. The matched MDE (2.73 / 2.14
pips) is above the matched estimates, so this is under-powered, not refuted.

Tradeability: kill criterion 4 (`PESSIMISTIC`) passes. Criterion 5 is evaluated per
trade and is pending the measured spread. On the field's standard test (net t under
`PESSIMISTIC`) the cost headroom before t falls to 2.5 is 0.24 pips (prefix) and
0.03 (postfix) at the assumed 0.36 / 0.27-pip spreads, so the measured spread
decides it (`docs/research/Gap fill cost methodology standards.md`).

What would settle both: the spec 004 gap fill. `scripts/download_gap_fill.py` is
fetching Dukascopy bid/ask for 2007-2014 and a 2015-2024 spread sample (status in
`specs/README.md`, *Dukascopy fetch*). Its analysis, including the weekday-matched
test, is pre-declared in spec 004 *Gap fill*; no filled data has been viewed.

Specs 003 and 005 test H3 independently, by different methods, and both reject it.
005 defers to 003's standardised regression as the proper test and keeps its own
raw-pips slope (t +1.89) as descriptive only. Neither supersedes the other.

The binding constraint is no longer method, and no longer purely hypothesis count -
it is that the one surviving effect is the same size as a cost not yet measured,
and its Gotobi specificity is not established. Spec
005 adds a second constraint on top: at a days-to-week horizon on spot, financing
is larger than any effect this repo has found, so new hypotheses should be
intraday, or on MJY, or not worth testing.

Context: `handoffs/README.md` first, then
`Research/Strategy/Hypothesis Review H1 to H3.md` and
`Research/Strategy/H1 Intervention Reaction.md`.
