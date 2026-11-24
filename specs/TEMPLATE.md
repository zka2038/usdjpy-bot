# Spec NNN: <short name>

**Author:** <name> · **Date:** <YYYY-MM-DD> · **Status:** idea / testing / passed / rejected / frozen

## Hypothesis
Who is forced to trade, when, and in which direction? One paragraph. "It looks like it works on a chart" is not a mechanism.

## Evidence
Links to papers, bank research or prior tests. Note sample period and whether it was out-of-sample.

## Rules (exact, no discretion)
- Days: <e.g. gotobi days, last UK business day of month, all JP business days>
- Entry: <side> at <HH:MM JST / HH:MM GMT>, <order type>
- Exit: <HH:MM> or <condition>; stop: <rule>
- Filters / skip conditions: <BoJ days, holidays, vol threshold...>
- Size: <USD notional; ≥ 100k to avoid IBKR minimum commission>

## Data needed
<Dukascopy ticks / CME 6J / CFTC / MOF ...>

## Kill criteria (decided BEFORE testing)
- Mean net pips per trade ≤ 0 under base costs on pre-holdout data, or
- t-stat < 2, or
- Effect absent in the 2022+ period, or
- Fails under PESSIMISTIC costs.

## Parameters
List every tunable number. Fewer is better: each one you tune spends statistical power.

## Results
<filled in after testing: link to results/ files, summary table, decision>
