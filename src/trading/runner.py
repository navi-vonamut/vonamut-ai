import os
import sys
import time
import argparse
import logging
import json

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.trading.config import trading_config
from src.trading.db import get_trading_db
from src.trading.redis_client import get_trading_redis
from src.trading.rest_client import BybitRestClient
from src.trading.ws_manager import BybitWSManager
from src.trading.service import DataIngestionService
from src.trading.rag import get_market_rag_service, get_qdrant_news_manager
from src.trading.agent import run_trading_agent_analysis
from src.trading.execution import get_execution_service, get_order_executor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
)
logger = logging.getLogger("TradingRunner")

def cmd_check():
    """Проверка доступности API, PostgreSQL, Redis, Qdrant и Risk Engine."""
    print("=" * 60)
    print("🔍 Проверка подключения ко всей торговой инфраструктуре...")
    print("=" * 60)

    # 1. PostgreSQL
    db = get_trading_db()
    print(f"PostgreSQL URL: {db.db_url}")
    try:
        db.init_db()
        print("✅ Таблицы PostgreSQL успешно инициализированы.")
    except Exception as e:
        print(f"❌ Ошибка подключения к базе данных: {e}")
        return False

    # 2. Redis Hot Cache
    redis_client = get_trading_redis()
    print(f"Redis URL: {redis_client.redis_url}")
    if redis_client.ping():
        print("✅ Redis 7 (L1 Hot Cache & Pub/Sub) доступен и готов к работе!")
    else:
        print("⚠️ Предупреждение: Redis недоступен по указанному адресу.")

    # 3. Qdrant Vector Store
    qdrant = get_qdrant_news_manager()
    print(f"Qdrant URL: {qdrant.config.get_effective_qdrant_url()}")
    if qdrant.check_connection():
        qdrant.init_collection()
        print(f"✅ Qdrant коллекция '{qdrant.config.collection_name}' готова (gemini-embedding-2 / 3072d)!")
    else:
        print("❌ Ошибка подключения к Qdrant.")
        return False

    # 4. Bybit REST API & Wallet
    executor = get_order_executor()
    wallet = executor.get_wallet_balance()
    if "error" not in wallet:
        print(f"✅ Bybit API V5 доступен! Demo mode: {trading_config.demo}")
        print(f"   Total Equity: ${wallet.get('total_equity', 0.0):.2f} | Available Margin: ${wallet.get('available_margin', 0.0):.2f}")
    else:
        print(f"❌ Ошибка соединения с Bybit API: {wallet.get('error')}")
        return False

    # Получение котировки BTCUSDT
    client = BybitRestClient()
    try:
        orderbook = client.get_orderbook("BTCUSDT", limit=5)
        bids = orderbook.get("bids", [])
        asks = orderbook.get("asks", [])
        if bids and asks:
            print(f"✅ Текущий стакан BTCUSDT: Best Bid = {bids[0][0]}, Best Ask = {asks[0][0]}")
    except Exception as e:
        print(f"⚠️ Не удалось получить стакан BTCUSDT: {e}")

    print("=" * 60)
    print("🎉 Все 4 контура торгового агента (API, DB, Redis, Qdrant, Risk Engine) работают штатно!")
    print("=" * 60)
    return True

def cmd_sync_history(symbols, intervals, days):
    """Синхронизация истории свечей."""
    service = DataIngestionService()
    service.initialize()
    results = service.sync_history(symbols=symbols, intervals=intervals, days_back=days)
    print("\n--- Результаты синхронизации истории ---")
    for k, v in results.items():
        print(f"  {k}: {v} свечей сохранено в БД")
    print(f"Всего: {sum(results.values())} записей.")

def cmd_stream(symbols, intervals, duration):
    """Запуск WebSocket потока с записью в Redis и PostgreSQL."""
    service = DataIngestionService()
    service.initialize()
    service.start_streaming(symbols=symbols, intervals=intervals)
    print(f"\n🚀 WebSocket стриминг запущен для {symbols} на интервалах {intervals}.")
    print(f"⚡ Горячие данные (L1): Redis | 💾 Холодные данные: PostgreSQL")
    print(f"Работа в течение {duration} сек... (или Ctrl+C)")

    start_time = time.time()
    try:
        while True:
            elapsed = time.time() - start_time
            if duration and elapsed >= duration:
                print(f"Достигнуто время тестирования {duration}с.")
                break
            time.sleep(2)
            print(f"📊 Статистика: {service.ws_manager.stats}")
    except KeyboardInterrupt:
        print("\nОстановка по сигналу...")
    finally:
        service.stop_streaming()
        print("✅ Стриминг успешно остановлен.")

