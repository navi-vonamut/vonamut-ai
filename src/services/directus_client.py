import os
import logging
import httpx
from typing import Optional, Dict, Any
from src.core.schemas import SMMLead, LeadStatus

logger = logging.getLogger("DIRECTUS_CLIENT")

DIRECTUS_URL = os.getenv("DIRECTUS_URL", "http://directus:8055").rstrip("/")
DIRECTUS_ADMIN_EMAIL = os.getenv("DIRECTUS_ADMIN_EMAIL", "admin@astroguido.com")
DIRECTUS_ADMIN_PASSWORD = os.getenv("DIRECTUS_ADMIN_PASSWORD", "super_secure_password_here")
DIRECTUS_STATIC_TOKEN = os.getenv("DIRECTUS_STATIC_TOKEN", "astroguido-admin-token-2026")

class DirectusClient:
    """Сервис для интеграции с коллекциями Directus REST API."""
    
    def __init__(self):
        self.base_url = DIRECTUS_URL
        self.access_token: Optional[str] = DIRECTUS_STATIC_TOKEN or None

    async def _get_auth_headers(self) -> Dict[str, str]:
        """Возвращает заголовки авторизации. Если токена нет — выполняем вход."""
        headers = {"Content-Type": "application/json"}
        if not self.access_token and DIRECTUS_ADMIN_EMAIL and DIRECTUS_ADMIN_PASSWORD:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"{self.base_url}/auth/login",
                        json={"email": DIRECTUS_ADMIN_EMAIL, "password": DIRECTUS_ADMIN_PASSWORD},
                        timeout=10.0
                    )
                    if resp.status_code == 200:
                        data = resp.json().get("data", {})
                        self.access_token = data.get("access_token")
                        logger.info("🔑 Успешная аутентификация в Directus API")
            except Exception as e:
                logger.error(f"⚠️ Не удалось войти в Directus: {e}")

        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    async def create_smm_lead(self, lead: SMMLead) -> Optional[SMMLead]:
        """Создает новую запись лида в коллекции smm_lead в Directus."""
        url = f"{self.base_url}/items/smm_leads"
        headers = await self._get_auth_headers()
        
        payload = lead.model_dump(exclude_none=True)
        # Приводим Enum к строкам для JSON API
        if "social_network" in payload and hasattr(payload["social_network"], "value"):
            payload["social_network"] = payload["social_network"].value
        if "status" in payload and hasattr(payload["status"], "value"):
            payload["status"] = payload["status"].value
            
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(url, json=payload, headers=headers, timeout=15.0)
                if res.status_code in (200, 201):
                    data = res.json().get("data", {})
                    logger.info(f"✅ Лид @{lead.lead_username} успешно сохранен в Directus! ID: {data.get('id')}")
                    return SMMLead(**data)
                else:
                    logger.error(f"❌ Ошибка создания лида в Directus: {res.status_code} - {res.text}")
                    return None
        except Exception as e:
            logger.error(f"❌ Сбой обращения к Directus API (create_smm_lead): {e}")
            return None

    async def get_smm_lead_by_username(self, username: str) -> Optional[SMMLead]:
        """Получает данные лида из коллекции smm_lead по его никнейму."""
        clean_user = username.lstrip("@").strip()
        url = f"{self.base_url}/items/smm_leads?filter[lead_username][_eq]={clean_user}&sort=-id&limit=1"
        headers = await self._get_auth_headers()
        
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(url, headers=headers, timeout=15.0)
                if res.status_code == 200:
                    items = res.json().get("data", [])
                    if items:
                        return SMMLead(**items[0])
                    logger.info(f"ℹ️ Лид @{clean_user} не найден в Directus.")
                    return None
                else:
                    logger.error(f"❌ Ошибка запроса лида в Directus: {res.status_code} - {res.text}")
                    return None
        except Exception as e:
            logger.error(f"❌ Сбой обращения к Directus API (get_smm_lead_by_username): {e}")
            return None

    async def update_smm_lead_status(
        self, 
        lead_id: str, 
        status: LeadStatus, 
        dm_message: Optional[str] = None
    ) -> bool:
        """Обновляет статус и текст отправленного Direct для записи в Directus."""
        url = f"{self.base_url}/items/smm_leads/{lead_id}"
        headers = await self._get_auth_headers()
        
        payload: Dict[str, Any] = {"status": status.value if hasattr(status, "value") else str(status)}
        if dm_message:
            payload["dm_message"] = dm_message
            
        try:
            async with httpx.AsyncClient() as client:
                res = await client.patch(url, json=payload, headers=headers, timeout=15.0)
                if res.status_code == 200:
                    logger.info(f"✅ Статус лида ID {lead_id} успешно обновлен на {status}!")
                    return True
                else:
                    logger.error(f"❌ Ошибка обновления лида {lead_id} в Directus: {res.status_code} - {res.text}")
                    return False
        except Exception as e:
            logger.error(f"❌ Сбой обращения к Directus API (update_smm_lead_status): {e}")
            return False

directus_client = DirectusClient()
