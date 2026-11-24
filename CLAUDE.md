# usdjpy-bot — working rules

Research → backtest → live pipeline for USDJPY, executed through IBKR. Layer 1 is
pandas event studies and predictive regressions in this repo; most ideas should die
here, cheaply. Layer 2 is NautilusTrader with bid/ask fills.

**Read the relevant spec in `specs/` before touching any study.** Each has its kill
criteria declared before testing. Do not revise kill criteria after seeing results.

---

## Hard rules

**Holdout.** `HOLDOUT_START = 2025-01-01` in `src/usdjpy/config.py`. Nothing on or
after that date is used until a strategy has passed on earlier data and its spec is
frozen. `events.window_trades` defaults `allow_holdout=False` — leave it. Each look
spends it. If you use post-holdout data for anything, declare it in the spec and in
the research doc, and say whether it informed selection or testing.

**One cost model.** Every result goes through `costs.CostModel` (bid/ask fills +
IBKR 0.20bp, $2 min, 0.10 pips slippage/side) and must also survive `PESSIMISTIC`.
Base round trip is 0.836 pips ex-spread at 159; `PESSIMISTIC` is 1.236.

**Compare against control days, not zero.** An effect present on every day is
time-of-day drift, not the flow you hypothesised.

**Pre-declare parameters.** No grid-searching entry/exit times over the full sample.
Each tuned number spends statistical power and there is none spare — see
`Research/Strategy/Hypothesis Review H1 to H3.md` §2.

---

## Inference rules (learned the hard way; see the Review doc for the simulations)

**Report the MDE beside every null.** `stats.min_detectable_pips`. A null whose MDE
sits far above the effect size the literature claims is uninformative, not evidence
of absence. H1 was rejected because its daily MDE was 174–314 pips against a
published 17–27 pip effect — the test was impossible, not merely negative.

**Clustered events need `stats.clustered_t`, not the naive t.** Events on
consecutive dates are not independent observations. MOF interventions are 7
operation days in 4 pre-holdout episodes, so `events.summarize`'s
`mean/(sd/√n)` is optimistic by 1.32–1.47×. Applies to intervention, BOJ-meeting
clusters, and any window rule spanning adjacent days.

**Regressions of FX returns on a rates signal must be volatility-standardised.**
Plain OLS t rejects on 77.3% of pure nulls when the regressor's volatility
co-moves with the return's. White HC errors fix the size (5.7%) and then destroy
the power (9.7% at ρ=0.05). Standardising both sides by EWMA vol gives size 3.7%
and power 100%. Use `signals.predictive_regression`, which reports `t_hc`,
`t_naive` and their ratio — expect 5–7 on raw, ~1 on standardised.

**Test and estimate are different regressions.** The standardised spec has correct
size and high power: use it to TEST. The shared vol divisor inflates its
correlation 2.2–2.8×, so it is not an estimator of magnitude. The raw spec recovers
ρ almost exactly: use it to SIZE. Reading the standardised ρ as the tradeable
correlation turns a Sharpe-0.47 effect into an apparent 1.30.

**Validate the harness before trusting a null.** Build a synthetic series with a
known effect and confirm the code recovers it, and that a true null does *not*
pass. `signals.synthetic_check` does this and `scripts/rate_path_study.py` refuses
to run on real data until it passes. This is not ceremony: a calibration simulator
that paired `x_t` with a contemporaneously-correlated `y_t` returned power = size
in every cell, an apparent null from a harness with no signal in it.

**Autocorrelation SEs must be the HC sandwich**, `stats.acf_se_hc`. Not `1/√T`, and
not the variance-inflation form (inconsistent: size 27% at T=2000 → 47% at
T=5000). On FX vol dynamics the correct SE is 4.9–7.4× the textbook value.

**Variance ratios must use the robust z**, `stats.variance_ratio`. The textbook
homoskedastic test declares pure GARCH random walks mean-reverting 79.5% of the
time.

**Hurst exponents need vol-standardised returns**, `stats.ewma_standardise` first.
Raw-return DFA bias is −0.099 against a truth of 0.5.

---

## Two bars, not one

Significance and tradeability are a factor of three apart. At the published median
73% backtest-to-live Sharpe haircut:

| | Backtest SR | implied t (20y) | net @10% vol, 2 trades/wk |
|---|---|---|---|
| detection (t=2) | 0.45 | 2.0 | +0.57%/yr |
| multiple testing (t=3) | 0.67 | 3.0 | +1.16%/yr |
| live SR 0.30 | 1.11 | 4.97 | +2.35%/yr |

**Never set a kill criterion at t=2 alone.** State a tradeability bar separately.
A result can be significant and unprofitable.

**The limit:** detectable Sharpe at t=2 is `2/√(years of data)`, independent of
holding horizon — the √n and √(252/h) factors cancel exactly. Horizon is a question
about costs and capacity, never about power. Only cross-sectional breadth moves
this.

---

## Timestamp traps

All of these manufacture *positive* results from no signal.

1. **FRED `DEXJPUS` is a 12:00 ET noon snapshot, not a close.** Never pair it with
   a US equity or VIX close — the "predictor" is then observed four hours after the
   "predicted" print. Use the Dukascopy bars. Nikkei is worse: Tokyo closes ~14h
   before the US.
2. **A matched-date US-minus-Japan yield spread mixes two information sets across
   the date line.** Treasury's curve for *T* publishes after the US close on *T*;
   MOF publishes the JGB curve for *T* in the JST evening. Use
   `signals.build_spread`, which lags the US leg one business day and the JGB leg
   none, and records per-leg staleness.
3. **CFTC COT** is a Tuesday snapshot released Friday ~15:30 ET — first actionable
   bar is the following Monday, four trading days later.
4. **MOF daily intervention detail publishes quarterly** (~100 days late). Regime
   labelling only, never a contemporaneous input. Its monthly periods run ~29th to
   ~28th, not calendar months.

---

## Gotchas in this repo

- `calendars.gotobi_days()` **includes the last business day of the month**, so
  spec 001's treatment group bundles two mechanisms. Month-end is 17% of those days
  and roughly 28% of the measured effect. `specs/004` separates them.
- CME `6J`/`MJY` are quoted **USD per JPY — the inverse of spot**. One USDJPY pip
  is 0.396 MJY ticks = $0.494/contract, not one tick. MJY maintenance margin is
  $280 and settlement is **deliverable**.
- Size for gap survival, not margin. A 700-pip intervention gap is 123.6% of one
  MJY contract's maintenance margin, so margin availability is misleading as a
  sizing guide. A stop is not protection: USDJPY moved 160.17 → 156.60 in ~11
  minutes on 2024-04-29, and MOF repeatedly chooses thin-liquidity windows.
- `data/` and `results/` are gitignored. A fresh clone has no data; symlink it or
  work in the clone that has it.

---

## Current state

| Spec | Status | Note |
|---|---|---|
| 001 gotobi / Tokyo fix | tested | confounded with month-end; re-read after 004 |
| 002 intervention disclosure | **rejected** | real effect, 1.3 episodes/yr, SR 0.24–0.43 |
| 003 rate-path revision | testing | needs `data/dgs2.csv`, `data/jgbcme_all.csv` |
| 004 turn-of-month separation | testing | no new data needed |

Four signal families already died: trend/technical, calendar-as-signal, carry, risk
appetite. Eight families examined, six dead, two testable, zero tested. The binding
constraint is now the number of hypotheses worth testing, not the method.

Context: `Research/Strategy/Hypothesis Review H1 to H3.md` and
`Research/Strategy/H1 Intervention Reaction.md`.
