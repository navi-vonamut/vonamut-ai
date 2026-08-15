from src.trading.execution.service import ExecutionService
from src.trading.db import get_trading_db
from src.trading.execution.models import TradingOrder

service = ExecutionService()
service.initialize()

# Simulated high-confidence BUY signal
sample_buy_decision = {
    'symbol': 'BTCUSDT',
    'action': 'BUY',
    'confidence': 0.85,
    'entry_price': 63400.0,
    'stop_loss': 62500.0,
    'take_profit_1': 65200.0,
    'take_profit_2': 66000.0,
    'recommended_leverage': 5,
    'reasoning_en': 'Breakout above key consolidation with heavy volume.',
    'reasoning_ru': 'Пробой ключевой консолидации на высоком объеме.'
}

res = service.process_and_execute_signal(sample_buy_decision, dry_run=True)
print("Execution Status:", res.get("status"))
print("Risk Validation Passed:", res.get("risk_validation", {}).get("passed"))
print("Calculated Qty:", res.get("risk_validation", {}).get("position_qty"), "BTC")
print("Position Value USD:", res.get("risk_validation", {}).get("position_value_usd"))
print("Required Margin USD:", res.get("risk_validation", {}).get("required_margin_usd"))
print("Stop Loss:", res.get("risk_validation", {}).get("stop_loss"))
print("Take Profit:", res.get("risk_validation", {}).get("take_profit"))
print("Risk/Reward Ratio:", res.get("risk_validation", {}).get("risk_reward_ratio"))
print("Order ID:", res.get("execution", {}).get("order_id"))

# Check PostgreSQL persistence
db = get_trading_db()
with db.get_session() as session:
    saved_orders = session.query(TradingOrder).all()
    print("Total Orders in PostgreSQL:", len(saved_orders))
    if saved_orders:
        latest = saved_orders[-1]
        print(f"Latest DB Order: {latest.symbol} {latest.side} {latest.qty} @ {latest.price} | SL: {latest.sl_price}, TP: {latest.tp_price} | Status: {latest.status}")
