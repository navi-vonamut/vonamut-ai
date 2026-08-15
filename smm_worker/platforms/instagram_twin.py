import asyncio
import random
import logging
import time
from typing import List, Dict, Any, Optional
from utils.helpers import prepare_device, cleanup_device

logger = logging.getLogger("INSTAGRAM_TWIN")

async def human_delay(min_sec: float = 1.5, max_sec: float = 4.0):
    """Имитация человеческой задержки между действиями."""
    delay = random.uniform(min_sec, max_sec)
    await asyncio.sleep(delay)

async def open_user_profile(d, username: str):
    """Открывает профиль пользователя прямо внутри Instagram без перезапуска приложения."""
    clean_username = username.lstrip("@").strip()
    logger.info(f"👤 Переход в профиль @{clean_username} в Instagram...")
    
    # 1. Попытка клика по аватарке / никнейму прямо из открытой шторки комментариев
    try:
        user_elem = d(descriptionMatches=f"(?i).*Перейти в профиль {clean_username}.*|.*Посмотреть историю {clean_username}.*")
        if not user_elem.exists(timeout=1.5):
            user_elem = d(textMatches=f"(?i)^{clean_username}\\s*$")

        if user_elem.exists(timeout=2):
            logger.info(f"👆 Кликаем по никнейму/аватарке @{clean_username} прямо в комментарии...")
            user_elem.click()
            await human_delay(3.0, 4.5)
            if d(textMatches="(?i).*Подписаться|Follow|Сообщение|Message.*").exists(timeout=3):
                logger.info(f"✅ Профиль @{clean_username} мгновенно открыт напрямую из комментариев!")
                return
    except Exception as e:
        logger.warning(f"⚠️ Прямой клик по комментарию не сработал: {e}")

    # 2. Попытка открытия через нативный интент deep link
    d.shell(f'am start -a android.intent.action.VIEW -d "instagram://user?username={clean_username}"')
    await human_delay(3.0, 4.5)

    if d(textMatches="(?i)Instagram|Инстаграм").exists(timeout=2):
        logger.info("👆 Нажимаем иконку Instagram в системном диалоге...")
        d(textMatches="(?i)Instagram|Инстаграм").click()
        await human_delay(1.0, 2.0)
        always_btn = d(textMatches="(?i)Всегда|Только сейчас|Just once|Always")
        if always_btn.exists(timeout=2):
            always_btn.click()
            await human_delay(2.0, 3.0)

async def open_hashtag_feed(d, hashtag: str):
    """Открывает ленту публикаций целевой ниши по хэштегу через нативный поиск в Instagram и выбирает пост."""
    clean_tag = hashtag.replace("#", "").replace("/", "").strip()
    if not clean_tag:
        logger.warning("⚠️ Некорректный хэштег (пустой после очистки).")
        return
    logger.info(f"🏷️ Ищем целевую нишу по хэштегу #{clean_tag} в Instagram...")
    
    # 1. Если был открыт полноэкранный Reels или комментарии — выходим на шаг назад
    if d(resourceIdMatches=".*reels.*|.*clips.*|.*comment_edit_text.*").exists(timeout=2):
        d.press("back")
        await human_delay(1.0, 1.5)

    # 2. Убеждаемся что Instagram запущен
    d.app_start("com.instagram.android", stop=False)
    await human_delay(2.0, 3.0)

    # 3. Переходим во вкладку поиска (нижнее меню)
    search_tab = d(descriptionMatches="(?i)Поиск.*|Search.*|Интересное", resourceIdMatches=".*search_tab.*|.*explore_tab.*")
    if search_tab.exists(timeout=3):
        search_tab.click()
        await human_delay(1.5, 2.5)
    else:
        d.click(320, 2250)
        await human_delay(1.5, 2.5)

    # 4. Нажимаем строку поиска вверху
    search_input = d(resourceIdMatches=".*action_bar_search_edit_text.*|.*search_box.*|.*search_input.*")
    if search_input.exists(timeout=3):
        search_input.click()
        await human_delay(1.0, 1.5)
    else:
        d.click(500, 150)
        await human_delay(1.0, 1.5)

    d.send_keys(f"#{clean_tag}")
    await human_delay(2.5, 3.5)

    # Переключаемся на вкладку "Метки" (Tags)
    tags_tab = d(textMatches="(?i)Метки|Tags")
    if tags_tab.exists(timeout=2):
        tags_tab.click()
        await human_delay(1.5, 2.5)

    # Кликаем по первому совпадению с тегом
    tag_result = d(textMatches=f"(?i)#{clean_tag}.*")
    if tag_result.exists(timeout=3):
        tag_result.click()
        await human_delay(3.5, 4.5)
    else:
        d.click(300, 380)
        await human_delay(3.5, 4.5)

    # 5. Делаем случайное количество свайпов сетки (от 1 до 4 раз) для выбора уникального глубокого поста
    num_swipes = random.randint(1, 4)
    logger.info(f"📜 Скроллим сетку хэштега #{clean_tag} {num_swipes} раз(а) для случайного глубокого выбора...")
    for _ in range(num_swipes):
        try:
            d.swipe(500, 1600, 500, 700, 0.3)
        except Exception:
            d.shell("input swipe 500 1600 500 700 300")
        await human_delay(1.2, 2.2)

    # Выбираем случайный пост из текущего вида сетки
    grid_positions = [
        (270, 750),   # Пост #1
        (810, 750),   # Пост #2
        (270, 1250),  # Пост #3
        (810, 1250),  # Пост #4
        (270, 1750),  # Пост #5
        (810, 1750)   # Пост #6
    ]
    
    cx, cy = random.choice(grid_positions)
    logger.info(f"🔥 Открываем уникальный пост сетки по координатам ({cx}, {cy})...")
    d.click(cx, cy)
    await human_delay(3.5, 5.0)


