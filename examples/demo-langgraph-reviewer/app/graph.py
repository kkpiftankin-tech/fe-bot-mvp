# Импортируем Literal для точной типизации возможных переходов.
from typing import Literal

# Импортируем константы и класс графа из LangGraph.
from langgraph.graph import StateGraph, START, END

# Импортируем настройки.
from app.config import settings

# Импортируем тип состояния и узлы графа.
from app.agents import AgentState, planner_node, worker_node, reviewer_node, revise_node

# Функция роутинга после reviewer.
def route_after_review(state: AgentState) -> Literal["revise", END]:
    # Если reviewer принял ответ, завершаем граф.
    if state["status"] == "accepted":
        return END
    
    # Если превышен лимит итераций, тоже завершаем граф, чтобы не зациклиться.
    if state["iterations"] >= settings.max_iterations:
        return END
    
    # Иначе отправляем в узел revise.
    return "revise"

# Функция сборки и компиляции графа.
def build_graph():
    # Создаём граф на базе общей схемы состояния.
    graph = StateGraph(AgentState)
    
    # Регистрируем узлы.
    graph.add_node("planner", planner_node)
    graph.add_node("worker", worker_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("revise", revise_node)
    
    # Указываем стартовую последовательность.
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "worker")
    graph.add_edge("worker", "reviewer")
    
    # После ревью решаем: конец или доработка.
    graph.add_conditional_edges("reviewer", route_after_review, ["revise", END])
    
    # После доработки снова отправляем на ревью.
    graph.add_edge("revise", "reviewer")
    
    # Компилируем и возвращаем готовый runnable graph.
    return graph.compile()

# Создаём singleton-экземпляр графа на уровне модуля.
agent_graph = build_graph()