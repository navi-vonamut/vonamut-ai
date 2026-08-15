from langchain_core.messages import SystemMessage, ToolMessage, AIMessage
from src.core.memory import get_memory_store
from langchain_google_genai import ChatGoogleGenerativeAI
from src.tools.project_tools import manage_tasks, manage_milestones
from src.core.ui_utils import SafeStep

llm = ChatGoogleGenerativeAI(model="gemma-4-31b-it")
all_ceo_tools = [manage_tasks, manage_milestones]
llm_with_tools = llm.bind_tools(all_ceo_tools)

async def ceo_node(state):
    memory = get_memory_store()
    messages = state['messages']
    user_query = messages[-1].content.lower()
    current_project = state.get("project_id", "AstroGuido_v1")
    
    # 🎯 Проверяем, дал ли пользователь команду на исполнение
    approval_keywords = ["погнали", "утверждаю", "запускай", "приступай", "делай"]
    has_approval_word = any(word in user_query for word in approval_keywords)
    
    # Переводим или сохраняем статус утверждения в состоянии
    is_approved = state.get("is_approved", False) or has_approval_word

    # RAG Поиск контекста
    step_rag = SafeStep(name="Поиск по архивам (RAG)...", type="run")
    await step_rag.send()
    try:
        relevant_docs = memory.similarity_search(user_query, k=3)
        context = "\n".join([doc.page_content for doc in relevant_docs])
        step_rag.set_output("Контекст успешно загружен.")
    except Exception as e:
        context = "Нет данных в памяти."
        step_rag.set_output(f"Память пуста: {e}")
    finally:
        step_rag.update()

    # 🛑 ФАЗА 1: РЕЖИМ БРЕЙНШТОРМА (План еще не утвержден)
    if not is_approved:
        system_prompt = SystemMessage(content=f"""
        Ты — СEO агентства AstroGuido. Твой текущий режим: **БРЕЙНШТОРМ И КОНСУЛЬТАЦИЯ**.
        ТЕКУЩИЙ ПРОЕКТ: {current_project}
        
        СЕЙЧАС ТЕБЕ ЗАПРЕЩЕНО СТАТЬ ЗАДАЧИ И ВЫЗЫВАТЬ ИНСТРУМЕНТЫ. 
        Твоя цель — обсудить с Владельцем концепцию (например, архитектуру видео-конвейера Remotion, шаблоны, интеграцию с озвучкой).
        Задавай уточняющие вопросы, предлагай варианты реализации, критикуй и улучшай идеи Владельца.
        
        В конце своего ответа мягко напомни, что как только концепция устроит Владельца, он должен написать «Утверждаю» или «Погнали», чтобы ты перешел к декомпозиции на задачи.

        КОНТЕКСТ ИЗ ПАМЯТИ:
        {context}
        """)
        
        step_think = SafeStep(name="СЕО обдумывает концепцию...", type="run")
        await step_think.send()
        response = llm.invoke([system_prompt] + messages) 
        step_think.set_output("Анализ завершен.")
        step_think.update()
        
        return {
            "messages": [response], 
            "next_node": "END", 
            "is_approved": False
        }

    # 🚀 ФАЗА 2: РЕЖИМ АКТИВНОГО ИСПОЛНЕНИЯ (Пользователь дал отмашку)
    else:
        system_prompt = SystemMessage(content=f"""
        Ты — СEO агентства AstroGuido. Владелец **УТВЕРДИЛ** план действий. Твой режим: **ИСПОЛНЕНИЕ**.
        ТЕКУЩИЙ ПРОЕКТ: {current_project}
        
        Разверни стратегию на Канбан-доске на основе ваших договоренностей из истории сообщений:
        1. Создай этапы в Дорожной карте через `manage_milestones(action='create', ...)`.
        2. Разбей на конкретные задачи для отделов через `manage_tasks(action='create', ...)`. Назначай на 'SMM' или 'PROGRAMMER'.
        
        После создания всех задач подготовь финальный отчет для Владельца о том, что работа запущена.
        """)
        
        chain_messages = [system_prompt] + messages
        
        step_think = SafeStep(name="СЕО формирует задачи по проекту...", type="run")
        await step_think.send()
        response = llm_with_tools.invoke(chain_messages)
        step_think.set_output("План декомпозирован.")
        step_think.update()
        
        max_iterations = 3
        while response.tool_calls and max_iterations > 0:
            chain_messages.append(response)
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                step_tool = SafeStep(name=f"Инструмент: {tool_name}", type="tool")
                step_tool.input = str(tool_call["args"])
                await step_tool.send()
                
                if tool_name == "manage_tasks":
                    result = manage_tasks.invoke(tool_call["args"])
                elif tool_name == "manage_milestones":
                    result = manage_milestones.invoke(tool_call["args"])
                else:
                    result = f"Error: Tool {tool_name} not found."
                
                step_tool.set_output(str(result))
                step_tool.update()
                
                chain_messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))
            
            step_process = SafeStep(name="Подведение итогов по задачам...", type="run")
            await step_process.send()
            response = llm_with_tools.invoke(chain_messages)
            step_process.set_output("Готово.")
            step_process.update()
            max_iterations -= 1

        return {
            "messages": [response], 
            "next_node": "END", 
            "is_approved": True
        }
