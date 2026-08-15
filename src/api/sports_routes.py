import logging
import asyncio
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.sports.ingestion.odds_worker import OddsIngestionWorker
from src.sports.rag.qdrant_sports_manager import get_qdrant_sports_manager
from src.sports.agent.graph import sports_analytical_graph
from src.sports.telegram.bot import get_sports_telegram_bot
from src.db.base import SessionLocal
from src.db.models import SportsMatch, SportsOdds, SportsBet

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sports", tags=["Sports Analytics Agent"])

class InsiderIngestRequest(BaseModel):
    text: str
    source: str = "@sports_insider"
    team1: str
    team2: str

class ManualAnalysisRequest(BaseModel):
    match_id: str

@router.get("/matches")
async def get_matches():
    """
    Получение списка текущих матчей из базы данных (0 внешних запросов к API).
    """
    worker = OddsIngestionWorker()
    matches = worker.get_cached_matches()
    return {
        "status": "success",
        "count": len(matches),
        "matches": matches
    }

@router.post("/sync-odds")
async def sync_odds(force: bool = Query(False)):
    """
    Запуск скачивания расписания и коэффициентов Pinnacle через The-Odds-API.
    Параметр force=True форсирует реальный внешний HTTP-запрос к API.
    """
    worker = OddsIngestionWorker()
    matches = await worker.fetch_and_store_odds(force=force)
    return {
        "status": "success",
        "ingested_matches_count": len(matches),
        "matches": matches
    }

@router.post("/ingest-insider")
async def ingest_insider(req: InsiderIngestRequest):
    """
    Добавление инсайда вручную или через вебхук в векторную базу Qdrant (sports_context_24h).
    """
    qdrant_mgr = get_qdrant_sports_manager()
    success = qdrant_mgr.add_insider_post({
        "text": req.text,
        "source": req.source,
        "team1": req.team1,
        "team2": req.team2
    })
    return {
        "status": "success" if success else "duplicate_or_error",
        "team1": req.team1,
        "team2": req.team2
    }

@router.post("/analyze")
async def analyze_match(req: ManualAnalysisRequest):
    """
    Запуск 3-узлового LangGraph графа анализа матча на перевес (Value Betting).
    """
    db: Session = SessionLocal()
    try:
        match_obj = db.query(SportsMatch).filter_by(match_id=req.match_id).first()
        if not match_obj:
            raise HTTPException(status_code=404, detail=f"Match with ID '{req.match_id}' not found.")

        team1 = match_obj.team1
        team2 = match_obj.team2
        league = match_obj.league
        commence_time = match_obj.commence_time.isoformat()
    finally:
        db.close()

    initial_state = {
        "match_id": req.match_id,
        "league": league,
        "team1": team1,
        "team2": team2,
        "commence_time": commence_time,
        "odds_team1": 2.0,
        "odds_draw": None,
        "odds_team2": 2.0,
        "insider_context": [],
        "context_text": "",
        "ai_prob_team1": 0.33,
        "ai_prob_draw": None,
        "ai_prob_team2": 0.33,
        "ai_reasoning": "",
        "is_value_bet": False,
        "best_outcome": None,
        "selected_team": None,
        "selected_odds": None,
        "selected_prob": None,
        "value_percentage": None,
        "bet_record_id": None
    }

    final_state = await sports_analytical_graph.ainvoke(initial_state)

    # Если найден валуй — отправляем алерты в Telegram
    if final_state.get("is_value_bet"):
        sports_bot = get_sports_telegram_bot()
        await sports_bot.send_value_bet_signal(final_state)

    return {
        "status": "completed",
        "match": f"{team1} vs {team2}",
        "is_value_bet": final_state.get("is_value_bet"),
        "best_outcome": final_state.get("best_outcome"),
        "odds": final_state.get("selected_odds"),
        "ai_probability": final_state.get("selected_prob"),
        "value_percentage": final_state.get("value_percentage"),
        "ai_reasoning": final_state.get("ai_reasoning")
    }

@router.get("/bets")
async def get_bets(status: Optional[str] = None):
    """
    Получение списка найденных валуев и истории решений пользователя.
    """
    db: Session = SessionLocal()
    try:
        query = db.query(SportsBet)
        if status:
            query = query.filter_by(user_action=status.upper())
        bets = query.order_by(SportsBet.created_at.desc()).all()
        
        res = []
        for b in bets:
            res.append({
                "id": b.id,
                "match_id": b.match_id,
                "league": b.league,
                "match": f"{b.team1} vs {b.team2}",
                "bet_target": b.bet_target,
                "odds": b.bookmaker_odds,
                "ai_probability": b.ai_probability,
                "value_percentage": b.value_percentage,
                "ai_reasoning": b.ai_reasoning,
                "user_action": b.user_action,
                "created_at": b.created_at.isoformat()
            })
        return {"count": len(res), "bets": res}
    finally:
        db.close()
