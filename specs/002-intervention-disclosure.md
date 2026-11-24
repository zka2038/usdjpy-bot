# Spec 002: MOF/BOJ intervention disclosure

**Author:** bzk · **Date:** 2026-11-24 · **Status:** rejected

Rejected before testing, on frequency and power grounds. The underlying effect is
real and published; it is the *tradeability* that fails. No holdout was spent on a
test — see "Holdout position" below.

## Hypothesis

Japanese FX interventions are disclosed with a two-business-day delay through a
rule-based BOJ accounting report. The BOJ publishes a daily settlement estimate
whether or not intervention occurred; the information is carried by the *deviation*
between that release and money brokers' forecasts. Money brokers and dealers who
were uncertain whether an operation took place are forced to re-mark once the
deviation confirms it, so the forced trade is a repricing of intervention-risk
expectations on a known clock (18:00 JST), two business days after the operation.
Because the portfolio-balance channel acts contemporaneously with the operation
while the quantitative information arrives only with the lag, the two are
separately identified.

Direction: yen appreciation (USDJPY down) on disclosure.

## Evidence

- Lu, Urushidani & Kameda, "Market response to foreign exchange intervention
  information release: Evidence from Japan's return to active intervention,"
  *International Review of Economics & Finance*, June 2026.
  <https://www.sciencedirect.com/science/article/pii/S1059056026004247>
  WP: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5374821>
  Sample 2022–2024 (**pre-holdout**). High-frequency USD/JPY, self-controlled
  design comparing disclosure to non-disclosure days.
  - −0.172 yen/USD on a 15-day control window
  - −0.269 yen/USD on a 30-day control window
  - dose-response: −0.035 yen per ¥1tn confirmed; −0.022 pp of opening value;
    both significant at 1%
  - placebo and randomisation robustness; next-day realised vol falls
  This is in-sample for the authors and has not been independently replicated.
- Ito & Yabu, ordered probit reaction function, 2004/8–2018/3 regime:
  rate-of-change term **insignificant** (10.22, t≈0.9); deviation from the 5-year
  moving average **significant** (−33.32, t≈−2.9).
  <https://www.fbc.keio.ac.jp/~tyabu/JapaneseForexInterventions.pdf>
  So the statistics support level-and-trend defence, contradicting officials' own
  "speed not levels" framing.
- MOF intervention record, April 1991 – September 2026 (daily detail, quarterly
  publication):
  <https://www.mof.go.jp/policy/international_policy/reference/feio/foreign_exchange_intervention_operations.csv>

## Rules (exact, no discretion)

- Days: each MOF-confirmed operation date + 2 business days (the disclosure date).
- Entry: short USDJPY at 18:00 JST / 09:00 GMT, market.
- Exit: 00:00 JST next day (the published effect peaks around midnight JST at
  roughly −0.25% of opening value); no discretionary extension.
- Stop: none. **A stop is not protection in this regime** — USDJPY moved
  160.17 → 156.60 in ~11 minutes on 2024-04-29, and MOF has repeatedly chosen
  thin-liquidity windows. Size for a 500-pip gap instead, or express via options.
- Filters: skip if the 18:00 JST quote is stale beyond `events.quote_at`
  tolerance; skip BOJ MPM days.
- Size: ≥ USD 100k notional (IBKR minimum commission).

## Data needed

- Dukascopy 1-min bid/ask, 18:00–00:00 JST on each disclosure date plus matched
  control dates (`usdjpy.dukascopy`, `scripts/download.py`).
- MOF confirmed operation dates and amounts (CSV above). **Published quarterly,
  ~100 days late — regime labelling only, never a contemporaneous input.**
- BOJ daily settlement estimate (18:00 JST releases).
- **Money broker settlement forecasts — NOT LOCATED IN ANY FREE SOURCE.** This is
  the binding gap: without it the deviation that constitutes the signal cannot be
  reconstructed in real time, only inferred after the fact from the quarterly MOF
  record. May be unobtainable at retail.

## Kill criteria (decided BEFORE testing)

- Mean net pips per trade ≤ 0 under base costs on pre-holdout data, or
- **t-stat < 2 computed on CLUSTERS, not operation days** (`stats.clustered_t`) — or
- Effect absent in the 2022+ period, or
- Fails under `PESSIMISTIC` costs, or
- **Fewer than 8 independent episodes available pre-holdout** (added for this spec;
  see below).

## Parameters

Three, none tuned: entry 18:00 JST and exit 00:00 JST are taken from the paper's
reported effect profile, not searched; the +2-business-day disclosure lag is
institutional, not fitted.

## Results — rejected on power, not on sign

Costs are **not** the binding constraint. Under `costs.CostModel` at 159:

| | Round trip ex-spread | All-in (~0.6 spread) | 17.2-pip effect | 26.9-pip effect |
|---|---|---|---|---|
| base | 0.836 pips | 1.44 | net 15.8 (92% kept) | net 25.5 (95% kept) |
| `PESSIMISTIC` | 1.236 pips | 1.84 | net 15.4 (89% kept) | net 25.1 (93% kept) |

Frequency is. `stats.cluster_ids` on the MOF dates (4-day gap rule):

| Sample | Operation days | Independent episodes | Episodes/yr |
|---|---|---|---|
| pre-holdout (2022–2024) | 7 | **4** | 1.3 |
| full (2022–Nov 2026) | 13 | **6** | 1.3 |

Net annualised Sharpe, assuming per-event risk of one daily sd (0.63% at 10% vol):

| Sample | Edge 0.172 yen | Edge 0.269 yen |
|---|---|---|
| pre-holdout only | 0.24 | 0.39 |
| full sample | 0.26 | 0.43 |

And the study cannot see its own effect. `stats.min_detectable_pips`, 5-day
window, sd of a 5-day move = 224 pips:

| n treated as | MDE at 80% power |
|---|---|
| 13 operation days | 174 pips |
| 6 clusters | ~256 pips |
| 4 pre-holdout clusters | **314 pips** |

Published effect: **17–27 pips.** The daily test is 10–18× too insensitive. A null
from it would carry no information, which is why this spec is rejected rather than
tested: running it would spend effort and holdout for a foregone null.

**Decision: rejected as a strategy. Retained as a risk overlay** — do not hold long
USDJPY into a defended level. Justification for the overlay rather than the trade
is in `Research/Strategy/H1 Intervention Reaction.md`, including the MJY gap
arithmetic (a 700-pip gap is 123.6% of one contract's maintenance margin).

**What would change this verdict:** an intraday replication on the 13 dates, which
needs only a few MB of Dukascopy data, *plus* a source for money-broker settlement
forecasts. If the broker series is obtainable, reopen as spec 002a with the entry
conditioned on the forecast deviation rather than on the MOF record.

## Holdout position

`HOLDOUT_START = 2025-01-01`. No test was run, so no holdout look was spent on a
result. However, **H1 was partly *selected* on holdout-period evidence** — the two
2026 intervention clusters, the joint US Treasury operation of 2026-07-31, and the
160 threshold all informed why this hypothesis looked worth examining. That is
selection contamination, not test contamination.

It changes nothing here: the rejection reproduces on pre-holdout data alone (4
episodes, 1.3/yr, Sharpe 0.24–0.39 — the same verdict as the full sample). Recorded
so a future reader does not mistake this for a clean out-of-sample finding.

The rhetoric-ladder variant of H1 is **not** proposed as a spec: on 2026-04-30 the
Vice Minister's "final warning" and the operation were the same event, so the top
rung is coincident, not leading. (That observation is itself holdout-period.)
