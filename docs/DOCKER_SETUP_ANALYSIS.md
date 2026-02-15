# Docker Compose Setup — Complete Analysis & Implementation

Date: 2026-02-15T19:14:00Z
Task ID: Week 2 #5 — Docker Compose Dev Setup
Status: ⏳ IN PROGRESS

---

## Executive Summary

This document provides a detailed analysis of Task #5 from Week 2 of the implementation roadmap. The goal is to create a fully functional Docker Compose development environment that allows developers to:
- Run PostgreSQL database locally
- Run Redis cache/broker locally  
- Run Celery worker and beat scheduler locally
- Execute end-to-end scraping pipelines without manual setup
- Validate all integration points before pushing code

**Current situation**: Docker and docker-compose.yml exist but are empty. The application is designed to work with these services (as evidenced by celery_app.py and settings.py), but a development-friendly compose file is missing.

---

## What's Currently Implemented

### 1. Celery Configuration (✅ Present)
- **File**: `backend/celery_app.py`
- **Status**: Complete and functional
- **What it does**:
  - Initializes Celery app with Redis broker and backend
  - Defines beat schedule (cron-like tasks)
  - Routes tasks to specific queues (scraping, ml)
  - Configures retry logic and timeouts
- **Current scheduled tasks**:
  - `scrape-reddit-posts`: Every 30 minutes
  - `fetch-stock-data`: Every hour
  - `generate-signals`: Daily at 14:30 UTC (2:30 PM)
  - `monitor-signals`: Every 5 minutes
  - `cleanup-old-data`: Weekly cleanup
  - `system-report`: Daily report
  - `refresh-trending-cache`: Every 10 minutes

### 2. Task Definitions (✅ Present)
- **Files**: `backend/tasks/scraping_tasks.py`, `backend/tasks/ml_tasks.py`, `backend/tasks/maintenance_tasks.py`
- **Status**: Task stubs exist; need verification with real Redis/Celery setup
- **Key tasks**:
  - `scrape_reddit_scheduled()` — Fetch Reddit posts
  - `fetch_stocks_scheduled()` — Fetch stock prices
  - `generate_daily_signals()` — ML inference
  - Other ML and maintenance tasks

### 3. Database Configuration (✅ Present)
- **File**: `backend/config/settings.py`
- **Status**: Reads from environment variables
- **Requires**:
  - `DATABASE_URL` — PostgreSQL connection string
  - `REDIS_URL` — Redis connection string
- **Examples in .env.example**:
  - `DATABASE_URL=postgresql://stockuser:your_password@localhost:5432/stockmarket`
  - `REDIS_URL=redis://localhost:6379/0`

### 4. Database Models (✅ Present)
- **Files**: `backend/models/*.py` (reddit, stock, trading_signal, user)
- **Migrations**: `alembic/versions/*`
- **Status**: Schema is defined and ready to migrate
- **Key tables**:
  - `reddit_posts` — Store Reddit scraping results
  - `stock_prices` — Store OHLCV data
  - `trading_signals` — Store ML predictions and status
  - `users` — User authentication

---

## What's Missing

### 1. Docker Compose Dev File (❌ Missing)
- **File needed**: `docker/docker-compose.dev.yml`
- **Purpose**: Define services for local development
- **Required services**:
  - **PostgreSQL** (port 5432) — Database
  - **Redis** (port 6379) — Cache and task broker
  - **Celery Worker** (background process) — Executes scraping/ML tasks
  - **Celery Beat** (background process) — Schedules tasks
- **Missing features**:
  - Health checks for each service
  - Environment variable injection
  - Volume persistence for DB and logs
  - Proper logging configuration
  - Multi-stage build for Python app

### 2. Development Documentation (❌ Missing)
- **File needed**: `docs/DEVELOPMENT.md`
- **Should document**:
  - How to start the dev environment
  - How to view logs for each service
  - How to trigger tasks manually
  - How to reset/clean the database
  - How to monitor Celery with Flower (optional)
  - Troubleshooting common issues

### 3. Flower Configuration (⚠️ Optional but recommended)
- **Purpose**: Web-based Celery monitoring UI
- **Port**: 5555
- **Nice to have**: Add to docker-compose for visibility into task execution

---

## Detailed Implementation Plan

### Step 1: Create docker/docker-compose.dev.yml
**File**: `docker/docker-compose.dev.yml`
**Purpose**: Define all services needed for local development

