from langgraph.graph import StateGraph, START, END
from src.core.state import OfficeState
from src.agents.ceo.node import ceo_node
from src.agents.programmer.node import programmer_node
from src.agents.smm.node import smm_node
from src.agents.seo_auditor.node import seo_auditor_node

def route_by_user_choice(state: OfficeState) -> str:
    """Маршрутизация на основе явного выбора пользователя в интерфейсе"""
    return state.get("selected_agent", "ceo")

def create_graph(checkpointer=None):
    graph = StateGraph(OfficeState)
    
    graph.add_node("ceo", ceo_node)
    graph.add_node("programmer", programmer_node)
    graph.add_node("smm", smm_node) 
    graph.add_node("seo_auditor", seo_auditor_node)
    
    # Прямо со старта идем к агенту, которого пользователь выбрал в меню ChatSettings
    graph.add_conditional_edges(
        START,
        route_by_user_choice,
        {
            "ceo": "ceo",
            "programmer": "programmer",
            "smm": "smm",
            "seo_auditor": "seo_auditor"
        }
    )
    
    # Внутренний роутинг CEO (если один агент вызывает другого)
    graph.add_conditional_edges(
        "ceo",
        lambda state: state.get("next_node", "END"),
        {
            "programmer": "programmer",
            "seo_auditor": "seo_auditor",
            "smm": "smm", 
            "END": END
        }
    )
    
    graph.add_edge("programmer", END),
    graph.add_edge("seo_auditor", END),
    graph.add_edge("smm", END) 
    
    # Компилируем граф с переданным хранилищем памяти
    return graph.compile(checkpointer=checkpointer)