FROM python:3.13-slim

WORKDIR /app

# Install dependencies
COPY core/pyproject.toml .
RUN pip install --no-cache-dir . 2>/dev/null || pip install --no-cache-dir \
    fastapi uvicorn pydantic pydantic-settings sqlalchemy asyncpg \
    redis httpx qdrant-client python-jose passlib python-multipart arq

# Copy shared library and service code
COPY core/shared/ /app/shared/
COPY core/agent_orchestrator/ /app/

EXPOSE 8001

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
