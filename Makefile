.PHONY: help \
  install install-dev \
  docs-validate rag-validate rag-index \
  test test-unit test-component test-integration test-e2e test-rag test-prompt \
  fmt lint typecheck \
  run-api run-api-reload \
  up-infra up-llm up-app up-all down logs ps \
  smoke smoke-demo \
  demo-up demo-down

# ----------------------------------------------------------------------------
# Defaults
# ----------------------------------------------------------------------------

PYTHON ?= python3
PIP    ?= $(PYTHON) -m pip
VENV   ?= .venv
COMPOSE ?= docker compose -f infra/compose/docker-compose.yml
SERVICE ?=
# rule_based (default) — быстро, без LLM. llm — реальная классификация
# секций через ClassifierTreeSectionClassifier (SETUP-13 / ADR-HTC-09) и
# доп. taxonomy-aware doc_type detection; требует доступный Ollama.
FE_BOT_TAXONOMY_MODE ?= llm

help:
	@echo "Common targets:"
	@echo "  install / install-dev   - install runtime / dev dependencies"
	@echo "  test-unit/component/... - layered tests"
	@echo "  run-api / run-api-reload - local FastAPI"
	@echo "  up-infra / up-llm / up-app / up-all - Compose profiles"
	@echo "  smoke                   - end-to-end smoke check"
	@echo "  demo-up / demo-down     - legacy reviewer demo in examples/"

# ----------------------------------------------------------------------------
# Install
# ----------------------------------------------------------------------------

install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -e ".[dev,rag,data]"

# ----------------------------------------------------------------------------
# Docs / RAG validation
# ----------------------------------------------------------------------------

docs-validate:
	$(PYTHON) scripts/docs/validate_traceability.py

rag-validate:
	$(PYTHON) scripts/rag/validate_rag_cards.py rag/cards rag/manifests/chunk_manifest.jsonl

rag-index:
	$(PYTHON) scripts/rag/build_index.py --cards rag/cards --manifest rag/manifests/chunk_manifest.jsonl

# ----------------------------------------------------------------------------
# Tests (layered ladder — see README.md Debug Levels)
# ----------------------------------------------------------------------------

test: test-unit test-component test-integration

test-unit:
	$(PYTHON) -m pytest tests/unit -q

test-component:
	$(PYTHON) -m pytest tests/component -q

test-integration:
	$(PYTHON) -m pytest tests/integration -q

test-e2e:
	$(PYTHON) -m pytest tests/e2e -q

test-rag:
	$(PYTHON) -m pytest tests/rag_eval -q

test-prompt:
	$(PYTHON) -m pytest tests/prompt_eval -q

# ----------------------------------------------------------------------------
# Quality
# ----------------------------------------------------------------------------

fmt:
	$(PYTHON) -m ruff format src tests schemas validators

lint:
	$(PYTHON) -m ruff check src tests schemas validators

typecheck:
	$(PYTHON) -m mypy

# ----------------------------------------------------------------------------
# Local run (no containers, no LangGraph yet — wired in Day 7)
# ----------------------------------------------------------------------------

run-api:
	PYTHONPATH=src FE_BOT_TAXONOMY_MODE=$(FE_BOT_TAXONOMY_MODE) $(PYTHON) -m uvicorn fe_bot.app:create_app --factory --host 127.0.0.1 --port 8000

run-api-reload:
	PYTHONPATH=src FE_BOT_TAXONOMY_MODE=$(FE_BOT_TAXONOMY_MODE) $(PYTHON) -m uvicorn fe_bot.app:create_app --factory --host 127.0.0.1 --port 8000 --reload

# ----------------------------------------------------------------------------
# Compose stack (see infra/compose/docker-compose.yml for profiles)
#
# Profiles:
#   infra - postgres + qdrant + minio
#   llm   - ollama
#   app   - fe-bot FastAPI/LangGraph container
# ----------------------------------------------------------------------------

up-infra:
	$(COMPOSE) --profile infra up -d

up-llm:
	$(COMPOSE) --profile llm up -d

up-app:
	$(COMPOSE) --profile app up -d --build

up-all:
	$(COMPOSE) --profile infra --profile llm --profile app up --build

down:
	$(COMPOSE) down -v

logs:
	$(COMPOSE) logs -f $(SERVICE)

ps:
	$(COMPOSE) ps

# ----------------------------------------------------------------------------
# Smoke tests
# ----------------------------------------------------------------------------

smoke:
	bash scripts/smoke/smoke-local.sh

smoke-demo:
	bash scripts/smoke/smoke-demo.sh

# ----------------------------------------------------------------------------
# Legacy reviewer demo (examples/demo-langgraph-reviewer)
# ----------------------------------------------------------------------------

demo-up:
	docker compose -f examples/demo-langgraph-reviewer/docker-compose.yml up --build -d

demo-down:
	docker compose -f examples/demo-langgraph-reviewer/docker-compose.yml down -v
