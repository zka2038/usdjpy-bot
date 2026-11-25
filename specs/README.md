# Strategy specs

One file per idea. A spec is written, and its kill criteria fixed, **before** any test is run.
Sources for specs 006–018: `docs/research/USDJPY additional strategies to test.md` (test queue) and
`docs/research/USDJPY retail trading strategies.md` (earlier shortlist), both dated 2026-11-24.

## Index

| # | Spec | Priority tier / author | Horizon | Data ready? | Status |
|---|---|---|---|---|---|
| 001 | [Gotobi / Tokyo 9:55 fix](001-gotobi-tokyo-fix.md) | Earlier report #1 | Intraday (hours) | Y | upheld; mechanism unconfirmed (004's A-vs-B was uninformative) |
| 002 | [MOF/BoJ intervention disclosure](002-intervention-disclosure.md) | bzk | — | — | rejected |
| 003 | [Rate-path revision](003-rate-path-revision.md) | bzk | — | — | rejected below SR 0.73; undecidable 0.73–0.98 |
| 004 | [Turn-of-month separation](004-turn-of-month-separation.md) | bzk | — | — | effect confirmed (t +3.15 / +3.11); separation unanswerable; tradeability blocked on spread; gap fill declared (see *Dukascopy fetch*) |
| 005 | [Rate-path revision, trade simulation (H3)](005-rate-path-trade-test.md) | Haru | — | — | rejected |
| 006 | [Weekend-gap reversal](006-weekend-gap-reversal.md) | Tier 1 #1 | Mon intraday – 3 days | Y (check Sunday-open bars) | idea |
| 007 | [No-news 1-min shock fade](007-no-news-shock-fade.md) | Tier 1 #2 | 15–60 min | partial (release calendar) | idea |
| 008 | [US release post-jump continuation](008-us-release-post-jump-continuation.md) | Tier 1 #3 | Hours – 1 day | N (release calendar) | idea |
| 009 | [BoJ statement → press-conference reversal](009-boj-statement-press-conference-reversal.md) | Tier 1 #4 | Hours | partial (rate-check dates) | idea |
| 010 | [Round-number fade / breakout vs placebo](010-round-number-fade-breakout.md) | Tier 1 #5 | 30–120 min | Y (loader needs high/low) | idea |
| 011 | [Treasury auction cycle](011-treasury-auction-cycle.md) | Tier 1 #6 | Hours | N (auction calendar) | idea |
| 012 | [Equity-shock haven short](012-equity-shock-haven-short.md) | Tier 1 #7 | 1–3 days | partial (SP500 scriptable) | idea |
| 013 | [COT leveraged-fund extreme + turn](013-cot-extreme-turn.md) | Tier 1 #8 | 4 weeks | Y | idea |
| 014 | [Vol-scaled trend + carry, crash filters](014-vol-scaled-trend-carry.md) | Earlier report #2–3 | Weekly / months | partial (DFF scriptable) | idea |
| 015 | [Month-end equity-hedge rebalancing](015-month-end-equity-hedge-rebalance.md) | Earlier report #4 | 1 hour, monthly | partial (SP500 scriptable) | idea |
| 016 | [Rate differential, correlation-gated](016-rate-differential-correlation-gated.md) | Earlier report #5 | Weekly | partial (DGS2 scriptable) | idea |
| 017 | [Risk overlays (judged on drawdown)](017-risk-overlays.md) | Overlay | Daily / weekly | partial (HAR model, release calendar) | idea |
| 018 | [Expected-null calendar battery](018-expected-null-battery.md) | Tier 0d | Mixed | Y | idea |

"Partial/N" items and how to fill them are listed in each spec's *Data needed* section.

## Build first (Tier 0, not specs)

- **0a Seasonality map:** mean and t by 30-min JST bucket, by year, gotobi vs non-gotobi; the
  overnight/NY split; day-of-week; spread by minute-of-week (Eightcap). This is the control every window
  test is read against.
- **0b Volatility model:** HAR-RV on 5-min RV, minute-of-week vol profile, vol-target sizing (used by
  007, 017).
