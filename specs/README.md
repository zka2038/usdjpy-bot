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
| 004 | [Turn-of-month separation](004-turn-of-month-separation.md) | bzk | — | — | effect confirmed (t +3.15 / +3.11); separation unanswerable; tradeability blocked on spread |
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
