import os
import asyncio
import chainlit as cl
import httpx
from chainlit.input_widget import Select
from langchain_core.messages import HumanMessage

# Официальные инструменты Chainlit для работы с БД
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# Импорты вашего графа
from src.graph import create_graph
from src.ui.menus import send_project_menu
from src.ui.handlers import handle_system_commands

import chainlit.server
from chainlit.server import app as chainlit_app
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from src.api.webhooks import router as webhooks_router
from src.api.trading_routes import router as trading_router
from src.api.sports_routes import router as sports_router

# Создаем роут для дашборда
dashboard_router = APIRouter()

@dashboard_router.get("/trading", response_class=HTMLResponse)
async def serve_trading_dashboard():
    """Отдача монохромного веб-дашборда в стиле Vercel для торгового терминала."""
    html_path = os.path.join(os.path.dirname(__file__), "ui", "trading_dashboard.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Dashboard HTML not found</h1>", status_code=404)

# Внедряем все кастомные маршруты в chainlit.server.router перед catch-all /{full_path:path}
for r in webhooks_router.routes + trading_router.routes + sports_router.routes + dashboard_router.routes:
    chainlit.server.router.routes.insert(-1, r)

# Патч для исправления ошибки FastAPI OpenAPI /docs (AttributeError: 'OAuth2PasswordBearerWithCookie' has no attribute 'model')
from chainlit.auth import OAuth2PasswordBearerWithCookie
from fastapi.openapi.models import OAuth2 as OAuth2Model, OAuthFlows as OAuthFlowsModel, OAuthFlowPassword

_openapi_flows = OAuthFlowsModel(password=OAuthFlowPassword(tokenUrl="/login"))

def _patch_dependant_for_openapi(dep):
    if not dep:
        return
    call = getattr(dep, "call", None)
    if isinstance(call, OAuth2PasswordBearerWithCookie):
        if not hasattr(call, "model"):
            call.model = OAuth2Model(flows=_openapi_flows)
    for sub in getattr(dep, "dependencies", []):
        _patch_dependant_for_openapi(sub)

for r in list(chainlit.server.app.routes) + list(chainlit.server.router.routes):
    _patch_dependant_for_openapi(getattr(r, "dependant", None))

# Запуск фонового сканера рынка Bybit
try:
    from src.trading.screener import get_screener_worker
    get_screener_worker().start_background()
except Exception as _e:
    logging.getLogger(__name__).warning(f"Could not start screener worker: {_e}")

# Запуск потокового слушателя новостей (News-First Catalyst Listener)
try:
    from src.trading.news import get_news_stream_listener
    get_news_stream_listener().start_background()
except Exception as _e:
    logging.getLogger(__name__).warning(f"Could not start news stream listener: {_e}")

# Запуск менеджера жизненного цикла позиций (Breakeven + Trailing Stop + Time-exit)
try:
    from src.trading.execution import get_lifecycle_worker
    get_lifecycle_worker().start()
except Exception as _e:
    logging.getLogger(__name__).warning(f"Could not start position lifecycle worker: {_e}")

# Запуск интерактивного Telegram терминала & Alerts Gateway (aiogram 3.x)
try:
    from src.trading.telegram import get_telegram_bot
    get_telegram_bot().start_background()
except Exception as _e:
    logging.getLogger(__name__).warning(f"Could not start Telegram bot: {_e}")

# Запуск бота спортивной аналитики (Sports Value Betting Bot)
try:
    from src.sports.telegram.bot import get_sports_telegram_bot
    get_sports_telegram_bot().start_background()
except Exception as _e:
    logging.getLogger(__name__).warning(f"Could not start Sports Telegram bot: {_e}")




DATABASE_URL = os.getenv("DATABASE_URL")  # База Chainlit
ASTRO_DB_URL = os.getenv("ASTRO_DB_URL")  # База LangGraph
DIRECTUS_URL = os.getenv("DIRECTUS_URL", "http://directus:8055")

GLOBAL_LANGGRAPH_POOL: AsyncConnectionPool = None

