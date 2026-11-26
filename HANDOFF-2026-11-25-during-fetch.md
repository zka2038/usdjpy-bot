# Handoff — 2026-11-25 17:00 UTC: work to do while the Dukascopy fetch runs

For a Claude CLI agent picking up from the session that chose and started the
spec 004 gap-fill fetch. This file covers **one thing**: what to do while that
fetch runs, and how not to contaminate it.

**Read first, in this order:**
1. `CLAUDE.md`: standing rules, inference rules, timestamp traps, repo gotchas.
   They all apply here. Where this file and `CLAUDE.md` disagree, `CLAUDE.md` wins.
2. `HANDOFF.md`: project state. Its §2 paragraphs about the download (five
   hours, ~23,500 requests, 1–2 hours of wall clock) are **superseded** by item 3.
3. `specs/README.md`, section *Dukascopy fetch: options and decision*: what is
   being fetched and why.
4. `specs/004-turn-of-month-separation.md`, section *Gap fill*: how the fetched
   data must be used. It is a pre-declaration and must not be revised after any
   filled data has been seen.

This file points to those documents rather than copying their numbers. A fact
stored twice in this repo has been corrected in one place only three times
already.

---

## 1. What the previous session did

Commits on branch `research/002-intervention-disclosure`, **not pushed**:

| Commit | What |
|---|---|
| `e7dcfa2` | `dukascopy`: tree guard (`_hours.json`), AppleDouble skip, backoff for rate limiting |
| `4aa99cc` | Option C chosen and recorded in the triage; spec 004 *Gap fill* declared; `docs/DATA.md` catalogues `data/tokyo_hours/` |
| `f5ba137` | `TOKYO_MORNING_HOURS = (22, 23, 0, 1)`, closed-hour trimming, `days` filter, `scripts/download_gap_fill.py` |

Also:
- `stash@{0}` holds local edits superseded by `origin/main`, verified line by line.
  Do not pop it.
- The branch's upstream is gone. Renaming it is the user's call.
- **One correction to numbers quoted in chat:** spec 004 has **1,075**
  pre-holdout B days, not 1,088. The missing trades are 193 prefix and 128
  postfix, not 206 and 141. The triage and spec 004 carry the corrected figures.

---

## 2. The running fetch: read this before running anything

`scripts/download_gap_fill.py all` is running **detached**:
- Started 2026-11-25 ~16:55 UTC, under `caffeinate -i`.
- Writes to `data/tokyo_hours/USDJPY/`.
- Log: `data/tokyo_hours/fetch.log`. PID: `data/tokyo_hours/fetch.pid`.
- It does the three stages in order at one request per 30 s, about 10,400
  requests, so **about 3.6 days if it is never blocked**, plausibly longer:
  1. Feb–Jul 2023 (~4 h)
  2. a 2015–2024 spread sample (~13 h)
  3. every weekday 2007–2014 (~70 h)

How to tell where it is:

```bash
tail -5 "data/tokyo_hours/fetch.log"                        # progress, HTTP 429s, restarts
pgrep -fl "download_gap_fill.py all"                        # still alive?
~/.venvs/usdjpy-bot/bin/python scripts/download_gap_fill.py all --dry-run   # what is left (filenames only)
```

If it has died, which an unmounted drive, sleep or reboot can cause, restart it
the same way. It resumes and skips finished days:

```bash
cd "/Volumes/bzk Drive/usdjpy-bot" && nohup caffeinate -i ~/.venvs/usdjpy-bot/bin/python -u \
  scripts/download_gap_fill.py all >> data/tokyo_hours/fetch.log 2>&1 &
```

A process started with `&` from an agent's shell may die when that session ends.
To make it outlive your session, start it with `subprocess.Popen([...],
start_new_session=True)`, as the current one was, and write its PID to
`data/tokyo_hours/fetch.pid`.

Stop it with `pkill -f "download_gap_fill.py all"`. A day is written only once all
of its hours are fetched, so killing it never leaves a partial file.

