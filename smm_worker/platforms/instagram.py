
import os
import asyncio
import logging
import time

# Импортируем нашу функцию прогрева
from platforms.warmup import warmup_instagram 

logger = logging.getLogger("INSTAGRAM_BOT")

async def publish_to_instagram(d, task, local_image_paths):
    try:
        logger.info("📱 Инициализация Instagram-бота на устройстве...")
        
        # 0. ПРОБУЖДЕНИЕ ЭКРАНА И ПРОГРЕВ
        logger.info("💡 Принудительная разблокировка Xiaomi 8T...")
        
        d.shell("input keyevent KEYCODE_WAKEUP")
        await asyncio.sleep(1)
        d.swipe(500, 1500, 500, 500, 0.2) 
        await asyncio.sleep(1)
        d.shell("svc power stayon true")

        # Запускаем прогрев (имитация живого пользователя перед постингом)
        await warmup_instagram(d, duration_minutes=2)

        # 1. ЗАГРУЗКА КАРТИНОК (С ПРАВИЛЬНОЙ СОРТИРОВКОЙ)
        logger.info("📥 Копируем картинки в обратном порядке для правильной сортировки...")
        remote_folder = "/storage/emulated/0/DCIM/Camera/"
        d.shell(f"mkdir -p {remote_folder}") 
        
        session_id = int(time.time())
        remote_paths_to_delete = []
        
        for i, img_path in reversed(list(enumerate(local_image_paths))):
            remote_path = f"{remote_folder}astro_{session_id}_{i}.jpg"
            tmp_path = f"/data/local/tmp/astro_tmp_{i}.jpg"
            
            d.push(img_path, tmp_path)
            d.shell(f"cp {tmp_path} {remote_path}")
            d.shell(f"rm {tmp_path}") 
            
            remote_paths_to_delete.append(remote_path)
            d.shell(f"am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file://{remote_path}")
            
            await asyncio.sleep(1.5)
            
        logger.info(f"✅ Успешно загружено {len(local_image_paths)} файлов (в нужном порядке)!")
        await asyncio.sleep(4)

        # 2. ЗАПУСК INSTAGRAM
        logger.info("🚀 Запускаем Instagram...")
        d.app_start("com.instagram.android", stop=True)
        await asyncio.sleep(10)

        # 3. НАЖАТИЕ ПЛЮСА
        logger.info("➕ Нажимаем кнопку создания поста...")
        d(resourceId="com.instagram.android:id/action_bar_buttons_container_left").click(timeout=15)
        await asyncio.sleep(2)

        # 4. ПЕРЕКЛЮЧЕНИЕ НА REELS
        logger.info("🎬 Выбираем вкладку REELS...")
        d(resourceId="com.instagram.android:id/cam_dest_clips").click(timeout=10)
        await asyncio.sleep(2)

        # 5. МУЛЬТИВЫБОР
        logger.info("🗂 Включаем мульти-выбор...")
        d(resourceId="com.instagram.android:id/gallery_menu_multi_select_button").click(timeout=10)
        await asyncio.sleep(1.5)

        # 6. ВЫБОР ФОТОГРАФИЙ (КАРУСЕЛЬ)
        logger.info("🖼 Выбираем картинки...")
        for i in range(len(local_image_paths)):
            d(resourceIdMatches=".*thumbnail.*", instance=i).click(timeout=5)
            await asyncio.sleep(0.8) 

        # 7. ДАЛЕЕ (После выбора фото)
        logger.info("➡️ Переходим к сборке Reels...")
        d(resourceId="com.instagram.android:id/media_thumbnail_tray_button").click(timeout=10)
        
        logger.info("⏳ Ждем обработку видео Инстаграмом (10 секунд)...")
        await asyncio.sleep(10)
        
        # 8. ЭКРАН СИНХРОНИЗАЦИИ АУДИО
        logger.info("🎵 Проверяем экран синхронизации аудио...")
        audio_btn = d(resourceId="com.instagram.android:id/primary_footer_text_button", textMatches="(?i)Далее|Пропустить|Next|Skip")
        
        if audio_btn.exists(timeout=5):
            logger.info("✅ Экран аудио пойман, нажимаем...")
            audio_btn.click()
            await asyncio.sleep(5)
        else:
            logger.info("⏩ Экран аудио не появился, идем дальше.")
        
        # 9. ЭКРАН РЕДАКТОРА (ДАЛЕЕ)
        logger.info("✂️ Ждем редактор эффектов...")
        next_btn = d(resourceId="com.instagram.android:id/clips_right_action_button")
        
        if next_btn.wait(timeout=20.0):
            next_btn.click()
            await asyncio.sleep(2)
        else:
            d.screenshot("error_editor_stuck.jpg")
            raise Exception("Не удалось найти кнопку 'Далее' в редакторе эффектов.")
            
        # 10. ВВОД ТЕКСТА ПОДПИСИ
        logger.info("✍️ Вводим описание и хэштеги...")
        d(resourceId="com.instagram.android:id/caption_input_text_view").wait(timeout=10) 
        d(resourceId="com.instagram.android:id/caption_input_text_view").click()
        await asyncio.sleep(1)
        
        safe_caption = task.description[:2000]
        d.send_keys(safe_caption) 
        await asyncio.sleep(2)

        # 11. ПУБЛИКАЦИЯ
        logger.info("🚀 НАЖИМАЕМ ПОДЕЛИТЬСЯ!")
        d(resourceId="com.instagram.android:id/share_button").click(timeout=5)
        
        logger.info("✅ Reels отправлен на публикацию. Ждем завершения загрузки в фоне...")
        await asyncio.sleep(10) 

        # 12. УБОРКА МУСОРА И ВЫКЛЮЧЕНИЕ ТЕЛЕФОНА
        logger.info("🧹 Удаляем исходники картинок из памяти устройства...")
        d.shell(f"rm -rf {remote_folder}")
        
        for path in remote_paths_to_delete:
            d.shell(f"am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file://{path}")

        logger.info("👋 Выходим из Instagram и гасим экран...")
        for _ in range(5):
            d.press("back")
            await asyncio.sleep(0.5)
            
        d.app_stop("com.instagram.android")
        
        # Снимаем запрет на засыпание и имитируем нажатие кнопки питания
        d.shell("svc power stayon false")
        d.shell("input keyevent KEYCODE_POWER")
        
        logger.info("🎉 Цикл публикации успешно завершен! Телефон ушел спать.")

    except Exception as e:
        logger.error(f"❌ Сбой публикации Instagram: {e}")
        d.screenshot("instagram_error_state.jpg")
        
        # Гасим экран даже в случае критического падения скрипта
        d.shell("svc power stayon false")
        d.shell("input keyevent KEYCODE_POWER")
        raise e