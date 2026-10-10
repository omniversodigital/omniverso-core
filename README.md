# 🌌 OMNIVERSO Platform Core
### Distributed Autonomous Bots, Microservice Gateways & Unified Management Plane

[![Go](https://img.shields.io/badge/Go-API_Gateway-00ADD8?logo=go&logoColor=white)](https://go.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Microservices-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-Command_Center-61dafb?logo=react&logoColor=black)](https://react.dev/)
[![Docker](https://img.shields.io/badge/Docker-Full_Orchestration-2496ed?logo=docker&logoColor=white)](https://docker.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16_Relational-336791?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector_Engine-dc2626?logo=qdrant&logoColor=white)](https://qdrant.tech/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **Omniverso Core:** Enterprise AI Ecosystem — Modular, Scalable, Distributed & High-Throughput. Built and maintained by **Omniverso Digital**.

## Quick Start

```bash
# 1. Copy env file and configure API keys
cp .env.example .env
# Edit .env with your API keys

# 2. Start everything
docker compose up -d

# 3. Verify health
make health

# 4. Open Command Center
# http://localhost:3000
```

## Architecture

```
omniverso/
├── gateway/              → Go API Gateway (:8080)
├── core/
│   ├── shared/           → Python shared library
│   ├── agent_orchestrator/ → Agent management (:8001)
│   ├── model_router/     → Multi-provider AI routing (:8002)
│   └── task_engine/      → Background task worker
├── web/command-center/   → React dashboard (:3000)
├── data/migrations/      → PostgreSQL schemas
└── docker-compose.yml    → Full stack orchestration
```

## Services

| Service | Port | Stack | Description |
|---------|------|-------|-------------|
| Gateway | 8080 | Go + Chi | Auth, rate limiting, reverse proxy |
| Orchestrator | 8001 | Python + FastAPI | Agent CRUD, chat, tasks |
| Model Router | 8002 | Python + FastAPI | Multi-provider AI routing |
| Task Worker | — | Python + ARQ | Background task processing |
| Command Center | 3000 | React + Vite | Dashboard UI |
| PostgreSQL | 5432 | postgres:16 | Primary database |
| Redis | 6379 | redis:7 | Cache + queues |
| Qdrant | 6333 | qdrant | Vector search |

## API Endpoints

### Public
- `GET /health` — Gateway health
- `GET /ready` — Full readiness check
- `POST /auth/login` — Get JWT token
- `POST /auth/register` — Register user

### Authenticated (Bearer JWT)
- `GET /api/v1/agents` — List agents
- `POST /api/v1/agents` — Create agent
- `POST /api/v1/agents/chat` — Chat with agent
- `POST /api/v1/agents/tasks` — Create task
- `GET /api/v1/models/providers` — List AI providers
- `POST /api/v1/models/complete` — Model completion
- `GET /api/v1/status` — Ecosystem status

### API Key (X-API-Key header)
- All `/api/ext/v1/*` routes — External consumer access

## Operations

```bash
make up          # Start all services
make down        # Stop all services
make logs        # Tail logs
make health      # Check all services
make db-shell    # PostgreSQL CLI
make redis-shell # Redis CLI
make build       # Rebuild all images
make clean       # Remove everything (destructive)
```

## Tech Stack

- **Gateway**: Go 1.24, Chi router, JWT, Redis rate limiter
- **Services**: Python 3.13, FastAPI, SQLAlchemy async, Pydantic v2
- **Data**: PostgreSQL 16, Redis 7, Qdrant (vectors)
- **Frontend**: React 19, Vite 6, custom dark theme
- **Infra**: Docker Compose (local), GKE Autopilot (production)
- **AI**: Gemini, OpenAI, Anthropic, OpenRouter (multi-provider)

## License

Proprietary — OMNIVERSO Digital
