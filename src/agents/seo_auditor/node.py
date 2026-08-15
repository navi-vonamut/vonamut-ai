from src.core.state import OfficeState
from .graph import seo_auditor_app
from langchain_core.messages import AIMessage

def seo_auditor_node(state: OfficeState):
    """
    Узел-обертка для запуска графа SEO Auditor.
    Передает состояние из основного графа во внутренний граф агента.
    """
    # Подготавливаем входные данные для SEO Auditor
    inputs = {
        "target_url": state.get("target_url"),
        "primary_keyword": state.get("primary_keyword"),
    }
    
    # Запускаем внутренний граф агента
    result = seo_auditor_app.invoke(inputs)
    
    # Извлекаем финальный отчет
    final_report = result.get("final_report")
    
    # Создаем сообщение от ИИ на основе отчета, чтобы оно отобразилось в чате
    messages = []
    if final_report:
        messages.append(AIMessage(content=final_report))
    
    # Возвращаем результат в основное состояние
    return {
        "messages": messages,
        "final_report": final_report,
        "next_node": "END"
    }