async def get_global_db_pool():
    global GLOBAL_LANGGRAPH_POOL
    is_closed = True
    if GLOBAL_LANGGRAPH_POOL is not None:
        try:
            is_closed = getattr(GLOBAL_LANGGRAPH_POOL, "closed", False) or getattr(GLOBAL_LANGGRAPH_POOL, "_closed", False)
        except Exception:
            is_closed = True

    if is_closed:
        print("🔗 Инициализация единого глобального пула подключений PostgreSQL для LangGraph...")
        GLOBAL_LANGGRAPH_POOL = AsyncConnectionPool(
            conninfo=ASTRO_DB_URL, 
            max_size=10, 
            kwargs={"autocommit": True, "prepare_threshold": 0},
            open=False
        )
        await GLOBAL_LANGGRAPH_POOL.open()
    return GLOBAL_LANGGRAPH_POOL

async def get_compiled_graph():
    pool = await get_global_db_pool()
    pool_checkpointer = AsyncPostgresSaver(pool)
    return create_graph(checkpointer=pool_checkpointer)

def get_default_state():
    return {
        "messages": [], 
        "project_id": None, 
        "user_access_level": 3, 
        "task_stack": [],
        "selected_agent": "ceo",
        "is_approved": False
    }


# =====================================================================
# ⚙️ ПОДКЛЮЧЕНИЕ ОФИЦИАЛЬНОГО ДАТА-ЛЕЙЕРА CHAINLIT
# =====================================================================
if DATABASE_URL and "postgresql+asyncpg" not in DATABASE_URL:
    SQLALCHEMY_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
else:
    SQLALCHEMY_URL = DATABASE_URL

@cl.data_layer
def get_data_layer():
    """Регистрирует встроенный слой данных Chainlit на базе SQLAlchemy"""
    return SQLAlchemyDataLayer(conninfo=SQLALCHEMY_URL)