### Rules while it runs

**Data keeps arriving under your feet, so anything that reads
`data/tokyo_hours/` gives a different answer each time you run it.** The rules:

1. **Do not read the contents of `data/tokyo_hours/`.** No loading, no plotting,
   no "quick look". This is both a stability rule and a blinding rule: spec 004's
   gap fill is declared before the filled data is seen, and that only holds while
   nobody has seen it. Listing filenames and `--dry-run` are fine.
2. **Do not call `load_minute_bars(SYMBOL, DATA_DIR / "tokyo_hours")`.** It also
   writes a cache (`data/tokyo_hours/bars_USDJPY_1min.parquet`) whose staleness
   check is by mtime, so a mid-fetch cache can be served later.
3. **Send nothing to datafeed.dukascopy.com.** No probes, no `scripts/download.py`.
   The fetch shares your IP's rate limit, and a burst earned a ~6-hour block on
   2026-11-25.
4. **What is safe:** everything that reads `datasets.load_minute(...)`
   (`data/bars_1min/*.parquet`), `results/`, `data/macro/`, `data/positioning/` and
   `data/calendars/`. The fetch never writes those. `turn_of_month_study.py
   --source combined` is unaffected. Its `--source dukascopy-ticks` reads
   `DATA_DIR/USDJPY`, the 15-day 2003 tree, so do not use it.
5. **Develop the gap-fill code against synthetic tick trees in `tmp_path`**, not
   against the real tree (task 3).
6. **Run nothing that counts as a new hypothesis on USDJPY 2007–2024.** See
   `CLAUDE.md` on the trial budget. Every task below is verification,
   infrastructure or bookkeeping.

---

## 3. Tasks, in priority order

Python is `~/.venvs/usdjpy-bot/bin/python`. Tests:
`~/.venvs/usdjpy-bot/bin/python -m pytest -q tests` (15 pass at `f5ba137`).
If git reports "non-monotonic index", clean the AppleDouble files (`CLAUDE.md`,
HANDOFF §6). Commit with the repo's configured identity. Do not push unless the
user asks.

### Task 1: HistData UTC alignment in US summer — **DONE 2026-11-25**

> **Status:** settled. US summer is aligned, but from 2019 HistData's raw clock
> changes on EU DST dates, so the US/EU mismatch weeks were an hour early. The user
> chose to correct it in the loader (`datasets.fix_histdata_dst`) and re-run spec 004.
> Script, finding, triage item, spec 004 *Results* and a dated *Gap fill* amendment
> are all committed; `docs/DATA.md`'s HistData row has the evidence.
> - The as-run spec 004 numbers changed (prefix +2.301p t +3.47, n=881; postfix
>   +1.683p t +3.34). `results/004_*.csv` now holds the corrected trades; the pre-fix
>   trades are in `results/archive/004_as_run_pre_dst_fix/`. **Task 2:** reproduce
>   0.9744 (SR 0.1062, n=882) from the archive, then compute on `results/`.
> - **Still stale, on purpose:** `CLAUDE.md` (*Current state*, trial-budget
>   paragraph) and `HANDOFF.md` §2 quote the pre-fix numbers. They are updated after
>   the Task 2 DSR report, together, per Task 2's stop rule.

**Why first:** it is the one check that could move spec 004's headline numbers.
The triage lists it as open. `docs/DATA.md` says it is verified, and
`scripts/build_github_data.py` now converts from `America/New_York` with DST. But
nothing records that the parquet on disk was built by that version. If summer
timestamps are an hour off, every 2015–2024 summer trade in spec 004 entered and
exited at the wrong minute.

**Method:**
- Compare bid closes of `histdata_bid_2015_2025.parquet` against
  `dukascopy_bid_2007_2023.parquet` (overlap 2015-01 to 2023-03, gappy) and against
  `eightcap_bidask_2024_2026.parquet` (2024-06-19 to 2025-04).
