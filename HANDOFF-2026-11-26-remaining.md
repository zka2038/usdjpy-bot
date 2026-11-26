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

- **Branch `research/004-during-fetch`**, pushed, with a pull request to `main`.
  It carries everything since `origin/main` (`cd8b164`), including the four unpushed
  commits of the session before (`e7dcfa2`…`ff8aad9`). Merging is the user's step.
- **Tasks 1–4 of the during-fetch handoff are done.** Task 3's analysis is written
  and tested but cannot run until the fetch completes.
- **Spec 004, in one line:** B beats zero and unmatched control, but not
  weekday-matched control at the declared bar; criterion 4 passes; criterion 5 is
  pending the measured spread. Figures in `HANDOFF.md` §2 and the spec's *Results*.
- **Tests:** 62 pass (`~/.venvs/usdjpy-bot/bin/python -m pytest -q tests`).

## 2. The fetch

`scripts/download_gap_fill.py all`, writing `data/tokyo_hours/`. At this writing:
stage 1 complete, stage 2 at its first days with 441 days left, stage 3 not started
(2,506 days), and Dukascopy has been answering HTTP 429 for about 1.5 hours. Expect
days, not hours. What is fetched and why: `specs/README.md`, *Dukascopy fetch*.

```bash
cd "/Volumes/bzk Drive/usdjpy-bot"
tail -3 data/tokyo_hours/fetch.log
ps -p "$(cat data/tokyo_hours/fetch.pid)"            # alive?
~/.venvs/usdjpy-bot/bin/python scripts/004_gap_fill_analysis.py --check   # days left per stage (filenames only)
```

- **It has died once** (2026-11-25, between 22:43 and 23:02 UTC, no traceback) and
  was restarted. Restart it the way `HANDOFF-2026-11-25-during-fetch.md` §2
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
3. **Task 5, harness gaps** (`HANDOFF-2026-11-25-during-fetch.md` §3, each with
   tests, none running a strategy):
   - bid high/low in `datasets.load_minute`;
   - `summarize()` periods for 2015–19 / 2020–24, beside `events.PERIODS`;
   - a timestamp-based window helper for multi-day or ET-anchored holds;
   - a weekly portfolio simulator (specs 014/016/017);
   - loaders for the H.10 daily and the BoJ call-rate files. The H.10 noon check in
     `scripts/histdata_alignment_check.py` reads the file directly and could move onto
     the loader.
4. **Task 6, the volatility model:** HAR-RV on 5-minute realised vol, the
   minute-of-week vol profile, and vol-target sizing (specs 007, 017). Build it on
   `load_minute("combined")` and validate on synthetic data first.

## 4. Ask the user first

- **Running any of specs 006–018 on USDJPY 2007–2024.** About five hypotheses of
  trial headroom remain (`CLAUDE.md`, trial budget), and the user counts specs.
- **The JPY-cross breadth study** (`HANDOFF.md` §2 calls it the highest-value next
  study after the gap fill). It needs a new HistData cross-pair fetch, and
  `fetch_official.py` hardcodes `usdjpy`.
- **New fetches of any kind**, anything after `HOLDOUT_START`, any edit to kill
  criteria, renaming branches, and merging.

## 5. Housekeeping

- **Worktree.** This session worked in `.claude/worktrees/during-fetch`. `data/` and
  `results/` there are symlinks into the main checkout (`data/tokyo_hours` is
  deliberately not linked). After the merge the worktree can be removed with `git
  worktree remove`; the main checkout is still on `research/002-intervention-disclosure`
  at `ff8aad9`, whose upstream is gone.
- **`results/archive/004_as_run_pre_dst_fix/`** holds the pre-DST-fix trades that
  `scripts/004_dst_fix_verification.py` and the spec's "was" figures rely on.
  `results/` is gitignored; the verification script's docstring says how to
  regenerate the archive on a clean clone.
- **`stash@{0}`** holds edits superseded by `origin/main`, verified line by line in an
  earlier session. Do not pop it.
- **AppleDouble files.** The repo is on exFAT. If git reports "non-monotonic index",
  run `dot_clean -m . && find . -name '._*' -delete` (outside `data/tokyo_hours/`
  while the fetch runs).
