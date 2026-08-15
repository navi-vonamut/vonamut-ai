import chainlit as cl
from src.ui.menus import send_project_menu
from src.tools.indexer import index_multiple_repos

async def handle_system_commands(user_text: str) -> bool:
    """Обрабатывает системные команды. Возвращает True, если команда была обработана."""
    
    if user_text in ["/menu", "/меню", "сменить проект", "проект"]:
        await send_project_menu()
        return True

    if user_text in ["/index", "/индекс", "индексация"]:
        msg = cl.Message(content="⏳ Начинаю сканирование папок и загрузку документов в Qdrant. Подожди пару минут...")
        await msg.send()
        
        try:
            TARGET_PATHS = [
                "/app/projects/astro-docs/docs",       
                "/app/projects/astro-engine/docs", 
                "/app/projects/astro-guido/docs",  
                "/app/projects/astro-front/docs"   
            ]
            await cl.make_async(index_multiple_repos)(TARGET_PATHS, "astroguido")
            msg.content = "✅ Индексация успешно завершена! Вся документация загружена."
            await msg.update()
        except Exception as e:
            msg.content = f"❌ Сбой при индексации: {e}"
            await msg.update()
            
        return True

    return False