- Use offsets of −60, 0 and +60 minutes. Compute the median absolute difference on
  common minutes, **month by month**, and split by US DST (EDT vs EST).
- Also check the DST transition weeks, where `ambiguous="NaT"` drops the repeated
  hour.

**Done when:**
- A script exists (e.g. `scripts/histdata_alignment_check.py`).
- Its result is recorded in the HistData row of `docs/DATA.md`, the only
  catalogue.
- The triage's "Verify HistData UTC alignment" item is closed or restated.

**If any month's best offset is not 0, stop and report to the user before doing
anything else.** It would affect spec 004's as-run figures and the 2023 part of
spec 004's step 0.

### Task 2: Deflated Sharpe from the real trade distribution — **DONE, propagated 2026-11-25**

> **Status 2026-11-25:** `scripts/004_deflated_sharpe.py` reproduces 0.9744 / N=8 on
> the pre-DST-fix archive. On corrected trades, at N=5 specs: prefix DSR 0.988
> (normal) / 0.990 (sample moments), postfix 0.984 / 0.981. The sample-moment gain on
> prefix rests on one trade (2011-03-18, +209 pips); without it max N falls from 17
> to 10. **The user decided: count specs (N=5) for now; legs and variants stay open
> if specs converge.** Propagated late on 2026-11-25: `CLAUDE.md` (trial budget,
> holdout power, MDE example, traps 5 and 8, gotchas, *Current state*) and
> `HANDOFF.md` (§1, §2 rewritten, §4 rows, §5, §6, §7). Headroom stated as about
> five hypotheses (limits N=10–17 prefix, N=11 postfix).
> - An independent review on 2026-11-25 found a weekday confound (B 44% Fridays, C
>   11%): weekday-matched B vs C is t +1.91 / +2.28, below 2.5. Spec 004 now declares
>   a matched test and evaluates kill criterion 5 per trade. See spec 004 *Results*.
>   Note the DSR is against zero, not against matched control.

`CLAUDE.md`'s trial-budget paragraph quotes DSR 0.9744 at N=5 and the pass-up-to-N=8
headroom. Both assume skew 0 and Pearson kurtosis 3, and it says to expect them to
fall once computed from the trades.

**Method:**
1. From `results/004_prefix_long_B_gotobi_proper.csv` and the postfix file, take
   per-trade `net_pips`.
2. **First reproduce** 0.9744 with skew 0 and kurtosis 3, the per-trade SR
   0.1062 and n=882. If you cannot, the results CSVs may be stale: regenerate them
   with `scripts/turn_of_month_study.py` on committed code.
3. Then recompute with the sample skew and **Pearson** kurtosis
   (`scipy.stats.kurtosis(..., fisher=False)`), using `stats.deflated_sharpe`.
   Report DSR at N=5 and the largest N that still clears 0.95, for both legs.

These are as-run figures, which is legitimate now. The filled versions are item 7
of spec 004's *Gap fill* list and come later.

**Report to the user before editing `CLAUDE.md` or `HANDOFF.md`.** The headroom
number governs which sample every future spec may spend.

### Task 3: write spec 004's gap-fill analysis before the data arrives — **DONE 2026-11-26 (code); run pending the fetch**

> **2026-11-26:** written and tested, not run on real data. `scripts/004_gap_fill_analysis.py`
> (`--check` for gate status; refuses until every stage is complete), library
> `src/usdjpy/gapfill.py` and `src/usdjpy/tradeability.py`, tests `tests/test_gapfill.py`
> (14, synthetic trees: hour and level offsets step 0 must catch, a gap filled from
> the tree with both legs, the spread hierarchy, the gate, the labels). Smoke-run end
> to end on a stand-in tree built from the export. Details the spec left open are
> fixed in spec 004's dated *Implementation note*.
>
> **Earlier status 2026-11-25: questions settled, code not yet written.** The ambiguities
> below, and six more, were researched against field practice
> (`docs/research/Gap fill cost methodology standards.md`) and decided by the user.
> The decisions are spec 004's *Amendment: field standards*. Build the analysis to
> that section: own quote first, else stage 2 yearly mean; no-quote trades imputed
> by (fill bar × year) and flagged; no fetch deadline; and every reported-only
> diagnostic it lists. The criterion 5 diagnostics (95% label, break-even at t = 2.5
> and 1.645, bp t at own price, bp-stability test before the 159 view) are
> implemented in this task's code, not as a separate edit to
> `004_spread_sensitivity.py`.
> - The fetch died once (about 22:43–23:02 UTC, no traceback) and was restarted
>   with a dated line in `fetch.log`. Check it is alive before relying on it.

