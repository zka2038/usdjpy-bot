"""One shared cost model. Every backtest must use this so results are comparable.

Spread is taken from the actual bid/ask in the data (buy at ask, sell at bid).
On top of that we add IBKR commission and extra slippage per side.

IBKR IdealPro spot FX (checked Nov 2026): 0.20 bp of trade value, USD 2.00 minimum per order.
Orders below USD 25k go to odd-lot routing with worse prices - don't trade them.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

PIP = 0.01  # USDJPY


@dataclass(frozen=True)
class CostModel:
    notional_usd: float = 100_000
    commission_bp: float = 0.20
    min_commission_usd: float = 2.00
    slippage_pips: float = 0.10  # per side, beyond the quoted bid/ask
    # Overnight positions: IBKR pays benchmark - 0.5% on the long currency and charges
    # benchmark + 1.5% on the short one, so ~2% a year of notional goes to the broker either way.
    financing_skim_pct: float = 2.0

    def commission_usd(self, notional_usd: float | None = None) -> float:
        """Per-order commission; default at this model's notional."""
        n = self.notional_usd if notional_usd is None else abs(notional_usd)
        return max(n * self.commission_bp / 1e4, self.min_commission_usd)

    def commission_pips(self, price: float) -> float:
        """Per-side commission expressed in USDJPY pips at a given price."""
        usd_per_pip = self.notional_usd * PIP / price
        return self.commission_usd() / usd_per_pip

    def round_trip_pips(self, price: float) -> float:
        """Non-spread cost of a round trip (commission + slippage, both sides)."""
        return 2 * (self.commission_pips(price) + self.slippage_pips)

    def pips_to_usd(self, pips: float, price: float) -> float:
        return pips * self.notional_usd * PIP / price

    def financing_pips(self, side: int, price: float, usd_rate_pct: float, jpy_rate_pct: float,
                       days: float) -> float:
        """Carry over `days` calendar days (act/360) in USDJPY pips, after the broker's skim.

        Long USDJPY earns (USD rate - JPY rate); short pays it. The skim is charged either way.
        """
        carry_pct = side * (usd_rate_pct - jpy_rate_pct) - self.financing_skim_pct
        return price * carry_pct / 100 * days / 360 / PIP


ROLL_TZ, ROLL_HOUR = "America/New_York", 17


def roll_times(start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
    """UTC instants of the 17:00 New York rolls a position open over [start, end) is held through.

    One roll per calendar day, weekends included, so a position held over a weekend
    pays three nights however it is entered: interest accrues daily on the cash
    balances IBKR converts FX positions into. A roll at exactly `start` counts (the
    position is open at it), one at exactly `end` does not. Built on local dates, so
    17:00 stays 17:00 New York across DST. An intraday Tokyo hold crosses none.

    `horizon.simulate` charges fractional calendar days instead; the two agree on
    whole-day holds, which is all it simulates.
    """
    a, b = pd.Timestamp(start).tz_convert(ROLL_TZ), pd.Timestamp(end).tz_convert(ROLL_TZ)
    days = pd.date_range(a.date() - pd.Timedelta(days=1), b.date() + pd.Timedelta(days=1), freq="D")
    rolls = (days + pd.Timedelta(hours=ROLL_HOUR)).tz_localize(ROLL_TZ)
    return rolls[(rolls >= a) & (rolls < b)].tz_convert("UTC")


# Spread multipliers on the 2024-26 synthetic profile, by the era a trade's bars come
# from: spec 004's "era" sensitivity column (x2 for "era x2"). JUDGEMENT, NOT
# MEASUREMENT: a stress column, never the governing one. Keyed on the entry bar's
# source; "dukascopy_tree" (the spec 004 gap-fill tree) spans both eras, so it is
# keyed on date with the same boundary as the bid-only sources it fills.
ERA_SPREAD_MULT = {"eightcap": 1.0, "histdata": 2.5, "dukascopy": 5.0}
ERA_TREE_BOUNDARY = "2015-01-01"


def era_spread_multiplier(sources, dates) -> np.ndarray:
    """Era multiplier per trade from its entry-bar source and (JST) date."""
    src = pd.Series(list(sources))
    dts = pd.DatetimeIndex(dates)
    unknown = set(src) - set(ERA_SPREAD_MULT) - {"dukascopy_tree"}
    if unknown:
        raise ValueError(f"no era multiplier for sources {unknown}")
    k = src.map(ERA_SPREAD_MULT).to_numpy(dtype=float, copy=True)
    tree = (src == "dukascopy_tree").to_numpy()
    k[tree] = np.where(dts[tree] < pd.Timestamp(ERA_TREE_BOUNDARY), ERA_SPREAD_MULT["dukascopy"],
                       ERA_SPREAD_MULT["histdata"])
    return k


# Pessimistic variant to stress-test anything that looks good.
PESSIMISTIC = CostModel(slippage_pips=0.30, financing_skim_pct=2.5)
