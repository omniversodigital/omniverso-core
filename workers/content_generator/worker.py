"""OMNIVERSO — Automated Content & SEO Generator Worker.

Generates high-ranking SEO content, technical guides, and market synthesis articles
powered by Model Router. Publishes structured articles and records content revenue potential.
"""

from __future__ import annotations

import asyncio
import logging
import os

import httpx

logger = logging.getLogger("omniverso.content_generator")
logging.basicConfig(level=logging.INFO)

MODEL_ROUTER_URL = os.getenv("MODEL_ROUTER_URL", "http://model-router:8002")

ARTICLE_TOPICS = [
    "Maximizing Yield with Automated Arbitrage on Solana and Ethereum",
    "Building High-Agency AI Agents using FastAPI and Vector Databases",
    "Zero-Cap Flash Loans: Complete Guide to DEX Risk Management",
    "Modern Microservices in Go: Ultra-Low Latency API Gateways",
]

async def generate_article(topic: str) -> dict:
    """Generate a full-length SEO optimized technical article."""
    prompt = (
        f"Write a comprehensive, professional, SEO-optimized guide on: '{topic}'.\n"
        f"Include an Executive Summary, Key Architecture Points, Code Examples, and FAQ."
    )

    logger.info(f"Generating article for topic: '{topic}'...")

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.post(
                f"{MODEL_ROUTER_URL}/complete",
                json={
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 4096,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "topic": topic,
                "content": data.get("content", ""),
                "model_used": data.get("model", ""),
                "provider": data.get("provider", ""),
            }
        except Exception as e:
            logger.error(f"Failed to generate article: {e}")
            return {"topic": topic, "error": str(e)}

if __name__ == "__main__":
    logger.info("Content Generator Worker initialized.")
    # Quick test run for initial topic
    res = asyncio.run(generate_article(ARTICLE_TOPICS[0]))
    logger.info(f"Worker output sample length: {len(res.get('content', ''))} characters")
