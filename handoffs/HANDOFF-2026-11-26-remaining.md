# Handoff — 2026-11-26 00:00 UTC: what remains

For whoever picks this up next, including a cold CLI session. This file lists what
is left and where to start. It points to the documents that hold the numbers rather
than copying them: a fact stored twice in this repo has been corrected in one place
only, repeatedly.

**Read first, in this order:**
1. `CLAUDE.md`: standing rules. Where this file and `CLAUDE.md` disagree, `CLAUDE.md` wins.
2. `HANDOFF.md`: project state and the next action (§2), and every number that was
   wrong at some point (§4).
3. `HANDOFF-2026-11-25-during-fetch.md`: the session that produced the current state.
   Its §2 has the rules for working while the fetch runs, which still apply.
4. `specs/004-turn-of-month-separation.md`, section *Gap fill* and its dated
   amendments: how the fetched data must be used. Fixed before any of it was seen.

---

## 1. Where things stand

- **`main` is at PR #6** (merge `3588db6`, by the user, 2026-11-26 18:17 UTC), which carries
  this session's work up to `deb7291`. After it, `research/remaining-work` added the specs
  006-018 triage (`2cb2c67`) and its handoff notes; check `git log origin/main..` for
  what is not yet on `main`. Agents do not merge or push to `main`; `gh` is not installed
  on this machine, so the user opens and merges pull requests on GitHub.
- **Next session: start at §6 below** (scope for continuing), after the fetch check in §2.
- **Tasks 1–4 of the during-fetch handoff are done.** Task 3's analysis is written
  and tested but cannot run until the fetch completes.
- **Spec 004, in one line:** B beats zero and unmatched control, but not
  weekday-matched control at the declared bar; criterion 4 passes; criterion 5 is
  pending the measured spread. Figures in `HANDOFF.md` §2 and the spec's *Results*.
- **Tests:** 128 pass after Tasks 5 and 6, the hybrid clock and the EWMA seed fix (`~/.venvs/usdjpy-bot/bin/python -m pytest -q tests`).

## 2. The fetch

`scripts/download_gap_fill.py all`, writing `data/tokyo_hours/`. **At 2026-11-26 18:28
UTC: stages 1 and 2 complete; stage 3 has 2,436 days (~8,100 requests) left, about 68
hours at full pace, so 29 Nov at the earliest and probably later.** It ran at full pace
from the 14:48 restart, was rate-limited (HTTP 429, timeouts) from ~17:30 to ~18:15,
backing off and restarting itself (1 of 200 restarts used), and was moving again at
18:28. It has died twice, the second time (~13:44 UTC 26 Nov) on battery sleep,
which `caffeinate -i` does not prevent: **keep the machine on mains power** (at 18:28 it
was on battery, 18%). PID 51021 since the 14:48 restart. What is fetched and why:
`specs/README.md`, *Dukascopy fetch*.

```bash
cd "/Volumes/bzk Drive/usdjpy-bot"
tail -3 data/tokyo_hours/fetch.log
ps -p "$(cat data/tokyo_hours/fetch.pid)"            # alive?
~/.venvs/usdjpy-bot/bin/python scripts/004_gap_fill_analysis.py --check   # days left per stage (filenames only)
```

From a worktree, add `--tree-root "/Volumes/bzk Drive/usdjpy-bot/data/tokyo_hours"`:
the default reads the worktree's own `data/tokyo_hours`, which is deliberately not
linked, and reports every stage as untouched. Request counts (not just days):
`download_gap_fill.planned(*STAGES[s][:3], out_dir=...)`, also filenames only.

- **It has died twice** (2026-11-25 ~22:43, and 2026-11-26 ~13:44 UTC; no traceback
  either time) and was restarted each time. Restart it the way `HANDOFF-2026-11-25-during-fetch.md` §2
  describes, from the **main checkout** (`/Volumes/bzk Drive/usdjpy-bot`), never from
  a worktree: a worktree's script writes into the worktree's own `data/`. Start it
  with `start_new_session=True`, write its PID to `data/tokyo_hours/fetch.pid`, and
  add a dated line to `fetch.log`.
