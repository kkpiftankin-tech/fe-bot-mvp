# Импортируем FastAPI.
from fastapi import FastAPI
import uvicorn


# Импортируем граф агентов.
from app.graph import agent_graph

# Импортируем схемы запросов и ответов.
from app.schemas import RunAgentsRequest, RunAgentsResponse

# Создаём FastAPI-приложение.
app = FastAPI(title="Multi-Agent LangGraph + Ollama Demo")

# Описываем healthcheck endpoint.
@app.get("/health")
def healthcheck():
    # Возвращаем простой статус сервиса.
    return {"status": "ok"}

# Описываем endpoint, который запускает агентный пайплайн.
@app.post("/run", response_model=RunAgentsResponse)
def run_agents(request: RunAgentsRequest):
    # Собираем начальное состояние графа.
    
    print("run_agents")
    initial_state = {
        "task": request.task,
        "plan": "",
        "draft": "",
        "review": "",
        "final_answer": "",
        "iterations": 0,
        "status": "needs_revision",
    }
    
    # Вызываем LangGraph с этим состоянием.  /Users/aleksandrpiftankin/Documents/projects/langgraph-ollama-fastapi/.vscode/launch.json
    # /Users/aleksandrpiftankin/Documents/projects/langgraph-ollama-fastapi/.vscode/lanch.json
    result = agent_graph.invoke(initial_state)
    
    #print("result=",result)
    
    # Если reviewer так и не принял ответ, но цикл остановился по лимиту,
    # считаем последнюю версию draft временным финальным результатом.
    final_answer = result["final_answer"] or result["draft"]
    
    # Возвращаем типизированный HTTP-ответ.
    return RunAgentsResponse(
        task=result["task"],
        plan=result["plan"],
        draft=result["draft"],
        final_answer=final_answer,
        review=result["review"],
        iterations=result["iterations"],
        status=result["status"],
    )





if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )