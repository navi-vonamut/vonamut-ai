import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Подтягиваем URL нашей бизнес-базы из .env (через docker-compose)
DATABASE_URL = os.getenv("ASTRO_DB_URL")

if not DATABASE_URL:
    DATABASE_URL = "postgresql://astro_user:astro_password@postgres:5432/astroguido_db"

# Если запускаемся локально вне контейнера docker
if "@postgres:5432" in DATABASE_URL and not os.path.exists("/.dockerenv"):
    DATABASE_URL = DATABASE_URL.replace("@postgres:5432", "@localhost:5433")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для всех моделей
Base = declarative_base()