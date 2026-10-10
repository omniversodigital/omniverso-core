"""OMNIVERSO — Model Router Service.

Intelligent routing layer that abstracts multiple AI model providers behind
a unified API. Supports Gemini, OpenAI, Anthropic, and OpenRouter with
automatic fallback, cost tracking, and caching.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════

import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/2")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "gemini")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-2.5-flash")

# Cost per 1M tokens (input/output) in USD
PRICING = {
    "gemini": {
        "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
        "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
        "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    },
    "openai": {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
    },
    "anthropic": {
        "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
        "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    },
}

# Provider API endpoints
ENDPOINTS = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


# ═══════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════

class CompletionRequest(BaseModel):
    messages: list[dict[str, str]]
    model: str | None = None
    provider: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.7
    cache_ttl: int = 0  # seconds, 0 = no cache


class CompletionResponse(BaseModel):
    id: str
    content: str
    model: str
    provider: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    cached: bool = False


class ProviderStatus(BaseModel):
    name: str
    available: bool
    models: list[str]


# ═══════════════════════════════════════════════════════════
# Application
# ═══════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    app.state.http = httpx.AsyncClient(timeout=120.0)
    yield
    await app.state.http.aclose()
    await app.state.redis.aclose()


app = FastAPI(
    title="OMNIVERSO Model Router",
    version="1.0.0",
    lifespan=lifespan,
)


# ═══════════════════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "model-router",
        "version": "1.0.0",
        "providers": get_available_providers(),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/providers", response_model=list[ProviderStatus])
async def list_providers():
    """List all configured providers and their available models."""
    providers = []
    for name, key_var in [
        ("gemini", GEMINI_API_KEY),
        ("openai", OPENAI_API_KEY),
        ("anthropic", ANTHROPIC_API_KEY),
        ("openrouter", OPENROUTER_API_KEY),
    ]:
        providers.append(ProviderStatus(
            name=name,
            available=bool(key_var),
            models=list(PRICING.get(name, {}).keys()) if key_var else [],
        ))
    return providers


# ═══════════════════════════════════════════════════════════
# Completion Endpoint
# ═══════════════════════════════════════════════════════════

@app.post("/complete", response_model=CompletionResponse)
async def complete(request: CompletionRequest):
    """Route completion request to the best available provider."""
    provider = request.provider or DEFAULT_PROVIDER
    model = request.model or DEFAULT_MODEL

    # Check cache
    if request.cache_ttl > 0:
        cache_key = _cache_key(request.messages, model)
        cached = await app.state.redis.get(cache_key)
        if cached:
            data = json.loads(cached)
            data["cached"] = True
            return CompletionResponse(**data)

    # Validate provider availability
    available = get_available_providers()
    if provider not in available:
        # Fallback chain
        for fallback in ["gemini", "openai", "anthropic", "openrouter"]:
            if fallback in available:
                provider = fallback
                model = _default_model_for(provider)
                break
        else:
            raise HTTPException(
                status_code=503,
                detail="No AI providers configured. Set at least one API key.",
            )

    # Execute completion
    start = time.monotonic()
    try:
        if provider == "gemini":
            result = await _call_gemini(request.messages, model, request.max_tokens, request.temperature)
        elif provider == "openai":
            result = await _call_openai(request.messages, model, request.max_tokens, request.temperature)
        elif provider == "anthropic":
            result = await _call_anthropic(request.messages, model, request.max_tokens, request.temperature)
        elif provider == "openrouter":
            result = await _call_openrouter(request.messages, model, request.max_tokens, request.temperature)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Provider error: {str(e)}")

    latency = int((time.monotonic() - start) * 1000)

    # Calculate cost
    pricing = PRICING.get(provider, {}).get(model, {"input": 0, "output": 0})
    cost = (result["tokens_in"] * pricing["input"] + result["tokens_out"] * pricing["output"]) / 1_000_000

    response_data = {
        "id": str(uuid.uuid4()),
        "content": result["content"],
        "model": model,
        "provider": provider,
        "tokens_in": result["tokens_in"],
        "tokens_out": result["tokens_out"],
        "cost_usd": round(cost, 6),
        "latency_ms": latency,
        "cached": False,
    }

    # Cache if requested
    if request.cache_ttl > 0:
        cache_key = _cache_key(request.messages, model)
        await app.state.redis.setex(cache_key, request.cache_ttl, json.dumps(response_data))

    # Track usage
    await _track_usage(provider, model, result["tokens_in"], result["tokens_out"], cost, latency)

    return CompletionResponse(**response_data)


# ═══════════════════════════════════════════════════════════
# Provider Implementations
# ═══════════════════════════════════════════════════════════

async def _call_gemini(messages: list[dict], model: str, max_tokens: int, temperature: float) -> dict:
    """Call Google Gemini API."""
    # Convert messages to Gemini format
    contents = []
    system_instruction = None
    for msg in messages:
        if msg["role"] == "system":
            system_instruction = msg["content"]
        else:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    body: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        },
    }
    if system_instruction:
        body["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    url = f"{ENDPOINTS['gemini']}/models/{model}:generateContent?key={GEMINI_API_KEY}"
    resp = await app.state.http.post(url, json=body)
    resp.raise_for_status()
    data = resp.json()

    content = data["candidates"][0]["content"]["parts"][0]["text"]
    usage = data.get("usageMetadata", {})

    return {
        "content": content,
        "tokens_in": usage.get("promptTokenCount", 0),
        "tokens_out": usage.get("candidatesTokenCount", 0),
    }


async def _call_openai(messages: list[dict], model: str, max_tokens: int, temperature: float) -> dict:
    """Call OpenAI API."""
    resp = await app.state.http.post(
        f"{ENDPOINTS['openai']}/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        json={
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
    )
    resp.raise_for_status()
    data = resp.json()

    return {
        "content": data["choices"][0]["message"]["content"],
        "tokens_in": data["usage"]["prompt_tokens"],
        "tokens_out": data["usage"]["completion_tokens"],
    }


async def _call_anthropic(messages: list[dict], model: str, max_tokens: int, temperature: float) -> dict:
    """Call Anthropic Claude API."""
    system = None
    filtered = []
    for msg in messages:
        if msg["role"] == "system":
            system = msg["content"]
        else:
            filtered.append(msg)

    body: dict[str, Any] = {
        "model": model,
        "messages": filtered,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if system:
        body["system"] = system

    resp = await app.state.http.post(
        f"{ENDPOINTS['anthropic']}/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        json=body,
    )
    resp.raise_for_status()
    data = resp.json()

    return {
        "content": data["content"][0]["text"],
        "tokens_in": data["usage"]["input_tokens"],
        "tokens_out": data["usage"]["output_tokens"],
    }


async def _call_openrouter(messages: list[dict], model: str, max_tokens: int, temperature: float) -> dict:
    """Call OpenRouter API (OpenAI-compatible)."""
    resp = await app.state.http.post(
        f"{ENDPOINTS['openrouter']}/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://omniverso.digital",
            "X-Title": "Omniverso",
        },
        json={
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
    )
    resp.raise_for_status()
    data = resp.json()

    return {
        "content": data["choices"][0]["message"]["content"],
        "tokens_in": data.get("usage", {}).get("prompt_tokens", 0),
        "tokens_out": data.get("usage", {}).get("completion_tokens", 0),
    }


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def get_available_providers() -> list[str]:
    providers = []
    if GEMINI_API_KEY:
        providers.append("gemini")
    if OPENAI_API_KEY:
        providers.append("openai")
    if ANTHROPIC_API_KEY:
        providers.append("anthropic")
    if OPENROUTER_API_KEY:
        providers.append("openrouter")
    return providers


def _default_model_for(provider: str) -> str:
    defaults = {
        "gemini": "gemini-2.5-flash",
        "openai": "gpt-4o-mini",
        "anthropic": "claude-3-5-haiku-20241022",
        "openrouter": "google/gemini-2.5-flash",
    }
    return defaults.get(provider, DEFAULT_MODEL)


def _cache_key(messages: list[dict], model: str) -> str:
    raw = json.dumps({"messages": messages, "model": model}, sort_keys=True)
    return f"mr:cache:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


async def _track_usage(provider: str, model: str, tokens_in: int, tokens_out: int, cost: float, latency: int):
    """Track model usage in Redis for analytics."""
    try:
        pipe = app.state.redis.pipeline()
        today = datetime.utcnow().strftime("%Y-%m-%d")
        key = f"mr:usage:{today}"
        pipe.hincrby(key, f"{provider}:{model}:calls", 1)
        pipe.hincrby(key, f"{provider}:{model}:tokens_in", tokens_in)
        pipe.hincrby(key, f"{provider}:{model}:tokens_out", tokens_out)
        pipe.hincrbyfloat(key, f"{provider}:{model}:cost", cost)
        pipe.expire(key, 86400 * 30)  # Keep 30 days
        await pipe.execute()
    except Exception:
        pass  # Non-critical — don't fail requests for tracking errors


@app.get("/usage")
async def get_usage():
    """Get today's model usage stats."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    key = f"mr:usage:{today}"
    data = await app.state.redis.hgetall(key)
    return {"date": today, "usage": data}
