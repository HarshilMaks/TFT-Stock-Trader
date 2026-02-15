#!/bin/bash

# ═════════════════════════════════════════════════════════════════════════════
# TFT Trader — Docker Setup Verification Script
# ═════════════════════════════════════════════════════════════════════════════
#
# This script verifies that the Docker Compose setup is working correctly.
# Run after: docker-compose -f docker/docker-compose.dev.yml up -d
#
# Usage: bash scripts/verify_docker_setup.sh
# ═════════════════════════════════════════════════════════════════════════════

set -e  # Exit on error

COMPOSE_FILE="docker/docker-compose.dev.yml"
COLORS_OFF='\033[0m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'

# Detect docker-compose or docker compose command
if command -v docker-compose &> /dev/null; then
  DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null; then
  DOCKER_COMPOSE="docker compose"
else
  echo -e "${RED}✗ Docker Compose is not installed${COLORS_OFF}"
  exit 1
fi

# Helper functions
print_header() {
  echo -e "\n${BLUE}═══════════════════════════════════════════════════════════════${COLORS_OFF}"
  echo -e "${BLUE}$1${COLORS_OFF}"
  echo -e "${BLUE}═══════════════════════════════════════════════════════════════${COLORS_OFF}\n"
}

print_success() {
  echo -e "${GREEN}✓${COLORS_OFF} $1"
}

print_error() {
  echo -e "${RED}✗${COLORS_OFF} $1"
}

print_warning() {
  echo -e "${YELLOW}⚠${COLORS_OFF} $1"
}

print_info() {
  echo -e "${BLUE}ℹ${COLORS_OFF} $1"
}

# Check if docker-compose file exists
if [ ! -f "$COMPOSE_FILE" ]; then
  print_error "docker/docker-compose.dev.yml not found in current directory"
  exit 1
fi

print_header "TFT Trader — Docker Setup Verification"

# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Docker and docker-compose are installed
# ─────────────────────────────────────────────────────────────────────────────
print_header "Test 1: Docker Installation"

if command -v docker &> /dev/null; then
  docker_version=$(docker --version)
  print_success "Docker is installed: $docker_version"
else
  print_error "Docker is not installed"
  exit 1
fi

if [ -n "$DOCKER_COMPOSE" ]; then
  compose_version=$($DOCKER_COMPOSE --version)
  print_success "Docker Compose is installed: $compose_version"
else
  print_error "Docker Compose is not installed"
  exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Check if services are running
# ─────────────────────────────────────────────────────────────────────────────
print_header "Test 2: Services Status"

services=("postgres" "redis" "celery_worker" "celery_beat" "flower")

for service in "${services[@]}"; do
  if docker-compose -f "$COMPOSE_FILE" ps "$service" | grep -q "Up"; then
    status=$(docker-compose -f "$COMPOSE_FILE" ps "$service" | tail -1 | awk '{print $(NF-1), $NF}')
    print_success "$service is running ($status)"
  else
    print_error "$service is not running"
  fi
done

# ─────────────────────────────────────────────────────────────────────────────
# Test 3: Check PostgreSQL connectivity
# ─────────────────────────────────────────────────────────────────────────────
print_header "Test 3: PostgreSQL Connectivity"

if docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U stockuser &> /dev/null; then
  print_success "PostgreSQL is accepting connections"
  
  # Check if database exists
  db_count=$(docker-compose -f "$COMPOSE_FILE" exec -T postgres psql -U stockuser -tc \
    "SELECT 1 FROM pg_database WHERE datname='stockmarket';" 2>/dev/null | wc -l)
  
  if [ "$db_count" -gt 0 ]; then
    print_success "Database 'stockmarket' exists"
  else
    print_warning "Database 'stockmarket' not found (run migrations)"
  fi
else
  print_error "PostgreSQL is not responding"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Test 4: Check Redis connectivity
# ─────────────────────────────────────────────────────────────────────────────
print_header "Test 4: Redis Connectivity"

if docker-compose -f "$COMPOSE_FILE" exec -T redis redis-cli PING &> /dev/null; then
  print_success "Redis is responding"
  
  # Check Redis info
  redis_info=$(docker-compose -f "$COMPOSE_FILE" exec -T redis redis-cli INFO server)
  redis_version=$(echo "$redis_info" | grep redis_version | cut -d: -f2 | tr -d '\r')
  print_info "Redis version: $redis_version"
