# Hypothesis Review: H1 to H3

**Date:** 2026-11-24 · **Question:** is H1/H2/H3 enough to build a strategy on?
**Answer:** no for a trading system, yes for a research programme.
**Related:** `Research/Strategy/H1 Intervention Reaction.md`, `specs/002`, `specs/003`, `specs/004`

---

## 1. Where the pipeline actually stands

| Family | Stage reached | Verdict | Basis |
|---|---|---|---|
| Trend / technical rules | examined | **dead** | 388 rule portfolios, G11, 1–25 day holds: OOS net Sharpe −0.08 to +0.19, none significant |
| Calendar (Gotobi, fixes) | examined | **dead as signal** | ~1.8bp over 15 years; intraday, and decayed post-2008 |
| Carry / rate differential | examined | **dead** | relationship is contemporaneous; carry/risk 0.03–0.06 at 1–10 days |
| Risk appetite | examined | **dead** | next-week ΔVIX coefficient −0.03 (SE 0.11), R² ≈ 0 |
| H1 intervention disclosure | specced | **rejected** | 1.3 episodes/yr, Sharpe 0.24–0.43; daily test impossible |
| H2a year-end flow | calibrated | **dead** | n = 20 in 20 years, MDE 198 pips |
| H2b turn-of-month | calibrated | **testable, untested** | n = 240, MDE 31 pips → `specs/004` |
| H3 rate-path revision | calibrated | **testable, untested** | MDE Sharpe ≈ 0.33 in the standardised spec → `specs/003` |

**Eight families examined. Six dead. Two testable. Zero tested.**

That last number is the honest answer to the question. H2b and H3 are *calibrated* — I know what they could detect, not what they contain. A power calibration is not a result.

## 2. The two bars, and the gap between them

This is the finding that most changes how to read any future result. The Sharpe needed to be *statistically significant* and the Sharpe needed to be *worth trading* are not the same number, and they are a factor of three apart.

Using the published median 73% backtest-to-live Sharpe deterioration (live ≈ 0.27 × backtest):

| | Backtest Sharpe | Implied t (20y) | Live Sharpe | Net return @10% vol, 2 trades/wk |
|---|---|---|---|---|
| Detection bar (t=2) | 0.45 | 2.0 | 0.12 | +0.57%/yr |
| Multiple-testing bar (t=3) | 0.67 | 3.0 | 0.18 | +1.16%/yr |
| Live Sharpe 0.30 | **1.11** | **4.97** | 0.30 | +2.35%/yr |
| Live Sharpe 0.50 | 1.85 | 8.28 | 0.50 | +4.35%/yr |

So a result that clears the proper multiple-testing hurdle still delivers roughly **1.2%/yr net in live trading**. Not zero, and not a reason to operate a trading system.

For reference on how unlikely the t≈5 column is: the best-identified FX machine-learning study, with 70 predictors and proper Clark-West testing, put **Japan's out-of-sample R² at 0.19–0.28% and insignificant**, against a 10-currency composite of 1.51–1.86%. USDJPY is the weak case in that cross-section, not a neutral choice.

**Practical consequence: do not set a spec's kill criterion at t=2.** Significance at the detection bar is compatible with a strategy that is not worth running. State the tradeability bar separately from the statistical one.

## 3. A general limit worth keeping

The detectable Sharpe at t = 2 is

```
SR_min = 2 / sqrt(years of data)
```

**independent of holding horizon.** The √n and √(252/h) factors cancel exactly: n_eff = 252·Y/h, so 2/√n_eff × √(252/h) = 2/√Y. Twenty years buys 0.45 at t=2 and 0.67 at t=3, whether you hold one day or ten.

This means arguing about holding horizon is arguing about costs and capacity, never about statistical power. It also means the only lever that moves this limit is more *independent* observations — which, with years fixed, means cross-sectional breadth (more pairs), not finer sampling of one pair.

## 4. H1 — closed

Rejected on frequency, not sign. The disclosure effect is real and robustness-tested (−0.172 to −0.269 yen/USD) but fires on 1.3 independent episodes per year. Costs are not the constraint: the effect retains 89–95% of gross even under `PESSIMISTIC`. Retained as a risk overlay, not a strategy. Full treatment in `Research/Strategy/H1 Intervention Reaction.md`; rules and kill criteria in `specs/002-intervention-disclosure.md`.

## 5. H2 — one hypothesis was two, with opposite verdicts

| Variant | Obs/yr | n (20y) | Window | MDE at 80% |
|---|---|---|---|---|
| Fiscal year-end (31 Mar) | 1 | 20 | 10d | **198 pips** |
| Half-year end (30 Sep) | 1 | 20 | 10d | 198 pips |
| Both combined | 2 | 40 | 10d | 140 pips |
| Turn-of-month | 12 | 240 | 3d | **31 pips** |

The year-end variants are dead on arrival: a 198-pip March effect would be visible to every participant in the market. The turn-of-month variant has twelve times the data and an MDE of 31 pips, rising to ~53 under Bonferroni at 60 tests. Same hypothesis family; the only thing separating live from dead is how often the event fires.

### A confound in spec 001 that H2b should resolve

`calendars.gotobi_days()` includes **the last business day of the month** (月末) alongside the 5th/10th/15th/20th/25th. Spec 001's treatment group therefore bundles two mechanisms, and the published evidence says the one that is *not* Gotobi is the stronger:

