from typing import Annotated, List, TypedDict, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class OfficeState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]  
    # Метаданные для переключения контекста (Optional, т.к. при старте пуст)
    project_id: Optional[str]  
    user_access_level: int # 1 - Личное, 2 - Бизнес, 3 - Админ  
    # Список текущих активных задач (наш будущий Канбан)
    task_stack: List[dict]  
    # ВАЖНО: поле для управления графом (кто работает следующим)
    next_node: str
    selected_agent: str
    is_approved: bool
    
