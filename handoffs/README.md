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
| `HANDOFF-2026-11-26-remaining.md` | 2026-11-26 00:00, updated through 19:00 | What remains, fetch status and procedure, scope for continuing | **Current**: the detail behind the priority list |
| `HANDOFF-2026-11-26-next-session.md` | 2026-11-26 01:00 | How to start a session | **Current** |

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

**In progress**
- **Dukascopy gap-fill fetch, stage 3** (2007-2014 Tokyo mornings): runs unattended;
  status and procedure in `HANDOFF-2026-11-26-remaining.md` §2.

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

## Priority list (2026-11-26 ~19:15 UTC)

Set against the fetch: stage 3 needs about 68 more hours at full pace (29 Nov at the
earliest, later with rate limiting or a power loss), so everything below except P7 fits
before it ends. P7 jumps to the top the moment the fetch completes. Numbers in brackets
are items of `HANDOFF-2026-11-26-remaining.md` §6.

| | Item | Who | Needs | Why this rank |
|---|---|---|---|---|
| **P0** | Keep the fetch alive: mains power; restart by §2's procedure if it dies. Check it with `scripts/fetch_status.py` | user / agent | nothing | Three deaths so far (two at low battery); every hour lost is ~30 days of stage 3 |
| **P1** | Merge `research/remaining-work` into `main` | user | GitHub compare page (`gh` absent) | Carries the triage, the handoff updates and this folder |
| **P2** | Decide: sign off or amend the specs 006-018 triage, including whether each new pair starts its own spec count [6]; spec 007 bid or mid [4]; spec 017 HAR levels or log [5] | user | reading only | Minutes of work; P3, P5 and P6 depend on the first |
| **P3** | JPY-cross breadth study [7]: first pre-declare a spec (spec 004's rule on EURJPY, AUDJPY, GBPJPY, MOF days excluded) before any cross data is seen; then, on go-ahead, the HistData cross-pair fetch and per-pair spread profiles | agent, user go-ahead for the fetch | spec text; then a new fetch (HistData, not Dukascopy, so no shared rate limit) | Highest-value next study (`HANDOFF.md` §2): the only route to confirming spec 004's effect, and it runs alongside the fetch |
| **P4** | Spec 003 follow-ups [9]: compute the fixed-notional column against the unscaled spread change; re-run on `histdata` alone | agent; report before restating | data on disk | Cheap; corrects a mislabelled column in a rejected spec. Low value, so after P3 |
| **P5** | Data for the specs the triage approves [8]: US release calendar, Treasury auction calendar, full `fetch_official.py` (S&P 500, MOF and CFTC official files) | agent, each on go-ahead | P2 | Ordered by the triage; nothing to fetch until it is signed off |
| **P6** | Infrastructure for approved specs: bar-loop simulator for stops (007, 010), MJY cost and roll model if MJY rewrites are approved | agent | P2 | Only if the triage keeps those specs |
| **P7** | **When the fetch completes:** stop and tell the user; they review step 0's thresholds and the analysis code; run `scripts/004_gap_fill_analysis.py`; record the filled run in spec 004 and its copies [1-2] | agent, user review first | fetch complete | Time-triggered: top priority the moment the log ends `stage 3 complete` |
| **P8** | Housekeeping after the fetch and the merge [11]: remove the worktree; move the main checkout off `research/002-intervention-disclosure`; decide the stash entry | agent, ask before renaming or deleting | fetch complete | Must wait: the fetch runs from the main checkout |