Implement spec 004's *Gap fill* section exactly: step 0 (both parts), the filled
analysis, the measured-spread cost column, and re-derived figures 1–7, each with
*as run* and *filled* columns. Writing it now, unseen, means the eventual run
involves no choices made after seeing the data.

Requirements:
- **Refuse to run until the fetch is complete.** Reuse `planned()` from
  `download_gap_fill.py`: every stage must have 0 requests left.
- **Fills use stage 1 and stage 3 dates only.** Stage 2's sparse 2015–2024 days
  are a spread source, never a price source.
- **Both legs of a filled trade come from the Dukascopy tree.**
- **Test with pytest on synthetic tick trees in `tmp_path`**, including:
  - a constructed source offset that step 0 must catch
  - a gap that must be filled from the right source

**Ambiguities to put to the user, not resolve silently.** If you find others,
list them too.
- **"Dukascopy spread at its own execution bar".** This could be the bar's
  last-quote `ask − bid`, which is what a fill at that bar pays, or the minute's
  mean `spread` from `ticks_to_minute_bars`. The previous session's view: use
  last-quote `ask − bid`, since that is what `quote_at` fills on.
- **How the measured spread is applied to as-run 2007–2014 trades** whose bid comes
  from the export. Presumably the export bid plus the measured Dukascopy spread at
  the same minute, replacing the synthetic spread. Confirm.

Any amendment to the spec text must be dated and must state that no filled data
had been viewed when it was made.

### Task 4: hygiene — **DONE 2026-11-25**

> **Status:** all items done. `calendars.gotobi_days` pads from the first of
> `start`'s month and raises instead of overflowing; its month-start output is pinned
> by checksum in `tests/test_core.py`, and the spec 004 study re-runs byte-identical.
> The A/B/C partition is now `calendars.turn_of_month_groups`, shared by the study and
> the gap-fill analysis. The stale financing item is struck in the triage; the
> HistData item was restated under Task 1. `HANDOFF.md` §2's download paragraphs are
> replaced by a pointer, and the spec 001 contradiction is settled (do not restate).

- **Fix the `calendars.gotobi_days` bug.**
  - It loops until the date overflows when `start` is late in a month, e.g.
    `gotobi_days(date(2007,1,31), ...)`, because `pad_start` is `start − 15
    days` while the month loop starts at day 5 of `start`'s month.
  - Pad from the first of `start`'s month instead.
  - Add a test that output is unchanged for month-start ranges, which is what the
    studies use, and that late-month starts now work.
- **Correct stale items in the triage's *Harness gaps* list** (`specs/README.md`).
  "`costs.py` has no overnight financing" is wrong: `costs.CostModel.financing_pips`
  exists. The HistData item is closed or restated by task 1.
- **Replace HANDOFF.md §2's download paragraphs** with a pointer to the triage's
  *Dukascopy fetch* section. Do not copy its numbers.
- **Do not restate spec 001 as Gotobi-proper.** HANDOFF §6 asks for it, but the
  newer `CLAUDE.md` *Current state* says explicitly not to on 004's authority. Flag
  the contradiction to the user and change neither.

### Task 5: harness gaps the triage lists — **DONE 2026-11-26**

