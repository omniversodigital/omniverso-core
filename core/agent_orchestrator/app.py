"""OMNIVERSO — Agent Orchestrator Service.

Central orchestration layer for managing AI agents, conversations, and tasks.
Routes requests to the appropriate agent, manages context, and tracks execution.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from shared.config import get_settings
from shared.database import close_db, get_db
from shared.models import Agent, Task


# ═══════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════

class AgentCreate(BaseModel):
    name: str
    description: str | None = None
    agent_type: str = "general"
    system_prompt: str | None = None
    model_config_: dict = Field(default_factory=dict, alias="model_config")
    tools: list[str] = Field(default_factory=list)


class AgentResponse(BaseModel):
    id: str
    name: str
    description: str | None
    agent_type: str
    tools: list[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    agent_name: str | None = None
    title: str
    description: str | None = None
    input_data: dict = Field(default_factory=dict)
    priority: int = 5


class TaskResponse(BaseModel):
    id: str
    title: str
    status: str
    priority: int
    output_data: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    agent_name: str = "Research Agent"
    message: str
    context: dict = Field(default_factory=dict)
    model: str | None = None
    stream: bool = False


class ChatResponse(BaseModel):
    id: str
    agent: str
    response: str
    model_used: str
    tokens_in: int
    tokens_out: int
    latency_ms: int


# ═══════════════════════════════════════════════════════════
# Application
# ═══════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    settings = get_settings()
    app.state.http_client = httpx.AsyncClient(
        base_url=settings.model_router_url,
        timeout=60.0,
    )
    yield
    await app.state.http_client.aclose()
    await close_db()





# ═══════════════════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "agent-orchestrator",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


# ═══════════════════════════════════════════════════════════
# Agent Endpoints
# ═══════════════════════════════════════════════════════════

@app.get("/agents", response_model=list[AgentResponse])
async def list_agents():
    """List all registered agents."""
    async with get_db() as db:
        result = await db.execute(
            select(Agent).where(Agent.is_active.is_(True)).order_by(Agent.name)
        )
        agents = result.scalars().all()
        return [
            AgentResponse(
                id=str(a.id), name=a.name, description=a.description,
                agent_type=a.agent_type, tools=a.tools or [],
                is_active=a.is_active, created_at=a.created_at,
            )
            for a in agents
        ]


@app.post("/agents", response_model=AgentResponse, status_code=201)
async def create_agent(data: AgentCreate):
    """Register a new agent."""
    async with get_db() as db:
        agent = Agent(
            name=data.name,
            description=data.description,
            agent_type=data.agent_type,
            system_prompt=data.system_prompt,
            model_config_=data.model_config_ if data.model_config_ else {},
            tools=data.tools,
        )
        db.add(agent)
        await db.flush()
        return AgentResponse(
            id=str(agent.id), name=agent.name, description=agent.description,
            agent_type=agent.agent_type, tools=agent.tools or [],
            is_active=agent.is_active, created_at=agent.created_at,
        )


@app.get("/agents/{agent_name}")
async def get_agent(agent_name: str):
    """Get agent details by name."""
    async with get_db() as db:
        result = await db.execute(select(Agent).where(Agent.name == agent_name))
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
        return AgentResponse(
            id=str(agent.id), name=agent.name, description=agent.description,
            agent_type=agent.agent_type, tools=agent.tools or [],
            is_active=agent.is_active, created_at=agent.created_at,
        )


# ═══════════════════════════════════════════════════════════
# Chat / Completion Endpoint
# ═══════════════════════════════════════════════════════════

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message to an agent and get a response via Model Router."""
    import time

    # Resolve agent
    async with get_db() as db:
        result = await db.execute(
            select(Agent).where(Agent.name == request.agent_name)
        )
        agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{request.agent_name}' not found")

    # Build messages for the model
    messages = []
    if agent.system_prompt:
        messages.append({"role": "system", "content": agent.system_prompt})
    messages.append({"role": "user", "content": request.message})

    # Call Model Router
    start = time.monotonic()
    try:
        response = await app.state.http_client.post(
            "/complete",
            json={
                "messages": messages,
                "model": request.model or get_settings().default_model,
                "provider": get_settings().default_provider,
                "max_tokens": 4096,
            },
        )
        response.raise_for_status()
        result_data = response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Model Router error: {str(e)}")

    latency = int((time.monotonic() - start) * 1000)

    return ChatResponse(
        id=str(uuid.uuid4()),
        agent=agent.name,
        response=result_data.get("content", ""),
        model_used=result_data.get("model", "unknown"),
        tokens_in=result_data.get("tokens_in", 0),
        tokens_out=result_data.get("tokens_out", 0),
        latency_ms=latency,
    )


# ═══════════════════════════════════════════════════════════
# Task Endpoints
# ═══════════════════════════════════════════════════════════

@app.post("/tasks", response_model=TaskResponse, status_code=201)
async def create_task(data: TaskCreate):
    """Create a new task for an agent."""
    async with get_db() as db:
        task = Task(
            title=data.title,
            description=data.description,
            input_data=data.input_data,
            priority=data.priority,
            status="pending",
        )

        if data.agent_name:
            result = await db.execute(
                select(Agent).where(Agent.name == data.agent_name)
            )
            agent = result.scalar_one_or_none()
            if agent:
                task.agent_id = agent.id

        db.add(task)
        await db.flush()
        return TaskResponse(
            id=str(task.id), title=task.title, status=task.status,
            priority=task.priority, output_data=task.output_data or {},
            created_at=task.created_at,
        )


@app.get("/tasks", response_model=list[TaskResponse])
async def list_tasks(status: str | None = None, limit: int = 50):
    """List tasks with optional status filter."""
    async with get_db() as db:
        query = select(Task).order_by(Task.created_at.desc()).limit(limit)
        if status:
            query = query.where(Task.status == status)
        result = await db.execute(query)
        tasks = result.scalars().all()
        return [
            TaskResponse(
                id=str(t.id), title=t.title, status=t.status,
                priority=t.priority, output_data=t.output_data or {},
                created_at=t.created_at,
            )
            for t in tasks
        ]


# ═══════════════════════════════════════════════════════════
# Stats
# ═══════════════════════════════════════════════════════════

@app.get("/stats")
async def get_stats():
    """Get ecosystem statistics."""
    from sqlalchemy import func as sqlfunc

    async with get_db() as db:
        agents_count = (await db.execute(
            select(sqlfunc.count()).select_from(Agent).where(Agent.is_active.is_(True))
        )).scalar() or 0

        tasks_count = (await db.execute(
            select(sqlfunc.count()).select_from(Task)
        )).scalar() or 0

        pending_tasks = (await db.execute(
            select(sqlfunc.count()).select_from(Task).where(Task.status == "pending")
        )).scalar() or 0

    return {
        "agents_active": agents_count,
        "tasks_total": tasks_count,
        "tasks_pending": pending_tasks,
        "timestamp": datetime.utcnow().isoformat(),
    }
