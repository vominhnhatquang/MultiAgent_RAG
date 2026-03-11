# ─── RAG Chatbot Makefile ─────────────────────────────────────────────────────
# Requires: docker, docker compose v2, make
.PHONY: up down logs init health backup clean build rebuild dev shell ps pull docker-start check-docker

COMPOSE      := docker compose
COMPOSE_DEV  := docker compose -f docker-compose.yml -f docker-compose.dev.yml
ENV_FILE     := .env

# Load .env if present
ifneq (,$(wildcard $(ENV_FILE)))
    include $(ENV_FILE)
    export
endif

# ─── Docker Daemon ────────────────────────────────────────────────────────────

## check-docker: Verify Docker daemon is running
check-docker:
	@docker info > /dev/null 2>&1 || (echo "ERROR: Docker daemon not running. Run 'make docker-start' first." && exit 1)

## docker-start: Start Docker daemon (WSL2 without systemd)
docker-start:
	@echo "Starting Docker daemon (WSL2)..."
	@sudo service docker start || sudo dockerd &
	@sleep 3
	@docker info > /dev/null 2>&1 && echo "Docker daemon started." || echo "Failed — check sudo permissions."

# ─── Production ───────────────────────────────────────────────────────────────

## up: Start all services in production mode (detached)
up:
	@echo "Starting RAG Chatbot (production)..."
	$(COMPOSE) up -d
	@echo "Services started. Run 'make health' to verify."

## down: Stop all services (keep volumes)
down:
	@echo "Stopping services..."
	$(COMPOSE) down

## down-v: Stop all services and remove volumes (DESTRUCTIVE)
down-v:
	@echo "⚠ Removing all containers AND volumes..."
	$(COMPOSE) down -v

## logs: Follow logs from all services
logs:
	$(COMPOSE) logs -f

## logs-SERVICE: Follow logs from a specific service (e.g. make logs-backend)
logs-%:
	$(COMPOSE) logs -f $*

## ps: Show running containers
ps:
	$(COMPOSE) ps

## pull: Pull latest images
pull:
	$(COMPOSE) pull

# ─── Build ────────────────────────────────────────────────────────────────────

## build: Build all custom Docker images
build:
	@echo "Building images..."
	$(COMPOSE) build --parallel

## rebuild: Force rebuild without cache
rebuild:
	@echo "Rebuilding images (no cache)..."
	$(COMPOSE) build --no-cache --parallel

# ─── Initialization ───────────────────────────────────────────────────────────

## init: Build images, start services, verify Ollama models
init:
	@$(COMPOSE) up -d --build
	@bash infra/scripts/init-ollama.sh http://localhost:11434
	@echo ""
	@bash infra/scripts/health-check.sh --wait

## init-ollama: Pull Ollama models only (services must be running)
init-ollama:
	@bash infra/scripts/init-ollama.sh http://localhost:11434

## migrate: Run database migrations
migrate:
	$(COMPOSE) exec backend alembic upgrade head

# ─── Health & Monitoring ──────────────────────────────────────────────────────

## health: Run health checks for all services
health:
	@bash infra/scripts/health-check.sh

## ram: Show RAM usage per container
ram:
	@python3 infra/monitoring/check_ram.py

## ram-watch: Watch RAM usage (refresh every 5s)
ram-watch:
	@python3 infra/monitoring/check_ram.py --interval 5

## stats: Show docker stats
stats:
	docker stats $(shell docker ps --filter "name=rag_" --format "{{.Names}}" | tr '\n' ' ')

# ─── Database ─────────────────────────────────────────────────────────────────

## backup: Backup PostgreSQL + Qdrant
backup:
	@bash infra/scripts/backup-db.sh

## restore: Restore from backup — Usage: make restore BACKUP=./data/backups/rag_backup_XYZ.tar.gz
restore:
	@bash infra/scripts/restore-db.sh $(BACKUP)

# ─── Development ──────────────────────────────────────────────────────────────

## dev: Start in development mode (hot reload, debug ports)
dev:
	@echo "Starting RAG Chatbot (development)..."
	$(COMPOSE_DEV) up

## dev-d: Start in development mode (detached)
dev-d:
	$(COMPOSE_DEV) up -d

## shell-backend: Open shell in backend container
shell-backend:
	$(COMPOSE) exec backend bash

## shell-postgres: Open psql in postgres container
shell-postgres:
	$(COMPOSE) exec postgres psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)

## shell-redis: Open redis-cli in redis container
shell-redis:
	$(COMPOSE) exec redis redis-cli

# ─── Tunnel ───────────────────────────────────────────────────────────────────

## tunnel: Setup Cloudflare Tunnel for public access
tunnel:
	@bash infra/scripts/tunnel-setup.sh cloudflare

## tunnel-ngrok: Setup ngrok tunnel (alternative)
tunnel-ngrok:
	@bash infra/scripts/tunnel-setup.sh ngrok

# ─── Cleanup ──────────────────────────────────────────────────────────────────

## clean: Remove dangling images, stopped containers, temp files
clean:
	@bash infra/scripts/cleanup.sh

## clean-full: Full cleanup including unused volumes
clean-full:
	@bash infra/scripts/cleanup.sh --full

# ─── Swap ─────────────────────────────────────────────────────────────────────

## swap: Create 2GB swap file (OOM backup, run once on host)
swap:
	@echo "Creating 2GB swap file at /swapfile..."
	@sudo fallocate -l 2G /swapfile && \
	 sudo chmod 600 /swapfile && \
	 sudo mkswap /swapfile && \
	 sudo swapon /swapfile && \
	 echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
	@echo "Swap created and enabled."

# ─── Help ─────────────────────────────────────────────────────────────────────

## help: Show this help
help:
	@grep -E '^## ' Makefile | sed 's/## //' | column -t -s ':'

.DEFAULT_GOAL := help