async def ensure_comments_opened(d) -> bool:
    """Гарантированно открывает окно комментариев к открытому посту/Reels."""
    logger.info("💬 Проверяем открыты ли комментарии...")
    
    # 1. Если поле ввода уже на экране
    if d(className="android.widget.EditText").exists(timeout=2) or d(resourceIdMatches=".*layout_comment_thread_edittext.*|.*comment_edit_text.*|.*row_thread_composer_edittext.*").exists(timeout=2):
        logger.info("✅ Секция комментариев уже открыта.")
        return True

    # 2. Ищем и нажимаем иконку комментариев
    comment_btn = d(descriptionMatches="(?i).*комментари.*|.*comment.*")
    if not comment_btn.exists(timeout=2):
        comment_btn = d(resourceIdMatches=".*comment_button.*|.*row_feed_button_comment.*|.*action_bar_button_comment.*|.*clips_comment_count.*|.*button_comment.*")

    if comment_btn.exists(timeout=3):
        logger.info("💬 Нажимаем иконку комментариев по селектору...")
        try:
            comment_btn.click()
            await human_delay(2.5, 4.0)
            if d(className="android.widget.EditText").exists(timeout=3) or d(resourceIdMatches=".*layout_comment_thread_edittext.*|.*comment_edit_text.*|.*row_thread_composer_edittext.*").exists(timeout=3):
                logger.info("✅ Секция комментариев открыта по кнопке!")
                return True
        except Exception as e:
            logger.warning(f"⚠️ Ошибка клика по кнопке комментариев: {e}")

    # 3. Нажимаем 'Посмотреть комментарии' если есть
    view_all = d(textMatches="(?i).*посмотреть.*комментари.*|.*view.*comment.*")
    if view_all.exists(timeout=2):
        logger.info("💬 Нажимаем 'Посмотреть все комментарии'...")
        view_all.click()
        await human_delay(2.5, 4.0)
        return True

    # 4. Резервный клик на боковой панели Reels (X: 970, Y: 1450)
    logger.info("💬 Пробуем резервный клик по иконке комментариев Reels...")
    d.click(970, 1450)
    await human_delay(2.5, 4.0)
    
    if d(resourceIdMatches=".*layout_comment_thread_edittext.*|.*comment_edit_text.*|.*row_thread_composer_edittext.*").exists(timeout=2):
        logger.info("✅ Секция комментариев открыта через резервные координаты!")
        return True

    return False

