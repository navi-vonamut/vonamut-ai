import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Шаг 1: Подключаемся к дефолтной базе 'postgres', чтобы создать новую базу
default_db_url = "postgresql://astro_user:astro_password@postgres:5432/postgres"

try:
    print("Подключаюсь к системной базе...")
    conn = psycopg2.connect(default_db_url)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT) # Обязательно для CREATE DATABASE
    cursor = conn.cursor()
    
    # Проверяем, существует ли уже база chainlit_db
    cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'chainlit_db'")
    exists = cursor.fetchone()
    
    if not exists:
        cursor.execute("CREATE DATABASE chainlit_db")
        print("✅ База 'chainlit_db' успешно создана!")
    else:
        print("✅ База 'chainlit_db' уже существует.")
        
    conn.close()
except Exception as e:
    print(f"Ошибка при создании базы: {e}")

# Шаг 2: Подключаемся к новой базе 'chainlit_db' и создаем таблицы
chainlit_db_url = "postgresql://astro_user:astro_password@postgres:5432/chainlit_db"

try:
    print("Подключаюсь к базе 'chainlit_db' для создания таблиц...")
    conn2 = psycopg2.connect(chainlit_db_url)
    conn2.autocommit = True
    cursor2 = conn2.cursor()

    queries = '''
    CREATE TABLE IF NOT EXISTS "User" ("id" UUID PRIMARY KEY, "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP, "identifier" TEXT NOT NULL UNIQUE, "metadata" JSONB NOT NULL);
    CREATE TABLE IF NOT EXISTS "Thread" ("id" UUID PRIMARY KEY, "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP, "name" TEXT, "userId" UUID, "userIdentifier" TEXT, "tags" TEXT[], "metadata" JSONB);
    CREATE TABLE IF NOT EXISTS "Step" ("id" UUID PRIMARY KEY, "name" TEXT NOT NULL, "type" TEXT NOT NULL, "threadId" UUID NOT NULL, "parentId" UUID, "disableFeedback" BOOLEAN NOT NULL DEFAULT false, "streaming" BOOLEAN NOT NULL, "waitForAnswer" BOOLEAN, "isError" BOOLEAN, "metadata" JSONB, "tags" TEXT[], "input" TEXT, "output" TEXT, "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP, "start" TIMESTAMP(3), "end" TIMESTAMP(3), "generation" JSONB, "showInput" TEXT, "language" TEXT, "indent" INTEGER);
    CREATE TABLE IF NOT EXISTS "Element" ("id" UUID PRIMARY KEY, "threadId" UUID, "type" TEXT, "url" TEXT, "chainlitKey" TEXT, "name" TEXT NOT NULL, "display" TEXT, "objectKey" TEXT, "size" TEXT, "page" INTEGER, "language" TEXT, "forId" UUID, "mime" TEXT);
    CREATE TABLE IF NOT EXISTS "Feedback" ("id" UUID PRIMARY KEY, "forId" UUID NOT NULL, "threadId" UUID NOT NULL, "value" INTEGER NOT NULL, "comment" TEXT);
    '''
    cursor2.execute(queries)
    conn2.close()
    print("✅ Успех! Системные таблицы Chainlit созданы.")
except Exception as e:
    print(f"Ошибка при создании таблиц: {e}")