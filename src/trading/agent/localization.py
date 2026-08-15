import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class LocalizationManager:
    """
    Менеджер локализации системных сообщений, логов и торговых уведомлений.
    Обеспечивает 100% гарантию надежности за счет глобального fallback на английский язык:
    любая ошибка интерполяции или отсутствие перевода никогда не приводит к падению системы.
    """

    TEMPLATES = {
        "CYCLE_STARTED": {
            "en": "Trading analysis cycle started for {symbol} ({timeframe}) in {mode} mode.",
            "ru": "Запущен аналитический цикл торговли для {symbol} ({timeframe}) в режиме {mode}."
        },
        "CONTEXT_FETCHED": {
            "en": "Market context loaded: {klines_count} klines, Best Bid={best_bid}, Best Ask={best_ask}, News items={news_count}.",
            "ru": "Рыночный контекст загружен: {klines_count} свечей, Best Bid={best_bid}, Best Ask={best_ask}, Новостей={news_count}."
        },
        "TECH_ANALYSIS_COMPLETE": {
            "en": "Technical analysis complete for {symbol}: Trend={trend}, RSI={rsi}, MACD={macd}, ATR={atr}, Ob Imbalance={imbalance}.",
            "ru": "Технический анализ завершен для {symbol}: Тренд={trend}, RSI={rsi}, MACD={macd}, ATR={atr}, Дисбаланс стакана={imbalance}."
        },
        "SIGNAL_BUY": {
            "en": "🟢 BUY SIGNAL GENERATED for {symbol} @ {entry_price}. SL: {sl}, TP1: {tp1}, TP2: {tp2}, R:R: {rr}. Confidence: {confidence}%.",
            "ru": "🟢 СИГНАЛ НА ПОКУПКУ (LONG) для {symbol} @ {entry_price}. SL: {sl}, TP1: {tp1}, TP2: {tp2}, R:R: {rr}. Уверенность: {confidence}%."
        },
        "SIGNAL_SELL": {
            "en": "🔴 SELL SIGNAL GENERATED for {symbol} @ {entry_price}. SL: {sl}, TP1: {tp1}, TP2: {tp2}, R:R: {rr}. Confidence: {confidence}%.",
            "ru": "🔴 СИГНАЛ НА ПРОДАЖУ (SHORT) для {symbol} @ {entry_price}. SL: {sl}, TP1: {tp1}, TP2: {tp2}, R:R: {rr}. Уверенность: {confidence}%."
        },
        "SIGNAL_HOLD": {
            "en": "⚪ HOLD / NO TRADE for {symbol}. Market condition: {trend}. Confidence: {confidence}%. Rationale: {reason}",
            "ru": "⚪ СИГНАЛ ВНЕ РЫНКА (HOLD) для {symbol}. Состояние: {trend}. Уверенность: {confidence}%. Причина: {reason}"
        },
        "RISK_ALERT": {
            "en": "⚠️ RISK ALERT: {message}",
            "ru": "⚠️ ПРЕДУПРЕЖДЕНИЕ О РИСКЕ: {message}"
        },
        "AGENT_ERROR": {
            "en": "❌ Agent execution error in node '{node}': {error}",
            "ru": "❌ Ошибка выполнения агента в узле '{node}': {error}"
        }
    }

    def format_message(self, key: str, lang: str = "en", **kwargs) -> str:
        """
        Форматирование сообщения на запрошенном языке с гарантированным английским fallback.
        """
        template_entry = self.TEMPLATES.get(key)
        if not template_entry:
            # Неизвестный ключ - безопасный fallback
            return f"[{key}] {', '.join(f'{k}={v}' for k, v in kwargs.items())}"

        en_template = template_entry.get("en", f"[{key}]")

        if lang.lower() == "ru":
            ru_template = template_entry.get("ru")
            if ru_template:
                try:
                    return ru_template.format(**kwargs)
                except Exception as e:
                    logger.warning(f"Failed to format Russian template for '{key}': {e}. Falling back to English.")

        # Fallback to English
        try:
            return en_template.format(**kwargs)
        except Exception as e:
            logger.error(f"Failed to format English template for '{key}': {e}")
            return f"[{key}] {', '.join(f'{k}={v}' for k, v in kwargs.items())}"

    def get_bilingual_log(self, key: str, **kwargs) -> Dict[str, str]:
        """
        Возвращает двуязычный словарь {message_en, message_ru} с гарантией заполненности обоих полей.
        """
        msg_en = self.format_message(key, lang="en", **kwargs)
        msg_ru = self.format_message(key, lang="ru", **kwargs)
        return {
            "message_en": msg_en,
            "message_ru": msg_ru or msg_en # Абсолютная гарантия отсутствия None
        }

_loc_manager_instance: Optional[LocalizationManager] = None

def get_localization_manager() -> LocalizationManager:
    global _loc_manager_instance
    if _loc_manager_instance is None:
        _loc_manager_instance = LocalizationManager()
    return _loc_manager_instance
