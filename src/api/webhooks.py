import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from src.agents.smm.workflows import run_phase_a_touch_workflow, run_phase_b_followback_workflow

logger = logging.getLogger("WEBHOOKS_API")
router = APIRouter(prefix="/api", tags=["SMM Automation & Webhooks"])

class CronPhaseARequest(BaseModel):
    source_tag: Optional[str] = Field(default=None, description="Тег для поиска постов, например #психологияотношений")

class FollowWebhookRequest(BaseModel):
    username: str = Field(..., description="Никнейм пользователя, который подписался")
    social_network: Optional[str] = Field(default="instagram", description="Социальная сеть")

@router.post("/smm/phase_a_cron")
async def trigger_phase_a_cron(background_tasks: BackgroundTasks, payload: Optional[CronPhaseARequest] = None):
    """
    Эндпоинт для вызова Cron (Directus Cron / Flow).
    Запускает Фазу А (Поиск и касание по целевому тегу) в фоновом режиме.
    """
    source_tag = payload.source_tag if payload else None
    logger.info(f"⏰ Триггер Cron Фазы А (Тег: {source_tag or 'случайный'})...")
    
    try:
        background_tasks.add_task(run_phase_a_touch_workflow, source_tag)
        return {
            "status": "accepted",
            "message": f"Фаза А успешно запущена в фоне (Тег: {source_tag or 'случайный'})"
        }
    except Exception as e:
        logger.error(f"❌ Ошибка вызова Фазы А: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhooks/instagram_follow")
async def handle_instagram_follow_webhook(payload: FollowWebhookRequest, background_tasks: BackgroundTasks):
    """
    Вебхук для мобильного приложения (Tasker / MacroDroid).
    Принимает пуш о новой подписке и запускает Фазу Б в фоне.
    """
    logger.info(f"📲 Получен вебхук о подписке от пользователя: @{payload.username}")
    
    try:
        background_tasks.add_task(run_phase_b_followback_workflow, payload.username)
        return {
            "status": "success",
            "message": f"Фаза Б успешно запущена в фоне для пользователя @{payload.username}"
        }
    except Exception as e:
        logger.error(f"❌ Ошибка обработки вебхука подписки: {e}")
        raise HTTPException(status_code=500, detail=str(e))
