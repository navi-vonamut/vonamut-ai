import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from langchain_core.tools import tool

@tool
def get_daily_trends(geo_code: str) -> str:
    """
    Получает самые горячие поисковые тренды для указанной страны.
    Args:
        geo_code (str): Двухбуквенный код (US, ES, RU, DE и т.д.).
    """
    url = f"https://trends.google.com/trends/trendingsearches/daily/rss?geo={geo_code.upper()}"
    try:
        # Притворяемся настоящим браузером Mac
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/rss+xml, text/xml'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)
        trends = [item.find('title').text for item in root.findall('.//item')[:10]]
        return f"🔥 Общие тренды ({geo_code}):\n" + "\n".join(trends)
    except Exception as e:
        return f"Google Trends заблокировал запрос ({e}). Попробуй использовать инструмент 'get_niche_news'."

@tool
def get_niche_news(topic: str, geo_code: str, language: str) -> str:
    """
    Ищет свежие новости по конкретной теме в заданном регионе.
    Используй это, если get_daily_trends выдал ошибку, или чтобы найти новости по узкой теме (например, 'astrology').
    Args:
        topic (str): Ключевое слово (например 'astrology' или 'астрология').
        geo_code (str): Код страны (US, ES, RU).
        language (str): Код языка (en, es, ru).
    """
    query = urllib.parse.quote(topic)
    url = f"https://news.google.com/rss/search?q={query}&hl={language}-{geo_code}&gl={geo_code}&ceid={geo_code}:{language}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)
        news = [item.find('title').text for item in root.findall('.//item')[:10]]
        return f"📰 Свежие новости по теме '{topic}' ({geo_code}):\n" + "\n".join(news)
    except Exception as e:
        return f"Ошибка поиска новостей: {e}"

# Экспортируем оба инструмента
trend_tools = [get_daily_trends, get_niche_news]