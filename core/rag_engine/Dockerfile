FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi uvicorn pydantic httpx qdrant-client

COPY core/rag_engine/ /app/

EXPOSE 8003

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8003", "--workers", "2"]