# =====================================================================
# 🚀 ГЛОБАЛЬНАЯ ИНИЦИАЛИЗАЦИЯ ТАБЛИЦ
# =====================================================================
async def init_databases_on_startup():
    """Выполняется один раз при старте сервера: создает таблицы."""
    print("🚀 Глобальная充нициализация базы данных...")
    
    retries = 15
    conn = None
    for i in range(retries):
        try:
            conn = await AsyncConnection.connect(DATABASE_URL, autocommit=True)
            print("🔗 Успешное подключение к PostgreSQL!")
            break
        except Exception as e:
            if i == retries - 1:
                raise e
            print(f"⚠️ Ожидание СУБД ({i+1}/{retries}). Пробуем через 3 сек...")
            await asyncio.sleep(3)

    try:
        async with conn:
            async with conn.cursor() as cur:
                await cur.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    "id" UUID PRIMARY KEY,
                    "identifier" TEXT NOT NULL UNIQUE,
                    "metadata" JSONB NOT NULL,
                    "createdAt" TEXT
                );
                CREATE TABLE IF NOT EXISTS threads (
                    "id" UUID PRIMARY KEY,
                    "createdAt" TEXT,
                    "name" TEXT,
                    "userId" UUID,
                    "userIdentifier" TEXT,
                    "tags" TEXT[],
                    "metadata" JSONB,
                    FOREIGN KEY ("userId") REFERENCES users("id") ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS steps (
                    "id" UUID PRIMARY KEY,
                    "name" TEXT NOT NULL,
                    "type" TEXT NOT NULL,
                    "threadId" UUID NOT NULL,
                    "parentId" UUID,
                    "streaming" BOOLEAN NOT NULL,
                    "waitForAnswer" BOOLEAN,
                    "isError" BOOLEAN,
                    "metadata" JSONB,
                    "tags" TEXT[],
                    "input" TEXT,
                    "output" TEXT,
                    "createdAt" TEXT,
                    "command" TEXT,
                    "start" TEXT,
                    "end" TEXT,
                    "generation" JSONB,
                    "showInput" TEXT,
                    "language" TEXT,
                    "indent" INT,
                    "defaultOpen" BOOLEAN,
                    "autoCollapse" BOOLEAN,
                    "modes" JSONB,
                    FOREIGN KEY ("threadId") REFERENCES threads("id") ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS elements (
                    "id" UUID PRIMARY KEY,
                    "threadId" UUID,
                    "type" TEXT,
                    "url" TEXT,
                    "chainlitKey" TEXT,
                    "name" TEXT NOT NULL,
                    "display" TEXT,
                    "objectKey" TEXT,
                    "size" TEXT,
                    "page" INT,
                    "language" TEXT,
                    "forId" UUID,
                    "mime" TEXT,
                    "props" JSONB,
                    FOREIGN KEY ("threadId") REFERENCES threads("id") ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS feedbacks (
                    "id" UUID PRIMARY KEY,
                    "forId" UUID NOT NULL,
                    "threadId" UUID NOT NULL,
                    "value" INT NOT NULL,
                    "comment" TEXT,
                    FOREIGN KEY ("threadId") REFERENCES threads("id") ON DELETE CASCADE
                );
                ''')
                print("✅ Все официальные таблицы Chainlit успешно созданы.")
    except Exception as table_err:
        print(f"❌ Ошибка генерации таблиц Chainlit: {table_err}")

    try:
        async with await AsyncConnection.connect(ASTRO_DB_URL, autocommit=True) as graph_conn:
            pool_checkpointer = AsyncPostgresSaver(graph_conn)
            await pool_checkpointer.setup()
            print("✅ Системные таблицы LangGraph успешно подготовлены.")
    except Exception as graph_err:
        print(f"❌ Ошибка генерации таблиц LangGraph: {graph_err}")

asyncio.ensure_future(init_databases_on_startup())


# =====================================================================
# 🔐 АВТОРИЗАЦИЯ ПОЛЬЗОВАТЕЛЕЙ
# =====================================================================
@cl.password_auth_callback
async def auth_callback(username: str, password: str):
    email = username if "@" in username else f"{username}@astroguido.com"
    login_url = f"{DIRECTUS_URL}/auth/login"
    payload = {"email": email, "password": password}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(login_url, json=payload, timeout=5.0)
            if response.status_code == 200:
                data = response.json().get("data", {})
                access_token = data.get("access_token")
                
                user_info_url = f"{DIRECTUS_URL}/users/me"
                headers = {"Authorization": f"Bearer {access_token}"}
                user_response = await client.get(user_info_url, headers=headers)
                
                if user_response.status_code == 200:
                    user_data = user_response.json().get("data", {})
                    user_id = user_data.get("id")
                    
                    return cl.User(
                        identifier=username,
                        metadata={"directus_user_id": user_id},
                        persisted=True
                    )
        except Exception as e:
            print(f"🛑 Ошибка подключения к Directus: {e}")
            
    return None

# =====================================================================
# 🎬 НАЧАЛО СЕССИИ ПОЛЬЗОВАТЕЛЯ
# =====================================================================
@cl.on_chat_start
async def start():
    current_user = cl.user_session.get("user")
    d_id = current_user.metadata.get("directus_user_id") if current_user else "anon"
    username = current_user.identifier if current_user else "anonymous"

    settings = await cl.ChatSettings([
        Select(
            id="agent_choice",
            label="🤖 Выберите Агента:",
            values=["ceo", "programmer", "smm", "seo_auditor"],
            initial_index=0,
        )
    ]).send()

    await cl.Message(content=f"🏢 Добро пожаловать в Цифровой Холдинг, **{username}**!").send()
    await send_project_menu()

    app_graph = await get_compiled_graph()
    cl.user_session.set("app_graph", app_graph)


    state = get_default_state()
    state["selected_agent"] = settings["agent_choice"]
    cl.user_session.set("state", state)

    user_thread_id = f"user_db_{d_id}"
    config = {"configurable": {"thread_id": user_thread_id}}
    
    try:
        graph_state = await app_graph.aget_state(config)
        if graph_state and "messages" in graph_state.values:
            past_messages = graph_state.values["messages"]
            
            for msg in past_messages:
                if msg.type in ["system", "tool"]:
                    continue
                
                author = "Вы" if msg.type == "human" else "ИИ-Ассистент"
                content = msg.content
                if isinstance(content, list):
                    content = "".join([b.get('text', '') for b in content if 'text' in b])
                
                if content.strip():
                    await cl.Message(author=author, content=content).send()
            
            cl.user_session.set("state", graph_state.values)
            await cl.Message(content=f"✨ *История чата для аккаунта успешно восстановлена.*").send()
    except Exception as e:
        print(f"История для {username} пуста или база недоступна: {e}")

@cl.on_settings_update
async def setup_agent(settings):
    state = cl.user_session.get("state")
    if state is None: state = get_default_state()
    state["selected_agent"] = settings["agent_choice"]
    cl.user_session.set("state", state)
    
    agent_labels = {"ceo": "CEO", "programmer": "Программист", "smm": "SMM", "seo_auditor": "SEO-Аудитор"}
    friendly_name = agent_labels.get(settings["agent_choice"], settings["agent_choice"])
    await cl.Message(content=f"🔄 Подключен specialist: **{friendly_name}**").send()

@cl.action_callback("select_project")
async def on_action(action: cl.Action):
    state = cl.user_session.get("state")
    if state is None: state = get_default_state()
    state["project_id"] = action.payload.get("id")
    cl.user_session.set("state", state)
    await cl.Message(content=f"✅ Контекст переключен. Активный проект: **{action.label}**").send()

# =====================================================================
# ✉️ ОБРАБОТКА ТЕКУЩИХ СООБЩЕНИЙ
# =====================================================================
@cl.on_message
async def main(message: cl.Message):
    user_text = message.content.strip().lower()
    if await handle_system_commands(user_text): 
        return

    state = cl.user_session.get("state")
    if state is None: 
        state = get_default_state()

    if not state.get("project_id"):
        await cl.Message(content="⚠️ Пожалуйста, сначала выберите проект.").send()
        await send_project_menu()
        return

    current_user = cl.user_session.get("user")
    d_id = current_user.metadata.get("directus_user_id") if current_user else "anon"

    state["messages"].append(HumanMessage(content=message.content))
    
    app_graph = await get_compiled_graph()
    cl.user_session.set("app_graph", app_graph)

    user_thread_id = f"user_db_{d_id}"
    config = {"configurable": {"thread_id": user_thread_id}}

    
    # Стабильный асинхронный вызов графа
    try:
        final_state = await app_graph.ainvoke(state, config)
    except Exception as e:
        if "pool" in str(e).lower() and "closed" in str(e).lower():
            print(f"⚠️ Пул подключений был закрыт ({e}). Автоматическое возобновление пула и графа...")
            global GLOBAL_LANGGRAPH_POOL
            GLOBAL_LANGGRAPH_POOL = None
            app_graph = await get_compiled_graph()
            cl.user_session.set("app_graph", app_graph)
            final_state = await app_graph.ainvoke(state, config)
        else:
            raise e

    cl.user_session.set("state", final_state)
    
    raw_res = final_state["messages"][-1].content
    thinking_content = ""
    text_content = str(raw_res).strip()

    # 1. Парсинг тегов <think>...</think>
    if "<think>" in text_content:
        try:
            if "</think>" in text_content:
                parts = text_content.split("</think>", 1)
                thinking_part = parts[0].split("<think>", 1)
                if len(thinking_part) > 1:
                    thinking_content = thinking_part[1].strip()
                text_content = parts[1].strip()
            else:
                # Если модель забыла закрыть тег, считаем всё внутри мыслями
                parts = text_content.split("<think>", 1)
                thinking_content = parts[1].strip()
                text_content = ""
        except Exception as e:
            print(f"⚠️ Ошибка обработки тегов рассуждения: {e}")

    # 2. Красивое разделение UI элементов в Chainlit
    
    # Если внутри <think> что-то было — отправляем под спойлер Step
    if thinking_content.strip():
        async with cl.Step(name="🤖 Процесс мышления ИИ...", type="run") as step:
            step.content = thinking_content.strip()

    # Формируем ответ пользователю с префиксом роли
    if text_content.strip():
        agent_choice = state.get("selected_agent", "ceo")
        is_approved_now = final_state.get("is_approved", False)
        
        if agent_choice == "programmer":
            role_prefix = "👨‍💻 **Разработчик (Код выполнен):**" if is_approved_now else "👨‍💻 **Разработчик (Проектирование):**"
        elif agent_choice == "smm":
            role_prefix = "📱 **SMM-Специалист:**"
        else:
            role_prefix = "💼 **CEO Холдинга:**"
            
        final_output = f"{role_prefix}\n\n{text_content.strip()}"
        await cl.Message(content=final_output).send()
    else:
        await cl.Message(content="*(Агент успешно выполнил техническую задачу)*").send()

@cl.on_chat_end
async def end():
    pass