import os
from typing import Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from .state import SEOAuditorState
from .prompts import INTENT_ANALYSIS_PROMPT, COMPARISON_PROMPT
from .tools.google_api import GoogleSEOClient
from .tools.web_analyzer import WebAnalyzer

# Инициализация инструментов и LLM
google_client = GoogleSEOClient()
web_analyzer = WebAnalyzer()
llm = ChatGoogleGenerativeAI(model="gemma-4-31b-it", temperature=0)

# --- УЗЛЫ ГРАФА ---

def detect_bounce_pages(state: SEOAuditorState):
    """Шаг 1: Поиск всех проблемных страниц в GA4"""
    print("🔍 Анализируем GA4 на предмет страниц с высоким Bounce Rate...")
    pages = google_client.get_high_bounce_pages()
    if not pages:
        return {"next_step": "end", "final_report": "Не удалось найти проблемные страницы в GA4."}
    
    urls = [p['url'] for p in pages]
    print(f"🚩 Найдено {len(urls)} проблемных страниц. Начинаем цикл анализа...")
    
    return {
        "problematic_urls": urls, 
        "current_url_index": 0, 
        "audit_results": [], 
        "next_step": "identify_intent"
    }

def identify_intent(state: SEOAuditorState):
    """Шаг 2: Определение интента. Если GSC молчит, выводим интент из контента страницы."""
    urls = state.get("problematic_urls", [])
    idx = state.get("current_url_index", 0)
    
    if idx >= len(urls):
        return {"next_step": "summarize_all"}
    
    url_path = urls[idx]
    full_url = url_path if url_path.startswith('http') else f"https://astroguido.com{url_path}"
    print(f"🔑 [{idx+1}/{len(urls)}] Анализируем интент для {full_url}...")
    
    # 1. Пробуем получить данные из Search Console
    queries = google_client.get_top_queries_for_url(full_url)
    
    if queries:
        keyword = queries[0]
        print(f"🎯 Найден реальный запрос в GSC: '{keyword}'")
        return {
            "target_url": url_path,
            "primary_keyword": keyword, 
            "next_step": "analyze_own_page"
        }
    
    # 2. Если в GSC пусто, пытаемся вывести интент из контента страницы
    print(f"⚠️ В GSC нет данных для {full_url}. Пытаемся вывести интент из контента...")
    page_data = web_analyzer.scrape_page(full_url)
    
    intent_prompt = f"""
    Проанализируй содержимое страницы и определи один главный поисковый запрос (keyword), по которому пользователь мог попасть на эту страницу.
    Верни ТОЛЬКО одну фразу (запрос), без пояснений.
    
    КОНТЕНТ СТРАНИЦЫ:
    {page_data}
    """
    
    try:
        response = llm.invoke(intent_prompt)
        content = response.content
        
        # Если модель вернула список блоков (размышления + ответ), берем последний блок
        if isinstance(content, list):
            content = content[-1]
            
        keyword = str(content).strip().strip('"').strip("'")
        print(f"🧠 Выведенный интент на основе контента: '{keyword}'")
        return {
            "target_url": url_path,
            "primary_keyword": keyword, 
            "next_step": "analyze_own_page"
        }
    except Exception as e:
        print(f"❌ Не удалось вывести интент: {e}")
        return {
            "current_url_index": idx + 1, 
            "audit_results": state.get("audit_results", []) + [{"url": url_path, "status": "error_intent"}],
            "next_step": "identify_intent"
        }

def analyze_own_page(state: SEOAuditorState):
    """Шаг 3: Скрапинг нашей страницы"""
    url = state['target_url']
    # Добавляем домен, если в GA4 путь относительный
    full_url = url if url.startswith('http') else f"https://astroguido.com{url}"
    
    print(f"📖 Читаем нашу страницу: {full_url}...")
    content = web_analyzer.scrape_page(full_url)
    
    return {"own_page_content": str(content), "next_step": "analyze_competitor"}

