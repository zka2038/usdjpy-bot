# Handoff — 2026-11-25 01:30

Written at the end of a long session for whoever picks this up next, including a
cold CLI session. **Updated late on 2026-11-25** after the during-fetch session
(record: `HANDOFF-2026-11-25-during-fetch.md`): §1, §2, §4, §5 and §6 carry its
results; every superseded number is in §4. `CLAUDE.md` has the standing rules; this file has the state,
the next action, and the mistakes made getting here so they are not repeated.

---

## 1. Where things stand

| Spec | Verdict | Why |
|---|---|---|
| 001 gotobi / Tokyo fix | **upheld (both rules); mechanism not established** (results and criteria reading recorded 2026-11-26 in spec 001 *Results*) | 004's A-vs-B separation is uninformative and its weekday-matched B-vs-C is below 2.5, so do **not** restate 001 as Gotobi-proper (the earlier advice to restate it is withdrawn). |
| 002 intervention disclosure | **rejected** | Real effect (−0.172 to −0.269 yen, robustness-tested) but 1.3 episodes/yr, Sharpe 0.24–0.43. Risk overlay only. |
| 003 rate-path revision | **rejected below SR 0.73; undecidable 0.73-0.98** | Max abs(t_hc) 1.78 vs the 2.81 bar (restated 2026-11-26), right sign at all four horizons. The "well-powered null" label was wrong: MDE Sharpe is 0.98 against a 0.73 tradeability bar. |
| 004 turn-of-month separation | **B beats zero and unmatched control; Gotobi specificity not established; separation unanswerable** | DST-corrected. Net vs zero t +3.47 / +3.34. B vs C t +3.28 / +2.80 unmatched, **+1.91 / +2.28 weekday-matched** (B is 44% Fridays). Declared A-vs-B t -1.39 / +0.21, uninformative. Criterion 4 passes; 5 pending the measured spread. |
| 005 rate-path trade test | **rejected** | Independent H3 retest built in the CLI without `CLAUDE.md`. Three variants, NW t −0.24 / +0.23 / −0.06 against a 3.0 bar (restated 2026-11-26), sub-periods flipping sign. Correctly declares itself descriptive and defers to 003. |

