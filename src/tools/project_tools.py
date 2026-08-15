from langchain_core.tools import tool
from src.db.base import SessionLocal
from src.db.models import Task, Milestone
from datetime import datetime

@tool
def manage_tasks(
    action: str, 
    task_id: int = None, 
    title: str = "Без названия", 
    description: str = "Нет описания", 
    assignee: str = "Не назначен", 
    status: str = "todo", 
    priority: str = "Medium"
) -> str:
    """
    Управляет канбан-доской задач.
    Actions: 
    - 'get_all': получить все задачи.
    - 'create': создать задачу. ОБЯЗАТЕЛЬНО передай: title, description, assignee.
    - 'update_status': изменить статус (нужен task_id и новый status).
    """
    db = SessionLocal()
    try:
        if action == 'get_all':
            tasks = db.query(Task).all()
            if not tasks:
                return "Канбан-доска пуста."
            
            result = []
            for t in tasks:
                assign = t.assignee if t.assignee else "Не назначен"
                report = t.agent_report if t.agent_report else "Ожидает выполнения"
                result.append(f"[{t.id}] СТАТУС: {t.status} | {t.title} | Исполнитель: {assign} | Отчет: {report}")
            return "\n".join(result)
        
        if action == 'create':
            # Важно: Directus чувствителен к регистру статусов. 
            # Используем lowercase 'todo', так как чаще всего в Директусе он пишется так.
            new_task = Task(
                title=title,
                description=description,
                assignee=assignee,
                status="todo",
                priority=priority
            )
            db.add(new_task)
            db.commit()
            return f"Задача '{title}' успешно добавлена на доску. Назначена на: {assignee}."

        if action == 'update_status':
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = status
                db.commit()
                return f"Статус задачи {task_id} изменен на {status}"
            return f"Задача {task_id} не найдена."
            
    except Exception as e:
        return f"Ошибка БД: {str(e)}"
    finally:
        db.close()
        
    return "Неизвестное действие."

@tool
def manage_milestones(action: str, title: str = None, deadline_iso: str = None) -> str:
    """
    Управляет глобальными этапами (Milestones) дорожной карты.
    Actions:
    - 'get_all': список всех этапов.
    - 'create': создать новый этап. Передай title и deadline_iso (формат YYYY-MM-DD).
    """
    db = SessionLocal()
    try:
        if action == 'get_all':
            milestones = db.query(Milestone).all()
            if not milestones: return "Нет активных этапов."
            return "\n".join([f"[{m.id}] {m.title} | Дедлайн: {m.deadline}" for m in milestones])

        if action == 'create':
            new_m = Milestone(title=title, status="Planned")
            if deadline_iso:
                try:
                    new_m.deadline = datetime.fromisoformat(deadline_iso)
                except:
                    pass
            db.add(new_m)
            db.commit()
            return f"Глобальный этап '{title}' успешно создан."
    except Exception as e:
        return f"Ошибка БД: {str(e)}"
    finally:
        db.close()
    return "Неизвестное действие."