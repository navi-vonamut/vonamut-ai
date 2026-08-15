import os
import asyncio
from mcp.server.fastmcp import FastMCP
from langchain_core.messages import HumanMessage, SystemMessage

# Инициализируем FastMCP сервер
mcp = FastMCP("Vonamut LangGraph Gateway")

# Ленивая инициализация графа
try:
    from src.graph import create_graph
    graph = create_graph()
    print("✅ LangGraph успешно подключен к MCP", flush=True)
except ImportError:
    graph = None
    print("❌ Ошибка импорта LangGraph", flush=True)

@mcp.tool()
async def ask_programmer_agent(user_query: str, current_file_context: str = "") -> str:
    """
    Отправляет запрос главному программисту в LangGraph для анализа архитектуры, 
    планирования изменений или написания кода.
    
    :param user_query: Что нужно сделать (запрос пользователя).
    :param current_file_context: Содержимое текущего открытого файла в IDE.
    """
    if not graph:
        return "Ошибка: LangGraph не инициализирован внутри Docker."

    # 1. Сканируем рабочую директорию, проброшенную в Docker
    workspace_dir = "/app/projects"
    detected_files = []
    try:
        detected_files = os.listdir(workspace_dir)
        detected_files = [f for f in detected_files if not f.startswith(".")]
    except Exception:
        detected_files = ["Ошибка чтения /app/projects"]

    # 2. Формируем контекст (здесь также можно вернуть блок с Directus)
    context_injection = (
        f"[ФИЗИЧЕСКИЙ КОНТЕКСТ ОКРУЖЕНИЯ]: Ты запущен внутри Docker-контейнера.\n"
        f"Список проектов/файлов в директории {workspace_dir}: {detected_files}\n"
        f"Контекст открытого файла в IDE:\n{current_file_context}\n\n"
        f"Формируй изменения в коде в виде четких Markdown-блоков, чтобы "
        f"клиент Continue мог их автоматически применить."
    )

    formatted_messages = [
        SystemMessage(content=context_injection),
        HumanMessage(content=user_query)
    ]

    inputs = {
        "messages": formatted_messages,
        "selected_agent": "programmer",
        "project_id": "vonamut-ai" # Или передавайте динамически, если нужно
    }

    try:
        config = {"configurable": {"thread_id": "vscode_mcp_docker_session"}}
        
        final_state = inputs
        async for chunk in graph.astream(inputs, config=config, stream_mode="values"):
            final_state = chunk

        last_message = final_state["messages"][-1]
        raw_content = last_message.content
        
        final_answer = "".join([b.get('text', '') for b in raw_content]) if isinstance(raw_content, list) else str(raw_content)
        
        if not final_answer.strip():
            final_answer = "*(Разработчик сформировал план изменений, но ответ пуст)*"
            
        return final_answer

    except Exception as e:
        return f"❌ Ошибка внутри LangGraph: {str(e)}"

if __name__ == "__main__":
    # Запускаем MCP по протоколу стандартного ввода/вывода
    mcp.run(transport='stdio')