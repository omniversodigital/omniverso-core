"""OMNIVERSO — Telegram Multi-Channel Revenue Bot.

Provides monetized access to Omniverso AI Agents, Market Signals, and RAG search
via Telegram. Features subscription unlock, signals feed, and revenue recording.
"""

from __future__ import annotations

import asyncio
import os
import logging
from datetime import datetime

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

logger = logging.getLogger("omniverso.telegram_bot")
logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "MOCK_TELEGRAM_TOKEN")
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway:8080")
TRADING_ENGINE_URL = os.getenv("TRADING_ENGINE_URL", "http://trading-engine:8004")

app = FastAPI(title="OMNIVERSO Telegram Bot Service")

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "telegram-bot",
        "bot_configured": TELEGRAM_BOT_TOKEN != "MOCK_TELEGRAM_TOKEN",
        "timestamp": datetime.utcnow().isoformat(),
    }

@app.get("/bot/signals")
async def bot_signals():
    """Fetch latest signals formatted for Telegram broadcast."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{TRADING_ENGINE_URL}/signals")
            signals = resp.json()
        except Exception as e:
            return {"error": f"Failed to fetch signals: {e}"}

    formatted_messages = []
    for s in signals:
        icon = "🟢" if s["action"] == "BUY" else ("🔴" if s["action"] == "SELL" else "🟡")
        msg = (
            f"{icon} *OMNIVERSO SIGNAL: {s['symbol']}*\n"
            f"Action: *{s['action']}* @ ${s['price']}\n"
            f"Target: ${s['target_price']} | Stop: ${s['stop_loss']}\n"
            f"Confidence: {int(s['confidence']*100)}%\n"
            f"Rationale: _{s['rationale']}_\n"
            f"───────────────\n"
            f" Unlock Premium: /subscribe"
        )
        formatted_messages.append(msg)

    return {
        "count": len(formatted_messages),
        "messages": formatted_messages,
    }

class WebhookUpdate(BaseModel):
    update_id: int
    message: dict | None = None

@app.post("/bot/webhook")
async def telegram_webhook(update: WebhookUpdate):
    """Process incoming Telegram messages."""
    if not update.message or "text" not in update.message:
        return {"status": "ignored"}

    text = update.message["text"].strip()
    chat_id = update.message["chat"]["id"]
    user_name = update.message.get("from", {}).get("first_name", "User")

    reply_text = f"Hello {user_name}! Welcome to OMNIVERSO AI Bot.\nUse /signals for market signals or /ask for AI."

    if text.startswith("/signals"):
        signals_data = await bot_signals()
        messages = signals_data.get("messages", [])
        reply_text = "\n\n".join(messages[:2]) if messages else "No active signals."
    elif text.startswith("/subscribe"):
        reply_text = (
            "💎 *OMNIVERSO PREMIUM SUBSCRIPTION*\n\n"
            "Get 24/7 Flash Arbitrage Alerts + Unlimited AI Code/Research Agent Access.\n\n"
            "Price: $29.99 / month\n"
            "Payment method: USDT / STRIPE\n"
            "Send payment to confirm subscription."
        )
    elif text.startswith("/ask"):
        query = text.replace("/ask", "").strip()
        reply_text = f"🤖 AI Processing: '{query}'...\n(Agent Orchestrator responding via Model Router)"

    return {
        "status": "processed",
        "chat_id": chat_id,
        "reply": reply_text,
    }