> **Status:** built and tested on synthetic data (`tests/test_harness.py`, 32 tests; 94
> pass in all). No strategy was run.
> 1. `datasets.load_minute(source, ohlc=True)` appends `bid_open`, `bid_high`,
>    `bid_low` for every source, shifted with the close by the HistData DST fix. Default
>    off, so no caller's frame changes. On the real files the plain columns are identical
>    with and without it, and there are 0 bars with high < max(open, close),
>    low > min(open, close) or NaN in any source. No source has ask extremes.
> 2. `events.PERIODS_2015_2024` and `summarize(..., periods=)`; the default is unchanged.
> 3. `events.timestamp_trades` (explicit UTC entry/exit, side per trade) and
>    `events.at_local` (date + offset + local clock time, so "16:50 ET on T+3" holds across
>    DST). It shares one pricing core with `window_trades`, which adds three trailing
>    columns: `nights` (17:00 New York rolls held, `costs.roll_times`), `financing_pips`
>    (per roll, at the rates published before it) and `mae_pips` (needs `ohlc=True`).
> 4. `src/usdjpy/portfolio.py`: carried positions on any UTC schedule, the spec 014
>    threshold rule, nightly financing, `CostModel` costs (a flat round trip costs exactly
>    what `window_trades` charges), holdout stop, `apply_multiplier`/`on_schedule` for spec
>    017, `quotes_from_mid` for the H.10 version, and `summary` (Sharpe, skew, max
>    drawdown, worst period, CVaR 5%, return/max drawdown).
> 5. `datasets.h10_daily()`; `histdata_alignment_check.py` now reads through it.
>
> **Defects fixed on the way:**
> - `window_trades` checked the holdout on the entry date only, so a window rolling past
>   New Year 2025 read holdout bars. Exits on or after `HOLDOUT_START` 00:00 UTC are now
>   skipped too.
> - `window_trades` charged no financing on windows held through 17:00 New York (specs
>   008 C, 012 A). Both helpers now charge it, and raise if such a trade has no rates.
>
> **Behaviour preserved, by diff** against a clean export of `0dd3c9d`:
> `turn_of_month_study.py`, `gotobi_study.py` and `histdata_alignment_check.py` give
> identical stdout. Every original trade column is text-identical in all 8 trade CSVs
> (7,786 rows); the new columns are all 0 / 0.0 / NaN, since specs 001 and 004 hold no night.
> All 9 alignment CSVs are byte-identical. The clean export also reproduced the shared
> `results/004_*.csv` byte for byte.
>
> **Put to the user, then settled 2026-11-26:**
> - **USD short rate: fetched** on the user's go-ahead. `data/official/fred_daily.csv` now
>   holds FRED DFF and DGS2 (only those two; provenance in `docs/DATA.md`). DGS2 came too
>   because spec 005, the BoJ loader's only consumer, cannot run without it.
> - **BoJ call-rate stamp: fixed**, after measuring it. It is now 10:00 JST on the first
>   JP business day of the next month, when the month's last final daily print appears;
>   the old stamp was 1 h (median) to 145 h early. On spec 005 the largest change in any
>   printed figure is 0.001 (V1 t −0.240 → −0.241, V3 mean −0.825 → −0.826), with financing
>   and both diagnostics unchanged at 2 dp. It cannot touch spec 004, which holds no night.
>   It is fixed because the Task 5 financing code makes this loader the JPY leg of every
>   overnight spec. Known-answer test in `tests/test_h3.py`.
> - **Found while measuring it: spec 005's published *Results* do not reproduce on
>   current code.** They reproduce exactly (3,976 days; −0.73 / +7.16 / −0.54 pips; t
>   −0.19 / +0.47 / −0.04; slope +0.96 at t +2.19) only with the HistData DST fix and the
>   exec-hour spread fix both undone. Spec 005 was committed (`51980ab`) before either.
>   On current code: 3,971 days; V1 −0.95 t −0.24, V2 +3.66 t +0.23, V3 −0.83 t −0.06;
>   slope +0.86 at **t +1.89**. The verdict is unchanged (every t far below 3.0). But
>   `CLAUDE.md` quoted 005's slope as t +2.19, and the spec's table was stale.
> - **Spec 005 restated 2026-11-26 on the user's decision.** Verified first: a fresh clone of
>   `research/remaining-work` at `bd66e20` (data linked, `tokyo_hours` not) passed 95 tests,
>   and its `h3_rate_study.py` stdout and all 6 result CSVs were byte-identical to the run
>   above. The spec's *Results*, `Research/Strategy/H3 Rate Path Trade Test.md` (its derived
>   figures, from a script that first reproduced the first version's figures on the
>   first-run code), `CLAUDE.md` and `HANDOFF.md` §1 were then rewritten from that clone's
>   output; superseded values are in `HANDOFF.md` §4.
> - `horizon.simulate` (spec 005) charges financing on fractional calendar days, while the
>   new code charges per roll. The two agree on its whole-day holds. Left alone.
> - Commission is priced at the fill in `window_trades` and at mid in the simulator: a
>   1e-5 relative difference.

