# Spec 003: rate-path revision

**Author:** bzk · **Date:** 2026-11-24 · **Status:** testing

Layer-1 test is a **predictive regression, not a trade simulation.** Trade rules are
stated below but are not to be built until the regression passes. See
`Research/Strategy/Hypothesis Review H1 to H3.md` §6 for the power calibration.

## Hypothesis

USDJPY's relationship to the US–Japan rate differential is overwhelmingly
*contemporaneous* — a 1-month window puts US 2y and 10y swaps at ~96% correlation
with USDJPY while the Japan 10y leg sits at −14%, and a 12-week rolling correlation
against the 10y spread averaged +0.43 pre-October-2025, peaked at 0.91, then
averaged −0.07. None of that is tradeable as stated.

Who is forced to trade: a US rate repricing lands in the New York session, while
the bulk of yen-funded carry and hedging flow is re-marked in the following Tokyo
session. Japanese institutional hedgers and yen-funded investors cannot adjust
instantaneously — hedge-ratio and funding decisions move on committee timescales,
not tick timescales. So a *revision in the expected rate path* should be impounded
with a lag of days rather than seconds, and the tradeable object is the **change**
in the differential, or the **residual** from a contemporaneous fair-value fit, not
the level.

Direction: a widening of the US-minus-Japan path (US repricing hawkish relative to
Japan) predicts USDJPY up over the following 1–10 days.

## Evidence

- Contemporaneous strength, not predictive: MNI (1-month window, US 2y/10y swaps
  ~96%, Japan 10y −14%); MUFG 12-week rolling correlation (+0.43 → −0.07 after
  October 2025). Both descriptive, neither out-of-sample.
- Only predictive evidence located is **quarterly and pooled across 8 currencies**:
  differential → excess return coefficient 2.17 at t+1 quarter, decaying to −0.04
  by t+10 (NBER WP 14473). Wrong frequency and not USDJPY-specific.
- One dated conditional statistic, **sample size and period not stated**, so treated
  as a hint not evidence: when US–Japan 2-year spreads compressed ≥15bp over five
  sessions, USDJPY fell in every instance, averaging −3.92%.
- **No published "yen per 100bp" beta exists.** No daily-frequency Granger or
  lead-lag study for USDJPY against the differential was found in any accessible
  source. This hypothesis has essentially no direct prior at 1–10 days — which is
  the reason to test it, and the reason not to expect much.

## Rules (exact, no discretion)

**Timestamping — the single most important rule here.** A matched-date
US-minus-Japan spread mixes two information sets across the date line. Treasury's
curve for date *T* publishes after the US close on *T*, so it was not knowable in
Tokyo on *T*. MOF publishes the JGB curve for *T* in the JST evening, before the US
session of the same date.

- Decision timestamp: **00:00 UTC** each day.
- US 2y: lagged **one business day** (last value published before the decision
  timestamp).
- JGB 2y: **no lag** (published JST evening of the prior date).
- Japanese and US holiday calendars differ: forward-fill each leg independently and
  record a `stale_days` column per leg. Drop any observation where either leg is
  stale by more than 3 business days (Golden Week, year-end).

**Signal.**
- `spread_t = US2Y_t(lagged) − JGB2Y_t`
- `raw_signal_t = spread_t − spread_{t−n}`, with **n = 5 business days** (one value,
  pre-declared, not searched)
- `vol_t` = EWMA conditional volatility of USDJPY daily log returns, λ = 0.94
  (`stats.ewma_standardise` convention)
- `signal_t = (raw_signal_t / sd_n(raw_signal)) / (vol_t / mean(vol))`, then
  z-scored over an expanding window using data up to *t* only

**Test (Layer 1).** Regress vol-standardised forward returns on the standardised
signal:
- `y = (log P_{t+h} − log P_t) / vol_t`, non-overlapping blocks
- `h ∈ {1, 3, 5, 10}` — four tests, declared in advance, Bonferroni-corrected
- White HC standard errors (`stats.acf_se_hc` convention; HC0 on the regression)
- Report `rho`, `t_HC`, `t_naive`, the HC/naive SE ratio, and the MDE alongside

**Trade rules, IF and only if the regression passes.** Not to be built before then.
- Entry: long USDJPY when `signal_t > +1.0`, short when `< −1.0`, at 00:00 UTC
- Exit: `h` business days later at 00:00 UTC, or on signal sign flip
- Stop: none; size for a 500-pip intervention gap (see `H1 Intervention Reaction.md` §6)
- Filters: skip BOJ MPM and FOMC decision days; skip if either yield leg is stale
- Size: ≥ USD 100k notional

## Data needed

| Series | Source | Notes |
|---|---|---|
| USDJPY 1-min bid/ask | `usdjpy.dukascopy`, `DATA_DIR` | existing pipeline |
| US 2y Treasury | FRED `DGS2` (from 1976-06-01) or Treasury CSV | daily; **pre-2023 Treasury needs the Daily Archives page** |
| JGB 2y | MOF `jgbcme_all.csv` (from 1974) | single direct download, no key |
| US 10y / JGB 10y | FRED `DGS10`, same MOF file | for the fair-value residual variant only |

Do **not** substitute FRED `DEXJPUS` for the FX leg: it is a 12:00 ET noon snapshot,
not a close, and pairing it with a US-close-stamped yield manufactures
predictability. Use the Dukascopy bars.

## Kill criteria (decided BEFORE testing)

1. `|t_HC| < 2.81` on the vol-standardised regression at every h (Bonferroni, 4 tests), or
2. Sign of `rho` inconsistent across h ∈ {1,3,5,10}, or
3. Effect absent in the `2022+` period (`events.PERIODS`), or
4. **Tradeability bar, separate from significance:** implied Sharpe below **0.67**
   (the t=3 multiple-testing hurdle on 20 years). A result that is significant but
   implies Sharpe < 0.67 is recorded as "effect exists, not tradeable" and does
   **not** proceed to Layer 2. See Review §2 — detection and tradeability are a
   factor of three apart, and t=2 significance is compatible with an unprofitable
   strategy.
5. Fails under `PESSIMISTIC` costs once trade rules exist.

## Parameters

Four, all pre-declared, none searched: lookback n = 5 business days; EWMA λ = 0.94;
entry threshold ±1.0 z; decision timestamp 00:00 UTC. The horizon h is tested at
four values and Bonferroni-corrected rather than selected.

**Not permitted:** searching n, λ or the threshold. Each tuned number spends power,
and §2 of the Review shows there is none spare.

## Harness requirement

Before trusting any null from this spec, confirm the regression code recovers a
**known** predictive link from synthetic data. A simulator bug that paired `x_t`
with a contemporaneously-correlated `y_t` produced power = size in every cell
during calibration — an apparent null from a harness with no signal in it. Build
the synthetic check first.

Expected HC/naive SE ratio on real data is **5–7×** if the signal's volatility
co-moves with FX volatility, and ~1× if it does not. Record it: a ratio near 1
means the vol-standardisation was unnecessary, and a large ratio on the
*standardised* series means the standardisation failed.

## Results

<to be filled in: link to `results/`, the rho/t table across h, the HC/naive ratio,
the MDE, and the decision>
