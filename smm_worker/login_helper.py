import asyncio
from playwright.async_api import async_playwright
import os

PROFILES_DIR = "browser_profiles"
os.makedirs(PROFILES_DIR, exist_ok=True)

async def manual_login_mobile(account_id: str, platform: str, login_url: str):
    print(f"🚀 Запускаем мобильный браузер для {platform} ({account_id})...")
    
    async with async_playwright() as p:
        # Выбираем устройство, как в боевом воркере
        device_config = p.devices['iPhone 15 Pro Max']
        
        # Запускаем браузер в ВИДИМОМ режиме
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        # Подкидываем мобильные параметры в контекст
        context = await browser.new_context(
            **device_config,
            locale="ru-RU",
            timezone_id="Europe/Moscow"
        )
        
        page = await context.new_page()
        await page.goto(login_url)
        
        print("\n" + "="*50)
        print("🛑 ВНИМАНИЕ: Пожалуйста, залогиньтесь вручную.")
        print("Окно будет выглядеть как экран смартфона — это нормально!")
        print("Обязательно нажми 'Сохранить данные для входа' (Not now / Save info), когда Инстаграм спросит.")
        print("У вас есть 3 минуты. Скрипт ждет...")
        print("="*50 + "\n")
        
        # Ждем 180 секунд (3 минуты). Если зайдешь быстрее — просто подожди.
        await asyncio.sleep(180) 
        
        # Сохраняем куки
        state_file = os.path.join(PROFILES_DIR, f"{account_id}_{platform}.json")
        await context.storage_state(path=state_file)
        
        print(f"✅ УСПЕХ! Сессия сохранена в файл: {state_file}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(manual_login_mobile(
        account_id="astro_ru_01", 
        platform="instagram", 
        login_url="https://www.instagram.com/accounts/login/"
    ))