```
relative spike frequency at the Tokyo 09:55 fix
  month-end  0.538
  Friday     0.301
  5th/10th   0.276
  all days   0.247
```

**As written, spec 001 cannot attribute any effect it finds to the Gotobi mechanism.** `specs/004` is therefore specified as a *separation* test — month-end-only versus Gotobi-excluding-month-end versus ordinary business days — rather than as a new discovery. If the effect lives entirely in month-end, spec 001's stated mechanism (importer USD demand on settlement days) is wrong even if its numbers are right.

## 6. H3 — viable, but only in one specification

H3 is the first design in this project where detectability sits inside tradeability. It is also the one most easily got wrong, and the margin between the right and wrong specification is enormous.

Simulated on a GARCH(1,1) process (α=.08, β=.90) with the signal's volatility loading 0.6 on the same vol factor, 20 years of daily data, 300 paths per cell:

| Specification | Size (nominal 5%) | Power at ρ=0.05 |
|---|---|---|
| Plain OLS t | **77.3%** | meaningless |
| White HC standard errors | 5.7% ✓ | **9.7%** |
| Volatility-standardised, HC | 3.7% ✓ | **100%** |

Plain OLS is unusable: when the regressor's volatility co-moves with the return's volatility — which US rates and USDJPY do — it rejects on 77% of pure nulls. HC errors restore the size and then destroy the power. Standardising **both** the signal and the return by conditional volatility fixes both at once, dropping the HC/naive standard-error ratio from 6.68 to 1.00.

The mechanism generalises beyond H3: **when the signal is largest exactly when the noise is largest, OLS over-weights the least informative observations.** Dividing through by conditional volatility equalises information per observation. It is GLS in effect. The inflation is driven entirely by that co-movement — the HC/naive ratio is 0.99 at zero shared volatility, 5.18 at a 0.3 loading, 6.71 at 0.6.

Minimum detectable effect, standardised specification, 20 years:

| ρ | Implied Sharpe | Power |
|---|---|---|
| 0.010 | 0.16 | 29% |
| 0.015 | 0.24 | 54% |
| **0.020** | **0.32** | **77%** |
| 0.030 | 0.48 | 98% |

Against section 2's table, note that 80% power at Sharpe 0.33 is *detection*, not tradeability. H3 can tell you whether the effect exists. It will not, at that magnitude, give you something worth running.

### Methodological note: the trap is not theoretical

Mid-way through this calibration I found a bug in my own simulator: the correlation was built between `x_t` and `y_t`, then `y_{t+1}` was regressed on `x_t`. There was no predictive signal in the data, so power equalled size in every cell, in every specification. That is exactly the contemporaneous-versus-predictive confusion that section 5 of `H1 Intervention Reaction.md` warns about in the context of FRED's noon-snapshot `DEXJPUS` — committed inside the code written to check for it, by someone who had written the warning hours earlier. Build a synthetic series with a known predictive link and confirm the harness recovers it before trusting any null.

## 7. What is built, and what is missing

**Built and reusable:**
- `costs.CostModel` wired to the actual venue; base round trip 0.836 pips ex-spread, `PESSIMISTIC` 1.236
- `stats.py`: HC autocorrelation SEs, clustered t, robust variance ratio, vol-standardised Hurst, MDE, Deflated Sharpe
- The clustered-t correction to the `t < 2` kill criterion (naive t optimistic by 1.32–1.47× on MOF-style clustered events)
- Gap sizing: a 700-pip intervention gap is 123.6% of one MJY contract's maintenance margin, so margin availability is the wrong constraint
- Timestamp discipline: the `DEXJPUS` noon trap, the cross-date-line yield-spread trap, the COT four-day lag, the MOF quarterly disclosure lag
- A power-first workflow that has now killed three ideas before they consumed effort

**Missing:**
- Any tested result
- Hypotheses. Two testable candidates will not produce a tradeable strategy. At a generous one-in-three survival rate that is 0.67 expected hits, and "survives" is the t=2 bar, not the t=5 one.
- Breadth. One pair, two event-conditioned ideas, no diversification — so even a genuine edge arrives with confidence intervals too wide to size against.

## 8. Three paths

1. **Run `specs/003` and `specs/004`.** Cheap, the harness exists, and a documented negative satisfies the repo's own standard — *most ideas should die here, cheaply*. Right if the purpose is finished research. Expect nulls.
2. **Widen the funnel.** For a tradeable result you need ten to fifteen mechanism-grounded hypotheses, not two. That means more sources of *forced* trading: Japanese lifer hedge-ratio resets, index rebalance flows, option-expiry pinning, cross-asset basis, JGB auction cycles.
3. **Change a constraint.** Cross-sectional across several pairs multiplies independent observations without multiplying years, which is the only lever on the 2/√(years) limit. Single-pair daily FX is the hardest version of this problem, and USDJPY is its weakest case.

## 9. Conclusion

The binding constraint has moved. The opening question was whether the data and the method were obtainable; both now are, and the apparatus is in better shape than most retail research ever reaches. The question now is whether there are enough ideas worth testing — and that is answered by reading market structure and identifying who is *obliged* to trade, not by more statistics.

Note what that implies about sequencing: the apparatus was finished before the hypothesis list was, which is the inverse of how these projects normally fail. The usual failure is a thin harness confidently backtesting fifty ideas. The position here is a strong harness with two. The second problem is the better one to have, and it is solved by reading rather than coding.
