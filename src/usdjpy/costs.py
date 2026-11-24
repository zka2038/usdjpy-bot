"""One shared cost model. Every backtest must use this so results are comparable.

Spread is taken from the actual bid/ask in the data (buy at ask, sell at bid).
On top of that we add IBKR commission and extra slippage per side.

IBKR IdealPro spot FX (checked Nov 2026): 0.20 bp of trade value, USD 2.00 minimum per order.
Orders below USD 25k go to odd-lot routing with worse prices - don't trade them.
"""
from __future__ import annotations

from dataclasses import dataclass

PIP = 0.01  # USDJPY


@dataclass(frozen=True)
class CostModel:
    notional_usd: float = 100_000
    commission_bp: float = 0.20
    min_commission_usd: float = 2.00
    slippage_pips: float = 0.10  # per side, beyond the quoted bid/ask

    def commission_usd(self) -> float:
        return max(self.notional_usd * self.commission_bp / 1e4, self.min_commission_usd)

    def commission_pips(self, price: float) -> float:
        """Per-side commission expressed in USDJPY pips at a given price."""
        usd_per_pip = self.notional_usd * PIP / price
        return self.commission_usd() / usd_per_pip

    def round_trip_pips(self, price: float) -> float:
        """Non-spread cost of a round trip (commission + slippage, both sides)."""
        return 2 * (self.commission_pips(price) + self.slippage_pips)

    def pips_to_usd(self, pips: float, price: float) -> float:
        return pips * self.notional_usd * PIP / price


# Pessimistic variant to stress-test anything that looks good.
PESSIMISTIC = CostModel(slippage_pips=0.30)
