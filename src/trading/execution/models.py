import datetime
from sqlalchemy import (
    Column, BigInteger, String, Numeric, Boolean,
    DateTime, JSON, Index
)
from src.trading.models import TradingBase

class TradingOrder(TradingBase):
    """
    Таблица для фиксации выставленных и исполненных торговых ордеров.
    """
    __tablename__ = "trading_orders"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    order_id = Column(String(64), nullable=True, index=True) # Bybit Order ID
    order_link_id = Column(String(64), nullable=True, index=True) # Client Order ID
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False) # Buy / Sell
    order_type = Column(String(20), default="Market", nullable=False) # Market, Limit
    price = Column(Numeric(18, 8), nullable=False)
    qty = Column(Numeric(24, 8), nullable=False)
    sl_price = Column(Numeric(18, 8), nullable=True)
    tp_price = Column(Numeric(18, 8), nullable=True)
    status = Column(String(30), default="Created", nullable=False) # Created, Submitted, Filled, Cancelled, Rejected
    executed_qty = Column(Numeric(24, 8), default=0.0)
    avg_price = Column(Numeric(18, 8), default=0.0)
    cum_fee = Column(Numeric(18, 8), default=0.0)
    is_dry_run = Column(Boolean, default=False, nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_orders_sym_time_desc", "symbol", created_at.desc()),
    )

    def __repr__(self):
        return f"<TradingOrder {self.symbol} {self.side} {self.qty} @ {self.price} [{self.status}]>"


class TradingPosition(TradingBase):
    """
    Таблица для отслеживания открытых и закрытых позиций на Bybit.
    """
    __tablename__ = "trading_positions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False) # Buy (Long), Sell (Short)
    size = Column(Numeric(24, 8), nullable=False)
    entry_price = Column(Numeric(18, 8), nullable=False)
    mark_price = Column(Numeric(18, 8), nullable=True)
    leverage = Column(Numeric(10, 2), default=1.0)
    unrealised_pnl = Column(Numeric(18, 8), default=0.0)
    realised_pnl = Column(Numeric(18, 8), default=0.0)
    status = Column(String(20), default="OPEN", nullable=False) # OPEN, CLOSED
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_positions_sym_status", "symbol", "status"),
    )

    def __repr__(self):
        return f"<TradingPosition {self.symbol} {self.side} {self.size} @ {self.entry_price} [{self.status}]>"
