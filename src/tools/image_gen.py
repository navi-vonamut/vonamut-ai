import os
import urllib.request
import urllib.parse
from langchain_core.tools import tool

PROJECTS_ROOT = "/app/projects"

@tool
def generate_image(prompt: str, filename: str) -> str:
    """
    Генерирует картинку по текстовому описанию (через бесплатный открытый API Pollinations/Flux).
    Args:
        prompt (str): Детальное описание картинки НА АНГЛИЙСКОМ ЯЗЫКЕ.
        filename (str): Имя файла для сохранения (например, 'post_image.jpg').
    """
    save_path = os.path.join(PROJECTS_ROOT, filename)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    try:
        print(f"DEBUG: Генерирую картинку через открытый API: {prompt}")
        
        # Кодируем промпт для URL (чтобы пробелы стали %20 и т.д.)
        encoded_prompt = urllib.parse.quote(prompt)
        
        # Обращаемся к Pollinations (под капотом работает нейросеть Flux)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1080&nologo=true"
        
        # Добавляем User-Agent, чтобы сервер не принял нас за спам-бота
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        
        with urllib.request.urlopen(req) as response, open(save_path, 'wb') as out_file:
            out_file.write(response.read())
            
        return f"Успех! Картинка успешно сгенерирована и сохранена по пути: {save_path}"
        
    except Exception as e:
        return f"Критическая ошибка при генерации картинки: {e}"

image_tools = [generate_image]