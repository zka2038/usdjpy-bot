# Spec 018: Expected-null calendar battery (FOMC, BoJ day, holidays, Golden Week, fiscal year-end, intraday momentum)

**Author:** Haru · **Date:** 2026-11-24 · **Status:** idea

## Hypothesis
Each item below is popular folklore or a dollar-wide result that the evidence says does **not** hold
for the yen. The usual reason: the yen's dual role as funding currency and haven cancels the
directional response to scheduled news, and calendar "flows" are not forced at a known time. They are
run **once**, cheaply, against control days, so the folklore is settled and logged in the
multiple-testing ledger. Nothing here is tradeable from this spec. A surprise hit graduates to its own
spec with fresh kill criteria and is tested on a fresh sample.

## Evidence (per test)
- N1/N2 FOMC: Mueller, Tahbaz-Salehi & Vedolin (FMG DP 54, 1994–2010) find a short-USD FOMC-day
  premium of 12.45bp (t = 2.43), ~75% of it before 14:15 ET, but **JPY −1.59bp vs −0.58bp otherwise
  (t = −0.16)**. Lucca & Moench (NY Fed SR512): no pre-FOMC drift in currencies. RAPS 2025:
  post-announcement FX returns cancel ~65% of the pre-FOMC drift.
- N3 BoJ day: Mueller et al. report a JPY-based portfolio at 18.16bp vs 0.75bp on BoJ days (t = 2.80,
  1998–2010; sign convention unverified). Test whether anything survives post-2010.
- N4/N5 holidays: ZAi FX (2007 – Mar 2019), yen up in 52.8% of 178 JP-holiday Tokyo sessions (not
  significant); GW 1999–2018, USDJPY fell 11 times and rose 9. The "pre-GW trend continues" idea is ZAi's
  untested impression. Obon and year-end are untested anywhere.
- N6 fiscal year-end: Mizuho, yen up in only 19 of 42 Marches (1973–2014); Monex, end-March turning
  points in 5 of 6 years (2000–2005). Anecdotal.
- N7 intraday momentum: Baltussen et al. (currency futures) find the coefficient fell from 1.31
  (t = 6.48, 1974–1999) to **0.33 (t = 1.45) in 2000–2020**. The Elaut et al. mechanism needs a hard
  session close, which spot lacks.

## Rules (exact, no discretion)
Each test reports the mean mid-pips on event days vs control days (`events.compare`, Welch), plus net
pips for the stated side. Size USD 100k where a side is stated.
- **N1 FOMC pre-window:** scheduled decisions (`datasets.fomc()`, unscheduled excluded). From T−1
  16:00 ET to T 13:55 ET. UTC: 21:00 / 20:00 → 18:55 / 17:55 (EST/EDT). JST: 06:00 / 05:00 on T →
  03:55 / 02:55 on T+1. Control: same window on non-FOMC days. Split SEP vs non-SEP.
- **N2 FOMC post-window:** 14:00–16:00 ET on T (19:00–21:00 / 18:00–20:00 UTC; 04:00–06:00 /
  03:00–05:00 JST on T+1). Same controls.
- **N3 BoJ decision day:** NY close to NY close around the decision. From 16:50 ET on the US date before
  the JST decision date (21:50 / 20:50 UTC the day before, EST/EDT; 06:50 / 05:50 JST on the decision
  date) to 16:50 ET on the decision date (06:50 / 05:50 JST the next day). Control: other JP business
  days. Exclude intervention days.
- **N4 JP-holiday Tokyo session:** JP bank-holiday weekdays (`calendars.jp_bank_holidays`), 09:00 →
  15:00 JST (00:00 → 06:00 UTC). Control: JP business days, excluding gotobi days (spec 001 effect).
- **N5 Holiday trend continuation:** signal = sign of USDJPY's 10-business-day return to the last
  Tokyo close (15:00 JST, 06:00 UTC) before Golden Week / Obon (Aug 13–16) / year-end (Dec 29 – Jan 3).
  Trade *with* the signal from that close to 15:00 JST on the first business day after.
- **N6 Fiscal year-end fade:** 20-business-day return into the last JP business day of March, at
  15:00 JST (06:00 UTC). Trade *against* it from that close for 10 JP business days (exit 15:00 JST).
  Controls: same rule at end-June, end-September and end-December.
- **N7 Intraday momentum regressions, by year:**
  - Tokyo: r(09:00–09:30 JST; 00:00–00:30 UTC) predicts r(14:30–15:00 JST; 05:30–06:00 UTC);
  - NY: r(08:30–09:00 ET; 13:30–14:00 / 12:30–13:00 UTC) predicts r(15:30–16:00 ET; 20:30–21:00 /
    19:30–20:00 UTC; 05:30–06:00 / 04:30–05:00 JST).
  Report slope, t and out-of-sample R².
- Filters: all windows avoid 16:55–17:10 ET; intervention days are excluded everywhere.

## Data needed
All in repo: `datasets.load_minute('combined')` (Dukascopy 2007–2014 gappy, HistData 2015–2024),
`datasets.fomc()` (2007 →), `datasets.boj()` (2010 →), `usdjpy.calendars` (holidays, gotobi),
`datasets.interventions()`. Data ready.

## Kill criteria (decided BEFORE testing)
Expected result: null for all seven. Each is one ledger entry, and the run is **not** repeated with
new windows. An item "survives" (i.e. earns its own spec, not a trade) only if:
- N1–N4, N7 (frequent events): event-minus-control t ≥ 3 **and** the same sign in 2015–2019 and
  2020–2024, **and** mean net > 0 under `PESSIMISTIC` for the implied side;
- N5–N6 (≈18 observations each, 2007–2024): binomial sign test p < 0.01 **and** same sign in 2007–2015
  and 2016–2024. Otherwise recorded as "folklore not supported".

## Parameters
None tuned. Windows are taken verbatim from the report (Tier 0d) and research notes.

## Implementation notes
N1–N4 fit `window_trades` (N1: `tz="America/New_York"`, dates = T−1, "16:00"→"13:55" rolls to the next
day; N2: "14:00"→"16:00"; N4: JST "09:00"→"15:00"). N5/N6 are multi-day holds and need the timestamp
helper from spec 002. N7 is a pandas regression on bar returns. Run after Tier 0a (seasonality map),
so every result can be read against the time-of-day baseline.

## Results
_Pending._
