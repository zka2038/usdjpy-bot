# Handoffs: index, roadmap and priorities

Every handoff lives in this folder (since 2026-11-26). Start here, then follow the read
order. Detail stays in the handoff that owns it; this page orders and points, and holds
the priority list.

## Read order for a new session

1. `../CLAUDE.md`: standing rules; it overrides everything.
2. This page: where the project is, and what to do next.
3. `HANDOFF-2026-11-26-next-session.md`: workspace, branch, decisions not to reopen, how
   the user wants work done.
4. `HANDOFF-2026-11-26-remaining.md`: what remains in detail, the fetch procedure (§2),
   what needs the user's go-ahead (§4), the scope for continuing (§6).
5. `HANDOFF.md`: project state and the log of every number that was wrong (§4).
6. `HANDOFF-2026-11-25-during-fetch.md`: rules while the fetch runs (§2), and the full
   records of Tasks 1-6.

## Index

| File | Written | Role | Status |
|---|---|---|---|
| `HANDOFF.md` | 2026-11-25 01:30, updated through 2026-11-26 | Project state, spec verdicts, superseded numbers | **Current** (rolling) |
| `HANDOFF-2026-11-25-during-fetch.md` | 2026-11-25 17:00 | Rules while the Dukascopy fetch runs; records of Tasks 1-6 | §2 rules **current**; Tasks 1-6 **done** (records) |
| `HANDOFF-2026-11-26-remaining.md` | 2026-11-26 00:00, updated through 2026-11-27 | What remains, fetch status snapshot and procedure, scope for continuing | **Current**: the detail behind the priority list |
| `HANDOFF-2026-11-26-next-session.md` | 2026-11-26 01:00, rewritten 2026-11-27 12:20, decisions added later that day | How to start a session: workspace, decisions not to reopen, how to work | **Current** |

### Convention for new handoffs

- Name it `HANDOFF-YYYY-MM-DD-<topic>.md` and put it here; add a row above, with its role
  and status, and mark the rows it supersedes.
- Update the roadmap and the priority list below in the same commit.
- Cite handoffs elsewhere by file name alone; names stay unique in this folder.
- Store each number once: the handoff points to the spec, `docs/DATA.md` or `HANDOFF.md`
  rather than copying it.

## Roadmap

**Done**
- **2026-11-24:** seeded data layer; specs 001-005 written; 001, 003, 004, 005 run.
  (`HANDOFF.md` §1)
- **2026-11-25:** exec-hour spread fix committed; HistData DST fix; spec 004 reviewed
  (weekday confound) and its Deflated Sharpe computed from the trades (N = 5 specs, user's
  decision); Dukascopy gap-fill fetch chosen and started; spec 004's gap-fill analysis
  pre-declared and written before any filled data exists. (`HANDOFF-2026-11-25-during-fetch.md`)
- **2026-11-26:** harness gaps (Task 5); DFF and DGS2 fetched; BoJ call-rate stamp fixed;
  volatility model (Task 6) with the hybrid minute-of-week clock; past-only EWMA seed;
  specs 005 and 003 restated on current code; spec 001's results recorded and its
  criteria reading decided (both rules upheld); PR #6 merged to `main`; specs 006-018
  triage brought from `research/trial-budget`, which was then deleted; handoffs moved
  into this folder. Every restatement was confirmed on a fresh clone before it was
  written. (`HANDOFF-2026-11-26-remaining.md` §3)
- **2026-11-26/27:** `scripts/fetch_status.py` (terminal status from file names and the
  log); the fetch's deaths traced to the external drive (dropouts, an accidental unplug)
  and sleep on battery; `data/disk-utility/fetch_supervisor.sh` restarts it automatically
  from the internal disk. (`HANDOFF-2026-11-26-remaining.md` §2)
