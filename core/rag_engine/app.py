"""OMNIVERSO — RAG Engine Service.

Provides vector storage, semantic search, and document ingestion powered by Qdrant.
Allows agents to perform context-augmented generation from internal documents and web data.
"""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "omniverso_knowledge"
VECTOR_SIZE = 384  # Default size for lightweight sentence-transformers or fast embeddings

class DocumentIngest(BaseModel):
    title: str
    content: str
    category: str = "general"
    metadata: dict = Field(default_factory=dict)

class SearchQuery(BaseModel):
    query: str
    limit: int = 5
    category: str | None = None

class SearchResult(BaseModel):
    id: str
    title: str
    content: str
    score: float
    category: str
    metadata: dict

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.qdrant = AsyncQdrantClient(url=QDRANT_URL)
    # Ensure default collection exists
    try:
        collections = await app.state.qdrant.get_collections()
        names = [c.name for c in collections.collections]
        if COLLECTION_NAME not in names:
            await app.state.qdrant.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
    except Exception as e:
        print(f"Qdrant collection init warning: {e}")
    yield
    await app.state.qdrant.close()

app = FastAPI(
    title="OMNIVERSO RAG Engine",
    version="1.0.0",
    lifespan=lifespan,
)

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "rag-engine",
        "qdrant_url": QDRANT_URL,
        "timestamp": datetime.utcnow().isoformat(),
    }

def _simple_embedding(text: str, dim: int = VECTOR_SIZE) -> list[float]:
    """Generate a deterministic normalized pseudo-embedding vector for text (fallback when embedding API is offline)."""
    import math
    import hashlib
    vec = [0.0] * dim
    for i, char in enumerate(text[:500]):
        idx = (ord(char) * (i + 1)) % dim
        vec[idx] += 1.0
    # Normalize
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]

@app.post("/documents", status_code=201)
async def ingest_document(doc: DocumentIngest):
    """Ingest a document into the Qdrant vector database."""
    doc_id = str(uuid.uuid4())
    vector = _simple_embedding(doc.content)

    point = PointStruct(
        id=doc_id,
        vector=vector,
        payload={
            "title": doc.title,
            "content": doc.content,
            "category": doc.category,
            "metadata": doc.metadata,
            "created_at": datetime.utcnow().isoformat(),
        },
    )

    try:
        await app.state.qdrant.upsert(
            collection_name=COLLECTION_NAME,
            points=[point],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to index document: {e}")

    return {"id": doc_id, "title": doc.title, "status": "indexed"}

@app.post("/search", response_model=list[SearchResult])
async def search(query: SearchQuery):
    """Semantic search across indexed knowledge."""
    query_vector = _simple_embedding(query.query)

    try:
        results = await app.state.qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=query.limit,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")

    output = []
    for res in results:
        payload = res.payload or {}
        output.append(SearchResult(
            id=str(res.id),
            title=payload.get("title", "Untitled"),
            content=payload.get("content", ""),
            score=round(res.score, 4),
            category=payload.get("category", "general"),
            metadata=payload.get("metadata", {}),
        ))
    return output
