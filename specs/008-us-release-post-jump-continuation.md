# Spec 008: US release (NFP/CPI) post-jump continuation

**Author:** Claude (research 2026-11-24) · **Date:** 2026-11-24 · **Status:** idea

## Hypothesis
NFP and CPI surprises force a repricing of Fed expectations. Fast money sets the first jump within
minutes, and that jump is the market-implied surprise. End users (real money, corporates, hedgers,
CTAs) rebalance over hours to days, and their order flow keeps pushing price the same way. Entering
after the first five minutes, once spreads normalise, skips the latency race that rules out news
scalping and tries to harvest only the slow-flow leg.

## Evidence
- For continuation (indirect): Evans & Lyons, "Do Currency Markets Absorb News Quickly?"
  ([NBER w11041](https://www.nber.org/papers/w11041.pdf)): news-induced customer flow stays
  significant for days, with persistent price effects. Evans & Lyons (JFE 2008, DM/$): about two-thirds
  of macro news's price effect runs through order flow.
- Against (direct, USDJPY-specific): Chaboud et al. ([Fed IFDP 823](https://www.federalreserve.gov/pubs/IFDP/2004/823/ifdp823.htm)),
  EBS EURUSD and USDJPY: the effect of a surprise on the conditional mean is absorbed quickly.
  Hashimoto & Ito (CIRJE): USDJPY reprices within minutes; deal counts stay elevated for 15–30 min.
- Pre-release drift: Kurov et al. ([ECB WP 1901](https://ecb.europa.eu/pub/pdf/scpwps/ecbwp1901.lv.pdf))
  find drift in the direction of the coming surprise from ~30 min before several US releases, mostly in
  E-mini futures.
- No paper documents a tradeable post-announcement drift in USDJPY beyond the first hour.
  **Exploratory.** About 240 NFP+CPI events in 2015–2024 before the filter.

## Rules (exact, no discretion)
- Days: BLS Employment Situation (NFP) and CPI release days, 08:30 ET. NFP and CPI are handled as
  separate series.
- r₅ = ln(mid 08:35 ET / mid 08:29 ET). In UTC: 13:29→13:35 (EST) / 12:29→12:35 (EDT). In JST:
  22:29→22:35 / 21:29→21:35.
- Signal: |r₅| > 2 × median |r₅| over that release's previous 12 occurrences (warm-up: seed with
  Dukascopy 2014 where bars exist, else skip until 12 are observed).
- Entry: in the direction of r₅ at **08:35 ET** (13:35 / 12:35 UTC; 22:35 / 21:35 JST), market order.
- Exit (three variants): (A) 10:00 ET (15:00 / 14:00 UTC; 00:00 next day / 23:00 JST); (B) 16:00 ET
  (21:00 / 20:00 UTC; 06:00 / 05:00 JST next day); (C) next Tokyo close 15:00 JST (06:00 UTC), held
  through one 17:00 ET roll. Stop: none in the event study; record MAE.
- Filters / skip conditions: skip MOF intervention days and T+1 (e.g. the 2024-07-11 CPI day carried a
  −340-pip intervention move, per docs/DATA.md); skip if FOMC statement falls inside the holding window.
- Diagnostic (logged, not traded): does sign(mid 08:29 ET / mid 08:00 ET) predict sign(r₅)? Report the
  hit rate and binomial p.
- Size: USD 100k.

## Data needed
- **Missing:** `data/calendars/us_releases.csv` (date, release, time_et) built from BLS release
  schedules and archives (free). Check rescheduled or delayed releases against the BLS archive.
  Consensus data are **not** needed (r₅ is the surprise proxy). This is Tier 0c.
- `datasets.load_minute('histdata')` 2015–2024; `datasets.load_minute('eightcap')` 2024-06 → 2024-12
  for the real spread at 08:35 ET; `datasets.fomc()`, `datasets.interventions()`.

## Kill criteria (decided BEFORE testing)
Exploratory, so t ≥ 3. The primary statistic is pooled NFP+CPI at exit B. Reject if any of:
- Mean net pips ≤ 0 under base costs, or t < 3;
- Sign differs between 2015–2019 and 2020–2024;
- Mean net ≤ 0 under `PESSIMISTIC`;
- Median real (Eightcap) spread at 08:35 ET > 1 pip *and* the result is ≤ 0 re-costed at that spread;
- Filtered events do not beat unfiltered events (if continuation is no stronger after big r₅, it is not
  the flow mechanism).

## Parameters
Multiplier 2×, lookback 12 releases, entry 08:35 ET, exits A/B/C (the three variants). Releases stay
limited to NFP and CPI; adding retail sales or PCE later counts as a new ledger entry.

## Implementation notes
`window_trades` fits: precompute up-signal and down-signal date lists and call with fixed side and
`tz="America/New_York"` for exits A/B ("08:35"→"10:00", "08:35"→"16:00"). For exit C use
`tz="Asia/Tokyo"`, splitting dates by US DST (entry "22:35" on EST dates, "21:35" on EDT dates, exit
"15:00", which rolls to the next day). Computing r₅ is a two-quote lookup per date. Add one night of
financing for C.

## Results
_Pending._
