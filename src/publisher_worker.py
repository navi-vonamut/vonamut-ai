import time
import requests
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.db.models import Post
from playwright.sync_api import sync_playwright
import os

# Конфиг
DB_URL = os.environ.get("ASTRO_DB_URL")
DOLPHIN_API = "http://host.docker.internal:3001"
# Маппинг: Регион -> ID профиля Dolphin (вставь свои ID сюда)
PROFILE_MAPPING = {
    "RU": "12345678", 
    "EN": "87654321",
    "ES": "11223344",
    "PT": "55667788"
}

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)

def check_and_publish():
    db = SessionLocal()
    now = datetime.datetime.utcnow()
    
    # Ищем посты: Одобренные, не опубликованные, время которых настало
    posts = db.query(Post).filter(
        Post.status == 'APPROVED', 
        Post.scheduled_at <= now
    ).all()

    for post in posts:
        print(f"🚀 Пора публиковать пост ID {post.id} для {post.region}")
        profile_id = PROFILE_MAPPING.get(post.region)
        
        if publish_via_dolphin(profile_id, post):
            post.status = 'PUBLISHED'
            db.commit()
            print(f"✅ Пост {post.id} успешно опубликован!")
            
    db.close()

def publish_via_dolphin(profile_id, post):
    try:
        # 1. Стартуем профиль
        start_resp = requests.get(f"{DOLPHIN_API}/v1.0/browser_ms/profiles/{profile_id}/start?automation=1").json()
        port = start_resp['automation']['port']

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://host.docker.internal:{port}")
            context = browser.contexts[0]
            page = context.pages[0]
            
            # 2. Логика публикации (концепт)
            page.goto("https://www.instagram.com/")
            # Здесь мы добавим логику кликов по кнопкам "Создать" -> "Загрузить"
            # Используем post.content и post.image_url
            
            time.sleep(5) # Ждем имитацию
            browser.close()
            
        # 3. Стопаем профиль
        requests.get(f"{DOLPHIN_API}/v1.0/browser_ms/profiles/{profile_id}/stop")
        return True
    except Exception as e:
        print(f"❌ Ошибка публикации: {e}")
        return False

if __name__ == "__main__":
    while True:
        check_and_publish()
        time.sleep(300) # Проверка каждые 5 минут