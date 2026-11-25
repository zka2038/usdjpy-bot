# Spec 009: BoJ statement → press-conference reversal

**Author:** Haru · **Date:** 2026-11-24 · **Status:** idea

## Hypothesis
The BoJ statement lands at no fixed time around midday JST, and fast traders and algos trade the
headline. At the 15:30 JST press conference the Governor's guidance often reframes the statement, and
headline-chasers must unwind before the Tokyo close and the London open. This is the weakest
mechanism in the queue: it is informational (reinterpretation) rather than flow someone is forced to
execute. It earns a test because BoJ days are where yen surprises cluster, the data are in the repo,
and the window overlaps no other strategy.

## Evidence
- Kamada ([Keio-IES DP2025-015](https://ies.keio.ac.jp/upload/DP2025-015_EN.pdf)), daily yen-dollar,
  1984 → May 2024, 375 meetings: under Kuroda, the large-surprise rate was **13.3% on policy-meeting
  days vs a 4.4% Tokyo baseline**; 6 of the top-30 yen surprises fell on BoJ days. The paper does not
  study continuation vs reversal.
- Mueller, Tahbaz-Salehi & Vedolin (FMG DP 54, 1998–2010): a JPY-based portfolio earned 18.16bp on
  BoJ announcement days vs 0.75bp otherwise (t = 2.80). The sign convention must be checked.
- Anecdotes only for the reversal: June 2024, the yen weakened to 158.25 on the statement, then Ueda's
  "considerable" taper comments took USDJPY back to the 156s ([MUFG FX Daily](https://www.bk.mufg.jp/report/dmr2024/FXDaily20240614.pdf));
  Jan 2024, 148.55 → ~147 on hike hints (FXStreet); MUFG Jan 2025 flags "big moves before and after
  the 15:30 press conference".
- Contamination: on 23 Jan 2026 USDJPY rose above 159 after the press conference, then fell below
  157.4 on rate-check rumours (Jiji). Of six 2026 decision days, the three down days all had ≥ 2-yen
  ranges tied to official action (Monex). Both 2026 cases are in the holdout.
- No rigorous intraday study exists. Expect ≈40–60 qualifying events. **Exploratory.**

## Rules (exact, no discretion)
- Days: `decision_date` in `datasets.boj()` (2010 →).
- Statement minute S = first 1-min bar between 11:00 and 14:00 JST (02:00–05:00 UTC) with
  |r| > 5 × median |r| of the same minute-of-day over the previous 20 JP business days. If none, skip.
- R₁ = ln(mid 15:25 JST / mid at S − 1 min).
- Signal: |R₁| > 0.3%.
- Entry: **fade** R₁ (short if R₁ > 0, long if R₁ < 0) at **15:25 JST (06:25 UTC)**, market order.
- Exit (two variants): (A) 17:00 JST (08:00 UTC, London open); (B) 23:59 JST (14:59 UTC). Stop: none
  in the event study; record MAE.
- Twin test (separate ledger entry): continuation, i.e. trade *with* R₁, same exits.
- Filters / skip conditions: skip MOF intervention days (`datasets.interventions()`) and rate-check
  days; skip if S − 1 or 15:25 bars are missing (Dukascopy gaps).
- Size: USD 100k.

## Data needed
- `datasets.boj()` (data/calendars/boj_mpm.csv, 2010 → 2027; no statement timestamps, hence detection).
- `datasets.load_minute('dukascopy')` 2010–2014 (gappy, reported only); `datasets.load_minute('histdata')`
  2015–2024 (main test).
- **Missing:** `data/calendars/rate_checks.csv` (add by hand). Check detected S against news archives
  for a sample of 10 meetings.

## Kill criteria (decided BEFORE testing)
Exploratory, so t ≥ 3 on the fade at exit A, 2015–2024 (2010–2014 reported separately). Reject if any of:
- Mean net pips ≤ 0 under base costs, or t < 3;
- Sign differs between 2015–2019 and 2020–2024 (rare-event variant of the 2022+ rule);
- Mean net ≤ 0 under `PESSIMISTIC`;
- Result turns ≤ 0 after dropping the single largest trade (the anecdotes are a few big days);
- Fewer than 30 qualifying events in 2015–2024: the test is reported as underpowered, not passed.

## Parameters
k = 5 and 20-day baseline (detection), R₁ threshold 0.3%, entry 15:25 JST, exits A/B. No tuning of
the 0.3% threshold.

## Implementation notes
Detecting S is path-dependent (a short scan of the 11:00–14:00 JST bars), but once S and R₁ are known
the trade is a fixed-clock window. So precompute fade-long and fade-short date lists, then call
`window_trades(bars, dates, "15:25", "17:00", side)` (and "23:59"). No bar-loop simulator needed unless
stops are added later. Spec 007 excludes BoJ days 11:00–16:00 JST, so the two do not collide.

## Results
_Pending._
