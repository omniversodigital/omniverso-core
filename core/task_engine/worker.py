"""OMNIVERSO — Task Engine Worker.

Background worker that processes queued tasks using ARQ (async Redis queue).
Picks up tasks from Redis, executes them via the appropriate agent, and
writes results back to the database.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime

import httpx

logger = logging.getLogger("omniverso.task_engine")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/1")
MODEL_ROUTER_URL = os.getenv("MODEL_ROUTER_URL", "http://localhost:8002")
DB_URL = os.getenv("DB_URL", "postgresql+asyncpg://omniverso:omniverso_dev_2024@localhost:5432/omniverso")


async def process_task(ctx: dict, task_id: str) -> dict:
    """Process a single task by ID.

    1. Load task from DB
    2. Resolve agent and system prompt
    3. Call Model Router
    4. Store results
    """
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    engine = create_async_engine(DB_URL, pool_size=5)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Import here to avoid circular deps at module level
    from shared.models import Agent, Task

    async with SessionLocal() as db:
        # Load task
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            logger.error(f"Task {task_id} not found")
            return {"error": "task not found"}

        # Mark as running
        task.status = "running"
        task.started_at = datetime.utcnow()
        await db.commit()

        try:
            # Resolve agent
            agent = None
            if task.agent_id:
                result = await db.execute(select(Agent).where(Agent.id == task.agent_id))
                agent = result.scalar_one_or_none()

            # Build prompt
            messages = []
            if agent and agent.system_prompt:
                messages.append({"role": "system", "content": agent.system_prompt})

            task_prompt = f"Task: {task.title}\n"
            if task.description:
                task_prompt += f"Description: {task.description}\n"
            if task.input_data:
                task_prompt += f"Input Data: {task.input_data}\n"
            task_prompt += "\nProvide a complete, actionable response."
            messages.append({"role": "user", "content": task_prompt})

            # Call Model Router
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{MODEL_ROUTER_URL}/complete",
                    json={
                        "messages": messages,
                        "max_tokens": 4096,
                        "temperature": 0.7,
                    },
                )
                resp.raise_for_status()
                result_data = resp.json()

            # Update task with results
            task.status = "completed"
            task.output_data = {
                "response": result_data.get("content", ""),
                "model": result_data.get("model", ""),
                "provider": result_data.get("provider", ""),
                "tokens_in": result_data.get("tokens_in", 0),
                "tokens_out": result_data.get("tokens_out", 0),
                "cost_usd": result_data.get("cost_usd", 0),
            }
            task.completed_at = datetime.utcnow()

        except Exception as e:
            logger.exception(f"Task {task_id} failed")
            task.status = "failed"
            task.error_message = str(e)
            task.retry_count = (task.retry_count or 0) + 1

        await db.commit()

    await engine.dispose()
    return {"task_id": task_id, "status": task.status}


# ARQ worker settings
class WorkerSettings:
    """ARQ worker configuration."""

    redis_settings = None  # Set dynamically
    functions = [process_task]
    max_jobs = 10
    job_timeout = 300  # 5 minutes
    max_tries = 3

    @staticmethod
    async def on_startup(ctx: dict):
        logger.info("Task Engine worker started")

    @staticmethod
    async def on_shutdown(ctx: dict):
        logger.info("Task Engine worker stopped")


if __name__ == "__main__":
    # Standalone runner for development
    logging.basicConfig(level=logging.INFO)
    logger.info("Task Engine starting in standalone mode...")
    logger.info(f"Watching Redis at {REDIS_URL}")
    logger.info(f"Model Router at {MODEL_ROUTER_URL}")

    # Simple polling loop for dev (production uses ARQ)
    async def dev_loop():
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        engine = create_async_engine(DB_URL, pool_size=5)
        SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        # Lazy import
        import importlib
        import sys
        sys.path.insert(0, "/app")

        from shared.models import Task

        while True:
            try:
                async with SessionLocal() as db:
                    result = await db.execute(
                        select(Task)
                        .where(Task.status == "pending")
                        .order_by(Task.priority.desc(), Task.created_at.asc())
                        .limit(1)
                    )
                    task = result.scalar_one_or_none()
                    if task:
                        logger.info(f"Processing task: {task.id} - {task.title}")
                        await process_task({}, str(task.id))
                    else:
                        await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(10)

    asyncio.run(dev_loop())
