import os
from langchain_core.tools import tool

# Путь к корневой папке твоих репозиториев (которую мы пробросили в Docker)
PROJECTS_ROOT = "/app/projects"

@tool
def read_file(file_path: str) -> str:
    """
    Читает содержимое файла.
    Args:
        file_path (str): Относительный путь к файлу (например, 'astro-engine/app/main.py').
    """
    full_path = os.path.join(PROJECTS_ROOT, file_path)
    
    if not os.path.exists(full_path):
        return f"Ошибка: Файл {file_path} не найден."
        
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Ошибка при чтении файла: {e}"

@tool
def write_file(file_path: str, content: str) -> str:
    """
    Записывает код или текст в файл (перезаписывает существующий или создает новый).
    Args:
        file_path (str): Относительный путь к файлу (например, 'astro-engine/app/main.py').
        content (str): Код или текст для записи.
    """
    full_path = os.path.join(PROJECTS_ROOT, file_path)
    
    # Создаем папки, если их нет
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    
    try:
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Успех! Файл {file_path} успешно записан/обновлен."
    except Exception as e:
        return f"Ошибка при записи файла: {e}"

# Экспортируем список инструментов для легкого подключения к агенту
file_tools = [read_file, write_file]