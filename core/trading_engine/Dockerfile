FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi uvicorn pydantic httpx

COPY core/trading_engine/ /app/

EXPOSE 8004

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8004", "--workers", "2"]
