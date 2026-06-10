# Импортируем функцию вызова Ollama.
from app.llm import call_ollama

# Импортируем TypedDict для типизации state.
from typing import TypedDict

# Описываем состояние, которым обмениваются узлы LangGraph.
class AgentState(TypedDict):
    # Исходная задача пользователя.
    task: str
    
    # План от planner.
    plan: str
    
    # Черновик решения от worker.
    draft: str
    
    # Комментарии reviewer.
    review: str
    
    # Финальный ответ.
    final_answer: str
    
    # Счётчик итераций.
    iterations: int
    
    # Итоговый статус.
    status: str

# Узел planner: строит короткий план решения.
def planner_node(state: AgentState) -> dict:
    # Формируем system prompt для planner-агента.
    system_prompt = (
        "Ты planner-агент в многоагентной системе. "
        "Твоя задача — декомпозировать пользовательскую задачу в короткий, ясный, технический план. "
        "Пиши структурированно и без лишней воды."
    )
    
    # Формируем user prompt из входной задачи.
    user_prompt = (
        f"Пользовательская задача:\n{state['task']}\n\n"
        "Составь план из 3-6 шагов."
    )
    
    # Вызываем локальную модель.
    plan = call_ollama(system_prompt, user_prompt)
    
    # Возвращаем обновление части состояния.
    
    state_loc = state["iterations"] + 1
    print(f"planner_node plan = {plan}\n state={state_loc}")
    return {
        "plan": plan,
        "iterations": state["iterations"] + 1
    }

# Узел worker: пишет решение по плану.
def worker_node(state: AgentState) -> dict:
    # Формируем system prompt для worker-агента.
    system_prompt = (
        "Ты worker-агент в многоагентной системе. "
        "Твоя задача — подготовить полезный, технически точный ответ по готовому плану. "
        "Если задача инженерная, отвечай структурированно и практично."
    )
    
    # Формируем user prompt, передавая задачу и план.
    user_prompt = (
        f"Задача:\n{state['task']}\n\n"
        f"План:\n{state['plan']}\n\n"
        "Подготовь черновой ответ."
    )
    
    # Получаем черновик от модели.
    draft = call_ollama(system_prompt, user_prompt)
    
    state_loc = state["iterations"] + 1
    print(f"worker_node draft = {draft} state={state_loc}")


    # Возвращаем обновление состояния.
    return {
        "draft": draft,
        "iterations": state["iterations"] + 1
    }

# Узел reviewer: проверяет черновик и решает, принять его или отправить на доработку.
def reviewer_node(state: AgentState) -> dict:
    # Формируем system prompt reviewer-агента.
    system_prompt = (
        "Ты reviewer-агент в многоагентной системе. "
        "Проверь черновик на ясность, полноту и соответствие задаче. "
        "Если ответ хороший, начни ответ со строки 'STATUS: accepted'. "
        "Если нужна доработка, начни ответ со строки 'STATUS: needs_revision'. "
        "После статуса кратко объясни причину."
    )
    
    # Формируем user prompt с контекстом задачи, плана и черновика.
    user_prompt = (
        f"Задача:\n{state['task']}\n\n"
        f"План:\n{state['plan']}\n\n"
        f"Черновик:\n{state['draft']}\n\n"
        "Проведи ревью."
    )
    
    # Получаем текст ревью от модели.
    review = call_ollama(system_prompt, user_prompt)
    
    # Определяем статус по префиксу ответа reviewer.
    status = "accepted" if review.lower().startswith("status: accepted") else "needs_revision"
    
    # Если ответ принят, финальным считаем текущий draft.
    final_answer = state["draft"] if status == "accepted" else ""
    
    state_loc = state["iterations"] + 1
    print(f"reviewer_node review = {review} state={state_loc}")
    
    
    # Возвращаем обновления состояния.
    return {
        "review": review,
        "status": status,
        "final_answer": final_answer,
        "iterations": state["iterations"] + 1
    }

# Узел revise: дорабатывает черновик на основе замечаний reviewer.
def revise_node(state: AgentState) -> dict:
    # Формируем system prompt для доработки.
    system_prompt = (
        "Ты worker-агент, который дорабатывает ответ после ревью. "
        "Исправь недостатки и верни улучшенную версию ответа."
    )
    
    # Передаём задачу, старый draft и review.
    user_prompt = (
        f"Задача:\n{state['task']}\n\n"
        f"Исходный план:\n{state['plan']}\n\n"
        f"Старый черновик:\n{state['draft']}\n\n"
        f"Замечания reviewer:\n{state['review']}\n\n"
        "Сделай улучшенную версию ответа."
    )
    
    # Вызываем модель повторно.
    improved_draft = call_ollama(system_prompt, user_prompt)

    state_loc = state["iterations"] + 1
    print(f"revise_node improved_draft = {improved_draft} state={state_loc}")


    
    # Возвращаем новый draft.
    return {
        "draft": improved_draft,
        "iterations": state["iterations"] + 1
    }