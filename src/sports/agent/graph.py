import json
import logging
from typing import Dict, Any, List, Optional, TypedDict
from sqlalchemy.orm import Session

from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.sports.config import sports_config
from src.sports.rag.qdrant_sports_manager import get_qdrant_sports_manager
from src.db.base import SessionLocal
from src.db.models import SportsMatch, SportsOdds, SportsBet

logger = logging.getLogger(__name__)

# Состояние графа
class SportsAgentState(TypedDict):
    match_id: str
    league: str
    team1: str
    team2: str
    commence_time: str
    
    # Node 1 Output
    odds_team1: float
    odds_draw: Optional[float]
    odds_team2: float
    insider_context: List[str]
    context_text: str
    
    # Node 2 Output
    ai_prob_team1: float
    ai_prob_draw: Optional[float]
    ai_prob_team2: float
    ai_reasoning: str
    
    # Node 3 Output
    is_value_bet: bool
    best_outcome: Optional[str]        # "Победа 1", "Ничья", "Победа 2"
    selected_team: Optional[str]       # Название выбранной команды
    selected_odds: Optional[float]     # Коэффициент Pinnacle
    selected_prob: Optional[float]     # Вероятность ИИ (0..1)
    value_percentage: Optional[float]  # Перевес (например +0.17 для +17%)
    bet_record_id: Optional[int]


# ==========================================
# NODE 1: Context Builder
# ==========================================
async def node_context_builder(state: SportsAgentState) -> SportsAgentState:
    """
    Достает линию Pinnacle из PostgreSQL и вытягивает инсайды из Qdrant за 48 часов.
    """
    match_id = state["match_id"]
    team1 = state["team1"]
    team2 = state["team2"]

    logger.info(f"[LANGGRAPH Node 1] Context Builder running for {team1} vs {team2}...")

    # 1. Загрузка кэфов из БД
    db: Session = SessionLocal()
    odds_t1, odds_draw, odds_t2 = 2.0, None, 2.0
    try:
        odds_obj = db.query(SportsOdds).filter_by(match_id=match_id, bookmaker=sports_config.target_bookmaker).first()
        if odds_obj:
            odds_t1 = odds_obj.odds_team1
            odds_draw = odds_obj.odds_draw
            odds_t2 = odds_obj.odds_team2
    except Exception as e:
        logger.error(f"[LANGGRAPH Node 1] DB error loading odds: {e}")
    finally:
        db.close()

    # 2. Получение инсайдов из Qdrant (sports_context_24h)
    qdrant_mgr = get_qdrant_sports_manager()
    context_posts = qdrant_mgr.query_match_context(team1, team2, hours_back=48, limit=10)
    
    insider_texts = []
    for p in context_posts:
        source = p.get("source", "telegram")
        text = p.get("text", "")
        insider_texts.append(f"[{source}]: {text}")

    combined_context = "\n".join(insider_texts) if insider_texts else "Инсайдеров и новостей за последние 48 часов не обнаружено."

    state["odds_team1"] = odds_t1
    state["odds_draw"] = odds_draw
    state["odds_team2"] = odds_t2
    state["insider_context"] = insider_texts
    state["context_text"] = combined_context
    return state


# ==========================================
# NODE 2: Reasoning & Probabilities (Gemini)
# ==========================================
async def node_reasoning_and_probabilities(state: SportsAgentState) -> SportsAgentState:
    """
    Gemini оценивает реальные вероятности победы на основе инсайдов, не смотря на коэффициенты.
    """
    team1 = state["team1"]
    team2 = state["team2"]
    context_text = state["context_text"]

    logger.info(f"[LANGGRAPH Node 2] Reasoning & Probabilities executing via Gemini for {team1} vs {team2}...")

    system_prompt = (
        "Ты эксперт спортивной аналитики. Твоя задача — оценить реальные вероятности исходов матча "
        "исключительно на основе текстового контекста (травмы, форма, мотивация, конфликт в команде, погода, составы).\n"
        "НЕ смотри на коэффициенты букмекеров при оценке.\n\n"
        "ВАЖНО: Верни строго валидный JSON в формате:\n"
        "{\n"
        '  "prob_team1": 0.45,\n'
        '  "prob_draw": 0.25,\n'
        '  "prob_team2": 0.30,\n'
        '  "reasoning_summary": "Краткая выжимка (1-2 предложения) главных причин оценки."\n'
        "}\n"
        "Сумма вероятностей (prob_team1 + prob_draw + prob_team2) должна быть равна 1.0."
    )

    user_prompt = (
        f"Матч: {team1} — {team2}\n\n"
        f"Собраный инсайдерский контекст:\n{context_text}"
    )

    # Инициализация Gemini
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.2,
        google_api_key=sports_config.google_api_key
    )

    try:
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        
        raw_content = response.content.strip()
        # Очистка JSON от markdown ограждений ```json ... ```
        if "```" in raw_content:
            raw_content = raw_content.split("```json")[-1].split("```")[0].strip()
            if raw_content.startswith("json"):
                raw_content = raw_content[4:].strip()

        data = json.loads(raw_content)

        state["ai_prob_team1"] = float(data.get("prob_team1", 0.33))
        state["ai_prob_draw"] = float(data.get("prob_draw", 0.33)) if data.get("prob_draw") is not None else None
        state["ai_prob_team2"] = float(data.get("prob_team2", 0.34))
        state["ai_reasoning"] = data.get("reasoning_summary", "Оценка проведена на основе контекста.")
    except Exception as e:
        logger.error(f"[LANGGRAPH Node 2] Error invoking Gemini or parsing JSON: {e}")
        # Фолбэк на случай ошибки LLM
        state["ai_prob_team1"] = 0.40
        state["ai_prob_draw"] = 0.25
        state["ai_prob_team2"] = 0.35
        state["ai_reasoning"] = f"Фолбэк анализ на основе новостей: {context_text[:100]}..."

    return state


