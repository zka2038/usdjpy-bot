# Spec 014: Volatility-scaled trend + carry with crash/intervention filters

**Author:** Claude (research 2026-11-24) · **Date:** 2026-11-24 · **Status:** idea

## Hypothesis
Two slow premia. **Trend:** information diffuses gradually and hedgers pay speculators to take the
other side, so 1–12-month returns persist. Moskowitz, Ooi & Pedersen find that speculators profit from
time-series momentum at hedgers' expense. **Carry:** the yen is the world's funding currency, so
being short it earns the rate gap plus a crash-risk premium. Losses come in sudden unwinds, when
VaR-constrained carry holders are forced to buy yen. In this regime trend and carry are both long
USDJPY and share the same tail: unwinds (Aug 2024) and MOF intervention near 160 (2022, 2024, 2026).
The crash filters try to cut that tail without giving up the premium.

## Evidence
- Moskowitz, Ooi & Pedersen (JFE 2012), 58 instruments, 1985–2009: 12m/1m TSMOM significant in every
  instrument; positions scaled to 40% ex-ante vol (EWMA, 60-day centre of mass); currency TSMOM
  alpha t = 3.41. Hurst, Ooi & Pedersen: positive in every decade back to 1880 across 67 markets.
- Against: Neely, Weller & Ulrich (JFQA 2009, true out-of-sample) find published MA/filter rules on
  dollar FX lost their profits by the mid-1990s. Chen (2020, 230 years, 21 currencies) finds no
  significant long-run currency momentum. SG Trend Index fell 20.4% May 2024 – May 2025.
- Carry: BNP (NBER w14473), short-JPY/long-USD earned ~1.1% a quarter, skewness −0.318, crash risk
  rising with the VIX. Jurek (JFE 2014, 1990–2012): crash premia explain at most one-third of carry,
  though his earlier 1999–2008 working paper found crash-neutral carry indistinguishable from zero, so
  the premium is fragile. BIS Bulletin 90: yen-funded carry "the hardest hit" in Aug 2024.
- Single-pair power is poor: separating a Sharpe of 0.3 from zero takes decades. So the decision rests
  on the literature prior plus robustness, not on t ≥ 2 (see kill criteria). Costs are negligible at
  weekly turnover.

## Rules (exact, no discretion)
- Days: weekly. Signal is computed on Friday data; rebalance at **Mon 08:00 JST (Sun 23:00 UTC)**,
  after the reopen spread has normalised.
- Excess return: r_ex = daily log spot change + (USD short rate − JPY short rate)/360 per calendar day.
- Signal s = mean of sign(r_ex over 21, 63, 252 trading days) ∈ {±1/3, ±1}.
- Vol: σ̂ = EWMA of daily log returns, 60-day centre of mass, annualised.
- Weight w = s × min(2, 10% / σ̂). Notional = w × N_base, with N_base = USD 300k (so the smallest
  non-zero position ≈ USD 100k; scale N_base to the account and pre-declare it).
- Trade only if |Δnotional| ≥ USD 100k or the sign changes (avoids the $2 minimum and odd-lot routing).
- Stop: none; the position is the signal.
- Filter bundle F (earlier report's crash overlay; long-USDJPY positions only; halve once if *any*
  holds):
  - VIX in the top decile of its trailing 1-year range;
  - TFF Leveraged-Fund net short JPY beyond its 90th percentile over 3 years (`available_from`-lagged);
  - spot > 158.
  - In addition, when spot > 158, go **flat** from the last Tokyo close (15:00 JST, 06:00 UTC) before a
    JP bank holiday and before each weekend (Fri 16:30 ET; 21:30 / 20:30 UTC; Sat 06:30 / 05:30 JST),
    and re-enter at the next Mon/post-holiday 08:00 JST.
  - The "warning ladder" (verbal escalation, rate checks) is not testable without headline data and is
    omitted.
- Financing: accrue nightly; long earns, short pays, at (benchmark differential − h), with broker
  haircut h ∈ {0, 1.5%/yr} (1.5% matches IBKR's example BM + 1.5% tier; use live rates at test time).

## Data needed
- Long daily history for signal and vol: `data/macro/fred_h10_usdjpy_daily_1971_2026.csv` (H.10 noon
  NY; **no loader yet**, add one to `datasets.py`) and DEXJPUS in `datasets.macro_daily()`.
- Execution prices 2015–2024: `datasets.load_minute('histdata')` at Mon 08:00 JST.
- Short rates: **DFF missing** (`scripts/fetch_official.py`); JPY: `data/macro/boj_call_rate_monthly_1985_2026.csv`
  (monthly, no loader) or OECD `IR3TIB01JPM156N` via fetch_official.
- Filters: VIX (`data/macro/vix_daily_1990_2026.csv`), `datasets.cot('tff')` (2010 →, so F is testable
  2010–2024 only), `usdjpy.calendars.jp_bank_holidays`.

## Kill criteria (decided BEFORE testing)
Core (unfiltered), 1990–2024 on H.10 closes with costs at `PESSIMISTIC` round trips per rebalance and
h = 1.5%. Reject if any of:
- Net Sharpe ≤ 0 over 1990–2024;
- Net Sharpe ≤ 0 over 2010–2024 (post-MOP sample);
- Fewer than 2 of the 3 single-lookback versions (21/63/252 only) have positive net Sharpe over 1990–2024;
- 2015–2024 execution-price backtest (1-min bars, Mon 08:00 JST) differs in sign from the H.10 version.
Filter F is adopted only if, vs the core over 2010–2016 **and** 2017–2024 separately, it cuts max
drawdown by ≥ 20% and does not lower the return/max-drawdown ratio. Report Sharpe and skew, but they
do not decide.

## Parameters
Lookbacks 21/63/252, EWMA COM 60, vol target 10%, leverage cap 2, N_base, rebalance threshold
USD 100k, F thresholds (top decile, 90th pct, 158). Variants (three): core; core + F; core with 12m
lookback only (MOP's original).

## Implementation notes
Not an event study. Needs a small weekly portfolio simulator (e.g. `src/usdjpy/portfolio.py`) with
positions carried across days, nightly financing, per-rebalance costs from `CostModel`, holdout
enforcement (stop at `HOLDOUT_START`), and weight multipliers so the spec 017 overlays plug in.
`window_trades` does not apply. Specs 016 and 017 reuse the simulator.

## Results
_Pending._
