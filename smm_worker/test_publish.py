import requests
import json

def test_pinterest_carousel():
    # Порт 8002, так как в docker-compose.yml мы пробросили "8002:8000"
    url = "http://localhost:8002/publish"
    
    # Формируем тестовое задание (PublishTask)
    payload = {
        "platform": "pinterest",
        "account_id": "astro_ru_01", # Тот самый аккаунт, для которого мы сохранили куки
        "image_urls": [
            # Используем пару тестовых вертикальных картинок с Unsplash
            "https://images.unsplash.com/photo-1518531933037-91b2f5f229cc?w=896&h=1024&fit=crop",
            "https://images.unsplash.com/photo-1532767153582-b1a0e5145009?w=896&h=1024&fit=crop"
        ],
        "title": "Солнце • Секстиль • Юпитер",
        "description": "Когда удача становится вашей второй натурой ✨\n\nУзнайте, как работают ваши аспекты в личном разборе на AstroGuido.\n\n#астрология #солнце #юпитер #гороскоп",
        "link": "https://astroguido.ru"
    }

    print(f"🚀 Отправляем задачу в SMM-воркер по адресу {url}...")
    
    try:
        response = requests.post(url, json=payload)
        print(f"Статус: {response.status_code}")
        print(f"Ответ сервера: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        print("\n⏳ Теперь смотри в окно браузера! Воркер работает в фоне.")
    except requests.exceptions.ConnectionError:
        print("❌ Ошибка: Не удалось подключиться. Убедись, что контейнер smm_worker запущен!")

if __name__ == "__main__":
    test_pinterest_carousel()