Services to include:
1. **PostgreSQL service**
   - Image: `postgres:16-alpine`
   - Environment: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
   - Ports: `5432:5432`
   - Volumes: `postgres_data:/var/lib/postgresql/data` (persistent)
   - Health check: `pg_isready` command
   
2. **Redis service**
   - Image: `redis:7-alpine`
   - Ports: `6379:6379`
   - Volumes: `redis_data:/data` (persistent)
   - Health check: `redis-cli PING`

3. **Celery Worker service**
   - Build: From `Dockerfile` (Python backend)
   - Environment: Load from `.env` file
   - Command: `celery -A backend.celery_app worker --loglevel=info --queues=scraping,ml`
   - Depends on: `postgres`, `redis`
   - Volumes: `./backend:/app/backend` (code hot-reload)

4. **Celery Beat service**
   - Build: From `Dockerfile` (Python backend)
   - Environment: Load from `.env` file
   - Command: `celery -A backend.celery_app beat --loglevel=info`
   - Depends on: `postgres`, `redis`
   - Volumes: `./backend:/app/backend`

5. **Flower service** (optional, recommended)
   - Image: `mher/flower:2.0`
   - Ports: `5555:5555`
   - Environment: Connect to Redis broker
   - Command: `flower --broker=redis://redis:6379`

### Step 2: Update Dockerfile for Dev Support
**File**: `Dockerfile`
**Changes needed**:
- Ensure it has a `dev` target or accepts `--target dev` flag
- Install development dependencies (pytest, etc.)
- Set working directory to `/app`
- Expose ports (8000 for API, 5555 for Flower optional)

### Step 3: Create docs/DEVELOPMENT.md
**Purpose**: Developer quick-start guide
**Should include**:
- Prerequisites (Docker, docker-compose, Python 3.11+)
- Quick start (5 min to running system)
- Service status checks
- How to trigger tasks manually
- Log viewing commands
- Database access and reset
- Troubleshooting

### Step 4: Update Makefile
**Add new targets**:
```makefile
docker-dev-up:        # Start dev environment
docker-dev-down:      # Stop dev environment  
docker-dev-logs:      # View all logs
docker-dev-logs-worker: # View worker logs
docker-dev-logs-beat:   # View beat logs
docker-dev-rebuild:   # Rebuild images
docker-dev-clean:     # Remove volumes (WARNING: deletes data)
docker-dev-db-reset:  # Reset database
docker-dev-migrate:   # Run migrations in container
docker-celery-monitor:# Start Flower UI
```

---

## Acceptance Criteria (Detailed)

### ✅ Criterion 1: Services Start Successfully
**Command**: `docker-compose -f docker/docker-compose.dev.yml up -d`
**Expected output**:
```
Creating postgres_container ... done
Creating redis_container ... done
Creating celery_worker_container ... done
Creating celery_beat_container ... done
```
**Verification**: `docker ps` shows 4 containers running

### ✅ Criterion 2: PostgreSQL is Ready
**Command**: `docker-compose -f docker/docker-compose.dev.yml exec postgres pg_isready`
**Expected output**: `accepting connections`
**Verification**: 
- Health check shows `(healthy)` in `docker ps`
- Can connect via `psql` client if installed

### ✅ Criterion 3: Redis is Ready
**Command**: `docker-compose -f docker/docker-compose.dev.yml exec redis redis-cli PING`
**Expected output**: `PONG`
**Verification**: Health check shows `(healthy)`

### ✅ Criterion 4: Celery Worker is Running
**Command**: `docker-compose -f docker/docker-compose.dev.yml logs celery_worker`
**Expected output**: Contains lines like:
```
[*] celery@xxx ready. Waiting for commands.
[*] Broker connection: connected
```
**Verification**: Worker shows ready and connected status

### ✅ Criterion 5: Celery Beat is Running
**Command**: `docker-compose -f docker/docker-compose.dev.yml logs celery_beat`
**Expected output**: Contains lines like:
```
celery beat v5.x.x is starting.
[*] Scheduler: Ticking...
```
**Verification**: Beat shows scheduled tasks

