import datetime
from sqlalchemy import (
    Column, BigInteger, Integer, String, Numeric, Boolean,
    DateTime, Text, JSON, UniqueConstraint, Index
)
from sqlalchemy.orm import declarative_base

TradingBase = declarative_base()

class MarketKline(TradingBase):
    """
    Таблица для хранения OHLCV свечей разных таймфреймов с биржи Bybit.
    """
    __tablename__ = "market_klines"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    interval = Column(String(10), nullable=False, index=True) # 1, 5, 15, 60, D
    open_time = Column(BigInteger, nullable=False, index=True) # timestamp in ms
    open_time_dt = Column(DateTime, nullable=False, index=True)
    open = Column(Numeric(18, 8), nullable=False)
    high = Column(Numeric(18, 8), nullable=False)
    low = Column(Numeric(18, 8), nullable=False)
    close = Column(Numeric(18, 8), nullable=False)
    volume = Column(Numeric(24, 8), nullable=False)
    turnover = Column(Numeric(24, 8), nullable=True)
    is_closed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("symbol", "interval", "open_time", name="uq_market_klines_sym_int_time"),
        Index("ix_klines_sym_int_time_desc", "symbol", "interval", open_time.desc()),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "interval": self.interval,
            "open_time": self.open_time_dt.isoformat() if self.open_time_dt else str(self.open_time),
            "open_time_ms": self.open_time,
            "open": float(self.open),
            "high": float(self.high),
            "low": float(self.low),
            "close": float(self.close),
            "volume": float(self.volume),
            "turnover": float(self.turnover) if self.turnover else None,
            "is_closed": self.is_closed,
        }

    def __repr__(self):
        return f"<MarketKline {self.symbol} {self.interval} {self.open_time_dt} C={self.close}>"


class OrderBookSnapshot(TradingBase):
    """
    Снимки стакана цен (глубина рынка) для анализа плотности ликвидности и дисбаланса.
    """
    __tablename__ = "orderbook_snapshots"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    timestamp = Column(BigInteger, nullable=False, index=True) # ms
    timestamp_dt = Column(DateTime, nullable=False, index=True)
    bids = Column(JSON, nullable=False) # list of [price, size]
    asks = Column(JSON, nullable=False) # list of [price, size]
    update_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_orderbook_sym_time_desc", "symbol", timestamp.desc()),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "timestamp_dt": self.timestamp_dt.isoformat() if self.timestamp_dt else None,
            "bids": self.bids,
            "asks": self.asks,
        }

    def __repr__(self):
        return f"<OrderBookSnapshot {self.symbol} @ {self.timestamp_dt}>"


class MarketTrade(TradingBase):
    """
    Поток публичных сделок (тиков) для анализа ленты сделок и Volume Delta.
    """
    __tablename__ = "market_trades"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    trade_id = Column(String(64), nullable=True, index=True)
    price = Column(Numeric(18, 8), nullable=False)
    size = Column(Numeric(24, 8), nullable=False)
    side = Column(String(10), nullable=False) # Buy / Sell
    timestamp = Column(BigInteger, nullable=False, index=True) # ms
    timestamp_dt = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_trades_sym_time_desc", "symbol", timestamp.desc()),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "trade_id": self.trade_id,
            "price": float(self.price),
            "size": float(self.size),
            "side": self.side,
            "timestamp": self.timestamp,
            "timestamp_dt": self.timestamp_dt.isoformat() if self.timestamp_dt else None,
        }

    def __repr__(self):
        return f"<MarketTrade {self.symbol} {self.side} {self.size}@{self.price}>"


class TradingSystemLog(TradingBase):
    """
    Системные логи и события агента с обязательным fallback на английский язык.
    """
    __tablename__ = "trading_system_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    level = Column(String(20), default="INFO", nullable=False) # INFO, WARNING, ERROR, RISK_ALERT
    component = Column(String(50), nullable=False) # Ingestion, RiskEngine, StateGraph, BybitWS
    message_en = Column(Text, nullable=False) # Primary standard message in English
    message_ru = Column(Text, nullable=True)  # Localized Russian message
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_logs_component_time_desc", "component", created_at.desc()),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "level": self.level,
            "component": self.component,
            "message_en": self.message_en,
            "message_ru": self.message_ru,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<TradingSystemLog [{self.level}] {self.component}: {self.message_en[:40]}...>"

    def get_localized_message(self, lang: str = "ru") -> str:
        if lang.lower() == "ru" and self.message_ru:
            return self.message_ru
        return self.message_en # Fallback to English