Specs 006–018 need these whichever sample they spend. Each gets tests and none
runs a strategy:
1. bid high/low in `datasets.load_minute`: the source parquets carry bid OHLC, and
   Eightcap also has bid/ask close
2. `summarize()` periods for the 2015–19 / 2020–24 split, added alongside
   `events.PERIODS`, which spec 004's tables use, not replacing them
3. a timestamp-based window helper for multi-day or ET-anchored holds
4. a weekly portfolio simulator, for 014/016/017
5. loaders for the H.10 daily and the BoJ call-rate files in `data/macro/`

### Task 6: Tier 0b volatility model — **DONE 2026-11-26**

> **Status:** `src/usdjpy/vol.py`, tested on synthetic data with known answers
> (`tests/test_vol.py`, 33 tests with the hybrid clock and seed fix; 128 pass in all), checked on real pre-holdout bars by
> `scripts/vol_model_check.py`. No strategy run; nothing predicts returns, so no trial
> budget is spent. The design was fixed before any real-data fit (stated in the session);
> one choice was then changed after the real-data check, below, and is marked as such.
> - **Realised variance:** 5-min bid, previous-tick, 17:00-to-17:00 New York trading days
>   (the `costs.roll_times` boundary), no cross-day returns, a day counts at >= 80% of its
>   5-min intervals. Synthetic: unbiased for integrated variance (ratio 1.00 +/- 0.02), also
>   with 30% of minutes missing; days missing their first quarter are flagged. Real
>   (`combined`): 99% of weekdays valid from 2015, 41-80% in 2007-2014, 56% in 2023 (the
>   HistData gap); median annualised vol 5-13% by year.
> - **HAR-RV** (spec 017 O2, lags 1/5/22, levels, direct h-step, expanding OLS on rows whose
>   target is observed by the forecast day, floor at the smallest training target,
>   annualised over 260 weekdays). Synthetic: recovers known coefficients (+/- 0.06) and a
>   perturbation test proves no look-ahead at h = 1 and 5. Real, out of sample from
>   2010-07: MSE 0.60x the naive forecast at h = 1 and 0.66x at h = 5; QLIKE better at
>   h = 1 (0.309 vs 0.337) but **marginally worse at h = 5 (0.255 vs 0.251)**; correlation
>   with realised 0.27 / 0.39; final coefficient sum 0.71 / 0.64, weighted to the 22-day lag.
>   Levels HAR is the spec's form; a log-HAR is the usual alternative if spec 017 wants it.
>   That is spec 017's choice to declare, not made here.
> - **EWMA** (`ewma_variance`, lam or centre of mass): seeded from the first 20 returns, no
>   look-ahead (tested).
> - **Minute-of-week baseline** (`seasonal_baseline`, spec 007's s_m and 017's spread z):
>   `stat` over the same cell in the previous 12 weeks (`"84D"`, spec 007's 60 trading days),
>   strictly before t, >= 8 observations. **`clock` is a required argument.** Real data
>   (HistData 2015-2024): any single clock gives a baseline for ~97% of minutes; the
>   DST-split clock of trap 7 (`jst_nydst`) for only **66.4%**, because each US DST change
>   empties the new regime's cells for ~8 weeks. **Changed after the real-data check:** the
>   first version counted the last 12 observations of a cell with no age limit; that
>   silently borrowed last year's same-DST weeks, breaking "previous 60 trading days", and
>   hid the 66% figure.
> - **Decision (user, 2026-11-26): the hybrid clock.** Asked whether one clock could work
>   with New York events shifted by the time-zone difference: yes, if New York-band minutes
>   (03:00-17:10 ET, fixed before measuring) are keyed in New York time and the rest in JST,
>   in **separate** key spaces (one shifted JST key space collides: 420 keys in an EDT week
>   hold two market states). `clock="hybrid"` (`vol.HYBRID_NY_BAND`), commit `2ecd0c6`.
>   Measured on HistData 2015-2024 (`scripts/vol_model_check.py` section 3): 96.1% of minutes
>   have a baseline; in the 4 weeks after each of 20 US DST changes, Thursday 08:30 ET is
>   over 5x baseline on 5.1% of minutes and 09:55 JST on 3.5%, as the matching single clock
>   gives, against 30.8% at 08:30 ET on a Tokyo clock and 18.8% at 09:55 JST on a New York
>   clock; the DST split has no baseline at all in those weeks. Cost: ~1 point of coverage
>   at the band-edge JST cells, and London (EU DST) an hour off ~4 weeks a year. Adopted for
>   minute-of-week work, **spec 007's s_m included**; spec 007's text is unchanged until it
>   is run, and its run declares `clock="hybrid"`.
> - **Sizing:** `vol_target_weight` (spec 014: 10%, cap 2; spec 017 O2: 8%); NaN vol
>   gives NaN, never a capped full position. Feeds `portfolio.simulate` targets.
>
> **Findings for later specs (not edited into them):**
> - **Spec 007 says "1-min mid log return"; use the bid.** On bid-only sources the
>   synthetic ask makes the mid step 2.34 pips at 05:59 JST and 2.20 at 06:59 JST every
>   day. With a minute-of-week baseline the steps are absorbed, so they hide real shocks at
>   those minutes (a 5x rule fires on 0.9% of days on the mid against 5.7% on the bid)
>   rather than creating false ones. *(My review note this session said they would create
>   false shocks; the measurement says otherwise.)*
> - **`signals.ewma_vol` and `stats.ewma_standardise` seeded with the full-sample
>   variance**, future data included. **Fixed 2026-11-26 on the user's decision**
>   (`stats.ewma_variance_past`), with spec 003 restated once to carry it: see
>   `HANDOFF-2026-11-26-remaining.md` §3 item 5.

HAR-RV on 5-minute realised volatility, the minute-of-week volatility profile, and
vol-target sizing, which specs 007 and 017 use. This is infrastructure, not a test.
Build it on `load_minute("combined")` and validate it on synthetic data first, per
`CLAUDE.md`.

---

## 4. Out of scope without the user's go-ahead

- **Running any of specs 006–018 on USDJPY 2007–2024.** 013, 018, and 006/010 after
  task 5 have the data, but each one spends spec 004's DSR headroom (task 2 may
  shrink it). They are meant for the JPY crosses.
- **New fetches:**
  - HistData cross-pair minute bars for the breadth study. `fetch_official.py`
    hardcodes `pair="usdjpy"`.
  - the Tier 0c calendars and the FRED series.

  These do not touch Dukascopy, but they extend scope. Ask first.
- **Anything after `HOLDOUT_START`**, any edit to kill criteria, pushing, and
  renaming the branch.

## 5. When the fetch finishes

The log ends with `stage 3 complete`. Tell the user. Do not start step 0 on your
own initiative: the user may want to review task 3's code and the step 0
thresholds first. The thresholds were set by the previous agent and are flagged
for the user's review in the commit history and chat.
