# Data

`data/` is git-ignored except `data/calendars/` and this file. Rebuild the rest with:

```
python scripts/build_github_data.py    # GitHub mirrors
python scripts/fetch_official.py       # official hosts -> data/official/
python scripts/download.py 2010-01-01 2024-12-31 --tokyo-hours
```

All timestamps in processed files are **UTC**. Prices are USDJPY in JPY. Load
everything through `usdjpy.datasets`, which handles sources, the synthetic ask and
release lags — not by reading parquet directly.

## The catalogue lives in `docs/DATA.md`

Coverage, sources, cross-checks and the verified caveats for every file are in
[`docs/DATA.md`](../docs/DATA.md). This file deliberately does not restate them.

It used to. The two copies drifted in both directions: the HistData
`histdata_bid_2015_2025.parquet` "Complete" claim was corrected in `docs/DATA.md`
and left standing here, while `dgs2.csv` and `jgbcme_all.csv` were catalogued here
and missing there. A reader of either file got one current fact and one stale one,
and nothing distinguished them. Provenance notes go in `docs/DATA.md` only.