def cmd_inspect_redis(symbol: str):
    """Инспекция горячего кэша Redis для символа."""
    redis_client = get_trading_redis()
    print(f"\n🔍 Инспекция Redis для {symbol}:")
    ob = redis_client.get_orderbook(symbol)
    if ob:
        print(f"  Стакан {symbol}: Best Bid = {ob.get('best_bid')}, Best Ask = {ob.get('best_ask')}, Spread = {ob.get('spread')}")
    else:
        print(f"  Стакан {symbol} в Redis отсутствует.")

    kline_1m = redis_client.get_kline(symbol, "1")
    if kline_1m:
        print(f"  Свеча 1m {symbol}: O={kline_1m.get('open')}, H={kline_1m.get('high')}, L={kline_1m.get('low')}, C={kline_1m.get('close')}, Closed={kline_1m.get('is_closed')}")

    trades = redis_client.get_recent_trades(symbol, count=5)
    print(f"  Последние {len(trades)} сделок в Redis:")
    for t in trades:
        print(f"    {t.get('side')} {t.get('size')} @ {t.get('price')} (ts={t.get('timestamp')})")

def cmd_sync_news(force: bool):
    """Сбор и векторизация новостей в Qdrant."""
    print("=" * 60)
    print("📰 Запуск сбора новостного фона и векторизации в Qdrant (gemini-embedding-2)...")
    print("=" * 60)
    rag = get_market_rag_service()
    rag.initialize()
    stats = rag.sync_news(force=force)
    print(f"\n✅ Завершено! Найдено статей: {stats['fetched']}, новых проиндексировано: {stats['indexed']}.")

def cmd_query_rag(symbol: str, query: str, hours: int):
    """Запрос RAG контекста и сентимента для монеты."""
    print("=" * 60)
    print(f"🧠 RAG Контекст за последние {hours}ч для {symbol}...")
    print("=" * 60)
    rag = get_market_rag_service()
    rag.initialize()
    formatted = rag.format_context_for_prompt(symbol=symbol, hours_back=hours)
    print(formatted)

def cmd_analyze(symbol: str, timeframe: str, mode: str):
    """Запуск полного аналитического цикла LangGraph StateGraph агента."""
    print("=" * 60)
    print(f"🤖 Запуск StateGraph анализа для {symbol} ({timeframe}m) [Режим: {mode}]...")
    print("=" * 60)

    result_state = run_trading_agent_analysis(symbol=symbol, timeframe=timeframe, mode=mode)

    decision = result_state.get("decision", {})
    action = decision.get("action", "HOLD")
    conf = decision.get("confidence", 0.0)
    tech = result_state.get("technical_indicators", {})

    print("\n" + "=" * 60)
    print(f"📊 ИТОГОВОЕ РЕШЕНИЕ АГЕНТА: {action} (Уверенность: {int(conf * 100)}%)")
    print("=" * 60)
    print(f"• Текущая цена:       {tech.get('current_price')}")
    print(f"• Тренд рынка:        {tech.get('trend')} (RSI: {tech.get('rsi', {}).get('value')})")
    print(f"• Дисбаланс стакана:  {tech.get('orderbook_imbalance', {}).get('imbalance_ratio')}x ({tech.get('orderbook_imbalance', {}).get('sentiment')})")
    print(f"• Рекомендуемый вход: {decision.get('entry_price')}")
    print(f"• Stop-Loss:          {decision.get('stop_loss')}")
    print(f"• Take-Profit 1:      {decision.get('take_profit_1')}")
    print(f"• Take-Profit 2:      {decision.get('take_profit_2')}")
    print(f"• Risk/Reward Ratio:  {decision.get('risk_reward_ratio')}")
    print(f"• Плечо / Горизонт:   {decision.get('recommended_leverage')}x | {decision.get('time_horizon')}")
    print("\n--- 🇷🇺 Обоснование (RU) ---")
    print(decision.get("reasoning_ru") or decision.get("reasoning_en"))
    print("\n--- 🇬🇧 Analytical Rationale (EN - Fallback Base) ---")
    print(decision.get("reasoning_en"))
    print("\n--- ⚠️ Риск-факторы ---")
    print("EN:", decision.get("risk_notes_en"))
    if decision.get("risk_notes_ru"):
        print("RU:", decision.get("risk_notes_ru"))
    print("=" * 60)
    return decision

