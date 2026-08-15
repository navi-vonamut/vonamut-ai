from fastapi import FastAPI, BackgroundTasks, Security, HTTPException, Depends
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
from playwright.async_api import async_playwright
import tempfile
import os
import asyncio
import logging
import uiautomator2 as u2

from utils.helpers import download_images, prepare_device, cleanup_device
from platforms.pinterest import publish_to_pinterest
from platforms.instagram import publish_to_instagram
from platforms.warmup import warmup_instagram

from platforms.instagram_twin import (
    scan_post_and_comments,
    interact_with_comment,
    follow_user_profile,
    send_direct_message,
    read_direct_messages,
    get_lead_latest_post_and_screenshot,
    publish_comment_to_post,
    check_profile_active_and_has_posts
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SMM_WORKER")

app = FastAPI(title="AstroGuido SMM Worker & Digital Twin")

# 🛡️ Настройка безопасности
API_KEY_NAME = "x-api-key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)
VALID_API_KEY = os.getenv("INTERNAL_API_KEY", "твой_дефолтный_ключ")
PHONE_IP = os.getenv("PHONE_IP", "192.168.100.87")

PROFILES_DIR = "/app/smm_worker/browser_profiles"
os.makedirs(PROFILES_DIR, exist_ok=True)

class PublishTask(BaseModel):
    platform: str        
    account_id: str      
    image_urls: list     
    title: str           
    description: str     
    link: str

class DMTask(BaseModel):
    username: str
    message: str

class ReplyCommentTask(BaseModel):
    comment_keyword: str
    reply_text: str = None
    action: str = "like"

class FollowTask(BaseModel):
    username: str

class PublishCommentTask(BaseModel):
    comment_text: str

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != VALID_API_KEY:
        logger.warning("🚨 Попытка несанкционированного доступа к SMM Worker!")
        raise HTTPException(status_code=403, detail="Доступ запрещен: Неверный API ключ")
    return api_key

def get_device():
    """Подключается к Android телефону по ADB IP."""
    return u2.connect(f"{PHONE_IP}:5555")

async def process_warmup():
    """Фоновая задача для воркера: будит телефон, греет Инсту и гасит экран"""
    logger.info(f"🔥 Запуск прогрева Instagram на устройстве {PHONE_IP}...")
    device = get_device()
    await prepare_device(device)
    try:
        await warmup_instagram(device, duration_minutes=3)
        logger.info("✅ Фоновый прогрев успешно завершен. Телефон спит.")
    except Exception as e:
        logger.error(f"❌ Ошибка во время прогрева на воркере: {e}")
    finally:
        await cleanup_device(device)        

async def process_publication(task: PublishTask):
    logger.info(f"🚀 Запуск задачи для {task.account_id} на платформе {task.platform}")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        local_image_paths = await download_images(task.image_urls, temp_dir)
        if not local_image_paths:
            logger.error("❌ Не удалось скачать картинки. Отмена публикации.")
            return

        # 🔀 МАРШРУТИЗАЦИЯ
        if task.platform == 'instagram':
            try:
                logger.info(f"🔌 Подключаемся к телефону {PHONE_IP} по Wi-Fi...")
                device = get_device()
                await publish_to_instagram(device, task, local_image_paths)
            except Exception as e:
                logger.error(f"❌ Сбой подключения к телефону: {e}")

        elif task.platform == 'pinterest':
            state_file = os.path.join(PROFILES_DIR, f"{task.account_id}_{task.platform}.json")
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
                
                if not os.path.exists(state_file):
                    logger.error(f"❌ Нет файла сессии {state_file}.")
                    await browser.close()
                    return
                
                context = await browser.new_context(storage_state=state_file)
                page = await context.new_page()
                
                await publish_to_pinterest(page, task, local_image_paths)
                
                await context.storage_state(path=state_file)
                await browser.close()

@app.post("/publish", dependencies=[Depends(verify_api_key)])
async def publish_post(task: PublishTask, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_publication, task)
    return {"status": "accepted", "message": f"Задача для {task.account_id} добавлена в очередь"}

@app.post("/warmup", dependencies=[Depends(verify_api_key)])
async def trigger_worker_warmup(background_tasks: BackgroundTasks):
    """Эндпоинт воркера для запуска прогрева"""
    background_tasks.add_task(process_warmup)
    return {"status": "accepted", "message": "Прогрев добавлен в очередь SMM Worker"}

# 🤖 ЭНДПОИНТЫ ЦИФРОВОГО ДВОЙНИКА (INSTAGRAM DIGITAL TWIN)

@app.post("/instagram/scan_feed", dependencies=[Depends(verify_api_key)])
async def scan_feed_endpoint(limit: int = 15, target_niche: str = None):
    """Считывает описание поста и комментарии целевой ниши или текущего экрана"""
    try:
        device = get_device()
        data = await scan_post_and_comments(device, limit=limit, target_niche=target_niche)
        return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"❌ Ошибка /instagram/scan_feed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/instagram/send_dm", dependencies=[Depends(verify_api_key)])
