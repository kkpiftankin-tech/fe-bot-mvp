# ADR-002. Ollama + llama3.2 как LLM по умолчанию

## Status

Accepted

## Context

Системе нужен надёжный LLM-runtime, локально доступный, без зависимости от облачных провайдеров и без обязательной интеграции с frontier-моделями.

Альтернативы:

1. **Прямая интеграция с одной из облачных API (OpenAI / Anthropic / Mistral cloud).** Высокое качество, простая интеграция, но: требует ключей и оплаты, неприемлемо для on-prem deployment-ов, не соответствует принципу C-06 (`docs/01-business/constraints.md`).
2. **vLLM / TGI прямо в Docker.** Высокая производительность, но требует GPU и ощутимо сложнее в эксплуатации.
3. **llama.cpp с REST-обёрткой.** Минимально, но без управления моделями, без single-process management.
4. **Ollama.** Управляет моделями (`pull`, `run`), даёт стандартный HTTP API (`/api/generate`, `/api/embeddings`), работает на CPU и GPU, подходит для laptop-scale.

## Decision

По умолчанию использовать Ollama с моделью `llama3.2:latest` (класс 1B–3B). Доступ через единый `LLM Gateway`.

## Consequences

- Положительные:
  - Локальный, бесплатный, on-prem. Соответствует C-06.
  - Стандартный HTTP API; легко мокать в тестах.
  - Поддерживает JSON-mode (форсирует структурированные выходы — критично для PLATFORM-03).
  - Управление моделями встроено.
- Отрицательные:
  - Качество маленькой модели требует узких промптов и обязательной валидации (см. [docs/00-methodology/prompt-engineering-rules.md](../../00-methodology/prompt-engineering-rules.md)).
  - Латентность CPU-inference выше, чем у облака; в эталоне закладываем 200–500 мс p95 (NFR-Perf-003).
  - При желании перейти на иную модель — все промпты должны быть переоценены через `tests/prompt_eval/`.
- Нейтральные:
  - Альтернативный backend (cloud) реализуется как ещё один адаптер `LLM Gateway` без изменений в агентах.

## Related

- [../c4-context.md](../c4-context.md)
- [../../01-business/constraints.md](../../01-business/constraints.md)
- [../../02-system/non-functional-requirements.md](../../02-system/non-functional-requirements.md)
- [../../00-methodology/prompt-engineering-rules.md](../../00-methodology/prompt-engineering-rules.md)
