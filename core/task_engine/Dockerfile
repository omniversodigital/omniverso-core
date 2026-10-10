FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    pydantic pydantic-settings sqlalchemy asyncpg httpx "redis[hiredis]" arq

COPY core/shared/ /app/shared/
COPY core/task_engine/ /app/

CMD ["python", "worker.py"]
