import os
from langchain_core.tools import tool
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.db.models import Post, Base

# Берем строку подключения из окружения Docker
DB_URL = os.environ.get("ASTRO_DB_URL", "postgresql://astro_user:astro_password@postgres:5432/astroguido_db")
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@tool
def save_post(region: str, platform: str, theme: str, content: str, image_path: str, scheduled_at: str = None) -> str:
    """
    Сохраняет пост в БД. 
    Args:
        ...
        scheduled_at (str): Время публикации в формате ISO (ГГГГ-ММ-ДД ЧЧ:ММ:СС).
    """
    db = SessionLocal()
    try:
        new_post = Post(
            region=region,
            platform=platform,
            theme=theme,
            content=content,
            image_url=image_path,
            status="DRAFT",
            scheduled_at=scheduled_at # 🔥 Добавляем поле сюда
        )
        db.add(new_post)
        db.commit()
        db.refresh(new_post)
        return f"Успех! Пост '{theme}' надежно сохранен в базу данных (ID: {new_post.id})."
    except Exception as e:
        db.rollback()
        return f"Ошибка при сохранении в БД: {e}"
    finally:
        db.close()

db_tools = [save_post]