# ==========================================
# NODE 3: Value Calculator (Python Engine)
# ==========================================
async def node_value_calculator(state: SportsAgentState) -> SportsAgentState:
    """
    Жесткая математика без LLM. Сравнивает вероятности от ИИ с линией Pinnacle.
    Формула: (Вероятность ИИ * Коэффициент) - 1.0.
    Если результат > 0.05 (+5%+ перевес) — сигнал проходит далее.
    """
    logger.info(f"[LANGGRAPH Node 3] Value Calculator math engine running...")

    threshold = sports_config.value_threshold

    # Исход 1: Победа Команды 1
    p1 = state["ai_prob_team1"]
    k1 = state["odds_team1"]
    val1 = (p1 * k1) - 1.0

    # Исход 2: Ничья (если есть)
    p_draw = state.get("ai_prob_draw")
    k_draw = state.get("odds_draw")
    val_draw = (p_draw * k_draw) - 1.0 if (p_draw is not None and k_draw is not None) else -1.0

    # Исход 3: Победа Команды 2
    p2 = state["ai_prob_team2"]
    k2 = state["odds_team2"]
    val2 = (p2 * k2) - 1.0

    options = [
        {"target": "Победа 1", "team": state["team1"], "prob": p1, "odds": k1, "val": val1},
        {"target": "Ничья", "team": "Ничья", "prob": p_draw or 0.0, "odds": k_draw or 0.0, "val": val_draw},
        {"target": "Победа 2", "team": state["team2"], "prob": p2, "odds": k2, "val": val2},
    ]

    # Сортировка по величие перевеса
    best_opt = max(options, key=lambda x: x["val"])

    if best_opt["val"] > threshold:
        state["is_value_bet"] = True
        state["best_outcome"] = best_opt["target"]
        state["selected_team"] = best_opt["team"]
        state["selected_odds"] = best_opt["odds"]
        state["selected_prob"] = best_opt["prob"]
        state["value_percentage"] = best_opt["val"]
        logger.info(
            f"[LANGGRAPH Node 3] VALUE FOUND! Match: {state['team1']} vs {state['team2']}, "
            f"Target: {best_opt['target']}, EV: +{best_opt['val']*100:.1f}%"
        )
        
        # Сохранение найденного сигнала в БД PostgreSQL (sports_bets)
        db: Session = SessionLocal()
        try:
            bet_record = SportsBet(
                match_id=state["match_id"],
                league=state["league"],
                team1=state["team1"],
                team2=state["team2"],
                bet_target=best_opt["target"],
                bookmaker_odds=best_opt["odds"],
                ai_probability=best_opt["prob"],
                value_percentage=best_opt["val"],
                ai_reasoning=state["ai_reasoning"],
                user_action="PENDING"
            )
            db.add(bet_record)
            db.commit()
            db.refresh(bet_record)
            state["bet_record_id"] = bet_record.id
        except Exception as e:
            db.rollback()
            logger.error(f"[LANGGRAPH Node 3] DB Error saving bet record: {e}")
        finally:
            db.close()
    else:
        state["is_value_bet"] = False
        state["best_outcome"] = None
        state["selected_team"] = None
        state["selected_odds"] = None
        state["selected_prob"] = None
        state["value_percentage"] = best_opt["val"]
        logger.info(f"[LANGGRAPH Node 3] No value bet found for {state['team1']} vs {state['team2']} (Max EV: {best_opt['val']*100:.1f}%)")

    return state


# ==========================================
# Построение LangGraph Графа
# ==========================================
def create_sports_graph():
    builder = StateGraph(SportsAgentState)

    builder.add_node("context_builder", node_context_builder)
    builder.add_node("reasoning", node_reasoning_and_probabilities)
    builder.add_node("value_calculator", node_value_calculator)

    builder.set_entry_point("context_builder")
    builder.add_edge("context_builder", "reasoning")
    builder.add_edge("reasoning", "value_calculator")
    builder.add_edge("value_calculator", END)

    return builder.compile()

sports_analytical_graph = create_sports_graph()