async def scan_post_and_comments(d, limit: int = 15, target_niche: Optional[str] = None) -> Dict[str, Any]:
    """
    Парсит описание поста/Reels и список комментариев.
    Если передан target_niche (хэштег или ниша), сначала переходит к нему.
    Поддерживает до 3 попыток выбора постов из сетки, если первому посту не удалось собрать комментарии.
    """
    logger.info(f"🔍 Начинаем парсинг публикаций (Ниша/Тег: {target_niche or 'текущий экран'})...")
    result = {"caption": "", "comments": []}
    
    await prepare_device(d)
    try:
        curr_app = d.app_current().get("package", "")
        if curr_app != "com.instagram.android":
            logger.info("📱 Instagram не в фокусе, запускаем приложение...")
            d.app_start("com.instagram.android", stop=False)
            await human_delay(3.0, 5.0)

        for attempt in range(1, 4):
            logger.info(f"🔄 [Попытка #{attempt}/3] Выбор и парсинг публикации по тегу {target_niche}...")
            
            try:
                if target_niche:
                    if target_niche.startswith("@"):
                        await open_user_profile(d, target_niche)
                    else:
                        await open_hashtag_feed(d, target_niche)

                # 1. Считываем текст описания поста
                caption_elements = d(resourceIdMatches=".*caption.*|.*media_caption.*|.*row_feed_comment_textview_caption.*")
                caption_texts = []
                for elem in caption_elements:
                    try:
                        txt = elem.info.get("text", "").strip()
                        if txt and len(txt) > 5:
                            caption_texts.append(txt)
                    except Exception:
                        pass
                
                result["caption"] = " ".join(caption_texts[:2])
                
                # 2. Открываем комментарии
                comments_opened = await ensure_comments_opened(d)
                if not comments_opened:
                    logger.warning(f"⚠️ [Попытка #{attempt}] Не удалось открыть секцию комментариев к посту.")
                    d.press("back")
                    await human_delay(1.5, 2.5)
                    continue

                # 3. Парсим комментарии по точной системной структуре Instagram
                scanned_comments = []
                seen_texts = set()
                scroll_attempts = 0
                max_scrolls = 4
                
                import re
                COMMENT_PATTERN_RU = re.compile(r'Пользователь\s+([a-zA-Z0-9._]+)\s+оставил\s+комментарий:\s*"([\s\S]+?)"', re.IGNORECASE)
                COMMENT_PATTERN_EN = re.compile(r'Comment\s+by\s+([a-zA-Z0-9._]+):\s*"([\s\S]+?)"', re.IGNORECASE)

                while len(scanned_comments) < limit and scroll_attempts < max_scrolls:
                    if d.app_current().get("package") != "com.instagram.android":
                        logger.warning("📱 Instagram свернулся, возвращаем на передний план...")
                        d.app_start("com.instagram.android", stop=False)
                        await human_delay(1.5, 2.5)

                    import xml.etree.ElementTree as ET
                    
                    try:
                        xml_str = d.dump_hierarchy()
                        xml_root = ET.fromstring(xml_str)
                        
                        for node in xml_root.iter():
                            raw_text = node.attrib.get("text", "") or node.attrib.get("content-desc", "")
                            if not raw_text:
                                continue
                                
                            # Мгновенный парсинг по нативному шаблону Instagram из XML дампы
                            m = COMMENT_PATTERN_RU.search(raw_text) or COMMENT_PATTERN_EN.search(raw_text)
                            if m:
                                author_name = m.group(1).strip()
                                c_text = m.group(2).strip()
                                
                                key = f"{author_name}:{c_text}"
                                if key not in seen_texts:
                                    seen_texts.add(key)
                                    scanned_comments.append({
                                        "author": author_name,
                                        "text": c_text,
                                        "timestamp": int(time.time())
                                    })
                                    logger.info(f"💬 [УСПЕШНО] @{author_name} — '{c_text[:50]}'")
                                    if len(scanned_comments) >= limit:
                                        break
                    except Exception as xml_err:
                        logger.warning(f"⚠️ Ошибка разбора XML hierarchy: {xml_err}")

                    if len(scanned_comments) < limit:
                        logger.info(f"📜 Скроллим шторку комментариев ниже ({scroll_attempts + 1}/{max_scrolls})...")
                        try:
                            d.swipe(500, 1400, 500, 800, 0.3)
                        except Exception:
                            d.shell("input swipe 500 1400 500 800 300")

                        scroll_attempts += 1
                        await human_delay(1.5, 2.5)

                if scanned_comments:
                    result["comments"] = scanned_comments
                    logger.info(f"✅ Успешно собрано {len(scanned_comments)} комментариев с попытки #{attempt}!")
                    return result
                else:
                    logger.warning(f"⚠️ [Попытка #{attempt}] В выбранном посте 0 комментариев. Закрываем и пробуем другой пост...")
                    # Безопасно закрываем шторку свайпом вниз вместо нажатия кнопки Назад
                    d.swipe(500, 500, 500, 1600, 0.3)
                    await human_delay(1.5, 2.5)

            except Exception as p_err:
                logger.warning(f"⚠️ Ошибка на попытке #{attempt}: {p_err}")
                d.swipe(500, 500, 500, 1600, 0.3)
                await human_delay(1.5, 2.5)

    except Exception as e:
        logger.error(f"❌ Ошибка при сканировании постов/комментариев: {e}")
    finally:
        await cleanup_device(d)
        
    return result