- **2026-11-27:** PR #7 merged to `main` (A1). The user decided A2: the specs 006-018
  triage was accepted with an amendment (a JPY cross is not a fresh sample for a
  yen-side hypothesis), spec 007 uses the bid, and spec 017's HAR form is deferred. The
  JPY-cross replication study was replaced by **spec 019**, a yen-leg / dollar-leg
  split of spec 004's B-day move, declared before any cross data exists, with its code
  and known-answer harness (152 tests pass). **No network
  fetches until the Dukascopy fetch completes** (user's instruction).
  (`specs/TRIAGE-006-018.md` *Sign-off*; `specs/019-yen-dollar-split.md`)

**In progress**
- **Dukascopy gap-fill fetch, stage 3** (2007-2014 Tokyo mornings): runs unattended under
  the supervisor; the latest status snapshot and the procedure are in
  `HANDOFF-2026-11-26-remaining.md` §2.

**Next:** the priority list below.

**Later**
- Spec 004's filled run and its record (when the fetch completes).
- Layer 2 (NautilusTrader, bid/ask fills) only for a result that passes Layer 1 and its
  tradeability bar; none has yet (spec 004's criterion 5 waits on the measured spread).

## Verified on a cold clone (2026-11-26 ~19:15 UTC)

A fresh clone of `research/remaining-work` at `8bd358d`, **no data linked**: 128 tests
pass. Every done item above is present in it; specs 001/003/005 carry their 2026-11-26
records; the triage is still marked PROPOSED; `research/trial-budget` is gone from
`origin`. Against the machine's data (filenames only): the fetch is alive with stage 3 at
2,428 days left and the gap-fill analysis refuses to run, as designed. Still missing:
`calendars/us_releases.csv`, `calendars/ust_auctions.csv`, `calendars/rate_checks.csv`,
`official/mof_intervention_all.csv`, `official/cftc_tff_jpy_official.csv`, S&P 500 and
every non-USDJPY bar file; `official/fred_daily.csv` holds DFF and DGS2 only;
`fetch_official.py` still hardcodes `usdjpy`. Open as stated: spec 007's rule still says
"mid", spec 017 declares no HAR form, spec 003's "raw" column defect and `histdata`-only
re-run are outstanding, and no bar-loop simulator for stops exists. The main checkout is
still on `research/002-intervention-disclosure`; one stash entry exists; `gh` is not
installed.

## Priority list (2026-11-27, after A1 and A2)

**Non-fetch work comes first** (user's instruction, 2026-11-27). **No new network fetch of
any kind** (HistData, FRED, calendars, any other host) **until the Dukascopy fetch logs
`stage 3 complete`** (user's instruction, 2026-11-27: a second fetch could draw rate-limiting
or IP blocking onto it). After that, each fetch still needs the user's go-ahead. Stage 3 needs about 2.2 days
at full pace and 3.4 at its recent pace (snapshot: `HANDOFF-2026-11-26-remaining.md` §2), so
group A fits before it ends. Group B waits for the fetch **and** for the user: when the fetch
completes, tell the user and carry on with group A until they have reviewed. Numbers in
brackets are items of `HANDOFF-2026-11-26-remaining.md` §6.

### A. Not blocked by the fetch: do these first

| | Item | Who | Needs | Why this rank |
|---|---|---|---|---|
| **A0** | Keep the fetch alive: mains power, a secure drive cable. Restarts are automatic (`data/disk-utility/fetch_supervisor.sh`); check with `scripts/fetch_status.py` and `bash ~/usdjpy-fetch-supervisor/fetch_supervisor.sh status` at the start of each session | user / agent | nothing | Eight deaths so far (drive dropouts, an unplug, sleep on battery); every hour lost is ~30 days of stage 3 |
| ~~A1~~ | ~~Merge `research/remaining-work` into `main`~~ | | | **Done 2026-11-27** (PR #7, `1bc3669`) |
| ~~A2~~ | ~~Triage sign-off; spec 007 bid or mid; spec 017 HAR form~~ | | | **Decided 2026-11-27**: triage accepted with the JPY-cross amendment; 007 bid; 017 deferred (`specs/TRIAGE-006-018.md` *Sign-off*) |
| **A3** | **Spec 019** (yen-leg / dollar-leg split; replaces the JPY-cross replication study [7]). Spec and code **written 2026-11-27** (`src/usdjpy/legsplit.py`, `scripts/019_yen_dollar_split.py`, `fetch_official.py --histdata-pairs`; the harness passes on synthetic data). Remaining, in order: the HistData fetch of six pairs, 2007-2024 (**after** the Dukascopy fetch completes, on go-ahead; the script refuses earlier); Step 0; Stage 1 (power, on control days), then stop for the user; Stage 2 only on their confirmation | agent; user for the fetch and for Stage 2 | the Dukascopy fetch complete, for the data; the code can be written before | The only study that speaks to spec 004's weekday confound. It spends one spec on USDJPY 2007-2024 at Stage 2 |
| **A4** | Spec 003 follow-ups [9]: compute the fixed-notional column against the unscaled spread change; re-run on `histdata` alone | agent; report before restating | data on disk | Cheap, and it corrects a mislabelled column in a rejected spec. **Next item in hand** |
| **A5** | Data for the specs the triage routes [8]: US release calendar, Treasury auction calendar, full `fetch_official.py` (S&P 500, MOF and CFTC official files), and minute bars for other pairs | agent, each on go-ahead | **the Dukascopy fetch complete** (no fetches before) | Deferred by the no-fetch instruction |
| **A6** | Infrastructure for the routed specs: bar-loop simulator for stops (007, 010), MJY cost and roll model for the MJY rewrites (012, 013, 014) | agent | nothing (A2 decided); no fetch | Build when a spec that needs it is next: the triage routes 007 and 010 to other pairs first, and 012-014 to MJY or park |

### B. Needs the fetch: after group A, and only with the user

| | Item | Who | Needs | Why last |
|---|---|---|---|---|
| **B1** | Decide how to check the day files written at a fetch death (they may be truncated; `HANDOFF-2026-11-26-remaining.md` §2): re-fetch those days, or a metadata-only integrity pass | user (can decide now) | fetch complete to act | Must precede B2; reading them earlier would break the blinding |
| **B2** | When the log ends `stage 3 complete`: tell the user; they review step 0's thresholds and the analysis code; then run `scripts/004_gap_fill_analysis.py` [1] | agent, after user review | fetch complete, B1 | Fully pre-declared; nothing to prepare beforehand |
| **B3** | Record the filled run in spec 004 and its copies [2] | agent | B2 | |
| **B4** | Housekeeping [11]: stop the supervisor if it has not exited; remove the worktree; move the main checkout off `research/002-intervention-disclosure`; decide the stash entry | agent; ask before renaming or deleting | fetch complete, A1 | The fetch and the supervisor run from the main checkout |
