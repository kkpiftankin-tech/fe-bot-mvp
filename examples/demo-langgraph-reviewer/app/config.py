# Импортируем BaseModel из pydantic, чтобы описать типизированные настройки приложения.
from pydantic import BaseModel


# Создаём класс Settings, в котором будут храниться настройки приложения.
class Settings(BaseModel):
    # Имя модели Ollama, которую будем вызывать локально.
    ollama_model: str = "llama3.2:latest"
    
    # Базовый URL локального сервера Ollama.
    ollama_base_url: str = "http://localhost:11434"
    
    # Температура генерации; маленькое значение даёт более стабильные ответы.
    temperature: float = 0.2
    
    # Максимальное число циклов графа, чтобы агентная система не ушла в бесконечную доработку.
    max_iterations: int = 6

# Создаём один глобальный объект настроек, который будем импортировать из других модулей.
settings = Settings()

