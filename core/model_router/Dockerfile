FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi uvicorn pydantic httpx "redis[hiredis]"

COPY core/model_router/ /app/

EXPOSE 8002

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "2"]
