from typing import TypedDict, List, Optional, Dict, Any

class SEOAuditorState(TypedDict):
    # Входные данные
    target_url: Optional[str]
    
    # Очередь анализа
    problematic_urls: List[str]
    current_url_index: int
    
    # Данные текущей итерации
    primary_keyword: Optional[str]
    own_page_content: Optional[str]
    own_page_metrics: Optional[dict]
    competitor_url: Optional[str]
    competitor_content: Optional[str]
    
    # Накопленные результаты
    audit_results: List[Dict[str, Any]]
    
    # Итоговое заключение
    final_report: Optional[str]
    next_step: str