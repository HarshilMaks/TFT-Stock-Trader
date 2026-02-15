# Docker Setup — Quick Reference Card

**Print this out or keep it as a browser tab!**

---

## 🚀 Quick Start (Copy & Paste)

```bash
# Step 1: Setup (first time only)
cp .env.example .env

# Step 2: Start everything
docker-compose -f docker/docker-compose.dev.yml up -d

# Step 3: Verify it works
bash scripts/verify_docker_setup.sh

# Step 4: Initialize database (first time only)
docker-compose -f docker/docker-compose.dev.yml exec celery_worker \
  alembic upgrade head

# Step 5: View logs
docker-compose -f docker/docker-compose.dev.yml logs -f
```

---

## 📊 Service Ports

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| PostgreSQL | 5432 | `postgresql://stockuser:stockpass123@localhost:5432/stockmarket` | Database |
| Redis | 6379 | `redis://localhost:6379/0` | Cache & Task Queue |
| Flower (Celery UI) | 5555 | `http://localhost:5555` | Monitor tasks |
| Backend API | 8000 | `http://localhost:8000` | (when running locally) |
| Frontend | 3000 | `http://localhost:3000` | (when running locally) |

---

## 🔍 Check Service Status

```bash
# See all services
docker-compose -f docker/docker-compose.dev.yml ps

# Check if healthy
docker-compose -f docker/docker-compose.dev.yml exec postgres pg_isready
docker-compose -f docker/docker-compose.dev.yml exec redis redis-cli PING

# View logs of one service
docker-compose -f docker/docker-compose.dev.yml logs -f postgres
docker-compose -f docker/docker-compose.dev.yml logs -f redis
docker-compose -f docker/docker-compose.dev.yml logs -f celery_worker
docker-compose -f docker/docker-compose.dev.yml logs -f celery_beat
```

---

## 🗄️ Database Commands

```bash
# Connect to database
docker-compose -f docker/docker-compose.dev.yml exec postgres \
  psql -U stockuser -d stockmarket

# Inside psql prompt:
\dt                    -- List all tables
SELECT * FROM reddit_posts LIMIT 5;  -- View data
\q                     -- Quit

# Or one-liner:
docker-compose -f docker/docker-compose.dev.yml exec postgres \
  psql -U stockuser -d stockmarket \
  -c "SELECT COUNT(*) FROM reddit_posts;"
```

---

## 💾 Redis Commands

```bash
# Connect to Redis
docker-compose -f docker/docker-compose.dev.yml exec redis redis-cli

# Inside redis-cli prompt:
PING                   -- Test connection
KEYS *                 -- List all keys
GET key_name           -- Get value
DBSIZE                 -- Number of keys
FLUSHDB                -- Clear all data (careful!)
EXIT                   -- Quit

# Or one-liner:
docker-compose -f docker/docker-compose.dev.yml exec redis \
  redis-cli KEYS '*'
```

---

## 🔄 Celery Task Monitoring

```bash
# View Flower UI (web interface)
open http://localhost:5555  # macOS
firefox http://localhost:5555  # Linux
start http://localhost:5555  # Windows

# Or check logs
docker-compose -f docker/docker-compose.dev.yml logs -f celery_worker
docker-compose -f docker/docker-compose.dev.yml logs -f celery_beat

# Manually trigger a task (Python)
docker-compose -f docker/docker-compose.dev.yml exec celery_worker python -c "
from backend.tasks.scraping_tasks import scrape_reddit_scheduled
scrape_reddit_scheduled.delay()
print('Task queued!')
"
```

---

## 🧪 Testing

```bash
# Run all tests
docker-compose -f docker/docker-compose.dev.yml exec celery_worker pytest tests/

# Run specific test file
docker-compose -f docker/docker-compose.dev.yml exec celery_worker pytest tests/test_scraper.py -v

# With coverage
docker-compose -f docker/docker-compose.dev.yml exec celery_worker \
  pytest tests/ --cov=backend --cov-report=html
```

---

## 🔧 Maintenance

```bash
# Stop services (keeps data)
docker-compose -f docker/docker-compose.dev.yml down

# Restart services (keeps data)
docker-compose -f docker/docker-compose.dev.yml restart

# Delete everything (⚠️ DELETES DATA)
docker-compose -f docker/docker-compose.dev.yml down -v

# View resource usage
docker stats

# Clean up unused Docker stuff
docker system prune

# Rebuild images (slow but thorough)
docker-compose -f docker/docker-compose.dev.yml build --no-cache
```

---

## 🐛 Quick Troubleshooting

| Problem | Command | Notes |
|---------|---------|-------|
| Port in use | `lsof -i :5432` | Find what's using the port |
| Worker not running | `docker-compose -f docker/docker-compose.dev.yml logs celery_worker` | Check error messages |
| DB won't connect | `docker-compose -f docker/docker-compose.dev.yml exec postgres pg_isready` | See if Postgres is ready |
| Redis connection error | Update `.env`: `REDIS_URL=redis://redis:6379/0` | Not `localhost` |
| Can't connect to Postgres | `docker-compose -f docker/docker-compose.dev.yml exec celery_worker alembic upgrade head` | Run migrations |
| Out of disk space | `docker system prune -a --volumes` | Clean up old images/data |
| Services crash | `docker-compose -f docker/docker-compose.dev.yml up` | Run in foreground to see errors |

---

## 📝 Common Makefile Commands

```bash
make docker-up       # Start containers
make docker-down     # Stop containers
make docker-logs     # View all logs
make migrate         # Run migrations
make test            # Run tests
make worker          # Start Celery worker (local)
make beat            # Start Celery beat (local)
```

---

## 📚 Documentation Files

- **Quick setup**: `docs/DEVELOPMENT.md` (5-min quick start section)
- **All commands**: `docs/DEVELOPMENT.md` (Common Commands section)
- **Troubleshooting**: `docs/DOCKER_SETUP_ANALYSIS.md` or `docs/DEVELOPMENT.md` (section 8)
- **Technical details**: `docs/DOCKER_SETUP_ANALYSIS.md`
- **Summary**: `docs/DOCKER_SETUP_SUMMARY.md`

---

## ❓ Need Help?

1. **Quick check**: `bash scripts/verify_docker_setup.sh`
2. **Read docs**: `docs/DEVELOPMENT.md` section 8 (Troubleshooting)
3. **Check logs**: `docker-compose -f docker/docker-compose.dev.yml logs -f [service_name]`
4. **Ask team**: Reach out to the development team

---

## 📍 Typical Workflow

```bash
# Morning: Start everything
docker-compose -f docker/docker-compose.dev.yml up -d

# During day: Monitor & develop
docker-compose -f docker/docker-compose.dev.yml logs -f
# View Flower at http://localhost:5555

# End of day: Stop containers (data stays)
docker-compose -f docker/docker-compose.dev.yml down

# Next morning: Restart
docker-compose -f docker/docker-compose.dev.yml up -d
```

---

## ✅ Health Check

All services healthy when:
- ✓ `docker-compose ps` shows all "Up"
- ✓ `pg_isready` returns "accepting connections"
- ✓ `redis-cli PING` returns "PONG"
- ✓ Flower at `http://localhost:5555` loads
- ✓ `docker-compose logs celery_worker` shows "ready"

---

**Keep this card handy while working with Docker!**
