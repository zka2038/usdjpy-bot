# Handoff — 2026-11-26 01:00 UTC: starting the next session

How to start a fresh CLI session on the remaining work. It covers the workspace,
the decisions not to reopen, and how to work. **What** remains, and in what order,
is in `HANDOFF-2026-11-26-remaining.md`. This file does not repeat it.

**Read first, in this order** (all handoffs are in `handoffs/` since 2026-11-26):
0. `handoffs/README.md`: the roadmap, the current priority list, and the handoff index.
1. `CLAUDE.md`: standing rules. It overrides everything else.
2. `HANDOFF-2026-11-26-remaining.md`: what remains, the fetch procedure, and what
   needs the user's go-ahead.
3. `HANDOFF.md` §2 and §4.
4. `HANDOFF-2026-11-25-during-fetch.md` §2 (rules while the fetch runs) and §3
   (Tasks 5 and 6 in full).
5. `specs/004-turn-of-month-separation.md`, *Gap fill* and every dated amendment,
   including the *Implementation note*.

---

## 1. Workspace and branch

- **Work in the existing worktree** at
  `/Volumes/bzk Drive/usdjpy-bot/.claude/worktrees/during-fetch` (enter it with
  `EnterWorktree`, `path=`). It has `research/remaining-work` checked out; git will not
  check one branch out in two places. Its `data/` and `results/` subfolders are
  symlinked into the main checkout. `data/tokyo_hours` is deliberately **not**
  linked: keep it that way.
- **Commit on `research/remaining-work`** with the repo's configured identity, and
  push only that branch: `git push origin research/remaining-work`. Its upstream is
  `origin/research/remaining-work`, not `main`.
- **`main` is the user's** (now PR #5, merge `cb04c11`; see the remaining-work handoff
  §1). Do not push to it, merge into it, or open a pull request against it; merging is
  the user's decision.
- **Leave the main checkout's branch alone**: `/Volumes/bzk Drive/usdjpy-bot`, on
  `research/002-intervention-disclosure`. The running fetch was started from it.

## 2. First action: check the fetch

Run the checks in `HANDOFF-2026-11-26-remaining.md` §2 and report the stage and the
requests left. Run `scripts/004_gap_fill_analysis.py --check` from the worktree; it
reads filenames only. If the fetch has died, restart it exactly as §2 there
describes: from the **main checkout's** script, never a worktree's.

**Projection made 2026-11-26 01:00 UTC.** Stage 1 was done; 1,422 stage 2 and 8,354
stage 3 requests were left (9,776). The fetch was then running at its 30-second
ceiling, about 120 requests an hour.
- **Full pace:** about 81 hours. Stage 2 done around 13:00 UTC on 26 Nov, stage 3
  around 10:00 UTC on 29 Nov.
- **Pace achieved so far** (608 requests in 8.1 hours since it started, about 62% of
  full, losing time to HTTP 429 blocks and one death): about 130 hours, finishing
  around 1 Dec.

**Re-measured 2026-11-26 01:04 UTC:** alive (PID 15067), one day file every 2 minutes,
which is full pace. Stage 1 done; stage 2 411 days / 1,414 requests, stage 3 2,506 / 8,354;
9,768 left. The projection above stands. **Later status** (a second death, the restart,
stage 2 done): `HANDOFF-2026-11-26-remaining.md` §2, the one place it is kept current.

More blocks, or the process dying unnoticed (laptop sleep is the likely cause), push
it later. Re-measure rather than trusting these dates. Day files' modification times
are metadata, not contents, and may be listed.

## 3. Decisions already made: do not reopen

- **Trial count: N = 5 specs** (`CLAUDE.md`, trial budget). The collaborator branch
  `research/trial-budget` (effective N = 11) was seen and deliberately not adopted; its
  triage proposal was kept (`specs/TRIAGE-006-018.md`) and the branch deleted on
  2026-11-26 (`HANDOFF-2026-11-26-remaining.md` §4 has the SHAs).
- **No fetch deadline.** A day leaves the requirement only by a dated note in spec 004
  recording the user's decision.
- **Kill criteria and their thresholds are fixed.** Spec 004's gap-fill analysis is
  fully specified. Change nothing in it before the filled run.
- **While the fetch runs:** never read the contents of `data/tokyo_hours/`; never call
  `load_minute_bars` on it; send nothing to datafeed.dukascopy.com. That includes the
  collaborator's `feature/dukascopy-fetch` downloader.

## 4. Order of work

As in `HANDOFF-2026-11-26-remaining.md` §3:
1. ~~**Task 5**, the harness gaps.~~ Done 2026-11-26 (`HANDOFF-2026-11-25-during-fetch.md` Task 5).
2. ~~**Task 6**, the volatility model.~~ Done 2026-11-26 (`HANDOFF-2026-11-25-during-fetch.md` Task 6).
2a. ~~**Spec 003 re-run check and spec 001 housekeeping**~~ Done 2026-11-26
   (`HANDOFF-2026-11-26-remaining.md` §3 items 5-6; spec 001's criteria reading decided).
3. **When the fetch completes, stop and tell the user** before running
   `scripts/004_gap_fill_analysis.py`, then continue with §3 items 1–2 there.
4. **Until then, and after:** `HANDOFF-2026-11-26-remaining.md` §6, the scope for
   continuing (decisions for the user, work the Dukascopy data does not block).

Ask the user before anything in §4 there.

## 5. How to work (user's standing preferences)

- **Review first, then one change set.** For each task, read the whole code path it
  touches, list every defect or change, then make one change set with tests and one
  commit. The user has asked explicitly for no piecemeal review-and-fix cycles.
- **Prove refactors preserve behaviour** by diffing script outputs and trade CSVs
  before and after.
- **Known answers first.** Test every new function on synthetic data with a known
  answer before it touches real data (`CLAUDE.md`, inference rules).
- **Store each fact once.** Point to `docs/DATA.md`, the spec, or `HANDOFF.md` rather
  than copying numbers.
- **Report at checkpoints.** Say what was checked, and stop where a handoff says to.
- **Tests:** `~/.venvs/usdjpy-bot/bin/python -m pytest -q tests` (62 pass at `8cad770`, 94 after Task 5).
- **exFAT:** delete AppleDouble files before committing
  (`find . -name '._*' -not -path './.git/*' -delete`), never under `data/tokyo_hours/`.
