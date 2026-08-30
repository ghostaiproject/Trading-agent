from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from ib_async import IB, LimitOrder, MarketOrder, Stock, Trade

from .config import Settings, WatchlistEntry


@dataclass
class AccountState:
    net_liquidation: float
    cash_balance: float
    buying_power: float


@dataclass
class Position:
    symbol: str
    quantity: float
    avg_cost: float
    market_price: float
    market_value: float


@dataclass
class MarketSnapshot:
    symbol: str
    last_price: float
    bid: float
    ask: float
    recent_closes: List[float]


class IBKRBroker:
    """Thin wrapper around ib_async for account state, market data, and orders.

    Requires TWS or IB Gateway running locally with the API enabled
    (Configuration > API > Settings > Enable ActiveX and Socket Clients).
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.ib = IB()

    def connect(self) -> None:
        self.ib.connect(self.settings.ib_host, self.settings.ib_port, clientId=self.settings.ib_client_id)
        self.ib.reqMarketDataType(self.settings.market_data_type)

    def disconnect(self) -> None:
        if self.ib.isConnected():
            self.ib.disconnect()

    @staticmethod
    def build_contract(entry: WatchlistEntry) -> Stock:
        return Stock(entry.symbol, entry.exchange, entry.currency, primaryExchange=entry.primary_exchange or "")

    def get_account_state(self) -> AccountState:
        summary = self.ib.accountSummary()

        def _find(tag: str) -> float:
            for row in summary:
                if row.tag == tag and row.currency == "BASE":
                    return float(row.value)
            return 0.0

        return AccountState(
            net_liquidation=_find("NetLiquidation"),
            cash_balance=_find("TotalCashValue"),
            buying_power=_find("BuyingPower"),
        )

    def get_positions(self) -> Dict[str, Position]:
        positions: Dict[str, Position] = {}
        for pos in self.ib.positions():
            if pos.position == 0:
                continue
            symbol = pos.contract.symbol
            ticker = self.ib.reqMktData(pos.contract, "", False, False)
            self.ib.sleep(1)
            market_price = ticker.marketPrice() or ticker.last or ticker.close or pos.avgCost
            self.ib.cancelMktData(pos.contract)
            positions[symbol] = Position(
                symbol=symbol,
                quantity=pos.position,
                avg_cost=pos.avgCost,
                market_price=market_price,
                market_value=market_price * pos.position,
            )
        return positions

    def get_market_snapshot(self, entry: WatchlistEntry) -> MarketSnapshot:
        contract = self.build_contract(entry)
        self.ib.qualifyContracts(contract)

        ticker = self.ib.reqMktData(contract, "", False, False)
        self.ib.sleep(2)
        last_price = ticker.marketPrice() or ticker.last or ticker.close or 0.0
        bid = ticker.bid or 0.0
        ask = ticker.ask or 0.0
        self.ib.cancelMktData(contract)

        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr="30 D",
            barSizeSetting="1 day",
            whatToShow="TRADES",
            useRTH=True,
        )
        recent_closes = [bar.close for bar in bars]

        return MarketSnapshot(symbol=entry.symbol, last_price=last_price, bid=bid, ask=ask, recent_closes=recent_closes)

    def place_order(
        self,
        entry: WatchlistEntry,
        action: str,
        quantity: int,
        order_type: str,
        limit_price: Optional[float],
    ) -> Optional[Trade]:
        """Submits an order. Returns None without contacting the broker when dry_run is set."""
        if self.settings.dry_run:
            return None

        contract = self.build_contract(entry)
        self.ib.qualifyContracts(contract)

        if order_type == "limit" and limit_price:
            order = LimitOrder(action.upper(), quantity, limit_price)
        else:
            order = MarketOrder(action.upper(), quantity)

        trade = self.ib.placeOrder(contract, order)
        self.ib.sleep(2)
        return trade
