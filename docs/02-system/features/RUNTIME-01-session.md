# RUNTIME-01. Сессия + ContextMemory

## Назначение

Открыть Runtime-сессию, выпустить `conversation_id`, привязать её к активной версии базы знаний и инициализировать пустую `ContextMemory`. Каждая последующая Runtime-фича читает и пишет через это состояние.

## Бизнес-ценность

Узлы LangGraph не имеют состояния; диалог — имеет. Фича сессии — то, что заставляет эту комбинацию работать: пользователь может закрыть вкладку, вернуться и продолжить с той фазы, на которой остановился.

## Пользовательский сценарий

1. Пользователь открывает чат-UI и жмёт **Start project**.
2. Система создаёт `conversation_id`, персистит пустую `ContextMemory`, ставит `current_phase = task_discovery`, фиксирует активную `kb_version`, к которой привязана сессия, и рендерит приветственное сообщение + первый промпт.
3. На любом последующем визите тот же `conversation_id` возобновляется с персистированного state.

## Связанные требования

- BR-FR-001..003 (создать сессию, восстановить по id, сбросить по intent `restart`).
- NFR-Sec-001 (per-session изоляция).
- NFR-Rel-003 (per-phase snapshots).

## Связанные агенты

- `SessionAgent`.

## Связанные сервисы

- Frontend Chat UI, API Backend, Session Service, ContextMemory Service, Conversation DB, LangGraph Orchestrator.

## Связанные контракты

- `ContextMemory` ([schemas/context_memory.py](../../../schemas/context_memory.py)) — см. [../../07-contracts/context-memory.md](../../07-contracts/context-memory.md).
- `SessionStartRequest`, `SessionStartResponse`.

## Критерии приёмки

- Старт Runtime без опубликованной активной KB ОБЯЗАН быть отклонён с actionable-ошибкой.
- Восстановление сессии ОБЯЗАНО проиграть текущую фазу, а не первую.
- Intent `restart` ОБЯЗАН очистить `ContextMemory` и стартовать новый session id; предыдущая сессия остаётся в audit.
- Тест: `tests/component/test_runtime_session.py`.
