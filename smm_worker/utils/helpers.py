import os
import aiohttp
import asyncio
import random
import logging

logger = logging.getLogger("SMM_HELPERS")

async def download_images(image_urls: list, temp_dir: str) -> list:
    """Скачивает все переданные картинки во временную папку."""
    local_paths = []
    async with aiohttp.ClientSession() as session:
        for idx, url in enumerate(image_urls):
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        file_path = os.path.join(temp_dir, f"slide_{idx}.jpg")
                        with open(file_path, 'wb') as f:
                            f.write(await response.read())
                        local_paths.append(file_path)
                        logger.info(f"📥 Картинка {idx + 1}/{len(image_urls)} скачана.")
            except Exception as e:
                logger.error(f"❌ Ошибка скачивания картинки {url}: {e}")
    return local_paths

async def human_scroll(page, distance=500, steps=10):
    """Плавно скроллит страницу вниз, имитируя движение пальца."""
    for _ in range(steps):
        amt = distance // steps
        await page.mouse.wheel(0, amt)
        await asyncio.sleep(random.uniform(0.1, 0.3))

async def human_delay(min_sec=2, max_sec=5):
    """Залипание на контенте (имитация чтения поста)."""
    delay = random.uniform(min_sec, max_sec)
    logger.info(f"⏳ Имитация чтения: пауза {delay:.1f} сек...")
    await asyncio.sleep(delay)

async def human_type(page, locator, text: str):
    """Печатает текст с рваным ритмом человеческих пальцев."""
    await locator.click()
    await human_delay(0.5, 1.5)
    for char in text:
        await page.keyboard.type(char)
        await asyncio.sleep(random.uniform(0.03, 0.15))

async def prepare_device(d):
    """💡 Разблокировка устройства: пробуждение экрана, снятие блокировки шторкой и удержание активности."""
    logger.info("💡 Разблокировка устройства: включаем экран, смахиваем блокировку и держим активность...")
    try:
        d.shell("input keyevent KEYCODE_WAKEUP")
        await asyncio.sleep(1)
        d.swipe(500, 1500, 500, 500, 0.2)
        await asyncio.sleep(1)
        d.shell("svc power stayon true")
    except Exception as e:
        logger.warning(f"⚠️ Предупреждение при разблокировке устройства: {e}")

async def cleanup_device(d, close_app: bool = True, app_package: str = "com.instagram.android"):
    """👋 Завершение работы: остановка приложения, сброс удержания экрана и засыпание."""
    logger.info("👋 Завершение работы: закрываем приложение и выключаем экран...")
    try:
        if close_app:
            for _ in range(3):
                d.press("back")
                await asyncio.sleep(0.3)
            d.app_stop(app_package)
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при закрытии {app_package}: {e}")
    finally:
        try:
            d.shell("svc power stayon false")
            d.shell("input keyevent KEYCODE_POWER")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при выключении экрана: {e}")