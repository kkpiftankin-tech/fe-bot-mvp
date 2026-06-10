# Импортируем BaseModel для описания входных и выходных DTO FastAPI.
from pydantic import BaseModel

# Описываем схему входного HTTP-запроса.
class RunAgentsRequest(BaseModel):
    # Пользовательская задача, которую надо решить агентной системе.
    task: str

# Описываем схему HTTP-ответа.
class RunAgentsResponse(BaseModel):
    # Исходная задача пользователя.
    task: str
    
    # План, который сделал planner.
    plan: str
    
    # Черновой результат, который сделал worker.
    draft: str
    
    # Финальный ответ после ревью.
    final_answer: str
    
    # Текст ревью от reviewer.
    review: str
    
    # Количество итераций графа.
    iterations: int
    
    # Статус завершения: accepted или needs_revision.
    status: str
    