async def interact_with_comment(d, comment_keyword: str, action: str = "like", reply_text: Optional[str] = None) -> bool:
    """
    Находит комментарий по ключевому тексту или автору и ставит лайк либо пишет ответ.
    """
    logger.info(f"🎯 Взаимодействие с комментарием содержащим '{comment_keyword}' (Действие: {action})...")
    await prepare_device(d)
    success = False
    try:
        target_comment = d(textContains=comment_keyword)
        if not target_comment.exists(timeout=5):
            logger.warning(f"⚠️ Комментарий с текстом '{comment_keyword}' не найден на экране.")
            return False
            
        if action == "like":
            logger.info("❤️ Ставим лайк комментарию...")
            target_comment.click()
            await human_delay(0.5, 1.0)
            target_comment.click()
            await human_delay(1.0, 2.0)
            success = True
            
        elif action == "reply" and reply_text:
            logger.info(f"💬 Отвечаем на комментарий: '{reply_text}'")
            reply_btn = d(textMatches="(?i)Ответить|Reply")
            if reply_btn.exists(timeout=3):
                reply_btn.click()
                await human_delay(1.0, 2.0)
                
            input_box = d(resourceIdMatches=".*layout_comment_thread_edittext.*|.*comment_edit_text.*")
            if input_box.exists(timeout=5):
                input_box.click()
                await human_delay(0.5, 1.0)
                d.send_keys(reply_text)
                await human_delay(1.0, 2.0)
                
                send_btn = d(resourceIdMatches=".*post_button.*|.*comment_post_button.*")
                if send_btn.exists(timeout=3):
                    send_btn.click()
                    logger.info("✅ Ответ на комментарий отправлен!")
                    await human_delay(2.0, 3.5)
                    success = True
    except Exception as e:
        logger.error(f"❌ Ошибка при взаимодействии с комментарием: {e}")
    finally:
        await cleanup_device(d)
    return success

async def follow_user_profile(d, username: str, like_recent_posts: bool = True) -> bool:
    """
    Открывает профиль пользователя, нажимает 'Подписаться' и ставит лайк на свежий пост.
    """
    logger.info(f"➕ Попытка подписки и прогрева профиля @{username}...")
    await prepare_device(d)
    success = False
    try:
        await open_user_profile(d, username)
        
        # 1. Нажимаем кнопку "Подписаться"
        follow_btn = d(textMatches="(?i)Подписаться|Follow", className="android.widget.Button")
        if follow_btn.exists(timeout=4):
            follow_btn.click()
            logger.info(f"✅ Успешно подписались на @{username}!")
            await human_delay(1.5, 2.5)
            success = True
        else:
            logger.info(f"ℹ️ Кнопка 'Подписаться' не найдена (возможно, уже подписка или закрытый аккаунт).")

        # 2. Если включен лайкинг постов — заходим на 1-й пост в сетке и ставим лайк
        if like_recent_posts:
            logger.info("❤️ Пробуем поставить лайк на свежий пост пользователя...")
            grid_items = d(resourceIdMatches=".*image_button.*|.*row_feed_photo.*|.*matrix_image_button.*|.*grid_image_view.*")
            if grid_items.exists(timeout=3) and len(grid_items) > 0:
                try:
                    grid_items[0].click()
                    await human_delay(2.0, 3.0)
                    
                    logger.info("❤️ Ставим лайк на пост...")
                    d.double_click(500, 900)
                    await human_delay(1.0, 2.0)
                    
                    d.press("back")
                    await human_delay(1.0, 1.5)
                    logger.info(f"✅ Поставлен лайк на публикацию @{username}!")
                    success = True
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось поставить лайк в профиле @{username}: {e}")

    except Exception as e:
        logger.error(f"❌ Ошибка подписки и прогрева @{username}: {e}")
    finally:
        await cleanup_device(d)
    return success