def analyze_competitor(state: SEOAuditorState):
    """Шаг 4: Поиск и анализ конкурента из ТОП-1"""
    keyword = state['primary_keyword']
    print(f"⚔️ Ищем лидера выдачи по запросу '{keyword}'...")
    
    competitors = web_analyzer.get_top_competitors(keyword)
    competitor_url = competitors[0] if competitors else None
    
    if not competitor_url:
        return {"next_step": "compare_and_conclude", "competitor_url": None}
    
    print(f"🏆 Найден конкурент: {competitor_url}. Анализируем его контент...")
    content = web_analyzer.scrape_page(competitor_url)
    
    return {
        "competitor_url": competitor_url, 
        "competitor_content": str(content), 
        "next_step": "compare_and_conclude"
    }

def compare_and_conclude(state: SEOAuditorState):
    """Шаг 5: Анализ конкретной страницы и сохранение результата"""
    print("🧠 Анализируем страницу и сравниваем с конкурентом...")
    
    prompt = COMPARISON_PROMPT.format(
        keyword=state['primary_keyword'],
        own_content=state['own_page_content'],
        competitor_content=state.get('competitor_content', "Конкурент не найден")
    )
    
    response = llm.invoke(prompt)
    
    # Сохраняем результат разбора этой страницы
    result = {
        "url": state['target_url'],
        "keyword": state['primary_keyword'],
        "analysis": response.content
    }
    
    return {
        "audit_results": state.get("audit_results", []) + [result],
        "current_url_index": state.get("current_url_index", 0) + 1,
        "next_step": "identify_intent"
    }

def summarize_all(state: SEOAuditorState):
    """Финальный шаг: Сбор всех разборов в один отчет"""
    print("📝 Формируем итоговый сводный отчет по всем страницам...")
    
    results = state.get("audit_results", [])
    if not results:
        return {"final_report": "Анализ не дал результатов.", "next_step": "end"}
    
    # Формируем большой промпт для суммаризации
    summary_text = "\n\n".join([
        f"Страница: {r.get('url')}\nЗапрос: {r.get('keyword')}\nАнализ: {r.get('analysis')}" 
        if isinstance(r, dict) and 'analysis' in r else f"Страница {r}: данных нет"
        for r in results
    ])
    
    final_prompt = f"""
    Ты — главный SEO-стратег. Перед тобой результаты анализа нескольких проблемных страниц сайта.
    Твоя задача: объединить их в один структурированный отчет для владельца.
    
    Группируй проблемы по типам (например, 'Проблемы с контентом', 'Технические ошибки', 'Слабые офферы').
    Дай общие рекомендации по исправлению всего раздела.
    
    ДАННЫЕ АНАЛИЗА:
    {summary_text}
    """
    
    response = llm.invoke(final_prompt)
    
    # Обработка ответа reasoning-модели (извлекаем только текст, убираем блоки thinking)
    content = response.content
    if isinstance(content, list):
        # Собираем все текстовые блоки в одну строку
        text_parts = [block['text'] for block in content if isinstance(block, dict) and block.get('type') == 'text']
        final_report = "\n".join(text_parts)
    else:
        final_report = str(content)
        
    return {"final_report": final_report, "next_step": "end"}

# --- СБОРКА ГРАФА ---

workflow = StateGraph(SEOAuditorState)

# Добавление узлов
workflow.add_node("detect_bounce_pages", detect_bounce_pages)
workflow.add_node("identify_intent", identify_intent)
workflow.add_node("analyze_own_page", analyze_own_page)
workflow.add_node("analyze_competitor", analyze_competitor)
workflow.add_node("compare_and_conclude", compare_and_conclude)
workflow.add_node("summarize_all", summarize_all)

# Определение связей (Edges)
workflow.set_entry_point("detect_bounce_pages")

workflow.add_edge("detect_bounce_pages", "identify_intent")

# Логика переходов из identify_intent
workflow.add_conditional_edges(
    "identify_intent",
    lambda state: state["next_step"],
    {
        "analyze_own_page": "analyze_own_page",
        "identify_intent": "identify_intent", # Пропуск страницы
        "summarize_all": "summarize_all"      # Все страницы обработаны
    }
)

workflow.add_edge("analyze_own_page", "analyze_competitor")
workflow.add_edge("analyze_competitor", "compare_and_conclude")

# После анализа одной страницы возвращаемся к проверке следующей
workflow.add_edge("compare_and_conclude", "identify_intent")

workflow.add_edge("summarize_all", END)

# Компиляция
seo_auditor_app = workflow.compile()