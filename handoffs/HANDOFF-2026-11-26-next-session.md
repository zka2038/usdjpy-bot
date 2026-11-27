# Handoff — starting the next session (written 2026-11-26 01:00 UTC, rewritten 2026-11-27 12:20 UTC)

How to start a fresh CLI session on the remaining work: the workspace, the decisions not
to reopen, and how to work. **What** remains and in what order is in `handoffs/README.md`
(the priority list) and `HANDOFF-2026-11-26-remaining.md` (the detail). This file does
not repeat them.

**Read first, in this order** (all handoffs are in `handoffs/`):
0. `handoffs/README.md`: roadmap, the current priority list, the handoff index.
1. `CLAUDE.md`: standing rules. It overrides everything else.
2. `HANDOFF-2026-11-26-remaining.md`: §2 the fetch (status, supervisor, procedure), §3
   what was done and decided, §4 what needs the user's go-ahead, §6 the scope behind each
   priority.
3. `HANDOFF.md` §2 and §4 (project state; every number that was ever wrong).
4. `HANDOFF-2026-11-25-during-fetch.md` §2 (rules while the fetch runs) and the Task 5
   and Task 6 records.
5. `specs/TRIAGE-006-018.md` before touching any of specs 006-018, and the spec itself
   before touching any study (`CLAUDE.md`).
6. `specs/004-turn-of-month-separation.md` *Gap fill* and its dated amendments, only when
   the fetch is complete.

---

## 1. Workspace and branch

- **One session at a time.** The session that wrote this ended at 2026-11-27 ~12:20 UTC.
  Do not run two sessions on the same worktree or branch.
- **Worktree:** `/Volumes/bzk Drive/usdjpy-bot/.claude/worktrees/during-fetch` (enter with
  `EnterWorktree`, `path=`), branch `research/remaining-work`. Its `data/` holds symlinks
  into the main checkout's data and `results/` is linked too; `data/tokyo_hours` is
  deliberately **not** linked. `data/official` (DFF, DGS2) is linked.
- **`main` is the user's.** `main` = PR #7 (`1bc3669`, merged 2026-11-27) and
  `research/remaining-work` is ahead of it by the commits since (`git log origin/main..`).
  The user merges on GitHub; `gh` is not installed. Never push to, merge into, or open a
  pull request against `main` yourself. If the user has merged since, start from
  `origin/main` (fast-forward the branch or branch anew; ask before renaming).
- **Commit** on `research/remaining-work` with the repo's configured identity; push only
  that branch.
- **Leave the main checkout alone:** `/Volumes/bzk Drive/usdjpy-bot`, on
  `research/002-intervention-disclosure`. The fetch, and the supervisor that restarts it,
  run `scripts/download_gap_fill.py` **from there**: switching its branch mid-fetch would
  change the code the next restart runs.

## 2. First action: check the fetch (do not restart it by hand)

```bash
~/.venvs/usdjpy-bot/bin/python scripts/fetch_status.py          # from the worktree
bash ~/usdjpy-fetch-supervisor/fetch_supervisor.sh status      # the auto-restart watcher
```

Report the stage, the requests left and whether both are running. **Restarts are
automatic** (`data/disk-utility/fetch_supervisor.sh`, since 2026-11-27 11:08 UTC). Restart by
hand only if the supervisor is not running: then start the supervisor
(`bash ~/usdjpy-fetch-supervisor/fetch_supervisor.sh start`), which restarts the fetch
itself. The manual fallback is in `HANDOFF-2026-11-26-remaining.md` §2. The latest status
snapshot, the deaths so far and their cause are there too; it is the one place they are
kept current. Day files' names and modification times may be listed; their contents may
not be read.

## 3. Decisions already made: do not reopen

- **Trial count: N = 5 specs** (`CLAUDE.md`, trial budget). `research/trial-budget`
  (effective N = 11) was not adopted and is deleted; its triage proposal survives as
  `specs/TRIAGE-006-018.md`, **accepted 2026-11-27** with an amendment (below).
