import subprocess
import os
from langchain_core.tools import tool

PROJECTS_ROOT = "/app/projects"

@tool
def execute_command(command: str) -> str:
    """
    Выполняет консольную команду в терминале Linux (внутри Docker).
    Используй это для запуска скриптов (например, 'python astro-engine/test_api.py'), 
    установки пакетов (pip install) или запуска тестов (pytest).
    Args:
        command (str): Команда для выполнения.
    """
    try:
        # Запускаем команду в папке с проектами, ждем максимум 30 секунд, чтобы агент не "завесил" систему
        result = subprocess.run(
            command,
            shell=True,
            cwd=PROJECTS_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Собираем вывод (и успешный, и ошибки)
        output = result.stdout
        if result.stderr:
            output += f"\nОШИБКИ (STDERR):\n{result.stderr}"
            
        if not output.strip():
            return "Команда выполнена успешно, но не вернула никакого вывода в консоль."
            
        return output
        
    except subprocess.TimeoutExpired:
        return f"Ошибка: Время выполнения команды '{command}' превысило 30 секунд. Процесс убит."
    except Exception as e:
        return f"Ошибка выполнения команды: {e}"

terminal_tools = [execute_command]