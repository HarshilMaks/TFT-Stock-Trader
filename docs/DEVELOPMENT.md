# TFT Trader — Local Development Setup Guide

**Version**: 1.0  
**Last Updated**: 2026-02-15  
**Audience**: Developers setting up local environment

---

## Table of Contents

1. [Quick Start (5 minutes)](#quick-start-5-minutes)
2. [Prerequisites](#prerequisites)
3. [Environment Setup](#environment-setup)
4. [Starting the Dev Environment](#starting-the-dev-environment)
5. [Running Migrations](#running-migrations)
6. [Common Commands](#common-commands)
7. [Monitoring & Debugging](#monitoring--debugging)
8. [Troubleshooting](#troubleshooting)
9. [Stopping & Cleaning](#stopping--cleaning)

---

## Quick Start (5 minutes)

For experienced developers, here's the TL;DR:

```bash
# 1. Clone and setup
git clone <repo-url>
cd tft-trader
cp .env.example .env  # Edit if needed (defaults work for local dev)

# 2. Start all services
docker-compose -f docker/docker-compose.dev.yml up -d

# 3. Wait for services to be healthy
docker-compose -f docker/docker-compose.dev.yml ps

# 4. Run migrations
docker-compose -f docker/docker-compose.dev.yml exec celery_worker \
  alembic upgrade head

# 5. View logs
docker-compose -f docker/docker-compose.dev.yml logs -f

# Done! Services are running. See "Common Commands" below.
```

---

## Prerequisites

Before you start, ensure you have:

### Required
- **Docker** (version 20.10+)  
  - Check: `docker --version`
  - Install: [docker.com/install](https://www.docker.com/products/docker-desktop)

- **Docker Compose** (version 2.0+, usually included with Docker Desktop)  
  - Check: `docker-compose --version`

- **Git**  
  - Check: `git --version`

- **Python 3.11+** (optional, for running code locally outside containers)  
  - Check: `python --version`

### Optional
- **PostgreSQL Client** (`psql`)  
  - Useful for direct database access
  - Install: `brew install postgresql` (macOS) or `apt install postgresql-client` (Linux)

- **Redis CLI**  
  - Useful for debugging Redis issues
  - Install: `brew install redis` (macOS) or `apt install redis-tools` (Linux)

---

## Environment Setup

### Step 1: Clone the Repository

```bash
git clone https://github.com/your-org/tft-trader.git
cd tft-trader
```

### Step 2: Create .env File

```bash
# Copy the example file
cp .env.example .env

# The defaults in the example are configured for docker/docker-compose.dev.yml:
#   DATABASE_URL=postgresql://stockuser:stockpass123@postgres:5432/stockmarket
#   REDIS_URL=redis://redis:6379/0
#
# These work as-is for local development. No edits needed unless:
# - You want different database name/password (edit both .env and docker/docker-compose.dev.yml)
# - You need to add Reddit API credentials (REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT)
```

### Step 3: Verify File Structure

Ensure these key files/folders exist:

```
tft-trader/
├── docker/docker-compose.dev.yml     ← Main dev compose file
├── Dockerfile                 ← Application container image
├── .env                        ← Your environment variables (created above)
├── .env.example               ← Template for .env
├── backend/
│   ├── api/main.py           ← FastAPI app
│   ├── celery_app.py         ← Celery configuration
│   ├── config/settings.py    ← App settings loader
│   ├── models/               ← SQLAlchemy models
│   ├── tasks/                ← Celery task definitions
│   └── ...
├── alembic/                   ← Database migrations
├── requirements.txt           ← Python dependencies
└── docs/
    └── DEVELOPMENT.md         ← This file
```

---

## Starting the Dev Environment

### Step 1: Start All Services

```bash
# Start in background
docker-compose -f docker/docker-compose.dev.yml up -d

# Or start in foreground (useful for debugging first-time issues)
docker-compose -f docker/docker-compose.dev.yml up
```

**Expected output** (background mode):
```
Creating tft-postgres ... done
Creating tft-redis ... done
Creating tft-celery-worker ... done
Creating tft-celery-beat ... done
Creating tft-flower ... done
```

### Step 2: Verify Services Are Running

```bash
docker-compose -f docker/docker-compose.dev.yml ps
```

**Expected output** — All services showing "Up" status:
```
NAME                    STATUS                PORTS
tft-postgres            Up (healthy)          5432/tcp
tft-redis               Up (healthy)          6379/tcp
tft-celery-worker       Up                    (no exposed ports)
tft-celery-beat         Up                    (no exposed ports)
tft-flower              Up (healthy)          5555:5555
```

**If a service shows "Exited"**: Check logs with `docker-compose -f docker/docker-compose.dev.yml logs [service_name]`

### Step 3: Wait for Health Checks

Services have health checks that ensure they're fully ready. Check the status:

```bash
# Watch health status (Ctrl+C to exit)
watch docker-compose -f docker/docker-compose.dev.yml ps
```

Wait until all services show either:
- `(healthy)` — explicitly healthy
- `Up` — running (no explicit health check)

⏱️ **First-time startup typically takes 30-60 seconds**

---

## Running Migrations

After services start, you need to initialize the database schema:

### Option 1: Run in Container (Recommended)

```bash
docker-compose -f docker/docker-compose.dev.yml exec celery_worker \
  alembic upgrade head
```

**Expected output**:
```
INFO  [alembic.runtime.migration] Running upgrade ... 
INFO  [alembic.runtime.migration] Creating tables...
```

### Option 2: Run Locally (if Python is installed)

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head
```

### Verify Tables Were Created

```bash
# Option A: Using psql (if installed)
psql postgresql://stockuser:stockpass123@localhost:5432/stockmarket -c "\dt"

# Option B: Using Docker
docker-compose -f docker/docker-compose.dev.yml exec postgres \
  psql -U stockuser -d stockmarket -c "\dt"
```

**Expected output** — Table list:
```
Schema |           Name           | Type  |
-------+--------------------------+-------+
 public | alembic_version          | table |
 public | reddit_posts             | table |
 public | stock_prices             | table |
 public | trading_signals          | table |
 public | users                    | table |
```

---

## Common Commands

### View All Logs

```bash
# View logs from all services (live)
docker-compose -f docker/docker-compose.dev.yml logs -f

# View logs from specific service
docker-compose -f docker/docker-compose.dev.yml logs -f celery_worker
docker-compose -f docker/docker-compose.dev.yml logs -f celery_beat
docker-compose -f docker/docker-compose.dev.yml logs -f postgres
docker-compose -f docker/docker-compose.dev.yml logs -f redis

# View last N lines
docker-compose -f docker/docker-compose.dev.yml logs --tail 50
```

### Access Database

```bash
# Using psql (if installed)
psql postgresql://stockuser:stockpass123@localhost:5432/stockmarket

# Using Docker container
docker-compose -f docker/docker-compose.dev.yml exec postgres \
  psql -U stockuser -d stockmarket

# Then run SQL queries:
# \dt              — List tables
# \d reddit_posts  — Show table structure
# SELECT * FROM reddit_posts LIMIT 5;  — View data
# \q              — Quit
```

### Access Redis

```bash
# Using redis-cli (if installed)
redis-cli

# Using Docker container
docker-compose -f docker/docker-compose.dev.yml exec redis redis-cli

# Then run commands:
# PING              — Test connection (should return PONG)
# KEYS *            — List all keys
# GET key_name      — Get value of key
# DBSIZE            — Number of keys in database
# FLUSHDB           — Clear all data (careful!)
# EXIT              — Quit
```

### Monitor Celery Tasks (Web UI)

```bash
# Flower is automatically started and available at:
# http://localhost:5555

# View in browser or via curl:
curl http://localhost:5555
```

**Flower shows**:
- Active tasks
- Task history
- Worker status
- Task execution times
- Failure rates

### Run Tests

```bash
# Using make command
make test

# Or directly with Docker
docker-compose -f docker/docker-compose.dev.yml exec celery_worker pytest tests/ -v

# With coverage
docker-compose -f docker/docker-compose.dev.yml exec celery_worker pytest tests/ --cov=backend
```

### Run Scraper Manually

```bash
# Run Reddit scraper (one-time)
docker-compose -f docker/docker-compose.dev.yml exec celery_worker \
  python scripts/scheduled_scraper.py --once

# Run stock scraper
docker-compose -f docker/docker-compose.dev.yml exec celery_worker \
  python scripts/scheduled_scraper.py --stocks
```

### Code Changes During Development

```bash
# Backend code changes (Python):
# - Changes are hot-reloaded in celery_worker and celery_beat containers
# - Restart if changes don't apply:
docker-compose -f docker/docker-compose.dev.yml restart celery_worker celery_beat

# Database schema changes:
# - Create migration file
docker-compose -f docker/docker-compose.dev.yml exec celery_worker \
  alembic revision --autogenerate -m "your description"

# - Apply migration
docker-compose -f docker/docker-compose.dev.yml exec celery_worker \
  alembic upgrade head
```

### View Celery Task Queue

```bash
# Check pending tasks
docker-compose -f docker/docker-compose.dev.yml exec redis redis-cli \
  LRANGE celery 0 -1

# Monitor in real-time
watch "docker-compose -f docker/docker-compose.dev.yml exec redis redis-cli DBSIZE"
```

---

## Monitoring & Debugging

### Check Service Health

```bash
# All services
docker-compose -f docker/docker-compose.dev.yml ps

# Detailed health info
docker-compose -f docker/docker-compose.dev.yml ps --format "table {{.Service}}\t{{.State}}\t{{.Status}}"
```

### View Live Logs with Timestamps

```bash
docker-compose -f docker/docker-compose.dev.yml logs --timestamps -f

# Or specific service with timestamps
docker-compose -f docker/docker-compose.dev.yml logs --timestamps -f celery_worker
```

### Execute Commands in Running Container

```bash
# Run Python script in worker container
docker-compose -f docker/docker-compose.dev.yml exec celery_worker \
  python -c "print('Hello from Docker')"

# Run shell in container
docker-compose -f docker/docker-compose.dev.yml exec celery_worker bash

# Run SQL in database container
docker-compose -f docker/docker-compose.dev.yml exec postgres \
  psql -U stockuser -d stockmarket -c "SELECT COUNT(*) FROM reddit_posts;"
```

### Inspect Container Details

```bash
# Show running processes in container
docker-compose -f docker/docker-compose.dev.yml exec celery_worker ps aux

# Show environment variables
docker-compose -f docker/docker-compose.dev.yml exec celery_worker env | sort

# Show network configuration
docker network ls
docker network inspect tft-trader_tft-network
```

---

## Troubleshooting

### Problem 1: Port Already in Use

**Symptom**: `Error: Port 5432 is already in use`

**Solution**:
```bash
# Option A: Kill the process using the port
lsof -i :5432  # Find what's using it
kill -9 <PID>

# Option B: Use a different port in docker/docker-compose.dev.yml
# Change:  "5432:5432" to "5433:5432"
# Then update .env DATABASE_URL to use port 5433
```

### Problem 2: Celery Worker Can't Connect to Redis

**Symptom**: Logs show `ConnectionError: Error 111 connecting to localhost:6379`

**Cause**: Worker is trying to connect to `localhost` instead of Docker service name

**Solution**:
```bash
# Verify .env has correct REDIS_URL
cat .env | grep REDIS_URL

# Should be: redis://redis:6379/0 (NOT localhost)

# If incorrect, edit .env and restart
docker-compose -f docker/docker-compose.dev.yml restart celery_worker celery_beat
```

### Problem 3: Database Doesn't Exist

**Symptom**: `FATAL: database "stockmarket" does not exist`

**Solution**:
```bash
# Create the database manually
docker-compose -f docker/docker-compose.dev.yml exec postgres \
  createdb -U stockuser stockmarket

# Then run migrations
docker-compose -f docker/docker-compose.dev.yml exec celery_worker \
  alembic upgrade head
```

### Problem 4: Celery Beat Not Triggering Tasks

**Symptom**: Beat logs show no "Scheduler: sending..." messages

**Solution**:
```bash
# Check beat logs for errors
docker-compose -f docker/docker-compose.dev.yml logs celery_beat

# Restart beat
docker-compose -f docker/docker-compose.dev.yml restart celery_beat

# Wait 30+ seconds and check if tasks are being triggered
docker-compose -f docker/docker-compose.dev.yml logs -f celery_worker
```

### Problem 5: Services Keep Crashing

**Symptom**: Containers show "Exited" status

**Solution**:
```bash
# View error logs
docker-compose -f docker/docker-compose.dev.yml logs [service_name]

# Rebuild images (sometimes helpful)
docker-compose -f docker/docker-compose.dev.yml build --no-cache

# Restart services
docker-compose -f docker/docker-compose.dev.yml up -d

# Check health again
docker-compose -f docker/docker-compose.dev.yml ps
```

### Problem 6: Out of Disk Space

**Symptom**: Docker or containers fail with disk space errors

**Solution**:
```bash
# Check Docker disk usage
docker system df

# Clean up unused volumes, networks, images
docker system prune

# Clean up everything (careful — removes all unused data)
docker system prune -a --volumes
```

### Problem 7: Python Dependencies Missing

**Symptom**: `ModuleNotFoundError: No module named 'X'` in logs

**Solution**:
```bash
# Rebuild the Docker image to reinstall dependencies
docker-compose -f docker/docker-compose.dev.yml build --no-cache celery_worker

# Restart the worker
docker-compose -f docker/docker-compose.dev.yml restart celery_worker
```

---

## Stopping & Cleaning

### Stop Services (Keep Data)

```bash
# Stop all services gracefully
docker-compose -f docker/docker-compose.dev.yml down

# Services can be restarted later without losing data
docker-compose -f docker/docker-compose.dev.yml up -d
```

### Stop & Clean Everything (Delete Data)

**⚠️ WARNING: This deletes all data in the database and Redis!**

```bash
# Remove all services and volumes
docker-compose -f docker/docker-compose.dev.yml down -v

# All databases will be empty when you restart
```

### Reset Just the Database

```bash
# Drop and recreate the database volume
docker-compose -f docker/docker-compose.dev.yml down postgres
docker volume rm tft-trader_postgres_data
docker-compose -f docker/docker-compose.dev.yml up -d postgres

# Wait for it to start, then run migrations again
docker-compose -f docker/docker-compose.dev.yml exec celery_worker alembic upgrade head
```

### View Volumes

```bash
# List all volumes
docker volume ls

# Inspect a specific volume
docker volume inspect tft-trader_postgres_data

# Remove a volume
docker volume rm tft-trader_postgres_data
```

---

## Quick Reference (Cheat Sheet)

| Task | Command |
|------|---------|
| Start services | `docker-compose -f docker/docker-compose.dev.yml up -d` |
| Stop services | `docker-compose -f docker/docker-compose.dev.yml down` |
| View all logs | `docker-compose -f docker/docker-compose.dev.yml logs -f` |
| View service logs | `docker-compose -f docker/docker-compose.dev.yml logs -f SERVICE_NAME` |
| Check service status | `docker-compose -f docker/docker-compose.dev.yml ps` |
| Run migrations | `docker-compose -f docker/docker-compose.dev.yml exec celery_worker alembic upgrade head` |
| Access database | `docker-compose -f docker/docker-compose.dev.yml exec postgres psql -U stockuser -d stockmarket` |
| Access Redis | `docker-compose -f docker/docker-compose.dev.yml exec redis redis-cli` |
| Monitor Celery | Open `http://localhost:5555` (Flower UI) |
| Run tests | `docker-compose -f docker/docker-compose.dev.yml exec celery_worker pytest tests/` |
| Restart service | `docker-compose -f docker/docker-compose.dev.yml restart SERVICE_NAME` |
| Rebuild images | `docker-compose -f docker/docker-compose.dev.yml build --no-cache` |
| Delete all data | `docker-compose -f docker/docker-compose.dev.yml down -v` |

---

## Getting Help

- **Check logs**: `docker-compose -f docker/docker-compose.dev.yml logs -f [service]`
- **Run in foreground**: `docker-compose -f docker/docker-compose.dev.yml up` (easier debugging)
- **Check file**: `docs/DOCKER_SETUP_ANALYSIS.md` (detailed reference)
- **Ask team**: Create an issue or reach out to the development team

---

**Happy developing! 🚀**
