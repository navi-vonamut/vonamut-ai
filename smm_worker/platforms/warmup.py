import asyncio
import random
import logging

logger = logging.getLogger("INSTAGRAM_WARMUP")

# Список ключевых слов, на которые бот будет реагировать
ASTRO_KEYWORDS = ["астролог", "гороскоп", "знак зодиака", "планет", "луна", "натальная", "карта", "прогноз", "таро"]

async def warmup_instagram(d, duration_minutes=2):
    """Имитация живого пользователя: листает ленту, ищет астро-посты и лайкает их"""
    logger.info(f"⏳ Начинаем прогрев аккаунта на {duration_minutes} минут...")
    
    # Запускаем Инстаграм (если еще не запущен)
    d.app_start("com.instagram.android", stop=False)
    await asyncio.sleep(5)
    
    # Переходим на вкладку Reels или главную ленту (давай греть через Reels, там проще «залипнуть»)
    # Обычно иконка Reels — это третья или четвертая кнопка снизу, но надежнее просто нажать на видео
    logger.info("📺 Переходим в ленту Reels для прогрева...")
    reels_tab = d(descriptionMatches="(?i)Reels|Клипы")
    if reels_tab.exists(timeout=5):
        reels_tab.click()
        await asyncio.sleep(3)

    start_time = asyncio.get_event_loop().time()
    end_time = start_time + (duration_minutes * 60)
    
    posts_viewed = 0
    likes_given = 0

    while asyncio.get_event_loop().time() < end_time:
        posts_viewed += 1
        logger.info(f"👀 Просмотр Reels #{posts_viewed}...")
        
        # 1. Залипаем на видео случайное время (от 5 до 15 секунд)
        watch_time = random.uniform(5.0, 15.0)
        await asyncio.sleep(watch_time)
        
        # 2. Сканируем экран на наличие астрологического контента по ключевым словам
        has_astro_context = False
        try:
            # Ищем любые текстовые элементы на экране (описание Reels)
            texts = d(className="android.widget.TextView")
            for t in texts:
                node_text = t.info.get('text', '').lower()
                if any(word in node_text for word in ASTRO_KEYWORDS):
                    has_astro_context = True
                    logger.info(f"🎯 Найдено совпадение по теме: '...{node_text[:30]}...'")
                    break
        except Exception:
            pass # Если не удалось прочитать текст, просто идем дальше

        # 3. Принимаем решение о лайке
        # Если тема наша — лайкаем с вероятностью 80%. Если не наша — с вероятностью 10% (для естественности)
        chance = 0.8 if has_astro_context else 0.1
        if random.random() < chance:
            logger.info("❤️ Ставим лайк этому посту!")
            # Лайкаем двойным тапом по центру экрана (самый надежный способ в Instagram Reels)
            d.double_click(500, 1000) 
            likes_given += 1
            await asyncio.sleep(1)

        # 4. Свайпаем к следующему видео
        # Свайп снизу вверх: (x_start, y_start, x_end, y_end, duration)
        d.swipe(500, 1600, 500, 400, 0.2)
        await asyncio.sleep(2) # Пауза на прогрузку следующего видео

    logger.info(f"✅ Прогрев завершен. Посмотрели: {posts_viewed}, Лайкнули: {likes_given}")