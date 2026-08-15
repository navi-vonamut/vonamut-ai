import logging
import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, select, desc
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.trading.config import trading_config
from src.trading.models import TradingBase, MarketKline, OrderBookSnapshot, MarketTrade, TradingSystemLog

logger = logging.getLogger(__name__)

class TradingDBManager:
    """
    Менеджер базы данных для работы с рыночными данными и торговыми логами.
    Поддерживает атомарные и пакетные upsert операции в PostgreSQL.
    """

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or trading_config.get_effective_db_url()
        self.engine = create_engine(self.db_url, pool_pre_ping=True, pool_size=10, max_overflow=20)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def init_db(self):
        """Создает таблицы в базе данных, если они отсутствуют."""
        try:
            TradingBase.metadata.create_all(bind=self.engine)
            logger.info("Trading database tables initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize trading database tables: {e}")
            raise

    def get_session(self) -> Session:
        """Получить сессию базы данных."""
        return self.SessionLocal()

    def upsert_klines(self, klines_data: List[Dict[str, Any]]) -> int:
        """Алиас для upsert_klines_batch."""
        return self.upsert_klines_batch(klines_data)

    def upsert_klines_batch(self, klines_data: List[Dict[str, Any]]) -> int:
        """
        Пакетная бесконфликтная вставка/обновление свечей (UPSERT).
        При совпадении (symbol, interval, open_time) обновляет текущие значения свечи.
        Дедуплицирует записи внутри пачки, сохраняя самое свежее состояние.
        """
        if not klines_data:
            return 0

        # Дедупликация внутри пачки: ключ (symbol, interval, open_time)
        dedup_map: Dict[tuple, Dict[str, Any]] = {}
        now = datetime.datetime.utcnow()
        for item in klines_data:
            open_time_ms = int(item["open_time"])
            open_dt = item.get("open_time_dt") or datetime.datetime.utcfromtimestamp(open_time_ms / 1000.0)
            key = (item["symbol"], str(item["interval"]), open_time_ms)
            dedup_map[key] = {
                "symbol": item["symbol"],
                "interval": str(item["interval"]),
                "open_time": open_time_ms,
                "open_time_dt": open_dt,
                "open": float(item["open"]),
                "high": float(item["high"]),
                "low": float(item["low"]),
                "close": float(item["close"]),
                "volume": float(item["volume"]),
                "turnover": float(item.get("turnover", 0.0) or 0.0),
                "is_closed": bool(item.get("is_closed", False)),
                "created_at": now,
                "updated_at": now,
            }

        rows = list(dedup_map.values())
        if not rows:
            return 0

        stmt = pg_insert(MarketKline).values(rows)
        update_cols = {
            "high": stmt.excluded.high,
            "low": stmt.excluded.low,
            "close": stmt.excluded.close,
            "volume": stmt.excluded.volume,
            "turnover": stmt.excluded.turnover,
            "is_closed": stmt.excluded.is_closed,
            "updated_at": stmt.excluded.updated_at,
        }
        upsert_stmt = stmt.on_conflict_do_update(
            constraint="uq_market_klines_sym_int_time",
            set_=update_cols
        )

        with self.get_session() as session:
            try:
                session.execute(upsert_stmt)
                session.commit()
                return len(rows)
            except Exception as e:
                session.rollback()
                logger.error(f"Error executing upsert_klines_batch: {e}")
                raise

    def insert_orderbook_snapshots_batch(self, snapshots: List[Dict[str, Any]]) -> int:
        """Пакетная вставка снимков стакана цен."""
        if not snapshots:
            return 0

        now = datetime.datetime.utcnow()
        db_items = []
        for snap in snapshots:
            ts_ms = int(snap["timestamp"])
            ts_dt = snap.get("timestamp_dt") or datetime.datetime.utcfromtimestamp(ts_ms / 1000.0)
            db_items.append(
                OrderBookSnapshot(
                    symbol=snap["symbol"],
                    timestamp=ts_ms,
                    timestamp_dt=ts_dt,
                    bids=snap["bids"],
                    asks=snap["asks"],
                    update_id=snap.get("update_id"),
                    created_at=now,
                )
            )

        with self.get_session() as session:
            try:
                session.bulk_save_objects(db_items)
                session.commit()
                return len(db_items)
            except Exception as e:
                session.rollback()
                logger.error(f"Error inserting orderbook snapshots batch: {e}")
                raise

    def insert_trades_batch(self, trades_data: List[Dict[str, Any]]) -> int:
        """Пакетная вставка тиков/сделок."""
        if not trades_data:
            return 0

        now = datetime.datetime.utcnow()
        db_items = []
        for t in trades_data:
            ts_ms = int(t["timestamp"])
            ts_dt = t.get("timestamp_dt") or datetime.datetime.utcfromtimestamp(ts_ms / 1000.0)
            db_items.append(
                MarketTrade(
                    symbol=t["symbol"],
                    trade_id=str(t.get("trade_id", "")),
                    price=float(t["price"]),
                    size=float(t["size"]),
                    side=str(t["side"]),
                    timestamp=ts_ms,
                    timestamp_dt=ts_dt,
                    created_at=now,
                )
            )

        with self.get_session() as session:
            try:
                session.bulk_save_objects(db_items)
                session.commit()
                return len(db_items)
            except Exception as e:
                session.rollback()
                logger.error(f"Error inserting trades batch: {e}")
                raise

    def log_event(
        self,
        component: str,
        message_en: str,
        message_ru: Optional[str] = None,
        level: str = "INFO",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Запись системного лога с поддержкой двуязычности и fallback на английский."""
        with self.get_session() as session:
            try:
                log_entry = TradingSystemLog(
                    level=level,
                    component=component,
                    message_en=message_en,
                    message_ru=message_ru or message_en,
                    details=details or {},
                    created_at=datetime.datetime.utcnow(),
                )
                session.add(log_entry)
                session.commit()
            except Exception as e:
                session.rollback()
                logger.warning(f"Failed to persist trading system log: {e}")

    def get_latest_klines(self, symbol: str, interval: str, limit: int = 100) -> List[MarketKline]:
        """Получить последние N свечей для анализа."""
        with self.get_session() as session:
            stmt = (
                select(MarketKline)
                .where(MarketKline.symbol == symbol, MarketKline.interval == interval)
                .order_by(desc(MarketKline.open_time))
                .limit(limit)
            )
            results = session.execute(stmt).scalars().all()
            return list(reversed(results)) # Сортировка по возрастанию времени

_db_instance: Optional[TradingDBManager] = None

def get_trading_db() -> TradingDBManager:
    global _db_instance
    if _db_instance is None:
        _db_instance = TradingDBManager()
    return _db_instance
