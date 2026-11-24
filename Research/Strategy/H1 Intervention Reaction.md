# H1 Intervention Reaction

**Date:** 2026-11-24 · **Verdict:** rejected as a strategy, retained as a risk overlay
**Spec:** `specs/002-intervention-disclosure.md` · **Code:** `src/usdjpy/stats.py`

> **Holdout notice.** `HOLDOUT_START = 2025-01-01`. Section 6 of this document is
> post-holdout material and is fenced off there. No test was run on holdout data,
> so no look was spent on a result — but H1 was partly *selected* on 2026 evidence,
> which is selection contamination. It changes nothing: the rejection reproduces on
> pre-holdout data alone. Do not use Section 6 for parameter choice or testing, and
> do not read any of this as a clean out-of-sample finding.

---

## 1. Verdict

The conditioning event is real, well identified and robustness-tested. It is also
too rare to trade: **1.3 independent episodes per year**, net Sharpe **0.24–0.43**.
Costs are not the problem — the effect retains 89–95% of gross even under
`PESSIMISTIC`. Frequency is.

| Component of H1 | Status | Reason |
|---|---|---|
| BOJ disclosure effect | Real, un-tradeable | 1.3 episodes/yr |
| MOF rhetoric, top rung | **Fails** | Coincident with the operation, not leading |
| Proximity to a defended level | Retained | As risk control, not signal |

Full rules, evidence links, kill criteria and the rejection table are in
`specs/002-intervention-disclosure.md`. This document holds the reasoning that
does not belong in a spec: why the test is impossible rather than merely
negative, the risk overlay, and the methodological corrections that came out of
the work.

## 2. Why this is not a weak test but no test

The paper reaches t ≈ 3–5 using high-frequency data in a narrow window. On daily
bars the same true effect is invisible, and more history does not fix it.

`stats.min_detectable_pips`, 5-day window, sd of a 5-day move 224 pips at 10%
annualised vol:

| n treated as | MDE at 80% power |
|---|---|
| 13 operation days | 174 pips |
| 6 clusters (`stats.cluster_ids`, 4-day gap) | ~256 pips |
| 4 pre-holdout clusters | **314 pips** |

Published effect: **17–27 pips.** Ten to eighteen times too insensitive.

This is the general lesson, and it is why `specs/002` was rejected rather than
run: **an unconditional or low-n test spreads the signal across the sample; an
event study concentrates it.** Same market, same data, roughly a hundredfold
difference in statistical efficiency, purely from conditioning. Any future spec
should report its MDE next to its result so a null is read as "the study cannot
see an effect this size", never as "no effect exists".

The companion case: an unconditional autocorrelation test on daily USDJPY would
need **~689 years** for 80% power against ρ₁ = −0.05 (an effect implying Sharpe
0.79, well worth trading). Tradeability begins near |ρ| ≈ 0.03–0.05; detectability
needs |ρ| ≈ 0.20, implying Sharpe > 3 on one pair at daily frequency. Such a test
survives only as an asymmetric diagnostic: a null is uninformative, and a strongly
significant result indicates a **data problem** — stale quotes, mid-price
construction, timestamp misalignment, a bad holiday join — not an edge.

## 3. A correction to this repo's kill criteria

`events.summarize()` reports t = mean / (sd/√n). For MOF interventions that is
optimistic, because operations arrive in runs of consecutive business days and are
not independent observations.

```
pre-holdout: 7 operation days -> 4 independent episodes   (t overstated 1.32x)
full sample: 13 operation days -> 6 independent episodes   (t overstated 1.47x)
```

The cluster count depends on the gap threshold; `stats.cluster_ids` defaults to
4 calendar days. **Any spec whose event days can fall on consecutive dates should
use `stats.clustered_t` for the `t-stat < 2` criterion**, which returns the naive
and clustered t side by side so the inflation is visible. This applies to
intervention, to BOJ-meeting clusters, and to any month-end rule where the window
spans adjacent days.

## 4. Corrections to the reaction function, and to an earlier error

**Officials' stated reaction function and their estimated one disagree.** Ito &
Yabu's ordered probit over 2004/8–2018/3 finds the rate-of-change term
insignificant (10.22, t≈0.9) and only deviation from the 5-year moving average
significant (−33.32, t≈−2.9). The statistics support level-and-trend defence, not
the "speed not levels" language officials use. No model has been fitted to the
2022–2026 sample.