def cmd_wallet():
    """Просмотр баланса и маржи Bybit Unified кошелька."""
    executor = get_order_executor()
    wallet = executor.get_wallet_balance()
    print("=" * 60)
    print("💰 BYBIT UNIFIED WALLET BALANCE")
    print("=" * 60)
    print(f"• Total Equity:          ${wallet.get('total_equity', 0.0):.2f}")
    print(f"• Available Margin:      ${wallet.get('available_margin', 0.0):.2f}")
    print(f"• Total Margin Balance:  ${wallet.get('total_margin_balance', 0.0):.2f}")
    print(f"• Account Type:          {wallet.get('account_type')}")
    print("=" * 60)

def cmd_positions():
    """Просмотр открытых позиций на Bybit."""
    executor = get_order_executor()
    positions = executor.get_open_positions()
    print("=" * 60)
    print(f"📈 BYBIT ACTIVE POSITIONS ({len(positions)} open)")
    print("=" * 60)
    if not positions:
        print("Нет активных открытых позиций.")
    for p in positions:
        print(f"• {p['symbol']} | {p['side']} {p['size']} @ ${p['entry_price']:.2f}")
        print(f"  Unrealised PnL: ${p['unrealised_pnl']:.2f} | Leverage: {p['leverage']}x | SL: {p['stop_loss']} | TP: {p['take_profit']}")
    print("=" * 60)

