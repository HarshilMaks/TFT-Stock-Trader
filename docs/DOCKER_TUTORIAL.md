Docker & Compose — Practical Guide for this repository

Purpose
-------
This document explains Docker basics in practical terms and describes the repository's Docker artifacts (compose file, verification script, volumes, and how to run and verify the development environment). It's written for developers new to Docker and for team onboarding.

Quick start
-----------
1. Copy environment file:

   cp .env.example .env

2. Start the dev environment (run from project root):

   docker-compose -f docker/docker-compose.dev.yml up -d

3. Check services status and logs:

   docker-compose -f docker/docker-compose.dev.yml ps
   docker-compose -f docker/docker-compose.dev.yml logs -f

4. Run the automated verification (optional):

   bash scripts/verify_docker_setup.sh

What this compose setup provides
--------------------------------
- PostgreSQL database (persistent via local volume)
- Redis (used as cache and Celery broker, persistent via local volume)
- Celery worker (builds from the repo Dockerfile and runs scraping/ML tasks)
- Celery beat (scheduler for periodic tasks)
- Flower (web UI for monitoring Celery on port 5555)

Key Docker concepts (short)
---------------------------
- Image vs Container: Images are recipes; containers are running instances of images.
- docker-compose: a YAML file that declares multiple services, networks and volumes and runs them together.
- Volumes: persist data outside containers (used here for Postgres, Redis, and Celery logs).
- Networks & service names: containers talk to one another using service names (e.g., postgres, redis), not localhost.
- Healthchecks: commands that report whether a service is ready; used to order startup.

Repo-specific files (what was added / where to look)
---------------------------------------------------
- docker/docker-compose.dev.yml
  - Main development compose file (services, ports, volumes, healthchecks, restart policies).
  - Important notes:
    - Postgres: image postgres:16-alpine, host port 5432 -> container 5432, volume: postgres_data.
    - Redis: image redis:7-alpine, port 6379 -> 6379, appendonly mode enabled, volume: redis_data.
    - Celery worker & beat: built from the repository Dockerfile (context: .). They mount ./backend for code hot-reload and depend on postgres and redis being healthy.
    - Flower: exposed at host port 5555 for web monitoring (http://localhost:5555).
    - Environment variables are expected to come from the project root .env file (see .env.example).

- scripts/verify_docker_setup.sh
  - Small utility that points at docker/docker-compose.dev.yml (COMPOSE_FILE) and runs a series of checks: pg_isready, redis PING, celery logs patterns, and Flower availability.
  - Run it from project root: bash scripts/verify_docker_setup.sh

- docs/DEVELOPMENT.md and other docs
  - Higher-level developer onboarding steps and commands; they now reference docker/docker-compose.dev.yml as the canonical compose path.

What happens when you run docker-compose -f docker/docker-compose.dev.yml up -d
-------------------------------------------------------------------------------
1. Docker pulls/builds images and creates the named Docker network (tft-network) and local volumes (postgres_data, redis_data, celery_logs).
2. Containers start in an order guided by healthchecks and depends_on: Postgres and Redis are started and checked; Celery waits for them to be healthy.
3. Postgres initializes (first-run SQL hooks if configured). Redis starts in AOF (append-only) mode.
4. Celery worker/beat connect to Redis (broker) and PostgreSQL (for app data) using service hostnames (redis, postgres).
5. Logs are written to Docker's logging driver (json-file) and can be tailed with docker-compose logs -f.

Why use Docker here (impact & trade-offs)
----------------------------------------
- Pros:
  - Reproducible development environment for everyone on the team.
  - Fast onboarding: "one command" to start all dependencies.
  - Isolation: no need to install DB/Redis locally or worry about version mismatch.
  - Parity with production config (helps to catch infra-related issues early).
- Cons / Costs:
  - Local resource usage (RAM/CPU) can be higher than native processes.
  - File permissions and volume ownership can cause startup errors (common with Postgres volumes).
  - Docker Compose does not replace production orchestrators (Kubernetes) but is ideal for local dev/testing.

Troubleshooting tips
--------------------
- Port conflicts: If host ports 5432 or 6379 are already in use, edit docker/docker-compose.dev.yml ports (e.g., 5433:5432) and update .env accordingly.
- Postgres won't start: check volume permissions, or remove volume and retry (docker-compose down -v) if you don't need persisted data.
- Celery can't connect: ensure Redis and Postgres show healthy in docker-compose ps and run docker-compose -f docker/docker-compose.dev.yml exec redis redis-cli PING
- Rebuild images if code changes affect Dockerfile: docker-compose -f docker/docker-compose.dev.yml build --no-cache celery_worker
- View logs for a single service: docker-compose -f docker/docker-compose.dev.yml logs -f celery_worker

Quick verification commands
---------------------------
- docker-compose -f docker/docker-compose.dev.yml ps
- docker-compose -f docker/docker-compose.dev.yml exec postgres pg_isready -U stockuser
- docker-compose -f docker/docker-compose.dev.yml exec redis redis-cli PING
- Open Flower: http://localhost:5555
- Run the scripted checks: bash scripts/verify_docker_setup.sh

Next steps (recommended)
------------------------
- Keep docker/docker-compose.dev.yml as the canonical development compose file (already moved and referenced everywhere).
- If you prefer shortcuts, add Makefile targets or npm scripts wrapping docker-compose commands.
- Learn these Docker commands for troubleshooting: docker ps -a, docker logs <container>, docker exec -it <container> /bin/sh, docker-compose down -v.

Further learning resources (short)
---------------------------------
- Docker docs: https://docs.docker.com/get-started/
- Docker Compose: https://docs.docker.com/compose/
- Intro to containers: https://www.docker.com/resources/what-container

If something fails locally, paste the output of: docker-compose -f docker/docker-compose.dev.yml ps && docker-compose -f docker/docker-compose.dev.yml logs --tail 100 and I will guide the fix.