- **No fetch deadline.** A day leaves the requirement only by a dated note in spec 004
  recording the user's decision.
- **Kill criteria and their thresholds are fixed.** Spec 004's gap-fill analysis is fully
  specified; change nothing in it before the filled run.
- **While the fetch runs:** never read `data/tokyo_hours/` contents; never call
  `load_minute_bars` on it; send nothing to datafeed.dukascopy.com (that includes
  `scripts/download.py` and the collaborator's `feature/dukascopy-fetch`).
- **Decided 2026-11-26/27 by the user** (records: `HANDOFF-2026-11-26-remaining.md` §3,
  `HANDOFF-2026-11-25-during-fetch.md` Tasks 5-6):
  - spec 001: the 2022+ criterion is read as mean > 0 and `PESSIMISTIC` as full-sample
    t >= 2; both rules upheld, mechanism not established; not Gotobi-proper;
  - specs 003 and 005 restated on current code (verdicts unchanged); do not restate again
    without a new reason;
  - `signals.ewma_vol` / `stats.ewma_standardise` use a past-only seed;
  - minute-of-week work uses `vol` clock `"hybrid"`, spec 007 included;
  - BoJ call-rate average stamped at publication; DFF and DGS2 fetched (only those two);
  - every handoff lives in `handoffs/`, with `handoffs/README.md` as index and roadmap;
  - the fetch is kept alive by the supervisor.
- **Decided 2026-11-27 by the user** (records: `specs/TRIAGE-006-018.md` *Sign-off*,
  spec 007 *Amendment*, spec 017 *Note*, `specs/019-yen-dollar-split.md`):
  - specs 006-018 triage **accepted**, with the amendment that a JPY cross is not a fresh
    sample for a yen-side hypothesis;
  - spec 007 uses the **bid**; spec 017's HAR form is **deferred** until 017 is unparked;
  - the JPY-cross study is **spec 019**, a yen-leg / dollar-leg split, not a replication.
    It spends one USDJPY spec at its Stage 2, and Stage 2 waits for the user;
  - **no network fetch of any kind until the Dukascopy fetch logs `stage 3 complete`.**

## 4. Order of work

**`handoffs/README.md`, *Priority list*.** Work that does not depend on the fetch comes
first; the fetch-dependent items wait for it and for the user. When the fetch completes,
**tell the user and keep going** with the item in hand: the gap-fill run waits for their
review of step 0's thresholds and the analysis code, and for their decision on the
possibly truncated day files. Ask the user before anything in
`HANDOFF-2026-11-26-remaining.md` §4 (new fetches, specs 006-018 on USDJPY, merging,
renaming branches, anything after `HOLDOUT_START`, any kill-criterion edit).

## 5. How to work (user's standing preferences)

- **Review first, then one change set.** Read the whole code path a task touches, list
  every defect or change, then make one change set with tests and one commit. No
  piecemeal review-and-fix cycles.
- **Prove refactors preserve behaviour** by diffing script outputs and trade CSVs before
  and after (export the old code to a temp dir; redirect `RESULTS_DIR` there rather than
  overwrite the shared `results/`).
- **Known answers first.** Test every new function on synthetic data with a known answer
  before it touches real data (`CLAUDE.md`, inference rules).
- **Restatements are confirmed on a fresh clone** before the text is written, and
  reported before anything is restated.
- **Store each fact once.** Point to `docs/DATA.md`, the spec, or `handoffs/HANDOFF.md`
  rather than copying numbers. Update `handoffs/README.md` (roadmap, priority list) in the
  same commit as any handoff change.
- **Report at checkpoints.** Say what was checked; stop where a handoff says to.
- **Tests:** `~/.venvs/usdjpy-bot/bin/python -m pytest -q tests` (130 pass at `5860834`).
- **exFAT:** delete AppleDouble files before committing
  (`find . -name '._*' -not -path './.git/*' -delete`), never under `data/tokyo_hours/`.
