FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi uvicorn pydantic httpx

COPY bots/telegram/ /app/

EXPOSE 8005

CMD ["uvicorn", "bot:app", "--host", "0.0.0.0", "--port", "8005", "--workers", "2"]