async def send_direct_message(d, username: str, message_text: str) -> bool:
    """
    Переходит в профиль пользователя, открывает Direct и отправляет сообщение.
    """
    logger.info(f"✉️ Отправка сообщения в Direct пользователю @{username}...")
    await prepare_device(d)
    success = False
    try:
        await open_user_profile(d, username)
        
        msg_btn = d(textMatches="(?i)Сообщение|Message", className="android.widget.Button")
        if not msg_btn.exists(timeout=5):
            menu_btn = d(descriptionMatches="(?i)Дополнительные параметры|More options")
            if menu_btn.exists(timeout=3):
                menu_btn.click()
                await human_delay(1.0, 2.0)
                send_msg_option = d(textMatches="(?i)Отправить сообщение|Send message")
                if send_msg_option.exists(timeout=3):
                    send_msg_option.click()
        else:
            msg_btn.click()
            
        await human_delay(3.0, 5.0)
        
        input_field = d(resourceIdMatches=".*row_thread_composer_edittext.*|.*row_thread_edit_text.*")
        if input_field.exists(timeout=8):
            input_field.click()
            await human_delay(1.0, 1.5)
            d.send_keys(message_text)
            await human_delay(1.5, 2.5)
            
            send_btn = d(resourceIdMatches=".*row_thread_composer_button_send.*|.*send_button.*")
            if send_btn.exists(timeout=3):
                send_btn.click()
                logger.info(f"🚀 Сообщение пользователю @{username} в Direct успешно отправлено!")
                await human_delay(3.0, 5.0)
                success = True
        else:
            logger.error("❌ Не найдено поле ввода сообщения в Direct.")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки сообщения в Direct @{username}: {e}")
    finally:
        await cleanup_device(d)
    return success

async def read_direct_messages(d) -> List[Dict[str, Any]]:
    """
    Переходит в Direct и считывает список входящих сообщений.
    """
    logger.info("📬 Чтение входящих сообщений в Direct...")
    await prepare_device(d)
    messages = []
    try:
        d.app_start("com.instagram.android", stop=False)
        await human_delay(2.0, 3.0)
        
        direct_icon = d(descriptionMatches="(?i)Direct|Сообщения|Messaging", resourceIdMatches=".*action_bar_search_button.*")
        if direct_icon.exists(timeout=5):
            direct_icon.click()
            await human_delay(3.0, 5.0)
            
            threads = d(resourceIdMatches=".*row_inbox_container.*|.*thread_title.*")
            for thread in threads:
                try:
                    txt = thread.info.get("text", "").strip()
                    if txt:
                        messages.append({"raw_thread_info": txt, "timestamp": int(time.time())})
                except Exception:
                    pass
        logger.info(f"✅ Считано {len(messages)} чатов/уведомлений Direct.")
    except Exception as e:
        logger.error(f"❌ Ошибка при чтении Direct: {e}")
    finally:
        await cleanup_device(d)
    return messages

async def get_lead_latest_post_and_screenshot(d, username: str) -> Dict[str, Any]:
    """
    Открывает профиль пользователя, переходит в последний пост, снимает скриншот и читает текст поста.
    """
    import base64
    clean_username = username.lstrip("@").strip()
    logger.info(f"📸 Получение скриншота последнего поста лида @{clean_username}...")
    await prepare_device(d)
    result = {
        "lead_username": clean_username,
        "target_post_url": f"https://instagram.com/{clean_username}",
        "caption": "",
        "screenshot_base64": ""
    }
    try:
        await open_user_profile(d, clean_username)
        
        grid_items = d(resourceIdMatches=".*image_button.*|.*row_feed_photo.*|.*matrix_image_button.*|.*grid_image_view.*")
        if grid_items.exists(timeout=4) and len(grid_items) > 0:
            grid_items[0].click()
            await human_delay(2.5, 4.0)
            
            # Читаем текст описания
            caption_elements = d(resourceIdMatches=".*caption.*|.*media_caption.*|.*row_feed_comment_textview_caption.*")
            caption_texts = []
            for elem in caption_elements:
                try:
                    txt = elem.info.get("text", "").strip()
                    if txt and len(txt) > 5:
                        caption_texts.append(txt)
                except Exception:
                    pass
            result["caption"] = " ".join(caption_texts[:2])
            
            # Снимаем скриншот экрана поста
            try:
                raw_bytes = d.screenshot(format="raw")
                if raw_bytes:
                    result["screenshot_base64"] = base64.b64encode(raw_bytes).decode("utf-8")
                    logger.info("✅ Скриншот поста успешно получен!")
            except Exception as ss_err:
                logger.warning(f"⚠️ Не удалось захватить raw-скриншот: {ss_err}")

    except Exception as e:
        logger.error(f"❌ Ошибка получения скриншота поста @{clean_username}: {e}")
    finally:
        await cleanup_device(d)
    return result