Four families died to literature (trend, calendar-as-signal, carry, risk
appetite). Two died to calibration (H2a year-end, H1's daily test). One died to
data (003). One survives (004), narrowed by the 2026-11-25 review: not established as
Gotobi-specific, and its tradeability waits on measured spreads.

---

## 2. The one next action that matters

*Rewritten late on 2026-11-25. The earlier text is in git history; its numbers were
superseded by the HistData DST fix and the spec 004 review (see §4).*

**Let the gap fill finish, then run spec 004's pre-declared filled analysis.** What
is being fetched, why, and the fetch's status are in `specs/README.md`, *Dukascopy
fetch*; how the data is used is fixed in spec 004's *Gap fill* section and its dated
amendments (the DST fix, the weekday-matched test, and *Amendment: field
standards*). Do not read `data/tokyo_hours/` until every stage of
`scripts/download_gap_fill.py` has 0 requests left. There is no deadline; restart
the fetch if it stops. The analysis code is the during-fetch handoff's Task 3 and is
not written yet. Write it against synthetic tick trees first.

**What spec 004 says now (as run, DST-corrected).** B (Gotobi-proper) Tokyo mornings
beat zero net of base costs: prefix +2.301 pips, t +3.47; postfix +1.683, t +3.34.
They beat unmatched control days on cost-free mid prices (t +3.28 / +2.80). But B is
44% Fridays against 11% in C, and non-Gotobi Fridays rise on their own: **matched by
weekday, B vs C is t +1.91 / +2.28, below the declared 2.5 bar.** The Gotobi-specific
claim is under-powered rather than refuted (matched MDE 2.73 / 2.14 pips). Kill
criterion 4 (`PESSIMISTIC`) passes. Criterion 5 is evaluated per trade and is pending
the measured spread; on the field's standard test (net t under `PESSIMISTIC`) the
cost headroom is 0.24 pips on prefix and 0.03 on postfix at the assumed spreads, so
the measured spread decides it. Field standards for every cost choice:
`docs/research/Gap fill cost methodology standards.md`.

**The trial budget.** Count specs (N=5) for now; legs and variants stay open if the
specs converge. Spec 004 passes the Deflated Sharpe hurdle up to N=17 on prefix (N=10
without its single +209-pip trade on 2011-03-18) and N=11 on postfix: **about five
hypotheses of headroom** on USDJPY 2007-2024, not three. At N=18 (all of 006-018)
neither leg clears. The DSR is against zero, not matched control. Route specs
006-018 onto other JPY crosses, or accept what they cost.

**Spending the holdout is still wrong.** ~70 prefix trades give SE 2.355 pips against
+2.301, expected t 0.98, power 16% at alpha 0.05; against matched control it is
lower again.

**The way out is breadth, which this repo's own limit section already names.**
Detectable Sharpe is `2/sqrt(years)` whatever the horizon, and only
cross-sectional breadth moves it. Spec 004 is one pair, one window, one flow. The
gotobi mechanism is JPY-side importer settlement demand, so it should appear in
EURJPY, AUDJPY and GBPJPY on the same dates and in the same Tokyo window. Testing
the same pre-declared rule across four pairs multiplies effective n without
waiting two years, and a mechanism that shows up in one pair and not the others
is evidence against the mechanism rather than for the pair. That is the highest-
value next study after the gap fill, and the weekday result makes it more so: a
Gotobi flow should appear on Gotobi days in every JPY pair, while a Friday effect
need not.

**Financing changes what is worth testing at all.** Spec 005's most useful output
is not its verdict but its cost line. IBKR's skim is 2.0% a year of notional in
either direction, which is **0.883 pips per calendar day held** at 159 — 4.42 pips
over five calendar days, before the rate differential. Each of spec 005's three
variants gave up about 5 pips a trade to it. Against that, the largest effect
eight signal families have produced is 2.3 pips (spec 004 prefix, DST-corrected).

So the days-to-week premise this project started from is dead **on spot**, and not
for statistical reasons: the broker takes more than twice the best available edge
before the strategy does anything. One overnight hold alone costs 0.88 pips, which
is 38–52% of spec 004's entire 1.7–2.3 pip effect. Spec 004 survives only because
it holds about two hours and crosses no night.

Three ways forward, in the order their cost structure favours them: stay intraday;
move to MJY futures, which carry no financing skim (margin $280, 0.396 ticks per
pip, deliverable — all in `CLAUDE.md`); or widen the pool only to hypotheses whose
holding period is hours. Do not test another days-to-week spot idea without
costing financing first.

**Second priority, if 004 resolves negative:** widen the hypothesis pool. Two
testable ideas produced one marginal survivor. A tradeable result needs ten to
fifteen mechanism-grounded hypotheses — more sources of *forced* trading:
Japanese lifer hedge-ratio resets, index rebalance flows, option-expiry pinning,
JGB auction cycles, cross-asset basis.

---

## 3. Do not do these

- **Do not set a kill criterion at t=2 alone.** Detection and tradeability are a
  factor of three apart. At the 73% live haircut, a result clearing t=3 still
  yields ~1.2%/yr. State a tradeability bar separately. (Spec 003's bar was
  written as 0.67; for its actual 16.7-year span it should be 0.73.)
- **Do not treat an unconditional autocorrelation test as a gate.** 80% power
  against ρ = −0.05 — an effect implying Sharpe 0.79 — needs ~689 years of daily
  data. It survives only as a diagnostic, and asymmetrically: a null is
  uninformative; a strongly significant result means suspect the *data*.
- **Do not read the standardised ρ as a tradeable correlation.** The shared vol
  divisor inflates it 2.2–2.8×. Test with the standardised spec, size with the
  raw one. Note `rate_path_signal` currently bakes in the vol scaling, so the
  "raw" column is not fixed-notional and `sharpe_from_raw` is mislabelled.
- **Do not report a null without its MDE.** H1 was rejected because its daily MDE
  was 174–314 pips against a 17–27 pip effect — impossible, not negative.
- **Do not use `macro_daily()` without `signals.build_spread`.** It joins US and
  Japan yields on matched dates, which mixes two information sets across the date
  line. It also returns `DEXJPUS`, the noon snapshot.
- **Do not use `cot()`'s `available_from` for a JST entry.** It reports Friday,
  but the release is Friday 15:30 ET = Saturday 05:30 JST. The first usable Tokyo
  bar is the following Monday.
- **Do not trade JST hours 6–8 off the current spread profile.** It is keyed on
  JST hour, but the 17:00 NY rollover lands at 06:00 JST under EDT and 07:00
  under EST, so those hours are DST-smeared. Key on (JST hour, NY DST flag) if a
  spec needs them.

---

## 4. Numbers that were wrong at some point tonight

Listed because the chat transcript contains all of them and only the last value
in each line is right.

| Quantity | Wrong values quoted | Correct |
|---|---|---|
| prefix_long all-in cost | 1.44 → 1.19 → 1.44 | **1.20 pips** (0.836 + 0.360) |
| Spec 004 `PESSIMISTIC` bar | 1.84 | **1.60 pips** (1.236 + 0.360) |
| Spec 003 tradeability bar | 0.645, 0.67 | **0.73** (3/√16.7) |
| H1 disclosure-effect Sharpe | 3.6 | **0.24–0.43** (9× overstated: ~3 events/yr, not ~250) |
| Bid-only substitution bias | "asymmetric, won't wash out" | **symmetric, exactly one spread**, correctable |
| HistData timestamps | "fixed EST, no DST" | **NY local WITH DST** (verified in `docs/DATA.md`) |
| Spec 004 power basis | 3-day window | **115/65-minute windows** |
| Vol-standardisation in 003 | "unnecessary, SE ratio 1.0" | **necessary**; applied upstream in `rate_path_signal`. Unscaled gives SE ratio 5.98 and 13% power; scaled gives 0.49 and 86% |
| 004 sub-period stability | "no period significant, signs flip" | **6/6 cells positive, 4/6 at abs(t) ≥ 1.96** |
| Location of the HistData error | "it's in CLAUDE.md" | **`Research/Strategy/Initial Strategy Survey.md`**, now corrected in place |
| exec-hour spread fix | documented as "Fixed in `datasets._with_synthetic_ask`" | **was never committed** until the commit carrying this row; the repo could not reproduce spec 004 |
| spec 004 prefix Sharpe | 0.74 from a clean clone | **0.74 needs the fix; a clean clone gave 0.661.** The figure is right for correct code, and was not reproducible |
| spec 004 MDE | 4.8 / 1.8 / 1.0 pips (A/B/C) | **5.71 / 2.19 / 1.20** — printed at alpha=0.05 (t=1.96) while the kill criterion is t=2.5 |
| spec 003 MDE Sharpe | 0.89, then 0.97 | **0.98** — SE(rho) is `se_ratio/sqrt(n)`, not `1/sqrt(n)`; 0.97 → 0.98 on the 2026-11-26 restatement |
| spec 003 power | "86% at rho=0.05, well-powered" | **underpowered**; that figure is the harness's, and the harness gives t +5.78 where real data gives +1.78 at the same rho |
| `histdata_bid_2015_2025.parquet` completeness | "Complete, ~372k min/yr" (`docs/DATA.md`) | **not complete** — up to ~60% of minutes missing 08:00–24:00 UTC, Feb–Jul 2023. Corrected in `docs/DATA.md` |
| HistData UTC alignment | "NY local with DST", everywhere | **except from 2019 in the US/EU DST mismatch weeks, where bars were an hour early**; `datasets.fix_histdata_dst` corrects it (CLAUDE.md trap 8) |
| spec 004 headline, as run | prefix +2.068 t +3.15 SR 0.743; postfix +1.561 t +3.11 | **+2.301 t +3.47 SR 0.817; +1.683 t +3.34**, on DST-corrected bars. Three trades carry most of the change |
| "Gotobi-proper differs from control" | t +3.28 / +2.80 (unmatched), read as the mechanism | **weekday-matched t +1.91 / +2.28**, below 2.5: B is 44% Fridays, C 11% |
| spec 001 restatement | "restate as Gotobi-proper" (§1, §6) | **do not**; withdrawn |
| spec 004 power | 83% / 80% "vs this effect" | **observed power restates t**; predictive replication Φ((t−2.5)/√2) is 75% / 72.5% |
| spec 004 postfix live Sharpe | 0.10 | **0.198** pre-fix, 0.213 now (live = as run × 0.27; 0.10 was 0.27 × era) |
| spec 004 postfix era Sharpe | 0.42, "below detection" | **0.485**: a short pays its exit spread, not its entry spread |
| criterion 5 bar | ~1.84, then 1.60; "the DST fix flipped postfix to a pass" | **per-trade bar, pending the measured column**; 1.60 withdrawn, the flip was an artefact of the wrong spread |
| DSR from the trade distribution | "expect it to fall" | **prefix rose** (positive skew, from one trade), postfix fell slightly |
| trial headroom | three (passes to N=8) | **about five** (N=5 specs; limits N=10–17 prefix, N=11 postfix) |
| holdout power | 14% | **16%** (SE 2.355 vs +2.301) |
| spec 004 day counts | A 234, B 1159, month-end 17% | **216 / 1075, 16.7%** pre-holdout (the old counts ran into 2026) |
| spec 001 verdict | "upheld", never recorded in the spec; the report read 2022+ as t ≥ 2 | **upheld for both rules on current code**, 2022+ read as mean > 0 (t ≥ 2 there has 17-23% power at the full-sample effect). On first-run code 1a failed `PESSIMISTIC` (t 1.62), so the first "upheld" was unsupported for 1a. Decided 2026-11-26, after the results were seen |
| spec 003 table (first run, 2026-11-25) | std t_hc +1.80 / +1.17 / +0.81 / +0.95; raw rho 0.0253 / 0.0437 / 0.0318 / 0.0431; rho 0.0303 at h=1; MDE rho 0.0613 | **+1.78 / +1.15 / +0.75 / +0.88; 0.0259 / 0.0441 / 0.0314 / 0.0413; 0.0302; 0.0620.** First table ran before the exec-hour and HistData DST fixes and with `ewma_vol` seeded on the whole series; verdict unchanged. Restated 2026-11-26, confirmed from a fresh clone |
| spec 005 headline (first run, 2026-11-24) | 3,976 days; −0.73 / +7.16 / −0.54 pips, NW t −0.19 / +0.47 / −0.04; slope +0.96 t +2.19; V2 long t 1.91 | **3,971 days; −0.95 / +3.66 / −0.83, t −0.24 / +0.23 / −0.06; slope +0.86 t +1.89; V2 long t 1.70.** Ran before the exec-hour, HistData DST and BoJ-stamp fixes; verdict unchanged. Restated 2026-11-26, confirmed from a fresh clone |

Seven of these were caught by computing something rather than reasoning about it.
Two were caught by the CLI session and were both invisible-failure modes: a
holdout leak that produced plausible numbers, and a tz-naive reindex that
produced an empty result indistinguishable from a null. Neither raised an error.

**The operative habit: build a synthetic case with a known answer and confirm the
harness recovers it before trusting any null.** `signals.synthetic_check` does
this and `scripts/rate_path_study.py` refuses to touch real data until it passes.

---

## 5. Provenance questions left open

- **`UNACCOUNTED-dukascopy.diff`** (sent to bzk, not committed). Adds the `hours`
  parameter, `TOKYO_MORNING_HOURS`, and a `FileNotFoundError` guard to
  `load_minute_bars`. It appeared in the assistant's workspace clone without
  being written in that conversation, so it was deliberately not committed under
  that attribution. The code reads correctly and the request arithmetic checks
  out. Review and commit under your own name if you want it.
- **`data/calendars/mof_intervention_transcribed.csv`** was transcribed through a
  web reader, not downloaded byte-for-byte. Totals reconcile against MOF's
  published figures (¥11.735tn Apr–May 2026, ¥15.40tn Jul–Aug 2026, and the
  ¥0 print for 29 Sep – 28 Oct 2026 confirms Sept/Oct were clear). Run
  `fetch_official.py` and diff before relying on pre-2010 rows.
- **`bars_1min/dukascopy_bid_2007_2023.parquet`** is a third party's GitHub
  export: 40–65% complete across 2011–18, **2020 absent**, ends 2023-03. Spec 003
  ran on `combined` and therefore included it, so its pre-2015 observations are
  non-randomly selected. A re-run on `histdata` alone is the clean check and
  costs about half the sample.
- **The 2023 HistData gap lands on spec 004's entry leg and nothing else.** Up to
  ~60% of minutes are missing between 08:00 and 24:00 UTC from Feb to Jul 2023.
  Spec 004's prefix entry is 23:00 UTC — inside that window. Its 00:55 exit and
  the whole postfix leg (00:55 → 02:00) are outside it. Spec 005 skips unquoted
  decision days rather than filling them, and spec 004 should be checked for the
  same behaviour: if it drops those days the effect is on a smaller sample than
  reported, and if it fills them the prefix fills are wrong. **Counted 2026-11-25:
  it drops them; 46 of 60 2023 prefix B days trade on DST-corrected bars. The gap
  fill restores the rest.**
- **MOF daily intervention detail publishes quarterly** (~100 days late), so it
  can label regimes but never be a contemporaneous input. The window
  2026-10-29 → 2026-11-26 — when USDJPY tested 160 three times — published
  2026-11-30 19:00 JST. Worth checking whether anything landed.

---

## 6. Repo hygiene pending

- ~~`specs/001-gotobi-tokyo-fix.md` should be restated: its treatment group is
  Gotobi-**proper**, and month-end is 17% of the days it currently includes.~~
  **Withdrawn 2026-11-25.** This contradicted `CLAUDE.md` *Current state*, and spec
  004's weekday-matched test now shows Gotobi-proper does not clear 2.5 against
  matched control. Leave spec 001 as it is.
- The branch is `research/002-intervention-disclosure` but carries 003 and 004
  results too. Rename, or title the PR for what is actually in it.
- `data/` and `results/` are gitignored. The repo now lives on an exFAT external
  drive at `/Volumes/bzk Drive/usdjpy-bot`, with `core.fileMode false` and
  `core.precomposeunicode true` set. If `._*` AppleDouble files reappear and git
  reports "non-monotonic index", run `dot_clean -m . && find . -name '._*'
  -delete`. `COPYFILE_DISABLE=1` is in `~/.zshrc` to prevent it.
- The venv is on the internal disk at `~/.venvs/usdjpy-bot`, deliberately — a
  venv on removable media breaks on every unmount.

---

## 7. The honest summary

The apparatus is in better shape than the hypothesis list, which is the inverse
of how these projects usually fail. The statistics are validated — four
corrections to standard practice, each checked against synthetic controls — the
cost model is wired to the real venue, the data layer is catalogued and
cross-validated, and the power calibrations exist for every hypothesis tested.

What is missing is ideas, and one download. The surviving effect is real on
cost-free prices and period-stable across eighteen years, and whether it is worth
trading turns entirely on a spread nobody measured in 2007. That is a tractable
question with a known answer-shape, which is a better position than most of this
project has been in.

What this session changed, beyond the horizon: spec 004's numbers became
reproducible. They were written up from a working tree whose exec-hour fix was
never committed, so for several days the repo could not produce its own
headline result and nobody noticed, because the gap was 0.23 pips and everything
still looked plausible. The effect survives the correction and strengthens
slightly (t +2.80 to +3.15). What remains open is the separation, which needs
2.3x the month-end sample that 18 years provides, and tradeability, which needs
the spread. Breadth across JPY crosses addresses the first and tests the
mechanism rather than the result.

The one thing that has genuinely narrowed is the horizon. This began as a
days-to-week project; spec 005 priced that horizon at 4.42 pips of financing over
five days against a best-available edge of 2.1, so what remains is intraday spot
or MJY futures. That is a smaller project than the one that was started, and a
real answer rather than an open question — the kind of constraint worth having
early, because it removes a whole class of hypotheses from the queue before any
of them are tested.

*Added late on 2026-11-25:* the during-fetch session narrowed the one survivor. A
HistData clock error (EU DST dates from 2019) was found and corrected, which
strengthened spec 004 against zero. An independent review then found that its
Gotobi-proper group is 44% Fridays; matched by weekday it no longer clears the
declared bar. So the open questions are now three, not two: separation, Gotobi
specificity, and tradeability. The gap fill bears on the last two, and its use is
fixed in advance.
