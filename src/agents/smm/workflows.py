import os
import json
import random
import string
import logging
import httpx
from typing import Dict, Any, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.core.schemas import SMMLead, LeadStatus, SocialNetwork
from src.services.directus_client import directus_client

logger = logging.getLogger("SMM_WORKFLOWS")

SMM_WORKER_URL = os.getenv("SMM_WORKER_URL", "http://astro_smm_worker:8000")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "твой_дефолтный_ключ")
WORKER_HEADERS = {
    "x-api-key": INTERNAL_API_KEY,
    "Content-Type": "application/json"
}

TAG_POOL = [
    "#психологияотношений",
    "#самопознание",
    "#астрология",
    "#осознанность",
    "#личностныйрост",
    "#духовноеразвитие"
]

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")

def _extract_text_content(content) -> str:
    if isinstance(content, str):
        return content.strip()
    elif isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text" and "text" in block:
                    parts.append(block["text"])
                elif "text" in block:
                    parts.append(block["text"])
        return "".join(parts).strip()
    return str(content).strip()

def _generate_promo_code(username: str) -> str:
    clean_user = "".join(filter(str.isalnum, username)).upper()[:4] or "LEAD"
    rand_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"IG-{clean_user}-{rand_suffix}"

def _generate_utm_link(source_tag: str, promo_code: str) -> str:
    clean_tag = source_tag.lstrip("#").strip()
    return f"https://astroguido.com/?utm_source=instagram&utm_medium=smm_agent&utm_campaign={clean_tag}&promo={promo_code}"


