import asyncio
import logging

logger = logging.getLogger("PINTEREST_BOT")

async def publish_to_pinterest(page, task, local_image_paths):
    try:
        logger.info("Открываем главную страницу Pinterest...")
        await page.goto("https://www.pinterest.com/", wait_until="domcontentloaded")
        await asyncio.sleep(4)
        
        logger.info("Ищем кнопку 'Создайте пин' в Бизнес-центре...")
        create_pin_btn = page.get_by_text("Создайте пин").last
        
        if await create_pin_btn.count() > 0:
            await create_pin_btn.click()
        else:
            logger.warning("Кнопка по тексту не найдена, идем по прямой ссылке бизнес-аккаунта...")
            await page.goto("https://www.pinterest.com/pin-builder/", wait_until="domcontentloaded")
        
        logger.info("Ждем загрузки редактора пинов...")
        await page.wait_for_selector('input[type="file"]', state="attached", timeout=30000)
        await asyncio.sleep(2)
        
        logger.info("Загружаем обложку...")
        file_input = page.locator('input[type="file"]')
        await file_input.set_input_files(local_image_paths[0])
        await asyncio.sleep(3)
        
        logger.info("Заполняем тексты...")
        title_input = page.get_by_placeholder("Добавьте название")
        if await title_input.count() > 0:
            await title_input.click()
            await title_input.fill(task.title)
            await asyncio.sleep(0.5)

        logger.info("Кликаем в область редактора DraftEditor...")
        editor_content = page.locator('.public-DraftEditor-content').first
        if await editor_content.count() > 0:
            await editor_content.click()
            await asyncio.sleep(0.5)
            safe_description = task.description[:700]
            await page.keyboard.type(safe_description, delay=15)
            await asyncio.sleep(0.5)
        else:
            logger.warning("⚠️ Контейнер .public-DraftEditor-content не найден.")

        link_input = page.get_by_placeholder("Добавьте целевую ссылку")
        if await link_input.count() > 0:
            await link_input.click()
            await link_input.fill(task.link)
            await asyncio.sleep(0.5)

        logger.info("Выбираем доску 'Астрологические аспекты'...")
        board_dropdown = page.locator('button[data-test-id="board-dropdown-save-button"]')
        if await board_dropdown.count() > 0:
            await board_dropdown.click()
            await asyncio.sleep(1)
            board_item = page.get_by_text("Астрологические аспекты", exact=True)
            if await board_item.count() > 0:
                await board_item.click()
                await asyncio.sleep(1)
            else:
                await page.locator('div[data-test-id="board-row-container"]').first.click()
        
        logger.info("Нажимаем Опубликовать...")
        publish_btn = page.get_by_role("button", name="Опубликовать")
        if await publish_btn.count() > 0:
            await publish_btn.click()
            await asyncio.sleep(10)
            logger.info("✅ Пин успешно отправлен на публикацию!")
        else:
            logger.error("❌ Не найдена кнопка Опубликовать.")
            await page.screenshot(path="pinterest_error_publish.png")
            
    except Exception as e:
        logger.error(f"❌ Ошибка в скрипте Pinterest: {e}")
        await page.screenshot(path="pinterest_error.png")
        raise e