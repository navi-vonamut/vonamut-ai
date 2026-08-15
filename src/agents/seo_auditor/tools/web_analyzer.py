from typing import List, Dict, Any
import requests
from bs4 import BeautifulSoup

class WebAnalyzer:
    def __init__(self):
        self.headers_desktop = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self.headers_mobile = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        }

    def scrape_page(self, url: str, device: str = "desktop") -> str:
        """
        Scrapes the content of a page. In a real scenario, this would use Playwright/Firecrawl 
        to handle JS rendering.
        """
        headers = self.headers_mobile if device == "mobile" else self.headers_desktop
        try:
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract key SEO elements
            title = soup.title.string if soup.title else ""
            h1 = soup.find('h1').text if soup.find('h1') else ""
            text = soup.get_text(separator=' ', strip=True)
            
            return f"Title: {title}\nH1: {h1}\nContent: {text[:5000]}" 
        except Exception as e:
            return f"Error scraping {url}: {str(e)}"

    def get_top_competitors(self, query: str) -> List[str]:
        """
        Uses Tavily API to find the top organic results for a query, 
        excluding the user's own domain.
        """
        print(f"Searching real top competitors for: {query}")
        from tavily import TavilyClient
        import os
        
        tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        try:
            # Ищем топ-10, чтобы иметь запас для фильтрации своего домена
            response = tavily.search(query=query, search_depth="advanced", max_results=10)
            
            # Фильтруем результаты, убирая свой сайт
            external_urls = [
                result['url'] for result in response['results'] 
                if "astroguido.com" not in result['url'].lower()
            ]
            
            return external_urls[:3] # Возвращаем топ-3 внешних конкурентов
        except Exception as e:
            print(f"Tavily search error: {e}")
            return []
