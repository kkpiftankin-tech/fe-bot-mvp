# FE-Bot API image. The actual src/fe_bot/api package will be implemented later;
# this Dockerfile is shaped so that the build succeeds even before the package
# has any modules — it installs runtime deps and falls back to a clear error if
# you try to start the container before the app exists.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /code

# Install runtime dependencies declared in pyproject.toml. We split the copy so
# Docker can cache the install layer when only source code changes.
COPY pyproject.toml README.md ./
RUN pip install --upgrade pip && pip install -e ".[rag,data]" || pip install \
        "fastapi>=0.113,<1.0" \
        "uvicorn[standard]>=0.30,<1.0" \
        "langgraph>=0.2,<1.0" \
        "langchain>=0.2,<1.0" \
        "langchain-community>=0.2,<1.0" \
        "pydantic>=2.7,<3.0" \
        "pydantic-settings>=2.4,<3.0" \
        "httpx>=0.27,<1.0" \
        "pyyaml>=6.0,<7.0"

COPY src /code/src
COPY schemas /code/schemas
COPY validators /code/validators
COPY prompts /code/prompts
COPY rag /code/rag

ENV PYTHONPATH=/code/src

EXPOSE 8000

# When src/fe_bot/api/main.py defines `app`, uvicorn picks it up.
# Until then, the container exits with a clear message.
CMD ["sh", "-c", "if [ -f /code/src/fe_bot/api/main.py ]; then exec uvicorn fe_bot.api.main:app --host 0.0.0.0 --port 8000; else echo 'fe_bot.api.main:app is not implemented yet — see docs/implementation-plan/' >&2; exit 64; fi"]