# =====================================================================
# 🚀 ФАЗА А: Поиск и касание (Directus Cron -> LangGraph)
# =====================================================================
async def run_phase_a_touch_workflow(source_tag: Optional[str] = None) -> Dict[str, Any]:
    """
    Алгоритм Фазы А:
    1. Берет тег из пула.
    2. Воркер находит топ-пост, собирает верхние 20 комментариев.
    3. LLM выбирает 1 лучшего комментатора (лида).
    4. Воркер подписывается на профиль лида и ставит лайк.
    5. Воркер делаем скриншот последнего поста лида + считывает текст.
    6. LLM (Vision + Text) генерирует комментарий по скриншоту и тексту.
    7. Воркер публикует комментарий под постом лида.
    8. LangGraph генерирует промокод/UTM и сохраняет строку в Directus (status: commented).
    """
    if not source_tag:
        source_tag = random.choice(TAG_POOL)

    logger.info(f"🚀 [Фаза А] Запуск поиска и касания по хэштегу: {source_tag}")
    
    async with httpx.AsyncClient(timeout=300.0) as http_client:
        # 1. Сканируем посты и комментарии воркером
        scan_url = f"{SMM_WORKER_URL}/instagram/scan_feed"
        try:
            scan_resp = await http_client.post(
                scan_url, 
                params={"limit": 20, "target_niche": source_tag}, 
                headers=WORKER_HEADERS
            )
            if scan_resp.status_code != 200:
                msg = f"❌ [Фаза А] Ошибка сканирования воркером: {scan_resp.status_code} - {scan_resp.text}"
                logger.error(msg)
                return {"status": "failed", "reason": msg}
            scanned_data = scan_resp.json().get("data", {})
        except Exception as scan_err:
            msg = f"❌ [Фаза А] Сбой соединения при сканировании: {scan_err}"
            logger.error(msg)
            return {"status": "failed", "reason": msg}
        comments = scanned_data.get("comments", [])
        caption = scanned_data.get("caption", "")

        logger.info(f"📊 [Фаза А] Считано описания: {caption[:100] if caption else '(без описания)'}")
        logger.info(f"📊 [Фаза А] Считано комментариев воркером ({len(comments)} шт): {json.dumps(comments, ensure_ascii=False)}")

        if not comments:
            msg = "⚠️ [Фаза А] Не найдено комментариев для анализа."
            logger.warning(msg)
            return {"status": "skipped", "reason": msg}

        # 2. Модель отбирает 3-5 лучших кандидатов в порядке приоритета
        select_prompt = f"""
        Проанализируй список комментариев к посту по теме '{source_tag}'.
        Описание поста: {caption}
        
        Список комментариев (каждый объект содержит поля 'author' и 'text'):
        {json.dumps(comments, ensure_ascii=False)}
        
        Выбери от 3 до 5 наиболее целевых и вовлеченных комментаторов (реальных пользователей) для первого касания с потенциальным клиентом AstroGuido.
        Отранжируй их по приоритету и качеству отзыва.
        
        Верни JSON строго формата:
        {{
            "candidates": [
                {{
                    "lead_username": "никнейм_из_поля_author",
                    "comment_text": "текст_выбранного_комментария",
                    "reason": "почему выбран этот комментарий"
                }}
            ]
        }}
        Отвечай ТОЛЬКО валидным JSON.
        """
        
        llm_resp = await llm.ainvoke([
            SystemMessage(content="Ты — эксперт по анализу социальных лидов и комьюнити-менеджменту."),
            HumanMessage(content=select_prompt)
        ])
        
        raw_json = _extract_text_content(llm_resp.content)
        logger.info(f"🤖 [Фаза А] Сырой ответ LLM отбора: {raw_json}")

        if "```json" in raw_json:
            raw_json = raw_json.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_json:
            raw_json = raw_json.split("```")[1].split("```")[0].strip()

        candidate_leads = []
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, list):
                raw_candidates = parsed
            else:
                raw_candidates = parsed.get("candidates", [])

            if isinstance(raw_candidates, list):
                for item in raw_candidates:
                    if isinstance(item, dict):
                        uname = item.get("lead_username", "").lstrip("@").strip()
                        c_text = item.get("comment_text", "")
                        c_reason = item.get("reason", "")
                    elif isinstance(item, str):
                        uname = item.lstrip("@").strip()
                        c_text = ""
                        c_reason = ""
                    else:
                        continue

                    if uname and uname not in ("active_user", "unknown_user", "instagram_user"):
                        candidate_leads.append({
                            "lead_username": uname,
                            "comment_text": c_text,
                            "reason": c_reason
                        })
        except Exception as parse_err:
            logger.warning(f"⚠️ Ошибка парсинга кандидатов от LLM: {parse_err}")

        # Дополняем резервными авторами из массива комментариев если списка недостаточно
        existing_names = {c["lead_username"] for c in candidate_leads}
        for c in comments:
            auth = c.get("author", "").lstrip("@").strip()
            if auth and auth not in ("active_user", "unknown_user", "instagram_user") and auth not in existing_names:
                existing_names.add(auth)
                candidate_leads.append({
                    "lead_username": auth,
                    "comment_text": c.get("text", ""),
                    "reason": "Резервный автор из комментариев"
                })
                if len(candidate_leads) >= 5:
                    break

        if not candidate_leads:
            msg = "⚠️ [Фаза А] Не найдено реальных аккаунтов пользователей в комментариях. Пропуск."
            logger.warning(msg)
            return {"status": "skipped", "reason": msg}

        logger.info(f"🎯 [Фаза А] Отбрано кандидатов для проверки: {[c['lead_username'] for c in candidate_leads]}")

        # 2.5. Перебираем кандидатов по очереди, пока не найдем активный/открытый профиль с постами
        chosen_lead = None
        for candidate in candidate_leads:
            cand_username = candidate["lead_username"]
            logger.info(f"🔎 [Фаза А] Проверяем кандидата @{cand_username}...")
            
            try:
                check_url = f"{SMM_WORKER_URL}/instagram/check_profile?username={cand_username}"
                check_resp = await http_client.post(check_url, headers=WORKER_HEADERS)
                if check_resp.status_code == 200:
                    p_data = check_resp.json().get("data", {})
                    if p_data.get("is_active"):
                        logger.info(f"✅ [Фаза А] Кандидат @{cand_username} прошел проверку! (Профиль открыт, посты есть)")
                        chosen_lead = candidate
                        break
                    else:
                        reason = p_data.get("reason", "Профиль пуст или недоступен")
                        logger.warning(f"⚠️ [Фаза А] Отклонен кандидат @{cand_username}: {reason}. Проверяем следующего...")
            except Exception as ch_err:
                logger.warning(f"⚠️ Ошибка проверки профиля @{cand_username}: {ch_err}")

        if not chosen_lead:
            msg = "⚠️ [Фаза А] Ни один из отобранных кандидатов не прошел проверку (все профили закрыты или пусты). Пропуск."
            logger.warning(msg)
            return {"status": "skipped", "reason": msg}

        lead_username = chosen_lead["lead_username"]
        logger.info(f"🚀 [Фаза А] Выбран активный лид для касания: @{lead_username}")

        # 3. Воркер подписывается на профиль и ставит лайк
        try:
            follow_url = f"{SMM_WORKER_URL}/instagram/follow"
            await http_client.post(follow_url, json={"username": lead_username}, headers=WORKER_HEADERS)
        except Exception as f_err:
            logger.warning(f"⚠️ Сбой при подписке на лида: {f_err}")

        # 4. Воркер делает скриншот последнего поста лида
        post_caption = ""
        screenshot_b64 = ""
        target_post_url = f"https://instagram.com/{lead_username}"
        
        try:
            ss_url = f"{SMM_WORKER_URL}/instagram/lead_post_screenshot?username={lead_username}"
            ss_resp = await http_client.post(ss_url, headers=WORKER_HEADERS)
            if ss_resp.status_code == 200:
                ss_data = ss_resp.json().get("data", {})
                post_caption = ss_data.get("caption", "")
                screenshot_b64 = ss_data.get("screenshot_base64", "")
                target_post_url = ss_data.get("target_post_url", target_post_url)
        except Exception as ss_err:
            logger.warning(f"⚠️ Сбой при получении скриншота поста лида: {ss_err}")

        # 5. Модель генерирует осознанный комментарий по картинке (если есть) + тексту
        comment_gen_prompt = f"""
        Ты — Цифровой Двойник AstroGuido (высокотехнологичный навигатор по астрологии и осознанности).
        Сгенерируй вежливый, осознанный и экспертный комментарий (1-2 предложения с эмодзи) к посту пользователя @{lead_username}.
        
        Описание поста лида: {post_caption or 'Визуальный пост в Instagram'}
        Контекст ниши: {source_tag}
        """

        message_content = [{"type": "text", "text": comment_gen_prompt}]
        if screenshot_b64:
            message_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{screenshot_b64}"}
            })

        comment_resp = await llm.ainvoke([HumanMessage(content=message_content)])
        our_comment = _extract_text_content(comment_resp.content)

        try:
            pub_url = f"{SMM_WORKER_URL}/instagram/publish_comment"
            await http_client.post(pub_url, json={"comment_text": our_comment}, headers=WORKER_HEADERS)
        except Exception as p_err:
            logger.warning(f"⚠️ Сбой при публикации комментария воркером: {p_err}")

        # 7. Запись лида в Directus (статус commented)
        promo_code = _generate_promo_code(lead_username)
        utm_link = _generate_utm_link(source_tag, promo_code)

        lead_schema = SMMLead(
            social_network=SocialNetwork.instagram,
            source_tag=source_tag,
            lead_username=lead_username,
            target_post_url=target_post_url,
            our_comment=our_comment,
            promo_code=promo_code,
            utm_link=utm_link,
            status=LeadStatus.commented
        )

        saved_lead = await directus_client.create_smm_lead(lead_schema)

        return {
            "status": "success",
            "lead_username": lead_username,
            "our_comment": our_comment,
            "promo_code": promo_code,
            "utm_link": utm_link,
            "directus_id": saved_lead.id if saved_lead else None
        }