async def publish_comment_to_post(d, comment_text: str) -> bool:
    """
    Публикует комментарий к текущему открытому посту.
    """
    logger.info(f"💬 Публикация комментария: '{comment_text}'...")
    await prepare_device(d)
    success = False
    try:
        await ensure_comments_opened(d)
        
        input_box = d(resourceIdMatches=".*layout_comment_thread_edittext.*|.*comment_edit_text.*|.*row_thread_composer_edittext.*")
        if input_box.exists(timeout=5):
            input_box.click()
            await human_delay(0.5, 1.0)
            d.send_keys(comment_text)
            await human_delay(1.0, 2.0)
            
            send_btn = d(resourceIdMatches=".*post_button.*|.*comment_post_button.*|.*send_button.*")
            if send_btn.exists(timeout=3):
                send_btn.click()
                logger.info("✅ Комментарий к посту успешно опубликован!")
                await human_delay(2.5, 4.0)
                success = True
        else:
            logger.error("❌ Не найдено поле ввода комментария.")
    except Exception as e:
        logger.error(f"❌ Ошибка публикации комментария: {e}")
    finally:
        await cleanup_device(d)
    return success

async def check_profile_active_and_has_posts(d, username: str) -> Dict[str, Any]:
    """
    Открывает профиль и проверяет, что он живой и наполнен контентом:
    - Профиль существует.
    - Нет плашек 'Публикаций пока нет' / 'Пользователь не найден'.
    - Аккаунт не закрытый (открыт для просмотра постов).
    - В сетке есть хотя бы 1 доступная публикация для касания.
    """
    clean_username = username.lstrip("@").strip()
    logger.info(f"🔎 Проверка профиля @{clean_username} на наличие постов и активность...")
    await prepare_device(d)
    result = {"is_active": False, "reason": "", "has_posts": False}
    try:
        await open_user_profile(d, clean_username)
        
        # 1. Проверяем наличие заблокированных/пустых/закрытых плашек
        no_posts = d(textMatches="(?i).*публикаций пока нет.*|.*no posts yet.*|.*пользователь не найден.*|.*user not found.*")
        if no_posts.exists(timeout=3):
            result["reason"] = "Аккаунт пуст (0 публикаций)."
            logger.warning(f"⚠️ Профиль @{clean_username}: {result['reason']}")
            return result

        private_account = d(textMatches="(?i).*это закрытый аккаунт.*|.*this account is private.*")
        if private_account.exists(timeout=2):
            result["reason"] = "Закрытый (приватный) аккаунт."
            logger.warning(f"⚠️ Профиль @{clean_username}: {result['reason']}")
            return result

        # 2. Проверяем наличие картинок/постов в сетке профиля
        grid_items = d(resourceIdMatches=".*image_button.*|.*row_feed_photo.*|.*matrix_image_button.*|.*grid_image_view.*")
        if grid_items.exists(timeout=4) and len(grid_items) > 0:
            result["is_active"] = True
            result["has_posts"] = True
            logger.info(f"✅ Профиль @{clean_username} прошел проверку! Найдено постов: {len(grid_items)}")
        else:
            result["reason"] = "Сетка постов пуста или не загрузилась."
            logger.warning(f"⚠️ Профиль @{clean_username}: {result['reason']}")

    except Exception as e:
        logger.error(f"❌ Ошибка проверки профиля @{clean_username}: {e}")
        result["reason"] = str(e)
    finally:
        await cleanup_device(d)

    return result

