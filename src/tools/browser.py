import os
from langchain_core.tools import tool
from playwright.sync_api import sync_playwright

PROJECTS_ROOT = "/app/projects"

@tool
def take_screenshot(url: str, filename: str) -> str:
    """
    Открывает браузер, переходит по указанному URL и делает скриншот страницы.
    Используй это для проверки сайтов, сбора визуальных данных или чтения новостей.
    Args:
        url (str): Ссылка на сайт (обязательно с https://, например 'https://apple.com').
        filename (str): Имя файла для сохранения (например, 'apple_screen.png').
    """
    save_path = os.path.join(PROJECTS_ROOT, filename)
    
    try:
        # Запускаем Playwright в синхронном режиме
        with sync_playwright() as p:
            # headless=True значит, что браузер работает в фоне (без интерфейса)
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Переходим на сайт и ждем, пока сеть не "успокоится" (загрузятся картинки)
            page.goto(url, wait_until="networkidle", timeout=20000)
            
            # Делаем фото!
            page.screenshot(path=save_path)
            browser.close()
            
        return f"Успех! Скриншот сайта {url} сохранен на диске по пути: {save_path}"
    except Exception as e:
        return f"Ошибка при работе с браузером: {e}"

browser_tools = [take_screenshot]