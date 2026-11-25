# Handoff — 2026-11-25 01:30

Written at the end of a long session for whoever picks this up next, including a
cold CLI session. `CLAUDE.md` has the standing rules; this file has the state,
the next action, and the mistakes made getting here so they are not repeated.

---

## 1. Where things stand

| Spec | Verdict | Why |
|---|---|---|
| 001 gotobi / Tokyo fix | **upheld** | 004 confirmed the mechanism lives in Gotobi-proper. Its own file still says "gotobi days" and should be restated. |
| 002 intervention disclosure | **rejected** | Real effect (−0.172 to −0.269 yen, robustness-tested) but 1.3 episodes/yr, Sharpe 0.24–0.43. Risk overlay only. |
| 003 rate-path revision | **rejected** | Well-powered null (86% simulated power at ρ=0.05). Max abs(t_hc) 1.80 vs the 2.81 bar. Right sign at all four horizons, too small. |
| 004 turn-of-month separation | **passed; tradeability undecidable** | Gotobi-proper differs from control, t +3.04 / +2.62, MDE below the published effect. As-run Sharpe **0.74**, the only result here to clear the t=3 bar of 0.71. |

Four families died to literature (trend, calendar-as-signal, carry, risk
appetite). Two died to calibration (H2a year-end, H1's daily test). One died to
data (003). One survives (004), blocked on cost provenance.

---

## 2. The one next action that matters

**Download genuine Dukascopy bid/ask for the Tokyo-morning window, 2007–2024.**

Spec 004's Sharpe is 0.74 under the measured 2024–26 raw-spread profile and 0.44
under plausible era-scaled spreads. That entire swing is one unverifiable
assumption. The effect is 1.5–2.1 pips; the spread uncertainty is 0.36 measured
against 0.9–1.8 plausible. So **"is this tradeable" is literally "what was the
retail spread in 2007–2024"**, and no amount of further statistics answers it.

Specs 001 and 004 trade 08:00–11:00 JST = 23:00–02:00 UTC, so you need five UTC
hours per day, not twenty-four:

```
hours = (22, 23, 0, 1, 2)     # padded either side for quote_at
~4,700 non-Saturday days x 5 = ~23,500 requests   (vs ~112,800 full-day)
roughly 1-2 hours wall clock, ~21% of full-day storage
```

Hour 0 also covers spec 003's 00:00 UTC decision timestamp, so one windowed
download serves both.

**Critical:** a windowed download is **not** interchangeable with a full one, and
`load_minute_bars` cannot tell the difference. Keep it in a separate `out_dir`
tree. `UNACCOUNTED-dukascopy.diff` (see §5) implements the `hours` parameter and
this warning; its arithmetic checks out.

Then re-run `scripts/turn_of_month_study.py` and
`scripts/004_spread_sensitivity.py` on real bid/ask. That converts spec 004 from
undecidable to decided, either way.

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
- **MOF daily intervention detail publishes quarterly** (~100 days late), so it
  can label regimes but never be a contemporaneous input. The window
  2026-10-29 → 2026-11-26 — when USDJPY tested 160 three times — published
  2026-11-30 19:00 JST. Worth checking whether anything landed.

---

## 6. Repo hygiene pending

- `specs/001-gotobi-tokyo-fix.md` should be restated: its treatment group is
  Gotobi-**proper**, and month-end is 17% of the days it currently includes.
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
