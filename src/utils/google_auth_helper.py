import os
from google_auth_oauthlib.flow import InstalledAppFlow
from dotenv import load_dotenv, set_key

# Загружаем текущие переменные окружения
load_dotenv()

# Области доступа (Scopes) для GA4 и Search Console
SCOPES = [
    'https://www.googleapis.com/auth/analytics.readonly',
    'https://www.googleapis.com/auth/webmasters.readonly'
]

def get_refresh_token():
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("❌ Ошибка: GOOGLE_CLIENT_ID или GOOGLE_CLIENT_SECRET не найдены в .env")
        return

    # Создаем поток авторизации
    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES
    )

    # Запускаем локальный сервер для получения кода авторизации
    # Это откроет браузер
    creds = flow.run_local_server(port=0)

    refresh_token = creds.refresh_token
    if refresh_token:
        # Сохраняем refresh_token в .env файл автоматически
        set_key(".env", "GOOGLE_REFRESH_TOKEN", refresh_token)
        print("\n✅ Успех! Refresh Token получен и сохранен в .env")
        print(f"Token: {refresh_token}")
    else:
        print("\n❌ Не удалось получить Refresh Token. Попробуйте пересоздать OAuth Client ID с типом 'Desktop App'.")

if __name__ == "__main__":
    get_refresh_token()