Practitioner thresholds in circulation (">1.5 yen/day over 3 days → operation
within a week") trace to a broker publication with internal numerical
contradictions and no stated sample. Do not use them.

**Error log — a 9× overstatement.** An earlier pass on this project put the
disclosure-effect Sharpe at 3.6. That assumed the event recurred on every daily
BOJ report (~250/yr) rather than on intervention disclosure days (~1.3 episodes/yr);
√(250/3) = 9.1, exactly the overstatement. The cause was computing on top of a
secondary summary instead of reading the paper's identification strategy. Recorded
because the same mistake is available to anyone reading the abstract: **"the BOJ's
daily report" is a daily event; "the disclosure" is not.**

## 5. Timestamp traps to encode before believing any result

Both manufacture *positive* findings from no signal.

1. **FRED `DEXJPUS` is a 12:00 ET noon buying-rate snapshot, not a 16:00 ET
   close.** Paired with a US equity or VIX close, the "predictor" is observed four
   hours *after* the "predicted" FX print. The Nikkei version is worse — Tokyo
   closes ~14h before the US. Note that the one publicly available practitioner
   event study on yen intervention uses DEXJPUS for exactly this purpose.
   This repo's Dukascopy bid/ask bars avoid the problem; do not substitute DEXJPUS
   for convenience.
2. **A matched-date US-minus-Japan yield spread mixes two information timestamps
   across the date line.** Treasury's curve for date *T* publishes after the US
   close on *T*, so it was not knowable in Tokyo on *T*; MOF publishes the JGB
   curve for *T* in the JST evening, before the US session of the same date. Fix:
   one daily decision timestamp, each leg lagged to its last genuinely published
   value — one day for the US leg, none for the JGB leg. Holiday calendars differ,
   so the spread is one-sidedly stale across Golden Week.
3. **CFTC COT** is a Tuesday snapshot released Friday ~15:30 ET; first actionable
   bar is the following Monday open — **four trading days** after the reference
   date. Aligning to the Tuesday date embeds look-ahead.
4. **MOF daily intervention detail publishes quarterly** (Jul–Sep 2026 appeared
   2026-11-09, ~100 days late). Regime labelling only. Joining on date is
   look-ahead of up to three months. MOF monthly periods also run roughly the 29th
   to the 28th, not calendar months.

## 6. Post-holdout context — DO NOT USE FOR TESTING OR PARAMETER CHOICE

Everything in this section is on or after `HOLDOUT_START`. It is recorded because
the risk overlay needs it, and because the positioning conflict is live. It
informed hypothesis selection. It must not inform a rule.

**Intervention record, 2026**, reconciled exactly against MOF's monthly aggregates:

```
Apr–May cluster        JPY 11,734.9 bn
Jul–Aug cluster        JPY 15,399.3 bn   (monthly record; US Treasury joined
                                          2026-07-31, first joint op since 1998)
                       ----------------
sum                    JPY 27,134.2 bn
published 2026 total   JPY 27,134.2 bn   (to 2026-10-28)
residual               JPY      0.0 bn
```

MOF's monthly print for 2026-09-29 – 2026-10-28 is **¥0**, so September and
October were clear. The window 2026-10-29 – 2026-11-26 — when USDJPY tested 160
three times — publishes **2026-11-30 19:00 JST**. "Not confirmed" is not "did not
occur": daily detail lags a quarter and MOF never confirms on the day.

**Gap sizing — the binding constraint, verified against CME's own pages.** Micro
JPY/USD (MJY): 1,250,000 JPY unit; tick 0.000001 USD/JPY = **$1.25**; quoted **USD
per JPY, the inverse of spot** (MJYZ6 0.00629 → 158.98); maintenance margin
**$280** (not ~$180, which is the Micro G5 average); **deliverable** settlement,
roll before 09:16 CT two business days before the third Wednesday of the quarter;
two quarters listed; front-month volume 410 contracts on 2026-11-24 — thin.

Because of the inverse quote, **one USDJPY pip is not one tick**: 159.00 → 159.01
moves MJY 0.396 ticks = **$0.494 per contract**.

| Intervention gap | Cost/contract | % of $280 margin |
|---|---|---|
| 400 pips | $197.76 | 70.6% |
| 500 pips | $247.21 | 88.3% |
| 700 pips | $346.09 | **123.6%** |

A single MJY contract can be carried past its own maintenance margin by one
intervention. At 28:1 effective leverage the micro contract's low margin is not low
risk, it is identical risk in a smaller wrapper. Sizing for survival on $10,000:
a 500-pip gap costing 5% of equity means **2 contracts, $566 margin** — 5.7% of the
account. **Margin availability is nowhere near binding; gap survivability is the
only constraint,** which makes the broker's margin requirement actively misleading
as a sizing guide.

**Positioning conflict, unresolved by design.** CFTC code 097741, futures-only,
week ending 2026-11-17, from the primary report:

```
non-commercial long    258,756   (66.3% of OI)
non-commercial short   142,439   (36.5% of OI)
NET                   +116,317   net LONG yen
implied w/e 11-10     +123,113   (matches the published +123.1K)
```

This refutes the undated "92.2K net short" figure in circulation. The crowded trade
has fully reversed — −163,412 net short yen in July 2026 to +116,317 net long now,
a **279,729-contract swing**. The consequence: if this long-yen crowd unwinds,
USDJPY rises *toward 160*, which is where intervention lives. The crowded-position
tail and the intervention tail now point in opposite directions and both are live.
**There is no position flat to both.** Any design touching either must resolve this
explicitly rather than averaging them.

## 7. Statistical corrections now in `src/usdjpy/stats.py`

Each validated against synthetic controls. Two are errors in the standard methods.

1. **The textbook variance-ratio test rejects on 79.5% of pure random walks**
   (GARCH(1,1) α=.08 β=.90, T=4000, 400 paths). Volatility clustering alone makes a
   random walk look mean-reverting four times in five. The Lo-MacKinlay
   heteroskedasticity-robust z, with the √T factor correctly applied, is sized at
   4.2% against a nominal 5%.
2. **The ACF standard error must be the direct HC sandwich**
   `var(ρ_k) = Σ x²_t x²_{t−k} / (Σ x²_t)²`. Not `1/√T`, and **not** the
   "variance inflation" form, which is inconsistent — simulated size rose from 27%
   at T=2000 to 47% at T=5000. The sandwich is sized at 4.7% and collapses to
   `1/√T` on homoskedastic data (ratio 0.999). On realistic FX vol dynamics it is
   **4.9–7.4×** the textbook SE.
3. **Hurst exponents require volatility-standardised returns.** On raw GARCH
   returns DFA bias is −0.099 against a truth of 0.5; EWMA standardisation (λ=0.94)
   cuts it to −0.004 and the spread by ~4×. This likely explains the inconsistency
   of published FX Hurst estimates.
4. **Portmanteau tests must use HC standard errors.** Ljung-Box assumes
   homoskedasticity and over-rejects severely.

Also in `stats.py`: `clustered_t` (section 3), `min_detectable_pips` (section 2),
and the Deflated Sharpe / False Strategy Theorem helpers. `expected_max_sharpe`
reproduces the published bracket at N=100 of 2.531 exactly, and `γ₄` is **Pearson**
kurtosis, not excess.

Hurdle on 10 years of daily data, by effective trial count:

| N | SR₀ to beat |
|---|---|
| 10 | 0.50 |
| 50 | 0.72 |
| 100 | 0.80 |
| 500 | 0.97 |
| 1,000 | 1.03 |

Consistency check: a t > 3.0 requirement implies Sharpe ≈ 0.95 on ten years, and
DSR reaches 0.97 at ~500 effective trials — the two gates bind equally at roughly a
500-trial search budget. Calibration anchor: at T=1000 and N=8800, SR₀ = **1.923**,
while the widely-cited random-walk demonstration produced a best-of-8800 in-sample
Sharpe of 1.27 — *below* what pure noise is expected to yield at that trial count.

## 8. Open items

| Item | Blocking |
|---|---|
| Intraday replication on the 13 disclosure dates | A few MB of Dukascopy data — tractable |
| Money broker settlement forecasts | **Not located free.** The real blocker |
| Reaction function on the 2022–2026 sample | No model exists |
| USDJPY 1w/1m IV, 25Δ risk reversals | 25Δ RR is OTC; no free authoritative source |
| MJY all-in cost (exchange + clearing fees) | Not published on CME's retrieved pages |
| Tax treatment (UK / China) | Jurisdiction-dependent; affects venue choice |
| `dukascopy.py` still working? | Dukascopy reportedly now returns 403/AWS WAF to scripted downloads |

## 9. Conclusion

H1 is a reason not to be long USDJPY into a defended level, and given that a
500-pip gap can exceed one micro contract's maintenance margin, that has genuine
survival value. It is not a strategy.

The two findings most likely to outlive the hypothesis are methodological, and both
came from calibrating before building rather than from running a backtest: the
textbook variance-ratio test declares random walks mean-reverting 79.5% of the
time, and a daily study of this hypothesis is ten to eighteen times too insensitive
to see the effect it is testing for. Each reversed a conclusion that had already
been written down. The repo's existing rule — *most ideas should die here, cheaply*
— is the right one; this is what it looks like when the dying is done properly.
