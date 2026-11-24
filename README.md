# usdjpy-bot

Research → backtest → live pipeline for USDJPY strategies, executed through Interactive Brokers.

## Workflow

1. **Idea** → copy `specs/TEMPLATE.md` to `specs/NNN-name.md`, fill in the hypothesis, exact rules
   (times in JST *and* GMT) and **kill criteria before testing**. Open a pull request.
2. **Event study** (this repo, Layer 1): pandas on Dukascopy bid/ask data via `usdjpy.events`.
   Most ideas should die here, cheaply.
3. **Realistic backtest** (Layer 2, later): survivors get ported to NautilusTrader with bid/ask
   fills, rollover interest and a fill model, using the same code that will run live on IBKR.
4. **Holdout check** → paper trade on IBKR → small live size.

## Rules of the repo

- **Holdout:** data from `HOLDOUT_START` (2025-01-01, in `src/usdjpy/config.py`) is excluded by
  default. Only pass `allow_holdout=True` once a spec is frozen. Each look spends it.
- **One cost model:** every result uses `usdjpy.costs.CostModel` (bid/ask fills + IBKR 0.2 bp,
  $2 min + slippage) and must also survive `PESSIMISTIC`.
- **Compare against control days**, not against zero. An effect that appears on every day is
  time-of-day drift, not the flow you hypothesised.
- **Pre-declare parameters.** No grid-searching entry/exit times over the full sample.

## Setup (macOS)

```bash
cd ~/Documents/Projects/usdjpy-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q                              # sanity tests
python scripts/gotobi_study.py                   # spec 001 on the seeded data
# rebuild / extend data (see docs/DATA.md):
python scripts/build_github_data.py              # GitHub mirrors (what seeded data/)
python scripts/fetch_official.py                 # FRED (incl. US 2y), MOF flows & intervention, CFTC
python scripts/download.py 2010-01-01 2026-11-20 # Dukascopy ticks (large; resumable)
```

## See the results

Spec 001 (gotobi), from the repo root:

```bash
.venv/bin/python scripts/gotobi_study.py     # summary tables in the terminal, trade CSVs in results/
.venv/bin/python scripts/gotobi_report.py    # rerun and build results/gotobi_report.html (~1 min)
open results/gotobi_report.html              # view the report in your browser
```

The report is one self-contained file that works offline: the kill-criteria verdict, per-rule
stats, cumulative and yearly net pips against control days, and how much extra cost each rule can
take. Both scripts take `--source combined|histdata|dukascopy|eightcap` (default `combined`).

`data/` and `results/` are git-ignored, so on a fresh clone run `python scripts/build_github_data.py`
first. It downloads about 2.5 GB. Don't add `--skip-ticks`: the Eightcap bid/ask bars that
`combined` needs are built from the ticks.

## Layout

```
specs/        strategy specs (one file per idea) + TEMPLATE.md
src/usdjpy/   dukascopy.py  tick download/parse, 1-min bid/ask bars
              calendars.py  JP business days, gotobi days, UK month-ends
              costs.py      shared IBKR cost model
              events.py     window-trade simulator, period summaries, event vs control test
              datasets.py   loaders for every file in data/ (prices, COT, macro, calendars)
scripts/      download.py, gotobi_study.py, gotobi_report.py (+ templates/ for the HTML report)
notebooks/    01_gotobi_event_study.ipynb
tests/        pytest
docs/DATA.md  data catalogue: sources, coverage, verified caveats
data/         git-ignored except data/calendars/; results/ git-ignored
```

## Notes on the data

- Dukascopy timestamps are UTC; Japan has no DST, so 09:55 JST is always 00:55 UTC.
- Dukascopy "volume" is their own liquidity, not market volume — don't build volume signals on it.
  Real volume needs CME 6J futures data (e.g. Databento).
- Dukascopy spreads ≠ IBKR spreads. Before going live, log IBKR IdealPro quotes around the
  windows you trade and recalibrate `slippage_pips`.