### ✅ Criterion 6: Database Migrations Applied
**Command**: `docker-compose -f docker/docker-compose.dev.yml exec backend alembic upgrade head`
**Expected output**: 
```
INFO  [alembic.runtime.migration] Running upgrade ... (existing tables created)
```
**Verification**: Database contains tables for reddit_posts, stock_prices, trading_signals

### ✅ Criterion 7: Scheduled Tasks Trigger
**Evidence**: 
- Beat scheduler logs show "Scheduler: sending..."
- Worker logs show task execution
- Database contains new reddit_posts or stock_prices after 30+ minutes

### ✅ Criterion 8: Logs Are Visible and Useful
**Commands**:
```bash
docker-compose -f docker/docker-compose.dev.yml logs -f                    # All services
docker-compose -f docker/docker-compose.dev.yml logs -f celery_worker      # Worker only
docker-compose -f docker/docker-compose.dev.yml logs -f celery_beat        # Beat only
docker-compose -f docker/docker-compose.dev.yml logs -f postgres           # Database only
```
**Expected**: Timestamps, service names, and clear messages visible

---

## Testing & Validation Plan

### Test 1: Basic Startup (5 min)
```bash
# Start services
docker-compose -f docker/docker-compose.dev.yml up -d

# Verify all containers running
docker ps | grep "tft-trader"

# Check health
docker-compose -f docker/docker-compose.dev.yml ps
```

### Test 2: Database Connectivity (10 min)
```bash
# Apply migrations
docker-compose -f docker/docker-compose.dev.yml exec backend alembic upgrade head

# Check tables were created
docker-compose -f docker/docker-compose.dev.yml exec postgres psql -U stockuser -d stockmarket -c "\dt"

# Expected: Table list including reddit_posts, stock_prices, trading_signals
```

### Test 3: Redis Connectivity (5 min)
```bash
# Ping Redis
docker-compose -f docker/docker-compose.dev.yml exec redis redis-cli PING

# Expected: PONG

# Check keys (should be empty initially)
docker-compose -f docker/docker-compose.dev.yml exec redis redis-cli KEYS '*'

# Expected: (empty array)
```

### Test 4: Celery Worker Health (5 min)
```bash
# View worker logs
docker-compose -f docker/docker-compose.dev.yml logs celery_worker

# Expected: "[*] celery@xxx ready. Waiting for commands."

# Try to trigger a task manually (from host machine with Python)
python -c "from backend.tasks.scraping_tasks import scrape_reddit_scheduled; scrape_reddit_scheduled.delay()"

# Expected: Worker logs show task acceptance and execution
```

### Test 5: Celery Beat Schedule (30+ min)
```bash
# Monitor beat logs
docker-compose -f docker/docker-compose.dev.yml logs -f celery_beat

# After 30 minutes:
# Expected: "Scheduler: sending..." messages indicating tasks were triggered

# Check worker logs for task execution
docker-compose -f docker/docker-compose.dev.yml logs celery_worker | grep "Task"
```

### Test 6: Data Persistence (5 min)
```bash
# Stop containers
docker-compose -f docker/docker-compose.dev.yml down

# Restart
docker-compose -f docker/docker-compose.dev.yml up -d

# Check data still exists
docker-compose -f docker/docker-compose.dev.yml exec postgres psql -U stockuser -d stockmarket -c "SELECT COUNT(*) FROM reddit_posts;"

# Expected: Same count as before (if any data was inserted)
```

### Test 7: Log Aggregation (5 min)
```bash
# View all logs with timestamps
docker-compose -f docker/docker-compose.dev.yml logs --timestamps

# View last 50 lines
docker-compose -f docker/docker-compose.dev.yml logs --tail 50

# View logs of single service
docker-compose -f docker/docker-compose.dev.yml logs celery_worker --tail 20
```

---

## Troubleshooting Guide

### Problem 1: Port Already in Use
**Symptom**: `Error: Port 5432 is already in use`
**Solution**:
```bash
# Find what's using the port
lsof -i :5432

# Either kill the process or use different port
# Edit docker/docker-compose.dev.yml: "5433:5432" instead of "5432:5432"
```

### Problem 2: Celery Worker Can't Connect to Redis
**Symptom**: Worker logs show `ConnectionError: Error 111 connecting to 127.0.0.1:6379`
**Cause**: Worker trying to connect to localhost instead of redis service name
**Solution**: Ensure `.env` has `REDIS_URL=redis://redis:6379/0` (not `localhost`)

