import json
import logging
from typing import List, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from sqlalchemy.orm import Session
from src.db.models import InstagramLead, InstagramConversation
from src.db.tools_helpers import get_db_session  # or standard SessionLocal

logger = logging.getLogger("DIGITAL_TWIN_AI")

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")

TWIN_SYSTEM_PROMPT = """
Ты — Цифровой Двойник и главный эксперт проекта AstroGuido (высокотехнологичный навигатор по астрологии, космическому таймингу и личному росту).

ТВОЯ МИССИЯ:
Общаться с потенциальными клиентами и аудиторией в Instagram так, как будто это пишет живой автор проекта.
- Тон (Tone of Voice): Экспертный, современный, дружелюбный, увлеченный. Без 'эзотерической воды', с фокусом на практическую пользу и инсайты.
- Цель общения: Выстроить доверие, ответить на вопросы пользователя, аккуратно предложить индивидуальный разбор/консультацию или ссылку на продукт.

ПРАВИЛА ОТВЕТОВ:
1. Пиши кратко, емко и вежливо (от 1 до 3 предложений для комментариев, до 4-5 предложений в Direct).
2. Используй эмодзи для передачи эмоций ✨.
3. Не будь навязчивым продавцом, предлагай польщу через диалог.
"""

async def analyze_and_extract_leads(caption: str, comments: List[Dict[str, Any]], db_session: Session) -> List[Dict[str, Any]]:
    """
    Анализирует список комментариев с помощью LLM, выявляет потенциальных клиентов (лидов),
    оценивает их намерение (intent_score: HIGH, MEDIUM, LOW) и сохраняет в БД.
    """
    if not comments:
        return []

    prompt = f"""
    Проанализируй пост и комментарии ниже. Твоя задача — найти комментарии пользователей, демонстрирующих интерес к услугам, вопросам или темам поста.
    
    ПОСТ: {caption}
    
    КОММЕНТАРИИ:
    {json.dumps(comments, ensure_ascii=False)}
    
    Верни JSON-массив с выявленными потенциальными лидами формата:
    [
      {{
        "text": "текст комментария",
        "intent_score": "HIGH/MEDIUM/LOW",
        "interests": "в чем именно заинтересован пользователь",
        "suggested_action": "reply_comment/send_dm/like"
      }}
    ]
    Отвечай ТОЛЬКО валидным JSON без дополнительных текстов.
    """
    
    try:
        response = await llm.ainvoke([SystemMessage(content="Ты — аналитик данных и специалист по социальным лидам."), HumanMessage(content=prompt)])
        raw = response.content.strip()
        if raw.startswith("```json"):
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif raw.startswith("```"):
            raw = raw.split("```")[1].split("```")[0].strip()
            
        leads_data = json.loads(raw)
        
        saved_leads = []
        for lead in leads_data:
            lead_text = lead.get("text", "")
            # Ищем или создаем лида в БД
            new_lead = InstagramLead(
                username=f"user_{hash(lead_text) % 10000}", # временно по хэшу текста, пока не распарсен exact username
                intent_score=lead.get("intent_score", "MEDIUM"),
                interests=lead.get("interests", ""),
                status="NEW",
                last_comment=lead_text
            )
            db_session.add(new_lead)
            saved_leads.append(lead)
            
        db_session.commit()
        logger.info(f"🎯 Выявлено и сохранено {len(saved_leads)} потенциальных лидов!")
        return saved_leads
    except Exception as e:
        logger.error(f"❌ Ошибка анализа лидов через LLM: {e}")
        return []

async def generate_dm_response(username: str, user_message: str, db_session: Session) -> str:
    """
    Генерирует персональный ответ в Direct с учетом истории диалога.
    """
    # Загружаем предыдущие сообщения
    history = db_session.query(InstagramConversation).filter_by(username=username).order_by(InstagramConversation.timestamp.asc()).all()
    
    conversation_context = ""
    for msg in history[-6:]:
        role_label = "Клиент" if msg.role == "user" else "Цифровой Двойник"
        conversation_context += f"{role_label}: {msg.message_text}\n"
        
    prompt = f"""
    ИСТОРИЯ ДИАЛОГА С @{username}:
    {conversation_context}
    
    НОВОЕ СООБЩЕНИЕ ОТ КЛИЕНТА:
    {user_message}
    
    Сгенерируй ответ от лица Цифрового Двойника AstroGuido.
    """
    
    response = await llm.ainvoke([SystemMessage(content=TWIN_SYSTEM_PROMPT), HumanMessage(content=prompt)])
    reply_text = response.content.strip()
    
    # Сохраняем в историю диалогов
    db_session.add(InstagramConversation(username=username, role="user", message_text=user_message))
    db_session.add(InstagramConversation(username=username, role="twin", message_text=reply_text))
    db_session.commit()
    
    return reply_text
