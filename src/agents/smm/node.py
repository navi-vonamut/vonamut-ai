from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from src.tools.browser import browser_tools 
from src.tools.trends import trend_tools
from src.tools.image_gen import image_tools
from src.tools.db_tools import db_tools
from src.tools.instagram_twin_tools import twin_tools
import chainlit as cl

all_smm_tools = browser_tools + trend_tools + image_tools + db_tools + twin_tools

# Привязываем все инструменты к Gemini
llm_with_tools = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite").bind_tools(all_smm_tools)

PROJECT_MANIFESTS = {
    "AstroGuido": """
    МИССИЯ ПРОЕКТА: AstroGuido — это высокотехнологичный навигатор по звездам. 
    Мы объединяем древнюю мудрость астрологии с точностью алгоритмов и AI. 
    НАШ ПОСЫЛ: Астрология — это не магия и не гадания. Это 'Космический тайминг', система координат для осознанных людей, предпринимателей и новаторов.
    СТИЛЬ (Tone of Voice): Экспертный, вдохновляющий, современный (Cyber-Zen). Никакой эзотерической 'воды', только четкие инсайты.
    ВИЗУАЛ: Минимализм, неоновые акценты, голограммы, эстетика будущего в сочетании с космосом.
    """,
    "default_project": "Действуй как стандартный креативный SMM-специалист."
}

async def smm_node(state):
    messages = state['messages']
    current_project = state.get("project_id", "AstroGuido") 
    brand_guidelines = PROJECT_MANIFESTS.get(current_project, PROJECT_MANIFESTS["default_project"])
    
    system_prompt = SystemMessage(content=f"""
    Ты — Senior SMM-Менеджер, Цифровой Двойник и Контент-Креатор проекта {current_project}.

    ТВОЯ МИССИЯ И СТИЛЬ:
    {brand_guidelines}

    ПРАВИЛА ИСПОЛЬЗОВАНИЯ ИНСТРУМЕНТОВ:
    - У тебя есть ПОЛНЫЙ доступ к инструментам: генерация изображений, сохранение постов в БД, поиск трендов, а также Instagram Digital Twin (сканирование ленты/комментариев, отправка сообщения в Direct, подписка, ответы на комментарии, запуск автономного цикла).
    - Если пользователь просит просканировать Instagram, найти лидов, отправить сообщение или запустить инструмент — вызови инструмент (например 'scan_instagram_leads' с параметром target_niche).
    - После получения результатов работы инструмента обязательно ПРОАНАЛИЗИРУЙ их и дай пользователю развернутый, понятный и красивый отчет в чате. Не оставляй ответ пустым!
    """)
    
    current_messages = [system_prompt] + messages
    
    step_exec = cl.Step(name="SMM-Отдел выполняет задачу...", type="run")
    await step_exec.send()
    
    response = await llm_with_tools.ainvoke(current_messages)
    step_count = 0
    max_steps = 5
    
    while response.tool_calls and step_count < max_steps:
        current_messages.append(response)
        
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            action = next((t for t in all_smm_tools if t.name == tool_name), None)
            
            step_tool = cl.Step(name=f"Инструмент маркетинга: {tool_name}", type="tool")
            step_tool.input = str(tool_args)
            await step_tool.send()
            
            if action:
                try:
                    result = action.invoke(tool_args)
                except Exception as e:
                    result = f"Ошибка инструмента: {e}"
            else:
                result = "Инструмент не найден."
                
            step_tool.output = str(result)
            await step_tool.update()
            
            current_messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"], name=tool_name))
            
        response = await llm_with_tools.ainvoke(current_messages)
        step_count += 1
        
    step_exec.output = "Задача SMM-отдела выполнена."
    await step_exec.update()

    raw_content = response.content
    if isinstance(raw_content, list):
        text_parts = []
        for block in raw_content:
            if isinstance(block, dict):
                text_parts.append(block.get('text', ''))
            elif isinstance(block, str):
                text_parts.append(block)
        text_only = "".join(text_parts)
    else:
        text_only = str(raw_content)

    if not text_only.strip():
        text_only = "✅ Операция в Instagram успешно выполнена! Данные собраны и обработаны."

    response.content = f"📸 **SMM-Отдел:**\n\n{text_only}"
    return {
        "messages": [response], 
        "next_node": "END", 
        "is_approved": True
    }