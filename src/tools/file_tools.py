import os

BASE_PROJECTS_PATH = "/app/projects"

def safe_write_code(project_id: str, filename: str, code: str):
    """Записывает код строго в папку конкретного проекта."""
    # Создаем путь: /app/projects/fitness_app/main.py
    project_path = os.path.join(BASE_PROJECTS_PATH, project_id)
    
    # Защита: не даем выйти за пределы BASE_PROJECTS_PATH
    full_path = os.path.abspath(os.path.join(project_path, filename))
    if not full_path.startswith(os.path.abspath(BASE_PROJECTS_PATH)):
        return "Ошибка: Попытка записи за пределы разрешенной зоны!"

    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w") as f:
        f.write(code)
    return f"Файл {filename} успешно сохранен в проекте {project_id}"