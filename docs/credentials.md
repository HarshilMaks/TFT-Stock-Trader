# Credentials & Secrets Setup Guide

> **⚠️ Security Warning:** NEVER commit `.env` to version control. Use `.env.example` as a template only.

This guide explains how to obtain and configure each credential required for TFT Trader development and production.

---

## Quick Start (Local Development)

For rapid local development, you can use the default values for some services:

```bash
cp .env.example .env

# Start local services
docker-compose -f docker/docker-compose.dev.yml up -d postgres redis

# Fill in REDDIT credentials (required), use defaults for others
# DATABASE_URL and REDIS_URL will work with docker-compose defaults
```

---

## Credentials by Category

### 1. PostgreSQL Database

**Required For:** Data storage (stock prices, Reddit posts, signals)

#### Local Development
No credentials needed — use defaults:
```dotenv
DATABASE_URL=postgresql://stockuser:stockpass@localhost:5432/stockmarket
```

Then create the database:
```bash
docker-compose -f docker/docker-compose.dev.yml up -d postgres
docker exec tft-trader-postgres createdb -U stockuser stockmarket
```

#### Cloud: Neon (Recommended for Production)
1. Sign up at [neon.tech](https://neon.tech)
2. Create a project and database
3. Copy the connection string (psql option):
   ```
   postgresql://neonuser:neon_password@ep-cool-sound-123.region.aws.neon.tech/dbname?sslmode=require
   ```
4. Add to `.env`:
   ```dotenv
   DATABASE_URL=postgresql://neonuser:neon_password@ep-cool-sound-123.region.aws.neon.tech/dbname?sslmode=require
   ```

#### Cloud: AWS RDS
1. Create an RDS PostgreSQL instance in AWS Console
2. Copy the endpoint and port: `mydb.region.rds.amazonaws.com:5432`
3. Create user and database in the RDS instance
4. Add to `.env`:
   ```dotenv
   DATABASE_URL=postgresql://rds_user:rds_password@mydb.region.rds.amazonaws.com:5432/tft_trader
   ```

---

### 2. Redis

**Required For:** Caching, rate limiting, task queue (Celery)

#### Local Development
No credentials needed — use default:
```dotenv
REDIS_URL=redis://localhost:6379/0
```

Start with:
```bash
docker-compose -f docker/docker-compose.dev.yml up -d redis
```

#### Cloud: Redis Cloud
1. Sign up at [redis.com/try-free](https://redis.com/try-free)
2. Create a free database
3. Go to "Security" → copy connection string (looks like):
   ```
   redis://default:your_api_token@redis-123456.c123.us-east-1-2.ec2.cloud.redislabs.com:12345
   ```
4. Add to `.env`:
   ```dotenv
   REDIS_URL=redis://default:your_api_token@redis-123456.c123.us-east-1-2.ec2.cloud.redislabs.com:12345
   ```

#### Cloud: Upstash (Serverless, Free Tier)
1. Sign up at [upstash.com](https://upstash.com)
2. Create a Redis database
3. Copy the REST URL from dashboard
4. Add to `.env`:
   ```dotenv
   REDIS_URL=redis://default:your_token@upstash-endpoint.upstash.io:12345
   ```

---

### 3. Reddit API (PRAW) — **CRITICAL**

**Required For:** Scraping stock mentions and sentiment from Reddit

#### Setup Steps

1. **Create Reddit App:**
   - Go to [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)
   - Scroll to bottom → "Create App" or "Create Another App"
   - **Name:** `TFT-Trader` (or your app name)
   - **App Type:** `script` (for data collection)
   - **Redirect URI:** `http://localhost:8000/api/auth/reddit/callback` (for dev)
   - **Description:** "Stock sentiment analysis application"
   - Click **Create App**

2. **Extract Credentials:**
   
   After creation, you'll see:
   ```
   TFT-Trader
   ┌─────────────────────────────────┐
   │ personal use script             │
   │                                 │
   │ ID: abc123def456ghi789          │ ← This is CLIENT_ID
   │ secret: xyz789uvw456rst123      │ ← This is CLIENT_SECRET
   └─────────────────────────────────┘
   ```

3. **Check Your Reddit Username:**
   - Go to [reddit.com/settings/profile](https://www.reddit.com/settings/profile)
   - Copy your username

4. **Add to `.env`:**
   ```dotenv
   REDDIT_CLIENT_ID=abc123def456ghi789
   REDDIT_CLIENT_SECRET=xyz789uvw456rst123
   REDDIT_USER_AGENT=TFT-Trader/1.0 (by your_username)
   ```

#### Rate Limiting Compliance
- Reddit allows **60 requests per minute** for authenticated users
- Our scraper uses exponential backoff (retries on 429 errors)
- Stick to 20 requests/min in production to be safe
- Never hammer the API with multiple concurrent scrapers

#### Troubleshooting
| Error | Fix |
|-------|-----|
| `PRAW InvalidAuthentication` | Check CLIENT_ID and CLIENT_SECRET are correct |
| `403 Forbidden` | Check USER_AGENT is set and in correct format |
| `429 Too Many Requests` | Rate limited — wait 60 seconds or reduce frequency |

---

### 4. Security & JWT

**Required For:** Authentication and request signing

#### Generate SECRET_KEY
```bash
# Option 1: Python one-liner
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Output: "rN3p7k_L9m2x5qZ4wA8bC1dE6fG-hI_jK0l"

# Option 2: Using openssl
openssl rand -base64 32
# Output: "3k7L9m2x5qZ4wA8bC1dE6fG-hI_jK0lrN3p8="
```

#### Add to `.env`
```dotenv
SECRET_KEY=rN3p7k_L9m2x5qZ4wA8bC1dE6fG-hI_jK0l
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

#### For Production (RS256 with Public/Private Keys)
```bash
# Generate RSA key pair
openssl genrsa -out private_key.pem 2048
openssl rsa -in private_key.pem -pubout -out public_key.pem

# Store securely (e.g., in AWS Secrets Manager)
# Update .env to reference the key paths or use environment secrets
```

---

### 5. Environment & Application Settings

```dotenv
# Development
ENVIRONMENT=development
DEBUG=True
LOG_LEVEL=INFO

# Production
ENVIRONMENT=production
DEBUG=False
LOG_LEVEL=WARNING
```

#### Frontend CORS Origins
```dotenv
# Development (multiple dev servers)
CORS_ORIGINS=http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000

# Production
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

---

### 6. Monitoring & Observability (Optional)

#### Sentry (Error Tracking)
1. Sign up at [sentry.io](https://sentry.io)
2. Create a project (select Python/FastAPI)
3. Copy DSN from Settings → Client Keys
4. Add to `.env`:
   ```dotenv
   SENTRY_DSN=https://key@sentry.io/project_id
   ```

#### OpenTelemetry (Distributed Tracing)
```dotenv
# Local development (optional)
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Production (e.g., Datadog, New Relic)
OTEL_EXPORTER_OTLP_ENDPOINT=https://your-otel-endpoint
```

---

## Checking Your Setup

### 1. Verify Database Connection
```bash
# From project root with .env configured
python -c "
from backend.config.settings import settings
print(f'✓ Database: {settings.database_url}')
print(f'✓ Redis: {settings.redis_url}')
print(f'✓ Reddit client_id: {\"CONFIGURED\" if ...}')"
```

### 2. Test Database
```bash
make migrate  # Run Alembic migrations
make shell    # Open Python REPL with models loaded
```

### 3. Test Reddit API
```bash
python -c "
from backend.scrapers.reddit_scraper import RedditScraper
scraper = RedditScraper()
posts = scraper.scrape_posts('wallstreetbets', limit=5)
print(f'✓ Reddit API works: {len(posts)} posts fetched')
"
```

### 4. Test Redis
```bash
# Via CLI
redis-cli -u $REDIS_URL ping
# Expected: PONG

# Via Python
from redis.asyncio import Redis
r = Redis.from_url("$REDIS_URL")
await r.ping()  # PONG
```

---

## Environment Variables Reference

| Variable | Required | Example | Notes |
|----------|----------|---------|-------|
| `DATABASE_URL` | ✅ Yes | `postgresql://user:pass@host/db` | Supports Neon, AWS RDS, local |
| `REDIS_URL` | ✅ Yes | `redis://default:token@host:port` | For caching & Celery |
| `REDDIT_CLIENT_ID` | ✅ Yes | `abc123def456ghi789` | From reddit.com/prefs/apps |
| `REDDIT_CLIENT_SECRET` | ✅ Yes | `xyz789uvw456rst123` | Keep secret! |
| `REDDIT_USER_AGENT` | ✅ Yes | `TFT-Trader/1.0 (by username)` | Reddit's rule: include username |
| `SECRET_KEY` | ✅ Yes | Generate with `secrets.token_urlsafe(32)` | Min 32 chars |
| `ALGORITHM` | ❌ No | `HS256` | Default is fine for dev |
| `ENVIRONMENT` | ❌ No | `development` | Used for logging/debug flags |
| `DEBUG` | ❌ No | `True` | Set to False in production |
| `LOG_LEVEL` | ❌ No | `INFO` | DEBUG, INFO, WARNING, ERROR |
| `CORS_ORIGINS` | ❌ No | `http://localhost:3000` | Comma-separated URLs |
| `SENTRY_DSN` | ❌ No | Empty | Add for error tracking |

---

## Common Issues & Troubleshooting

### "ModuleNotFoundError: No module named 'praw'"
```bash
# Install/update dependencies
pip install -r requirements.txt
# or
uv sync
```

### "postgresql can't connect to localhost:5432"
```bash
# Is postgres running locally?
docker-compose -f docker/docker-compose.dev.yml up -d postgres

# Check connection
psql postgresql://stockuser:stockpass@localhost:5432/stockmarket
```

### "redis.exceptions.ConnectionError"
```bash
# Start Redis
docker-compose -f docker/docker-compose.dev.yml up -d redis

# Verify
redis-cli ping
# Expected: PONG
```

### ".env file not found"
```bash
# Copy from template
cp .env.example .env

# Fill in required values (at minimum: DATABASE_URL, REDIS_URL, REDDIT_* credentials)
```

---

## Security Best Practices

1. **Never commit secrets:**
   ```bash
   # Check .gitignore includes .env
   cat .gitignore | grep "^\.env$"
   ```

2. **Rotate credentials regularly** (especially `SECRET_KEY` in production)

3. **Use strong, randomly-generated values:**
   ```bash
   # Generate 32-char secret
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

4. **For CI/CD pipelines,** use GitHub Secrets or your deployment platform's secret management:
   ```yaml
   # .github/workflows/test.yml
   env:
     DATABASE_URL: ${{ secrets.DATABASE_URL }}
     REDIS_URL: ${{ secrets.REDIS_URL }}
     REDDIT_CLIENT_ID: ${{ secrets.REDDIT_CLIENT_ID }}
   ```

5. **Enable SSL/TLS** for databases and Redis in production (Neon and Redis Cloud do this by default)

---

## Next Steps

1. Copy `.env.example` → `.env`
2. Obtain Reddit API credentials (takes ~2 min)
3. Configure DATABASE_URL and REDIS_URL (local or cloud)
4. Run `make migrate` to initialize the database
5. Run tests to verify: `pytest -xvs`

**Questions?** Check `README.md` or open an issue on GitHub.