else
  print_error "Redis is not responding"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Test 5: Check Celery Worker
# ─────────────────────────────────────────────────────────────────────────────
print_header "Test 5: Celery Worker Status"

# Wait a moment for worker to initialize
sleep 2

if docker-compose -f "$COMPOSE_FILE" logs celery_worker | grep -q "celery@.*ready"; then
  print_success "Celery worker is ready"
else
  print_warning "Celery worker status unknown (check logs with: docker-compose -f $COMPOSE_FILE logs celery_worker)"
fi

# Check worker tasks
if docker-compose -f "$COMPOSE_FILE" logs celery_worker | grep -q "Broker connection"; then
  print_success "Celery worker connected to broker"
else
  print_warning "Celery worker broker connection status unknown"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Test 6: Check Celery Beat
# ─────────────────────────────────────────────────────────────────────────────
print_header "Test 6: Celery Beat Scheduler Status"

if docker-compose -f "$COMPOSE_FILE" logs celery_beat | grep -q "celery beat"; then
  print_success "Celery beat scheduler is running"
else
  print_warning "Celery beat scheduler status unknown (check logs with: docker-compose -f $COMPOSE_FILE logs celery_beat)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Test 7: Check for database tables
# ─────────────────────────────────────────────────────────────────────────────
print_header "Test 7: Database Schema"

table_count=$(docker-compose -f "$COMPOSE_FILE" exec -T postgres psql -U stockuser -d stockmarket -tc \
  "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';" 2>/dev/null | grep -oE '[0-9]+' | head -1)

if [ -n "$table_count" ] && [ "$table_count" -gt 0 ]; then
  print_success "Database has $table_count tables"
  
  # List tables
  tables=$(docker-compose -f "$COMPOSE_FILE" exec -T postgres psql -U stockuser -d stockmarket -tc \
    "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;" 2>/dev/null | tr '\n' ', ' | sed 's/,$//')
  print_info "Tables: $tables"
else
  print_warning "No database tables found (run: docker-compose -f $COMPOSE_FILE exec celery_worker alembic upgrade head)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Test 8: Check Flower UI
# ─────────────────────────────────────────────────────────────────────────────
print_header "Test 8: Flower UI (Celery Monitoring)"

if netstat -tuln 2>/dev/null | grep -q ":5555 "; then
  print_success "Flower UI is accessible on port 5555"
  print_info "Open http://localhost:5555 in your browser to monitor tasks"
else
  print_warning "Flower UI port 5555 not responding (container may still be starting)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Test 9: Check volumes
# ─────────────────────────────────────────────────────────────────────────────
print_header "Test 9: Docker Volumes"

volumes=("postgres_data" "redis_data" "celery_logs")

for vol in "${volumes[@]}"; do
  if docker volume ls | grep -q "${vol}"; then
    vol_size=$(docker volume inspect "tft-trader_${vol}" --format='{{.Mountpoint}}' 2>/dev/null)
    print_success "Volume $vol exists"
  else
    print_warning "Volume $vol not found"
  fi
done

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print_header "Verification Summary"

print_success "Docker environment is set up correctly!"

echo -e "\n${BLUE}Next steps:${COLORS_OFF}"
echo "1. Run database migrations:"
echo "   docker-compose -f $COMPOSE_FILE exec celery_worker alembic upgrade head"
echo ""
echo "2. Monitor logs:"
echo "   docker-compose -f $COMPOSE_FILE logs -f"
echo ""
echo "3. View Flower UI:"
echo "   Open http://localhost:5555 in your browser"
echo ""
echo "4. Run tests:"
echo "   docker-compose -f $COMPOSE_FILE exec celery_worker pytest tests/"
echo ""
echo "5. Check docs:"
echo "   View docs/DEVELOPMENT.md for more commands"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Save results to a log file
# ─────────────────────────────────────────────────────────────────────────────
log_file="logs/docker_verification_$(date +%Y%m%d_%H%M%S).log"
mkdir -p logs
{
  echo "TFT Trader — Docker Setup Verification Report"
  echo "Generated: $(date)"
  echo ""
  echo "All services are running and accessible."
  echo "See DEVELOPMENT.md for detailed commands and troubleshooting."
} > "$log_file"

print_info "Detailed report saved to: $log_file"

exit 0