### Problem 3: Database Migration Fails
**Symptom**: `FATAL: database "stockmarket" does not exist`
**Solution**:
```bash
# Manually create database
docker-compose -f docker/docker-compose.dev.yml exec postgres \
  psql -U stockuser -tc "CREATE DATABASE stockmarket;"
```

### Problem 4: Celery Beat Not Triggering Tasks
**Symptom**: Beat logs show schedule but no "sending..." messages
**Cause**: Often a timezone or schedule configuration issue
**Solution**:
```bash
# Check beat logs for errors
docker-compose -f docker/docker-compose.dev.yml logs celery_beat

# Restart beat
docker-compose -f docker/docker-compose.dev.yml restart celery_beat
```

### Problem 5: Worker Crashes on Startup
**Symptom**: Worker container exits immediately
**Cause**: Python import errors or missing dependencies
**Solution**:
```bash
# View detailed logs
docker-compose -f docker/docker-compose.dev.yml logs celery_worker

# Rebuild image
docker-compose -f docker/docker-compose.dev.yml build --no-cache celery_worker

# Restart
docker-compose -f docker/docker-compose.dev.yml up -d celery_worker
```

### Problem 6: PostgreSQL Fails to Start
**Symptom**: PostgreSQL container exits
**Cause**: Volume permissions or corrupt data
**Solution**:
```bash
# Clean everything and restart (WARNING: deletes data)
docker-compose -f docker/docker-compose.dev.yml down -v
docker-compose -f docker/docker-compose.dev.yml up -d
```

---

## Implementation Checklist

- [ ] Create `docker/docker-compose.dev.yml` with PostgreSQL, Redis, Celery Worker, Celery Beat
- [ ] Add health checks for all services
- [ ] Add volume definitions for data persistence
- [ ] Update `Dockerfile` if needed for dev support
- [ ] Create `docs/DEVELOPMENT.md` with quick-start guide
- [ ] Add Makefile targets for common operations
- [ ] Test all acceptance criteria (Step 1-7 above)
- [ ] Document troubleshooting procedures
- [ ] Update main README with link to DEVELOPMENT.md
- [ ] Run E2E test: Start services → Migrate → View logs → Trigger task → Verify data

---

## Success Indicators

When Task #5 is complete, you should be able to:
1. ✅ Run `docker-compose -f docker/docker-compose.dev.yml up -d` and have all services start
2. ✅ View logs from all services: `docker-compose -f docker/docker-compose.dev.yml logs -f`
3. ✅ Run `alembic upgrade head` inside the container and see tables created
4. ✅ See Celery worker ready and waiting for tasks
5. ✅ See Celery beat scheduling tasks every 30 min (Reddit scrape) and hourly (stock fetch)
6. ✅ (After 30 min+) See tasks execute and data populate in database
7. ✅ Stop and restart services: data persists across restarts
8. ✅ New team member can follow docs/DEVELOPMENT.md and have full env running in <10 minutes

---

## Time Estimate & Effort Breakdown

- Design & create docker/docker-compose.dev.yml: **30 min**
- Update Dockerfile for dev support: **15 min**
- Create docs/DEVELOPMENT.md: **20 min**
- Add Makefile targets: **10 min**
- Test all acceptance criteria: **30 min**
- Document troubleshooting: **15 min**
- **Total: ~2 hours**

---

## Dependencies (Required Before Starting)

✅ Task #1: .env.example created (secrets documented)  
✅ Task #2-3: Retry logic + data validation  
✅ Task #4: Real scraper integration tests passing  
✅ Celery app defined (backend/celery_app.py)  
✅ Task definitions exist (backend/tasks/*)  
✅ Database models exist (backend/models/*)  

---

## Blockers & Risks

**No blockers identified** — all dependencies are met.

**Low risk** — Docker/compose setup is straightforward for these simple services.

**Potential issue** — If the application has undocumented dependencies on specific Python libraries, the Docker build might fail. Solution: Run `pip install -r requirements.txt` locally first to catch issues.

---

## Next Steps After Task #5 Complete

Once Docker Compose is working:
- Week 3 can begin with feature builder implementation (using real ingested data)
- All future tasks can assume a working local development environment
- CI/CD can be built on top of this compose setup
- Production deployment can use similar service patterns

---

End of analysis — proceed to implementation file: `docker/docker-compose.dev.yml`
