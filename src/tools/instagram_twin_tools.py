import os
import requests
import logging
from langchain_core.tools import tool

logger = logging.getLogger("INSTAGRAM_TWIN_TOOLS")

# Берем URL воркера из переменных окружения или дефолтный внутри докера
SMM_WORKER_URL = os.getenv("SMM_WORKER_URL", "http://astro_smm_worker:8000")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "твой_дефолтный_ключ")

HEADERS = {
    "x-api-key": INTERNAL_API_KEY,
    "Content-Type": "application/json"
}

@tool
def scan_instagram_leads(limit: int = 15, target_niche: str = None) -> str:
    """
    ОСНОВНОЙ ИНСТРУМЕНТ ДЛЯ ОТВЕТА ПОЛЬЗОВАТЕЛЮ В ЧАТЕ.
    Сканирует посты и комментарии в Instagram на подключенном устройстве и ВОЗВРАЩАЕТ тексты найденных комментариев Агенту для анализа и отображения в чате.
    Обязательно передавай target_niche (например '#астрология', '#гороскоп' или '@конкурент'), чтобы зайти в целевую нишу и вытащить свежие комментарии из популярных постов.
    """
    try:
        url = f"{SMM_WORKER_URL}/instagram/scan_feed?limit={limit}"
        if target_niche:
            url += f"&target_niche={requests.utils.quote(target_niche)}"
        res = requests.post(url, headers=HEADERS, timeout=150)
        if res.status_code == 200:
            data = res.json().get("data", {})
            return f"✅ Успешно собраны данные по постам/комментариям в нише '{target_niche or 'текущий экран'}':\n{data}"
        else:
            return f"❌ Ошибка воркера SMM: HTTP {res.status_code} - {res.text}"
    except Exception as e:
        return f"❌ Сбой обращения к SMM Worker: {e}"

@tool
def send_instagram_dm(username: str, message: str) -> str:
    """
    Отправляет личное сообщение пользователю username в Instagram Direct.
    """
    try:
        payload = {"username": username, "message": message}
        res = requests.post(f"{SMM_WORKER_URL}/instagram/send_dm", json=payload, headers=HEADERS, timeout=150)
        if res.status_code == 200:
            return f"🚀 Сообщение пользователю @{username} успешно отправлено!"
        else:
            return f"❌ Ошибка отправки DM: HTTP {res.status_code} - {res.text}"
    except Exception as e:
        return f"❌ Сбой отправки DM: {e}"

@tool
def reply_instagram_comment(comment_keyword: str, reply_text: str = None, action: str = "like") -> str:
    """
    Находит комментарий по ключевым словам и ставит лайк или пишет ответ.
    """
    try:
        payload = {"comment_keyword": comment_keyword, "reply_text": reply_text, "action": action}
        res = requests.post(f"{SMM_WORKER_URL}/instagram/reply_comment", json=payload, headers=HEADERS, timeout=150)
        if res.status_code == 200:
            return f"✅ Действие '{action}' по комментарию '{comment_keyword}' выполнено!"
        else:
            return f"❌ Ошибка ответа на комментарий: HTTP {res.status_code} - {res.text}"
    except Exception as e:
        return f"❌ Сбой вызова reply_comment: {e}"

@tool
def follow_instagram_user(username: str) -> str:
    """
    Подписывается на пользователя username в Instagram и прогревает его профиль (ставит лайк на свежую публикацию).
    """
    try:
        payload = {"username": username}
        res = requests.post(f"{SMM_WORKER_URL}/instagram/follow", json=payload, headers=HEADERS, timeout=150)
        if res.status_code == 200:
            return f"➕ Успешная подписка и лайк на посты пользователя @{username}!"
        else:
            return f"❌ Ошибка подписки: HTTP {res.status_code} - {res.text}"
    except Exception as e:
        return f"❌ Сбой выполнения подписки: {e}"

@tool
def run_digital_twin_lead_cycle(limit: int = 15, target_niche: str = None) -> str:
    """
    ИСПОЛЬЗУЕТСЯ ТОЛЬКО ДЛЯ АВТОНОМНОГО КРОНА (Directus Cron). НЕ вызывай в обычном разговоре в чате!
    Запускает асинхронную фоновую задачу разблокировки телефона и сканирования без показа промежуточных комментариев в текущий сеанс чата.
    """
    try:
        url = f"{SMM_WORKER_URL}/instagram/run_lead_cycle?limit={limit}"
        if target_niche:
            url += f"&target_niche={requests.utils.quote(target_niche)}"
        res = requests.post(url, headers=HEADERS, timeout=150)
        if res.status_code == 200:
            return f"🔄 Автономный фоновый цикл Digital Twin по нише '{target_niche or 'по умолчанию'}' успешно запущен в фоне на устройстве!"

        else:
            return f"❌ Ошибка запуска цикла: HTTP {res.status_code} - {res.text}"
    except Exception as e:
        return f"❌ Сбой вызова автономного цикла: {e}"


@tool
def get_lead_post_screenshot(username: str) -> str:
    """
    Открывает свежий пост пользователя username, снимает скриншот и считывает описание.
    """
    try:
        url = f"{SMM_WORKER_URL}/instagram/lead_post_screenshot?username={requests.utils.quote(username)}"
        res = requests.post(url, headers=HEADERS, timeout=150)
        if res.status_code == 200:
            return f"✅ Скриншот поста лида @{username} получен!"
        else:
            return f"❌ Ошибка получения скриншота поста: HTTP {res.status_code} - {res.text}"
    except Exception as e:
        return f"❌ Сбой получения скриншота поста: {e}"

@tool
def publish_post_comment(comment_text: str) -> str:
    """
    Публикует комментарий под открытым постом лида.
    """
    try:
        payload = {"comment_text": comment_text}
        res = requests.post(f"{SMM_WORKER_URL}/instagram/publish_comment", json=payload, headers=HEADERS, timeout=150)
        if res.status_code == 200:
            return "✅ Комментарий к посту лида успешно опубликован!"
        else:
            return f"❌ Ошибка публикации комментария: HTTP {res.status_code} - {res.text}"
    except Exception as e:
        return f"❌ Сбой публикации комментария: {e}"


twin_tools = [
    scan_instagram_leads, 
    send_instagram_dm, 
    reply_instagram_comment, 
    follow_instagram_user, 
    run_digital_twin_lead_cycle,
    get_lead_post_screenshot,
    publish_post_comment
]


