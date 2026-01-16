.PHONY: help install install-backend install-frontend dev sync clean migrate migrate-auto migrate-down test test-cov run-backend run-frontend run docker-build docker-up docker-down docker-logs scrape-reddit train-models backtest lint format shell

# Default target
help:
	@echo "Available commands:"
	@echo ""
	@echo "Setup:"
	@echo "  make install         - Install all dependencies (backend + frontend)"
	@echo "  make dev             - Install dev dependencies"
	@echo "  make sync            - Sync uv dependencies"
	@echo "  make clean           - Remove cache and temporary files"
	@echo ""
	@echo "Database:"
	@echo "  make migrate         - Run database migrations"
	@echo "  make migrate-auto    - Create new migration (msg='description')"
	@echo "  make migrate-down    - Rollback last migration"
	@echo ""
	@echo "Run:"
	@echo "  make run-backend     - Start FastAPI backend server"
	@echo "  make run-frontend    - Start Next.js frontend"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up       - Start docker containers"
	@echo "  make docker-down     - Stop docker containers"
	@echo "  make docker-logs     - View docker logs"
	@echo ""
	@echo "Data & ML:"
	@echo "  make scrape-reddit   - Run Reddit scraper (one-time)"
	@echo "  make scrape-scheduled - Run automated scheduled scraper"
	@echo "  make scrape-once     - Test scraper (single run)"
	@echo "  make train-models    - Train ML models"
	@echo "  make backtest        - Run backtesting"
	@echo "  make backtest        - Run backtesting"
	@echo ""
	@echo "Code Quality:"
	@echo "  make test            - Run tests"
	@echo "  make test-cov        - Run tests with coverage"
	@echo "  make lint            - Run linting"
	@echo "  make format          - Format code"
	@echo "  make shell           - Open Python shell with models loaded"

# Installation
install: install-backend install-frontend

install-backend:
	uv pip install -r requirements.txt

install-frontend:
	cd frontend && npm install

dev:
	uv pip install -r requirements-dev.txt

sync:
	uv sync

# Clean
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	rm -rf .coverage htmlcov/

# Database Migrations
migrate:
	uv run alembic upgrade head

migrate-auto:
	uv run alembic revision --autogenerate -m "$(msg)"

migrate-down:
	uv run alembic downgrade -1

# Run Application
app:
	@if [ ! -s backend/api/main.py ]; then \
		echo "❌ Error: backend/api/main.py is empty. Create FastAPI app first."; \
		exit 1; \
	fi
	uv run uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

# Docker
docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

# Data Collection & ML
scrape-reddit:
	uv run python scripts/scrape_reddit.py

scrape-scheduled:
	uv run python scripts/scheduled_scraper.py

scrape-once:
	uv run python scripts/scheduled_scraper.py --once

train-models:
	uv run python scripts/train_models.py

backtest:
	uv run python scripts/backtest.py

# Testing
test:
	uv run pytest tests/ -v

test-cov:
	uv run pytest tests/ --cov=backend --cov-report=html --cov-report=term

# Code Quality
lint:
	@echo "Linting backend..."
	@uv run ruff check backend/
	@echo "Linting scripts..."
	@uv run ruff check scripts/

format:
	@echo "Formatting backend..."
	@uv run ruff format backend/
	@echo "Formatting scripts..."
	@uv run ruff format scripts/

# Database Shell (requires psql installed)
db-shell:
	@if [ -z "$$DATABASE_URL" ]; then \
		echo "❌ Error: DATABASE_URL not set. Check your .env file."; \
		exit 1; \
	fi
	psql "$$DATABASE_URL"

# Python Shell
shell:
	uv run python -i -c "from backend.database.config import Base, engine; from backend.models.reddit import RedditPost; print('✓ Models loaded')"
