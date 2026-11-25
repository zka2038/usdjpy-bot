# Spec 016: Rate-differential rule gated by rolling correlation

**Author:** Haru · **Date:** 2026-11-24 · **Status:** idea

## Hypothesis
When USDJPY is in a "rates regime", real-money and leveraged investors reallocate toward the
higher-yielding currency as policy expectations move, and they do it with a lag. A widening US–JP 2y
spread then leads USDJPY higher over the following weeks. The regime switches on and off: in 2025–26
Japan-specific factors (fiscal policy, negative real rates, outflows) took over. So the rule trades
only while its own rolling correlation says the link is alive. This is not a forced flow. It is an
expectations channel with a regime gate, and it is weak evidence.

## Evidence
- MUFG via [FXStreet](https://www.fxstreet.com/news/usd-jpy-decouples-from-yield-spreads-mufg-202512051021)
  (Dec 2025): the 12-week rolling correlation of USDJPY with the US–JP 10y spread averaged **+0.43**
  before Oct 2025 and peaked at **0.91** (Feb 2025). After Oct 2025 it "collapsed to −0.07", with eight
  consecutive negative weeks.
- Daiwa (Jul 2026): the real-rate-differential explanation "has weakened" since autumn 2025. StoneX:
  relative rates "could not explain the yen's weakness" in 2025. Apr 2025 tariff shock: the link was
  "obliterated" (Investing.com/ING).
- LSEG (2026) argues differentials "remain the dominant driver", qualitatively, with no regressions.
- JIE 2023: once small-sample bias is corrected, no variable beats the random walk for the dollar out
  of sample.
- No academic out-of-sample test of a 2y-spread rule on USDJPY. Thresholds come from the earlier report,
  so **exploratory**. The earlier report suggests using it "mainly as a filter" for spec 010.

## Rules (exact, no discretion)
- Days: weekly. Signal data are Thursday values, so every input is published before the trade.
  FRED/H.15 DGS2 arrives with a lag of about one day; check the timing.
- Spread S_t = DGS2 − JGB 2Y (MOF). ΔS₄ = S_t − S_{t−4 weeks}.
- Gate: ρ = correlation over the last 12 weeks of weekly Δln(USDJPY) (H.10 noon NY, Thu→Thu) vs weekly ΔS.
- Position: if ρ > +0.4, take sign(ΔS₄) × USD 100k (long USDJPY if the spread widened); else flat.
- Entry/exit: rebalance at **Mon 08:00 JST (Sun 23:00 UTC)**, hold to the next Monday 08:00 JST.
  Market orders, traded only when the target position changes.
- Stop: none.
- Filters / skip conditions: no new entries in T+1…T+6 after a MOF intervention (spec 017).
- Size: USD 100k. Nightly financing: long earns, short pays (as in spec 014).

## Data needed
- **Missing: DGS2.** Run `scripts/fetch_official.py` → `data/official/fred_daily.csv`.
- In repo: JGB 2Y and 10Y as `JGB2Y`/`JGB10Y` in `datasets.macro_daily()` (MOF, 1974 → 2026-05); DGS10
  in `datasets.macro_daily()`; H.10 USDJPY in `data/macro/fred_h10_usdjpy_daily_1971_2026.csv` (needs a
  loader).
- Execution check 2015–2024: `datasets.load_minute('histdata')`.
- Note: with the JGB 2y near zero (roughly 1999–2022), S is effectively the US 2y alone.

## Kill criteria (decided BEFORE testing)
Exploratory, so t ≥ 3. Sample 1990-01 → 2024-12 (pre-holdout). Reject if any of:
- Mean weekly net return of the gated rule ≤ 0 (base costs + financing), or t < 3;
- Sign differs between 1990–2007 and 2008–2024;
- **Gate adds nothing:** gated-minus-ungated (always trade sign(ΔS₄)) mean is ≤ 0 in either half.
  The gate is the hypothesis;
- Fails under `PESSIMISTIC` (unlikely at weekly turnover).
Variant 3 (filter on spec 014) is judged by spec 017's drawdown rule instead.

## Parameters
Spread tenor (2y), change horizon 4 weeks, correlation window 12 weeks, gate +0.4. Variants (three):
(1) 2y spread as above; (2) 10y spread (DGS10 − JGB10Y, the MUFG statistic); (3) as a filter on spec 014,
setting 014's position to zero when ρ > 0.4 and sign(ΔS₄) opposes it.

## Implementation notes
Uses the spec 014 weekly portfolio simulator; `window_trades` does not apply. Compute everything on
the Thursday H.10 grid, then execute on 1-min bars for 2015–2024 to check that H.10-based and
execution-based P&L agree in sign.

## Results
_Pending._