# =====================================================================
# 📩 ФАЗА Б: Реакция на подписку (Телефон -> LangGraph)
# =====================================================================
async def run_phase_b_followback_workflow(username: str) -> Dict[str, Any]:
    """
    Алгоритм Фазы Б:
    1. Приложение на телефоне читает пуш о подписке -> дергает вебхук c username.
    2. Граф забирает контекст из Directus по username.
    3. Генерирует персональный Direct с учетом старого комментария и промокода.
    4. Воркер отправляет сообщение в Direct.
    5. Обновляется статус в Directus на dm_sent.
    """
    clean_user = username.lstrip("@").strip()
    logger.info(f"📩 [Фаза Б] Реакция на подписку пользователя @{clean_user}...")

    # 1. Забираем контекст из Directus
    lead = await directus_client.get_smm_lead_by_username(clean_user)
    
    prev_comment = lead.our_comment if lead else ""
    promo_code = lead.promo_code if lead else _generate_promo_code(clean_user)
    utm_link = lead.utm_link if lead else _generate_utm_link("#instagram", promo_code)

    # 2. Генерируем сообщение в Direct от Цифрового Двойника AstroGuido
    dm_prompt = f"""
    Пользователь @{clean_user} только что подписался на наш аккаунт в Instagram в ответ на наше касание!
    
    КОНТЕКСТ:
    - Наш прошлый комментарий под его постом: '{prev_comment or 'Очень интересный пост!'}'
    - Персональный промокод: {promo_code}
    - Ссылка для активации: {utm_link}
    
    Задача: Напиши теплое, вдохновляющее и не слишком навязчивое приветственное сообщение в Direct (3-4 предложения).
    Поблагодари за подписку, напомни о нашем проекте AstroGuido (космический тайминг и индивидуальный навигатор) и подари персональный промокод со ссылкой.
    """

    dm_resp = await llm.ainvoke([
        SystemMessage(content="Ты — Цифровой Двойник AstroGuido, общающийся в Direct с подписившимися пользователями."),
        HumanMessage(content=dm_prompt)
    ])
    
    dm_message = _extract_text_content(dm_resp.content)

    # 3. Воркер отправляет сообщение в Direct
    async with httpx.AsyncClient(timeout=120.0) as http_client:
        dm_url = f"{SMM_WORKER_URL}/instagram/send_dm"
        dm_worker_resp = await http_client.post(
            dm_url,
            json={"username": clean_user, "message": dm_message},
            headers=WORKER_HEADERS
        )

        send_success = dm_worker_resp.status_code == 200

    # 4. Обновляем статус в Directus
    if lead and lead.id:
        await directus_client.update_smm_lead_status(
            lead_id=lead.id,
            status=LeadStatus.dm_sent,
            dm_message=dm_message
        )

    return {
        "status": "success" if send_success else "partially_failed",
        "username": clean_user,
        "dm_message": dm_message,
        "dm_sent_worker": send_success
    }
