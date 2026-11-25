# Spec 006: Weekend-gap reversal

**Author:** Haru · **Date:** 2026-11-24 · **Status:** idea

## Hypothesis
Weekend news piles up while FX is shut. At the Sunday 17:00 ET reopen (Wellington/Sydney, the thinnest
hour of the week) a handful of market-makers set the first prints, and gap-triggered stop and
risk-reduction orders have to be filled against them. The largest gaps therefore overshoot. As Tokyo and
then London liquidity arrives, the dealers who absorbed that flow rebuild their inventory and price
partly retraces. The bet is **not** on gap direction (which is a coin flip) but on partial reversal of
the largest 5% of gaps.

## Evidence
- Dao et al., "A calendar effect: weekend overreaction (and subsequent reversal) in spot FX rates"
  ([NTU IRep](https://irep.ntu.ac.uk/id/eprint/35555/1/13113_Dao.pdf)). 16 USD pairs, daily Bloomberg,
  2002-01 → 2014-05; weekend return = ln(Mon open / Fri close); signal = top/bottom 5%. 15 of 16 pairs
  show significant reversal. Thresholds estimated 2002–2006, **out-of-sample 2007-01 → 2014-05**;
  after 0.08% round-trip cost and interest differentials, majors' alpha ≈ 0.05–0.06%/week; max
  drawdowns 2.3–24.1% across pairs.
- Yen (labelled "JPY/USD" in the paper): down gaps average −0.444% and retrace +0.148% by the European
  open, +0.183% by the US open, **+0.322% by the US close, +0.634% at 3 days (1% level)**. Up gaps
  average +0.537%, reverse −0.299% by the first US close (5% level), insignificant at 3 days
  (−0.163%), continuation (+0.135%) by one week.
- Size vs cost: 0.32% ≈ 50 pips, ~40× the repo's ~1.1-pip round trip.
- Weaknesses: (1) the quote convention may flip the asymmetry, so both sides are one pooled
  hypothesis; (2) Bloomberg "Monday opens" are indicative prints from the illiquid open, and Eightcap
  spreads are ~5 pips at 06:00–07:00 JST vs ~0.33 at 08:00 JST, so part of the gap may be gone by the
  time we can trade; (3) only ≈26 signals per side in 2015–2024; at an assumed 0.6–0.8% per-trade s.d.
  t = 2 needs ~15–25 trades, so a halved effect is undetectable; (4) event gaps can trend for months
  (Oct 2014 BoJ gap near 112.50 took ~1.5 years to fill, [Moneypost](https://www.moneypost.jp/225396/3/)).
  Retail "73% fill in 24 h" claims (FXNX) have no method and are ignored.
- 2015–2024 HistData is fully post-publication, so this is a clean out-of-sample test.

## Rules (exact, no discretion)
- Days: every weekend with a valid Friday reference and a reopen print.
  - Friday reference F = last mid at or before Fri 16:55 ET (21:55 UTC EST / 20:55 UTC EDT;
    Sat 06:55 / 05:55 JST).
  - Reopen print O = first mid after Sun 17:00 ET (22:00 / 21:00 UTC Sun; Mon 07:00 / 06:00 JST).
  - g = ln(O / F). Signal if g ≤ 5th or ≥ 95th percentile of the previous 260 weekends' g (past data
    only; seed the distribution with Dukascopy 2010–2014 weekends that have both prints; require
    ≥ 52 weekends before the first signal).
- Entry: down gap → **long**, up gap → **short**, market order at **Mon 08:00 JST (Sun 23:00 UTC)**.
- Exit (three pre-declared variants): (A) Mon 16:00 JST (07:00 UTC); (B) Mon 16:50 ET (20:50 UTC EDT /
  21:50 UTC EST; Tue 05:50 / 06:50 JST); (C) Thu 16:50 ET (same UTC/JST offsets). Stop: none in the
  event study (matches the paper); record MAE per trade. Live, a disaster stop is set separately.
- Filters / skip conditions: skip if the 08:00 JST spread > 1.0 pip (log count); skip if Monday falls
  in T+1…T+6 after a MOF intervention day (spec 017 rule). Weekends with known political events
  (elections, G7) are **flagged and reported separately, not excluded**.
- Size: USD 100k. On a Monday gotobi day, net against spec 001's 08:00–09:55 long; cap combined
  exposure at USD 100k.
- Always log the share of the gap already retraced at 08:00 JST: (mid₀₈₀₀ − O) / (F − O).

## Data needed
- `datasets.load_minute('histdata')` 2015-01 → 2024-12 (main test); `datasets.load_minute('dukascopy')`
  2010–2014 only to seed the threshold distribution; `datasets.load_minute('eightcap')` 2024-06-19 →
  2024-12-31 for real Monday-open spreads; `datasets.interventions()`.
- **Check first:** Sunday 17:00–19:00 ET bar coverage in HistData (often sparse). Also check HistData
  UTC alignment in US summer: docs/DATA.md says raw stamps are NY local *with* DST, while
  `scripts/build_github_data.py` applies a fixed +5 h. A 1-hour error moves the reopen print.
- Missing (holdout only): bars after 2026-06-05 via `scripts/download.py`.

## Kill criteria (decided BEFORE testing)
Confirmatory (rule and threshold come from Dao et al.), so t ≥ 2. Primary statistic: pooled contrarian
trades (both sides), exit B, 2015-01-01 → 2024-12-31. Reject if any of:
- Mean net pips ≤ 0 under base `CostModel()`, or t < 2;
- Pooled mean has a different sign in 2015–2019 and 2020–2024 (rare-event variant, replacing
  "effect present in 2022+": 2022–24 holds only ~8 signals per side);
- Mean net ≤ 0 under `PESSIMISTIC`;
- Exit C mean net ≤ 0 after overnight financing (short side pays carry, roughly 1.5–2 pips/night at an
  assumed 4% differential; use measured IBKR rates).
Report each side separately, but do not accept a single side unless it alone passes all of the above.
The 2025–26 holdout plus forward paper trading is the confirmation step.

## Parameters
Tail = 5% (from paper, not tuned); window = 260 weekends; entry 08:00 JST; exits A/B/C (the only three
variants). 10%/15% tails may be reported as robustness but play no part in the decision.

## Implementation notes
- Exit A fits `events.window_trades(bars, mondays, "08:00", "16:00", side)` with per-side date lists.
- Exits B and C span days and are anchored to ET, which `window_trades` cannot express (it rolls the
  exit at most one day). Add a small helper taking explicit UTC entry/exit timestamps and reusing
  `quote_at`. It must skip dates ≥ `HOLDOUT_START` the way `window_trades` does.
- F and O need custom lookups (last bar before / first bar after), not `quote_at`'s 5-min tolerance.
- `costs.py` has no financing; add a per-night carry term for B/C.
- `summarize()` periods (2005–14/2015–21/2022+) do not match the 2015–19/2020–24 split; compute it directly.

## Results
_Pending._
