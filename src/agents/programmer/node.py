from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from src.core.memory import get_memory_store
from src.core.ui_utils import SafeStep

# Импорты инструментов работы с файлами и терминалом
from src.tools.file_system import file_tools 
from src.tools.terminal import terminal_tools

all_tools = file_tools + terminal_tools
llm_with_tools = ChatGoogleGenerativeAI(model="gemma-4-31b-it").bind_tools(all_tools)
llm_pure = ChatGoogleGenerativeAI(model="gemma-4-31b-it")

async def programmer_node(state):
    memory = get_memory_store()
    current_project = state.get("project_id", "default_project")
    messages = state['messages']
    
    user_query = messages[-1].content.lower() if isinstance(messages[-1].content, str) else ""
    
    approval_keywords = ["погнали", "утверждаю", "запускай", "приступай", "делай", "пиши код"]
    has_approval_word = any(word in user_query for word in approval_keywords)
    
    is_approved = state.get("is_approved", False) or has_approval_word

    ceo_message = messages[-1].content
    ceo_task = "".join([b.get('text', '') for b in ceo_message]) if isinstance(ceo_message, list) else str(ceo_message)
        
    try:
        relevant_docs = memory.similarity_search(ceo_task, k=2)
        context = "\n".join([doc.page_content for doc in relevant_docs])
    except Exception:
        context = "Нет дополнительных данных по архитектуре."
        
    # 🛑 ФАЗА 1: РЕЖИМ ОБСУЖДЕНИЯ АРХИТЕКТУРЫ
    if not is_approved:
        system_prompt = SystemMessage(content=f"""
        Ты — Senior Python/TS Архитектор в проекте {current_project}. 
        ТЕКУЩИЙ РЕЖИМ: **ОБСУЖДЕНИЕ АРХИТЕКТУРЫ И ПРОЕКТИРОВАНИЕ**.
        
        СЕЙЧАС ТЕБЕ ЗАПРЕЩЕНО МЕНЯТЬ ФАЙЛЫ И ВЫПОЛНЯТЬ КОМАНДЫ.
        Твоя цель — обсудить с пользователем/СЕО техническое решение задачи.
        
        Алгоритм:
        1. Разбери задачу по кодингу.
        2. Опиши, какие файлы потребуется создать или изменить.
        3. Предложи оптимальный алгоритм или архитектурный паттерн.
        4. Задай уточняющие вопросы по логике, если они есть.
        
        В конце ответа обязательно напиши, что ждешь команды «Утверждаю» или «Погнали», чтобы физически приступить к написанию кода.
        
        КОНТЕКСТ ПРОЕКТА:
        {context}
        """)
        
        step_think = SafeStep(name="Разработчик проектирует архитектуру...", type="run")
        await step_think.send()
        
        response = await llm_pure.ainvoke([system_prompt] + messages)
        
        step_think.output = "Проектирование завершено."
        step_think.update()
        
        return {
            "messages": [response], 
            "next_node": "END", 
            "is_approved": False
        }

    # 🚀 ФАЗА 2: РЕЖИМ АКТИВНОГО ВЫПОЛНЕНИЯ
    else:
        # Режим выполнения кода (теперь мы просто отдаем инструкции для Continue)
        system_prompt = SystemMessage(content=f"""
        Ты — Senior Python/TS Разработчик в проекте {current_project}.
        У тебя есть доступ к инструментам редактирования файлов через систему Continue.

        Твоя задача — написать/модернизировать код согласно утвержденному плану.
        Выводи код в формате чистых Markdown блоков с указанием путей к файлам, чтобы клиент Continue мог автоматически применить эти изменения.
        """)

        response = await llm_pure.ainvoke([system_prompt] + messages)
        return {
            "messages": [response], 
            "next_node": "END", 
            "is_approved": True
        }
