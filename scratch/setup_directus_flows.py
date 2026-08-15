import os
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SETUP_DIRECTUS_FLOWS")

DIRECTUS_URL = os.getenv("DIRECTUS_URL", "http://directus:8055").rstrip("/")
TOKEN = os.getenv("DIRECTUS_STATIC_TOKEN", "astroguido-admin-token-2026")
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

def create_manual_flow():
    """Создает ручной триггер в панели Directus для запуска Фазы А по кнопке."""
    url = f"{DIRECTUS_URL}/flows"
    
    # Проверяем существующие потоки
    res = httpx.get(url, headers=HEADERS)
    if res.status_code == 200:
        flows = res.json().get("data", [])
        for f in flows:
            if f.get("name") == "🚀 Ручной поиск лидов SMM (Фаза А)":
                logger.info(f"ℹ️ Ручной поток уже существует! ID: {f['id']}")
                return f["id"]

    flow_payload = {
        "name": "🚀 Ручной поиск лидов SMM (Фаза А)",
        "icon": "auto_awesome",
        "color": "#6366F1",
        "status": "active",
        "trigger": "manual",
        "options": {
            "collections": ["smm_leads"],
            "location": "collection",
            "asynchronous": False
        }
    }
    
    resp = httpx.post(url, json=flow_payload, headers=HEADERS)
    if resp.status_code in (200, 201):
        flow_id = resp.json()["data"]["id"]
        logger.info(f"✅ Ручной поток успешно создан! ID: {flow_id}")
        
        # Добавляем операцию Webhook запроса к нашему приложению
        op_url = f"{DIRECTUS_URL}/operations"
        op_payload = {
            "flow": flow_id,
            "name": "Вызов эндпоинта Фазы А",
            "key": "trigger_phase_a_webhook",
            "type": "request",
            "position_x": 1,
            "position_y": 1,
            "options": {
                "method": "POST",
                "url": "http://app:8000/api/smm/phase_a_cron",
                "headers": [
                    {"header": "Content-Type", "value": "application/json"}
                ],
                "body": '{\n  "source_tag": "#психологияотношений"\n}'
            }
        }
        op_resp = httpx.post(op_url, json=op_payload, headers=HEADERS)
        if op_resp.status_code in (200, 201):
            logger.info("✅ Операция Webhook вызова успешно привязана к кнопке!")
        else:
            logger.error(f"❌ Ошибка создания операции: {op_resp.status_code} - {op_resp.text}")
        return flow_id
    else:
        logger.error(f"❌ Ошибка создания потока: {resp.status_code} - {resp.text}")
        return None


def create_cron_flow():
    """Создает регулярную Cron-задачу в панели Directus для автозапуска Фазы А."""
    url = f"{DIRECTUS_URL}/flows"
    
    res = httpx.get(url, headers=HEADERS)
    if res.status_code == 200:
        flows = res.json().get("data", [])
        for f in flows:
            if f.get("name") == "⏰ Авто-расписание SMM (Фаза А Cron)":
                logger.info(f"ℹ️ Cron поток уже существует! ID: {f['id']}")
                return f["id"]

    flow_payload = {
        "name": "⏰ Авто-расписание SMM (Фаза А Cron)",
        "icon": "schedule",
        "color": "#10B981",
        "status": "active",
        "trigger": "schedule",
        "options": {
            "cron": "0 */2 * * *"  # Каждые 2 часа
        }
    }
    
    resp = httpx.post(url, json=flow_payload, headers=HEADERS)
    if resp.status_code in (200, 201):
        flow_id = resp.json()["data"]["id"]
        logger.info(f"✅ Cron поток успешно создан! ID: {flow_id}")
        
        op_url = f"{DIRECTUS_URL}/operations"
        op_payload = {
            "flow": flow_id,
            "name": "Авто-вызов эндпоинта Фазы А по расписанию",
            "key": "cron_phase_a_webhook",
            "type": "request",
            "position_x": 1,
            "position_y": 1,
            "options": {
                "method": "POST",
                "url": "http://app:8000/api/smm/phase_a_cron",
                "headers": [
                    {"header": "Content-Type", "value": "application/json"}
                ],
                "body": "{}"
            }
        }
        op_resp = httpx.post(op_url, json=op_payload, headers=HEADERS)
        if op_resp.status_code in (200, 201):
            logger.info("✅ Операция Webhook привязана к Cron-расписанию!")
        else:
            logger.error(f"❌ Ошибка создания операции Cron: {op_resp.status_code} - {op_resp.text}")
        return flow_id
    else:
        logger.error(f"❌ Ошибка создания Cron потока: {resp.status_code} - {resp.text}")
        return None

if __name__ == "__main__":
    logger.info("🔧 Создание Автоматизаций (Flows) в Directus...")
    create_manual_flow()
    create_cron_flow()