async def send_dm_endpoint(task: DMTask):
    """Отправляет личное сообщение пользователю в Direct"""
    try:
        device = get_device()
        success = await send_direct_message(device, task.username, task.message)
        return {"status": "success" if success else "failed", "username": task.username}
    except Exception as e:
        logger.error(f"❌ Ошибка /instagram/send_dm: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/instagram/reply_comment", dependencies=[Depends(verify_api_key)])
async def reply_comment_endpoint(task: ReplyCommentTask):
    """Отвечает на комментарий или лайкает его"""
    try:
        device = get_device()
        success = await interact_with_comment(device, task.comment_keyword, action=task.action, reply_text=task.reply_text)
        return {"status": "success" if success else "failed"}
    except Exception as e:
        logger.error(f"❌ Ошибка /instagram/reply_comment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/instagram/follow", dependencies=[Depends(verify_api_key)])
async def follow_endpoint(task: FollowTask):
    """Подписывается на пользователя"""
    try:
        device = get_device()
        success = await follow_user_profile(device, task.username)
        return {"status": "success" if success else "failed", "username": task.username}
    except Exception as e:
        logger.error(f"❌ Ошибка /instagram/follow: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/instagram/check_dms", dependencies=[Depends(verify_api_key)])
async def check_dms_endpoint():
    """Считывает входящие сообщения Direct"""
    try:
        device = get_device()
        messages = await read_direct_messages(device)
        return {"status": "success", "messages": messages}
    except Exception as e:
        logger.error(f"❌ Ошибка /instagram/check_dms: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_digital_twin_lead_cycle(limit: int = 15, target_niche: str = None):
    logger.info(f"🔄 Запуск автономного цикла Instagram Digital Twin (Ниша: {target_niche or 'по умолчанию'})...")
    try:
        device = get_device()
        scanned_data = await scan_post_and_comments(device, limit=limit, target_niche=target_niche)
        comments = scanned_data.get("comments", [])
        logger.info(f"📊 Отсканирован пост. Комментариев собрано: {len(comments)}")
        logger.info("✅ Автономный цикл взаимодействия Digital Twin завершен.")
        return scanned_data
    except Exception as e:
        logger.error(f"❌ Ошибка автономного цикла Digital Twin: {e}")
        return None

@app.post("/instagram/run_lead_cycle", dependencies=[Depends(verify_api_key)])
async def run_lead_cycle_endpoint(background_tasks: BackgroundTasks, limit: int = 15, target_niche: str = None):
    """Запускает фоновую процедуру автономного взаимодействия цифрового двойника по нише/хэштегу"""
    background_tasks.add_task(process_digital_twin_lead_cycle, limit, target_niche)
    return {"status": "accepted", "message": f"Цикл взаимодействия Digital Twin запущен в фоне (Ниша: {target_niche or 'по умолчанию'})"}

@app.post("/instagram/lead_post_screenshot", dependencies=[Depends(verify_api_key)])
async def lead_post_screenshot_endpoint(username: str):
    """Открывает свежий пост пользователя, забирает скриншот и текст поста"""
    try:
        device = get_device()
        data = await get_lead_latest_post_and_screenshot(device, username)
        return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"❌ Ошибка /instagram/lead_post_screenshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/instagram/publish_comment", dependencies=[Depends(verify_api_key)])
async def publish_comment_endpoint(task: PublishCommentTask):
    """Публикует комментарий под открытым постом лида"""
    try:
        device = get_device()
        success = await publish_comment_to_post(device, task.comment_text)
        return {"status": "success" if success else "failed"}
    except Exception as e:
        logger.error(f"❌ Ошибка /instagram/publish_comment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/instagram/check_profile", dependencies=[Depends(verify_api_key)])
async def check_profile_endpoint(username: str):
    """Проверяет профиль на активность, наличие постов и доступность"""
    try:
        device = get_device()
        data = await check_profile_active_and_has_posts(device, username)
        return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"❌ Ошибка /instagram/check_profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