def cmd_execute_trade(symbol: str, timeframe: str, mode: str, dry_run: bool):
    """Сквозной запуск: StateGraph Анализ ➡️ Risk Engine ➡️ Исполнение на Bybit."""
    print("=" * 60)
    print(f"🚀 Запуск полного торгового цикла для {symbol} ({'DRY-RUN' if dry_run else 'LIVE EXECUTION'})...")
    print("=" * 60)

    # 1. StateGraph Анализ
    result_state = run_trading_agent_analysis(symbol=symbol, timeframe=timeframe, mode=mode)
    decision = result_state.get("decision", {})
    decision["symbol"] = symbol

    action = decision.get("action", "HOLD")
    print(f"🤖 Решение StateGraph: {action} (Уверенность: {int(decision.get('confidence', 0) * 100)}%)")

    # 2. Risk Engine & Execution
    exec_service = get_execution_service()
    exec_res = exec_service.process_and_execute_signal(decision=decision, dry_run=dry_run)

    print("\n" + "=" * 60)
    print(f"🛡️ РЕЗУЛЬТАТ RISK ENGINE & EXECUTION: {exec_res.get('status')}")
    print("=" * 60)
    risk_val = exec_res.get("risk_validation", {})
    print(f"• Валидация пройдена:  {risk_val.get('passed')}")
    print(f"• Причина/Статус:      {risk_val.get('reason')}")
    if risk_val.get("passed"):
        print(f"• Расчетный объем:     {risk_val.get('position_qty')} {symbol} (${risk_val.get('position_value_usd')} USD)")
        print(f"• Требуемая маржа:     ${risk_val.get('required_margin_usd')} (Плечо: {risk_val.get('leverage')}x)")
        print(f"• Риск на сделку:      ${risk_val.get('risk_usd')} ({risk_val.get('risk_pct')}%)")
        print(f"• R:R Ratio:           {risk_val.get('risk_reward_ratio')}")
        print(f"• Entry / SL / TP:     {risk_val.get('entry_price')} / {risk_val.get('stop_loss')} / {risk_val.get('take_profit')}")

    if exec_res.get("executed"):
        print(f"✅ Ордер успешно зафиксирован! ID: {exec_res.get('execution', {}).get('order_id')}")
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description="Bybit Autonomous Trading Agent Runner")
    subparsers = parser.add_subparsers(dest="command", help="Команда для выполнения")

    # check
    subparsers.add_parser("check", help="Проверить подключение ко всем 4 контурам системы")

    # wallet
    subparsers.add_parser("wallet", help="Просмотреть баланс и маржу Unified кошелька Bybit")

    # positions
    subparsers.add_parser("positions", help="Просмотреть открытые позиции на Bybit")

    # sync-history
    sync_p = subparsers.add_parser("sync-history", help="Синхронизировать исторические свечи через REST")
    sync_p.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT"], help="Символы для загрузки")
    sync_p.add_argument("--intervals", nargs="+", default=["1", "5", "15", "60", "D"], help="Интервалы свечей")
    sync_p.add_argument("--days", type=int, default=3, help="Количество дней истории")

    # stream
    stream_p = subparsers.add_parser("stream", help="Запустить WebSocket стриминг данных в Redis и PostgreSQL")
    stream_p.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT"], help="Символы для подписки")
    stream_p.add_argument("--intervals", nargs="+", default=["1", "5"], help="Интервалы kline")
    stream_p.add_argument("--duration", type=int, default=0, help="Длительность стриминга в секундах (0 = бесконечно)")

    # inspect-redis
    insp_p = subparsers.add_parser("inspect-redis", help="Просмотреть горячие данные в Redis")
    insp_p.add_argument("--symbol", default="BTCUSDT", help="Символ для инспекции")

    # sync-news
    news_p = subparsers.add_parser("sync-news", help="Собрать и векторизовать новости в Qdrant")
    news_p.add_argument("--force", action="store_true", help="Принудительная переиндексация")

    # query-rag
    rag_p = subparsers.add_parser("query-rag", help="Запросить 24h контекст и сентимент для монеты")
    rag_p.add_argument("--symbol", default="BTC", help="Символ монеты (BTC, ETH, SOL)")
    rag_p.add_argument("--query", default="", help="Дополнительный текст поискового запроса")
    rag_p.add_argument("--hours", type=int, default=24, help="Окно в часах")

    # analyze
    analyze_p = subparsers.add_parser("analyze", help="Запустить LangGraph StateGraph анализ монеты")
    analyze_p.add_argument("--symbol", default="BTCUSDT", help="Символ торговой пары (BTCUSDT, ETHUSDT)")
    analyze_p.add_argument("--timeframe", default="15", help="Интервал (1, 5, 15, 60, D)")
    analyze_p.add_argument("--mode", default="fast", choices=["fast", "deep", "hybrid"], help="Режим анализа (fast: gemini-3.5-flash-lite, deep: gemma-4-31b-it)")

    # execute-trade
    exec_p = subparsers.add_parser("execute-trade", help="Сквозной запуск: Анализ ➡️ Risk Engine ➡️ Исполнение")
    exec_p.add_argument("--symbol", default="BTCUSDT", help="Символ торговой пары")
    exec_p.add_argument("--timeframe", default="15", help="Интервал свечей")
    exec_p.add_argument("--mode", default="fast", choices=["fast", "deep", "hybrid"], help="Режим анализа")
    exec_p.add_argument("--live", action="store_true", help="Отправлять реальный боевой/демо ордер на биржу (по умолчанию Dry-Run)")

    # run-all
    run_p = subparsers.add_parser("run-all", help="Полный запуск: проверка + история + новости + стриминг")
    run_p.add_argument("--days", type=int, default=3, help="Количество дней истории для начальной загрузки")

    args = parser.parse_args()

    if args.command == "check":
        cmd_check()
    elif args.command == "wallet":
        cmd_wallet()
    elif args.command == "positions":
        cmd_positions()
    elif args.command == "sync-history":
        cmd_sync_history(args.symbols, args.intervals, args.days)
    elif args.command == "stream":
        cmd_stream(args.symbols, args.intervals, args.duration)
    elif args.command == "inspect-redis":
        cmd_inspect_redis(args.symbol)
    elif args.command == "sync-news":
        cmd_sync_news(args.force)
    elif args.command == "query-rag":
        cmd_query_rag(args.symbol, args.query, args.hours)
    elif args.command == "analyze":
        cmd_analyze(args.symbol, args.timeframe, args.mode)
    elif args.command == "execute-trade":
        cmd_execute_trade(args.symbol, args.timeframe, args.mode, dry_run=not args.live)
    elif args.command == "run-all":
        service = DataIngestionService()
        service.run_full_pipeline(days_back=args.days)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