- **No deadline** (user's decision, spec 004 *Amendment: field standards*). A day
  leaves the requirement only by a dated note in spec 004 recording the user's
  decision that it is unnecessary; pass those days to the analysis with `--waived`.
- **While it runs:** do not read `data/tokyo_hours/` beyond filenames, do not call
  `load_minute_bars` on it, and send nothing to datafeed.dukascopy.com.

## 3. Remaining work, in order

1. **When the fetch completes** (the log ends with `stage 3 complete`, and `--check`
   shows 0 days everywhere): **tell the user before running anything.** They may want
   to review step 0's thresholds and the analysis code first. Then:
   `python scripts/004_gap_fill_analysis.py`. If step 0's 2007–2014 gate fails, the
   script stops; amend the spec with a dated note saying what was seen, and use no
   fill until then.
2. **Record the filled run in spec 004.** Put the *filled* column beside *as run* in
   *Results* for figures 1–7, plus the diagnostics. Write the status line from the
   **weekday-matched** test and the **measured** criterion 5 column, and say so if as
   run and filled disagree on any kill criterion. Then update the copies the spec
   lists (`CLAUDE.md` *Current state* and trial budget, `HANDOFF.md` §2, the
   `specs/README.md` index), each saying which sample it quotes.
3. ~~**Task 5, harness gaps**~~ **Done 2026-11-26.** What was built, the two
   `window_trades` defects fixed, the diff proof, the DFF fetch and BoJ stamp fix that
   followed, and the spec 005 restatement (on the user's decision, confirmed from a fresh
   clone) are in `HANDOFF-2026-11-25-during-fetch.md` Task 5.
4. ~~**Task 6, the volatility model**~~ **Done 2026-11-26** (`src/usdjpy/vol.py`). What
   was built, the real-data checks, the user's choice of the hybrid minute-of-week clock
   (for spec 007 too), and the finding that spec 007 should use the bid are in
   `HANDOFF-2026-11-25-during-fetch.md` Task 6.
5. ~~**Spec 003 re-run check**~~ **Done 2026-11-26: restated, with the `ewma_vol` fix,
   on the user's decision.**
   - *Attribution.* Spec 003's first table reproduces exactly (every printed figure) on
     current code with **both** the HistData DST fix and the exec-hour spread fix undone
     and the old seed. The note here had said the exec-hour fix was already in; it was in
     the commit that carried the table (`f35dfb3`) but the table predates it. The spec's
     MDE paragraph (0.0613) matches the code with only the DST fix undone, so it was
     computed later: mixed provenance, now gone.
   - *Decisions (user, 2026-11-26).* (a) Fix `signals.ewma_vol`'s seed and restate spec 003
     once with it, rather than twice. (b) Fix `stats.ewma_standardise` now, though no
     result used it. Both now share `stats.ewma_variance_past` (expanding mean of past
     squared returns for 20 days, then the recursion): v[0] had been the variance of
     the whole series, future included. The seed alone moves spec 003's t by at most
     0.01; the variant that drops a 20-day burn-in instead moved h=10 by 0.24 through
     sample composition, so it was not used. `ewma_standardise` now returns len(r) - 1
     values.
   - *Verified first.* Code committed alone (`2ecd0c6`), cloned fresh: 128 tests pass,
     `rate_path_study.py --data` stdout and CSV byte-identical to the run the figures came
     from, and the synthetic harness section unchanged. Only then were spec 003 *Results*,
     `CLAUDE.md` (inference rule, *Current state*), `HANDOFF.md` §1 and §4 rewritten.
   - *Result.* max |t_hc| 1.80 → 1.78, MDE Sharpe 0.97 → 0.98; verdict unchanged.
6. ~~**Spec 001 housekeeping**~~ **Done 2026-11-26, and the reading decided** (2022+ by
   mean > 0, `PESSIMISTIC` by full-sample t ≥ 2: both rules pass; spec 001 *Results* gives
   the power argument and the disclosure). The finding that prompted the decision:
   Spec 001's figures had never been recorded in git: its *Results* read "_Pending._", and
   the verdict existed only in `gotobi_report.py`'s gitignored HTML. They are now in spec
   001 *Results*, on current code (fresh clone at `81c7b13`) and on first-run code (exec-hour
   and DST fixes undone). **Finding:** the report template, committed with the first run,
   reads "effect absent in 2022+" and "fails under PESSIMISTIC" as t < 2 within those
   slices. On that reading rule **1b passes every criterion, and rule 1a fails 2022+ on any
   code (t 0.97 now, 0.74 first run) and failed `PESSIMISTIC` on first-run code (t 1.62)**,
   so "upheld" was never true of 1a on that reading. On the plain mean > 0 reading both
   rules pass. Status copies updated (`CLAUDE.md`, `HANDOFF.md` §1 and §4, the
   `specs/README.md` index) and `gotobi_report.py`'s template now applies the same reading.
   Not restated as Gotobi-proper.

## 4. Ask the user first

- **Running any of specs 006–018 on USDJPY 2007–2024.** About five hypotheses of
  trial headroom remain (`CLAUDE.md`, trial budget), and the user counts specs.
- **The JPY-cross breadth study** (`HANDOFF.md` §2 calls it the highest-value next
  study after the gap fill). It needs a new HistData cross-pair fetch, and
  `fetch_official.py` hardcodes `usdjpy`.
- **New fetches of any kind**, anything after `HOLDOUT_START`, any edit to kill
  criteria, renaming branches, and merging.
- **Merging the remaining collaborator branch** (unmerged on `origin`):
  - ~~`research/trial-budget`~~ **Deleted from `origin` 2026-11-26 on the user's
    instruction**, after its one piece still of use, `specs/TRIAGE-006-018.md`, was brought
    to `research/remaining-work` and rewritten for N = 5 (`2cb2c67`). It had been
    deliberately not adopted: its ledger counted configurations (effective N=11) and
    concluded spec 004 fails the Deflated Sharpe hurdle; **the user chose to count specs,
    N=5 (2026-11-25; `CLAUDE.md`, trial budget), after seeing it.** Do not reopen the count
    on its authority. Its tip was `8f7f216` (parent `fe8da8c`, both 2026-11-25); the objects
    stay in the local repository until `git gc` prunes them, so while they last it can be
    recovered with `git branch research/trial-budget 8f7f216`. Its DSR sensitivities
    (variance-adjusted SR_0; intervention days excluded), run on DST-corrected trades on
    2026-11-26, change nothing at N=5 (all 0.979-0.994) and were not brought.
  - **`feature/dukascopy-fetch`** (a collaborator): a separate resumable Dukascopy
    downloader with its own 429 handling. It edits `src/usdjpy/datasets.py`, which
    `main` changed for the HistData fix, so a merge needs care there. It sends
    requests to datafeed.dukascopy.com: do not run it on this machine while the
    gap-fill fetch runs, since the two would share one rate limit.

## 5. Housekeeping

- **Worktree.** This session worked in `.claude/worktrees/during-fetch`. `data/` and
  `results/` there are symlinks into the main checkout (`data/tokyo_hours` is
  deliberately not linked). It now carries `research/remaining-work`; remove it with
  `git worktree remove` only once that branch is pushed and no longer needed. The main
  checkout is still on `research/002-intervention-disclosure` at `ff8aad9`, whose
  upstream is gone; leave it until the fetch, which was started from it, finishes.
- **`results/archive/004_as_run_pre_dst_fix/`** holds the pre-DST-fix trades that
  `scripts/004_dst_fix_verification.py` and the spec's "was" figures rely on.
  `results/` is gitignored; the verification script's docstring says how to
  regenerate the archive on a clean clone.
- **`stash@{0}`** holds edits superseded by `origin/main`, verified line by line in an
  earlier session. Do not pop it.
- **AppleDouble files.** The repo is on exFAT. If git reports "non-monotonic index",
  run `dot_clean -m . && find . -name '._*' -delete` (outside `data/tokyo_hours/`
  while the fetch runs).

## 6. Scope for continuing (written 2026-11-26 18:00 UTC, before the merge to `main`)

The user asked for this so the next session can continue after the fetch and, until then,
work on what the Dukascopy data does not block. It lists options; what is chosen is the
user's call. Everything below "Not blocked" may run while the fetch does, under §2's
rules (never read `data/tokyo_hours/`; send nothing to datafeed.dukascopy.com).

**What this session (2026-11-26) delivered**, in order, each recorded where it says:
Task 5 harness gaps; DFF/DGS2 fetched; BoJ call-rate stamp fixed; spec 005 restated;
Task 6 volatility model; hybrid minute-of-week clock; past-only EWMA seed and spec 003
restated; spec 001 results recorded. Tests: 128 pass. Every restatement was confirmed on
a fresh clone before it was written. Records: `HANDOFF-2026-11-25-during-fetch.md` Tasks 5
and 6, §3 items 3-6 above, `HANDOFF.md` §4 (superseded values).

### Blocked on the fetch (`data/tokyo_hours/` stage 3)
1. §3 item 1: tell the user, let them review step 0's thresholds and the analysis code,
   then run `scripts/004_gap_fill_analysis.py`. Its code path changed under it in Task 5
   (`window_trades` refactor: output proven identical on as-run trades, plus three
   trailing columns, all 0 / 0.0 / NaN there).
2. §3 item 2: record the filled run in spec 004 and its copies.

### Decisions only the user can make (no data needed)
3. ~~**Spec 001's kill-criterion reading**~~ Decided 2026-11-26 (§3 item 6): both rules pass.
4. **Spec 007's return series:** its rule says "1-min mid"; the measurement says use the
   bid (Task 6 record). Its clock is decided (`hybrid`). Changing "mid" is a rule change
   to an unrun spec, so the user's.
5. **Spec 017 O2's HAR form:** levels (as built; QLIKE slightly worse than naive at h=5)
   or log-HAR. Declare before spec 017 is run.
6. **Trial budget for specs 006-018** (§4): about five hypotheses of headroom on USDJPY
   2007-2024, or route them to other pairs. **A per-spec proposal now exists:**
   `specs/TRIAGE-006-018.md` (brought from `research/trial-budget` 2026-11-26 and rewritten
   against N = 5). It awaits the user's sign-off; nothing in it has taken effect.

### Not blocked by the Dukascopy data
7. **JPY-cross breadth study** (`HANDOFF.md` §2: the highest-value next study). Needs a
   HistData cross-pair fetch (a different host from Dukascopy, so no shared rate limit);
   `fetch_official.py` hardcodes `usdjpy`. Needs the user's go-ahead (new fetch). The
   harness from Tasks 5-6 applies unchanged.
8. **Data for specs 006-018**, each a new fetch or hand-built file, so each asks first:
   the US release calendar (specs 007, 008, 017 O5; `data/calendars/us_releases.csv`);
   S&P 500 for 012 and the other FRED series (full `fetch_official.py` run, which would
   also let the transcribed MOF intervention file be diffed against MOF's own CSV,
   `HANDOFF.md` §5). Already on disk: DFF, DGS2, VIX, COT, BoJ, FOMC, interventions.
9. **Spec 003 follow-ups its own *Results* list:** the "raw" column is not fixed-notional
   (`rate_path_signal` bakes in vol scaling; `sharpe_from_raw` mislabelled), and the clean
   re-run on `histdata` alone (2015-2024). Either changes figures: ask before restating.
10. **Specs whose inputs are ready, if the budget allows (item 6):** 013 (COT), 016
    (DGS2 + JGB + H.10 + portfolio simulator), 014 core (H.10 + DFF + BoJ + simulator),
    006 exit A/B (window and timestamp helpers; financing via DFF).

### Housekeeping after the merge
11. Once `research/remaining-work` is merged and the fetch has finished: remove the
    worktree (`git worktree remove`), and move the main checkout off
    `research/002-intervention-disclosure` (upstream gone; ask before renaming or deleting
    branches). Do not pop `stash@{0}`.
