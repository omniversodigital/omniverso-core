# ═══════════════════════════════════════════════════════════
# OMNIVERSO ECOSYSTEM — Makefile
# ═══════════════════════════════════════════════════════════

.PHONY: help up down restart logs ps build clean db-shell redis-shell test health

# Default
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Docker Operations ───────────────────────────────────
up: ## Start all services
	docker compose up -d
	@echo "\n✅ OMNIVERSO ecosystem running"
	@echo "   Gateway:    http://localhost:8080"
	@echo "   Web UI:     http://localhost:3000"
	@echo "   Qdrant:     http://localhost:6333/dashboard"

down: ## Stop all services
	docker compose down

restart: ## Restart all services
	docker compose restart

build: ## Rebuild all images
	docker compose build --no-cache

logs: ## Tail all logs
	docker compose logs -f --tail=50

ps: ## Show running services
	docker compose ps

clean: ## Stop and remove all data (DESTRUCTIVE)
	docker compose down -v --remove-orphans
	docker system prune -f

# ─── Individual Services ─────────────────────────────────
up-data: ## Start only data services
	docker compose up -d postgres redis qdrant

up-core: ## Start data + core services
	docker compose up -d postgres redis qdrant gateway orchestrator model-router

# ─── Database ────────────────────────────────────────────
db-shell: ## Open psql shell
	docker compose exec postgres psql -U omniverso

db-migrate: ## Run migrations
	docker compose exec postgres psql -U omniverso -f /docker-entrypoint-initdb.d/001_init.sql

# ─── Redis ────────────────────────────────────────────────
redis-shell: ## Open redis-cli
	docker compose exec redis redis-cli

# ─── Health Check ────────────────────────────────────────
health: ## Check all service health
	@echo "=== OMNIVERSO Health Check ==="
	@echo -n "PostgreSQL: " && docker compose exec -T postgres pg_isready -U omniverso 2>/dev/null && echo "✅" || echo "❌"
	@echo -n "Redis:      " && docker compose exec -T redis redis-cli ping 2>/dev/null || echo "❌"
	@echo -n "Qdrant:     " && curl -sf http://localhost:6333/readyz 2>/dev/null && echo " ✅" || echo "❌"
	@echo -n "Gateway:    " && curl -sf http://localhost:8080/health 2>/dev/null && echo " ✅" || echo "❌"
	@echo -n "Orchestr.:  " && curl -sf http://localhost:8001/health 2>/dev/null && echo " ✅" || echo "❌"
	@echo -n "ModelRouter:" && curl -sf http://localhost:8002/health 2>/dev/null && echo " ✅" || echo "❌"
	@echo -n "Web UI:     " && curl -sf http://localhost:3000 2>/dev/null && echo " ✅" || echo "❌"

# ─── Development ─────────────────────────────────────────
gateway-dev: ## Run gateway in dev mode
	cd gateway && go run .

test: ## Run all tests
	cd gateway && go test ./...
	cd core && python -m pytest tests/ -v
