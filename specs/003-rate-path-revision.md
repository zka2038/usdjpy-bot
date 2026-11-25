# Spec 003: rate-path revision

**Author:** bzk · **Date:** 2026-11-24 · **Status:** rejected below SR 0.73; undecidable in the band 0.73-0.98

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

## Results — rejected

Run 2026-11-25, `datasets.load_minute("combined")`, pre-holdout, n = 4,211
business days at h=1 (16.7 years).

| h | n | std t_hc | SE ratio | raw rho | SR est | MDE SR | verdict |
|---|---|---|---|---|---|---|---|
| 1 | 4211 | +1.80 | 1.09 | +0.0253 | 0.40 | 0.89 | null |
| 3 | 1403 | +1.17 | 1.11 | +0.0437 | 0.40 | 0.89 | null |
| 5 | 842 | +0.81 | 1.09 | +0.0318 | 0.23 | 0.89 | null |
| 10 | 421 | +0.95 | 1.13 | +0.0431 | 0.22 | 0.89 | null |

Kill criterion 1 fires at every horizon (max |t_hc| 1.80 vs the 2.81 Bonferroni
bar). Criterion 4 fires independently: every SR point estimate is below the
tradeability bar even ignoring significance.

**It fails informatively.** The sign is positive at all four horizons, in the
hypothesised direction, so criterion 2 does not fire. This is a correctly-signed
effect that is too small — consistent with the literature placing the predictive
content at multi-quarter rather than daily horizons.

**The null is NOT well-powered, and the earlier claim here was wrong.** It read
"simulation gives 86% power at ρ=0.05, so this is not H1's uninformative null".
That power figure comes from `synthetic_check`, and the harness is not calibrated
to this sample: it recovered true ρ=0.030 at `t_hc` +5.78, while the real data
gives ρ=0.0303 at +1.80. Same correlation, t 3.2× smaller, because USDJPY's
errors are far worse behaved than the synthetic DGP's. Recovery proves the code
works; it does not transfer power to the real sample.

The sample's own MDE is the number that counts, and it contradicts the claim —
see the blind-spot paragraph below, which was in this section all along and which
"well-powered" directly contradicts. Carrying the HC inflation through
(SE(ρ) = se_ratio/√n, not 1/√n) raises MDE ρ from 0.0563 to **0.0613** at h=1,
i.e. MDE Sharpe **0.97**, not 0.89. Observed MDE/ρ is 2.0× at h=1 rising to 4.5×
at h=5: the test cannot see effects of the size present.

**The SE ratio came back at 1.00–1.13, not the predicted 5–7.** That is *not*
evidence the heteroskedasticity problem is absent: `rate_path_signal()` already
divides the spread change by `fx_vol` before z-scoring, so the correction was
applied one step upstream of the regression. Simulated, an unscaled signal gives
SE ratio 5.98 and 13% power; the vol-scaled signal gives 0.49 and 86%. The
machinery earned its place — the regression-level diagnostic was quiet because
the fix had already worked.

**Known defect in the output.** Because `rate_path_signal()` bakes in the vol
scaling, the "raw" column is not a fixed-notional specification, so
`sharpe_from_raw` is not the fixed-notional Sharpe it is documented as. The
verdict is unaffected (all null) but the sizing column is mislabelled. Fix:
compute ρ once against the unscaled spread change.

**Blind spot to record.** MDE Sharpe is **0.97** (0.89 before the HC correction
above) while the tradeability bar is 0.73 (3/√16.7 for the actual span, not the
0.67 the script used). Effects implying a Sharpe between 0.73 and 0.97 were
**tradeable but undetectable** here.
A null does not rule them out. The gap exists because testing four horizons
pushes the Bonferroni detection bar above the economic one.

**Sample caveat.** n = 4,211 implies `combined`, which includes the 2007–2014
Dukascopy slice that is 40–65% complete across 2011–18 with 2020 absent. Those
observations are non-randomly selected — whichever days a third party's export
happened to capture. A re-run on `histdata` alone is the clean check and costs
about half the sample.
