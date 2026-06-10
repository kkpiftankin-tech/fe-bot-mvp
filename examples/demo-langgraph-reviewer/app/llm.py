# Импортируем httpx для HTTP-вызова локального Ollama API.
import httpx

from app.config import settings


def call_ollama(system_prompt: str, user_prompt: str) -> str:
    url = f"{settings.ollama_base_url}/api/generate"

    prompt = f"{system_prompt}\n\n{user_prompt}"

    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": settings.temperature
        },
    }

    with httpx.Client(timeout=120.0) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

    return data["response"]