- **0c Event calendars:** `data/calendars/us_releases.csv` (BLS/BEA NFP, CPI times),
  `data/calendars/ust_auctions.csv` (TreasuryDirect), `data/calendars/rate_checks.csv` (by hand),
  BoJ 2007–09 dates. Run `scripts/fetch_official.py` (DGS2, DFF, SP500, …) and `scripts/download.py`
  (bars after 2026-06-05; holdout use only).
- **Harness gaps found while writing the specs:**
  - `datasets.load_minute` returns bar close only, but stops need bid high/low.
  - `events.window_trades` rolls the exit at most one day and has one timezone, so it needs a
    timestamp-based helper for multi-day or ET-anchored holds.
  - `costs.py` has no overnight financing.
  - `summarize()` periods don't match the 2015–19/2020–24 split.
  - There is no weekly portfolio simulator (needed for 014/016/017).
  - There is no loader for the H.10 daily or the BoJ call-rate files.
  - Verify HistData UTC alignment in US summer: `docs/DATA.md` says the raw stamps are NY local with DST,
    while `scripts/build_github_data.py` applies a fixed +5 h.

## Dukascopy fetch: options and decision (2026-11-25)

Spec 004 is blocked on spread provenance, and its sample has data gaps. Both can be fixed with
Dukascopy bid/ask ticks, which are free but rate-limited hard: a burst of requests earned a block
of about 6 hours on 2026-11-25. After it lifted, roughly half the requests sent one every 30 s
still failed. One request is one UTC hour of one pair. **Decision: option C**, run by
`scripts/download_gap_fill.py` into `data/tokyo_hours/`. The full-day tree `data/USDJPY/` is not
touched.

### What the specs need from it

| Group | Specs | Does a Tokyo-window USDJPY fetch help? |
|---|---|---|
| Trade the Tokyo window | 001, 004 (and 003's 00:00 UTC decision) | **Yes. This is what the fetch is for.** |
| Monday 08:00 JST entry or rebalance | 006, 013, 014, 016 | Partly. Monday 08:00 JST reads the Sunday 22:59 UTC bar, which is in the window. 006 also needs the Sunday 21:00 UTC reopen under US daylight time, which is not. For 013/014/016, financing costs far more than the spread. |
| Event days at other hours | 008, 009, 011, 012, 015, 018 | No. Fetch event-hour spreads only for a spec that passes a test on existing data first. That is a few hundred days per spec. |
| Fills at arbitrary minutes | 007, 010 | No. They validate fills on Eightcap ticks (2024-06 onward). |
| Daily or weekly | 017 | No |

Two further limits on what Dukascopy can do for specs 006–018:
- **The trial budget** (`HANDOFF.md` §2) routes specs 006–018 onto other JPY crosses. Their main
  need is cross-pair minute bars, which HistData provides free. `fetch_official.py` hardcodes
  `usdjpy`, and the cross-pair files are not yet checked.
- **Most of what blocks them is not prices.** It is the calendars in 0c, FRED series, and bar
  high/low in the loader.

### Spec 004's missing trades

Spec 004 drops days with no quote at an execution minute. Pre-holdout B (Gotobi-proper) days
2007–2024: **1,075**.

| | Prefix (n=882) | Postfix (n=947) | Cause |
|---|---|---|---|
| 2007–2014 | 176 | 125 | gaps in the third-party Dukascopy bid export |
| 2023 | 13 | 0 | HistData's Feb–Jul 2023 gap covers the 23:00 UTC entry. In 2023 the prefix has 47 of 60 days. |
| 25 December (2015, 2017, 2019, 2023, 2024) | 4 | 3 | No source quotes; unfillable |
| **Total** | **193** | **128** | |

The prefix leg needs 990 trades for 80% power, and 882 are available. Filled, it would have about
1,071: about 83% power if the effect holds at +2.068.

### Options

Counts are requests; times assume one request every 30 s.

| | Scope | Requests | Time | Delivers |
|---|---|---|---|---|
| A | UTC hours 22–2, every non-Saturday day, 2007–2024 | 28,180 | ~10 days | Real bid/ask on every trade. About a third of the requests are for hours or days no spec reads. |
| A, trimmed | Hours 22, 23, 0, 1, market open only, 2007–2024 | 18,790 | ~6.5 days | The same, without the waste |
| B | Spread sample only | ~1,300 | ~11 h | Measured spread by era. Fills no gaps. |
| **C (chosen)** | **The staged fetch below** | **~10,500** | **~3.6 days** | **Fills the gaps and measures spread where it is least known** |

Option C, in order:

| Stage | UTC dates | Requests | Purpose |
|---|---|---|---|
| 1 | 2023-01-31 – 2023-07-31, every weekday | 520 | Restores the 13 prefix trades lost to the 2023 gap |
| 2 | First B day and first C day of each month, 2015–2024 (a fixed calendar rule) | 1,604 | Measured spread for the HistData era, on treatment and control days. From 2024-06 it doubles as a Dukascopy-vs-Eightcap venue check. |
| 3 | 2007–2014, every weekday | 8,354 | Real bid/ask where the spread is least known (the sensitivity script assumes up to 5× today's). Restores 176 prefix and 125 postfix trades. |

**Why C:**
- It restores the sample spec 004 declared, lifting the prefix leg past the 990 trades needed for
  80% power.
- It measures the spread where the uncertainty is largest, for 56% of the requests of trimmed
  A.
- Stage 3 is the first half of trimmed A, so extending to 2015–2024 later wastes nothing.

**Hours: UTC 22, 23, 0 and 1** (`dukascopy.TOKYO_MORNING_HOURS`). `events.quote_at` reads the bar
one minute before each trade:
- hour 22: the 23:00 entry, and the Monday 08:00 JST bar
- hour 23: spec 003's 00:00 decision
- hour 0: 00:55
- hour 1: 02:00

Hour 2 is not read by any spec and was dropped. Requests are trimmed to market hours (closed from
Friday 22:00 UTC to Sunday 21:00 UTC). Each day's hour set depends only on the weekday, so
overlapping stages write identical files.

**Caveats:**
- **Optional stopping.** The fill is motivated by a power shortfall seen after the result. It is
  declared before any filled data is seen, in spec 004's *Gap fill* section, which also fixes how
  the data will be used. It restores the declared sample under unchanged rules, so it is not a new
  trial.
- **Source switch.** Stage 3 replaces a bid-only third-party export with Dukascopy ticks inside
  2007–2014. Spec 004 requires the two to agree on overlapping minutes before any fill is used.
- **One venue.** The Dukascopy spread is one venue's quote, not IBKR's.
- **Sparse tree.** Stage 2 is a sample, so `data/tokyo_hours/` is sparse for 2015–2024. It is a
  spread source for that period, not a price source.

## Workflow

1. Copy `TEMPLATE.md` to `NNN-short-name.md`. Fill in the hypothesis (who is forced to trade), the
   evidence, exact rules (times in JST **and** UTC, with US/UK DST noted), the data needed, and the
   **kill criteria and parameters before running anything**. Open a PR.
2. Run the test on pre-holdout data only (`HOLDOUT_START = 2025-01-01`), with base `CostModel()` and
   `PESSIMISTIC`, against control days or placebos.
3. Record results in the spec's *Results* section (summary table, path to `results/` files, decision)
   and add one row per variant to the ledger below, **including failures**. `results/` is git-ignored,
   so the ledger and Results sections are the permanent record.
4. Set status: `rejected`, or `passed` → `frozen`. Only a frozen spec may look at the holdout, once.
   After that comes paper trading on IBKR.
5. When two live strategies fire together (e.g. a Monday gotobi day with a weekend-gap long), net the
   positions and cap combined exposure. Never stack full positions.

## Multiple-testing rule

The queue implies ~35 tests (8 strategies × up to 3 variants + ~10 diagnostics). At p < 0.05 about two
pass by chance, and Bonferroni (0.05/35) implies t ≈ 3.2. The compromise used here:

- **Confirmatory** (rule and parameters taken from published work: 006 weekend gaps, 010 Osler round
  numbers, 011 auction cycle, 015's all-month-end regression): **t ≥ 2**.
- **Exploratory** (thresholds chosen by us: 007, 008, 009, 012, 016, any hit from 018): **t ≥ 3 and the
  same sign in 2015–2019 and 2020–2024**.
- **Rare events** (≲ 30 trades per side in 2015–2024): replace the template's "effect present in 2022+"
  with "same sign in 2015–2019 and 2020–2024". The 2025–26 holdout plus forward paper trading is the
  confirmation.
- **Tiny samples** (013 COT, 018 N5/N6): a t-stat is meaningless there, so use the placebo/sign-test
  criteria in the spec. Report trade by trade.
- **Trend/carry (014) and overlays (017):** a single pair lacks the power to confirm a Sharpe of ~0.3,
  so these are judged on the literature prior plus the pre-declared robustness and drawdown criteria
  in their specs.
- At most 3 pre-declared variants per spec. No grid search. Every variant run counts.

## Not specced

**Data-acquisition track** (testable once data exists):
- Japanese retail liquidation rule: short when the TFX Click 365 retail net-long share is ≥ its 1-year
  90th percentile and USDJPY closes below its 10-day low; hold 5 days. Needs a consistent retail
  positioning series.
- Implied-vol / risk-reversal crash filter: needs IBKR CME JPY options implied-vol history.

**Deprioritised** (until a new yen-specific out-of-sample paper or a clear Tier 0a pattern appears):
- **Minute-scale lead-lag (UST/ES/Nikkei futures):** spot has led price discovery since 2006 (NY Fed
  SR262), retail latency is too slow, and intraday futures data is paid.
- **Daily residual "catch-up" model:** cheap, but no paper supports it, and JIE 2023 finds nothing
  beats the random walk out of sample for the dollar.
- **Options: risk-reversal timing, single-pair VRP, expiry pinning/barriers:** RRs explain little of
  future skew (Jurek). VRP evidence is cross-sectional only (Della Corte et al.). Pinning has no FX
  evidence. No option data in the repo.
- **Dollar-factor and cross-currency-basis signals:** dollar carry duplicates the US–JP rate filter.
  The basis-to-spot link is insignificant (R² 0.012, Fed IFDP 1283).
- **REER / PPP timing:** value added nothing in a 16-year out-of-sample test (Barroso & Santa-Clara).
  Use it only as a position-size cap.
- **Intraday momentum, overnight/NY switch, vol-filtered opening-range breakouts:** decayed
  (Baltussen: t = 1.45 post-2000), cost-bound (the switch nets ≈ 0), or in the breakout family that
  already failed. Intraday momentum is checked once in 018 N7.
- **Karnaukh signalled pre-FOMC trade:** JPY is the only G10 currency with an insignificant loading
  (0.30, t = 0.94), and it needs fed funds futures (ZQ) data.
- **Pre-BoJ drift:** rests on about five 2023 meetings (MNI).
- **Tankan / Tokyo CPI drift, JGB auctions and rinban, February redemptions, JGB coupon dates,
  dividend season:** no evidence found for any of them.
- **BoJ leak continuation, keyword-triggered intervention fades:** need timestamped headlines, and the
  samples are tiny.
- **Asset-manager vs leveraged-fund COT divergence:** no source supports it.
- **ML (intraday or daily):** the 2026 working papers disagree on whether ML beats the random walk at
  all. If tried, do it last, walk-forward, against the carry and trend benchmarks.
- **From the earlier report:** London-fix fades, Asian-range/London-open breakouts, RSI/Bollinger
  reversion, NFP/CPI/BoJ scalping, intervention-fade entries, 6J order flow, MOF weekly flows and
  calendar-month seasonality. Each has negative or absent cost-inclusive evidence, or too few events.

## Test ledger

| Date | Spec | Variant | Sample | n | Mean net pips | t | Decision |
|---|---|---|---|---|---|---|---|
| | | | | | | | |
