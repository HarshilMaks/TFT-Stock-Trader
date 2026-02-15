#!/bin/bash

# TFT Trader — Quick Setup Script
# Run this after cloning to initialize your development environment

set -e

echo "🚀 TFT Trader Development Setup"
echo "════════════════════════════════════════════════════════════════"

# 1. Check if .env exists
if [ ! -f .env ]; then
    echo "📋 Creating .env from .env.example..."
    cp .env.example .env
    echo "   ✓ Created .env"
else
    echo "   ✓ .env already exists"
fi

# 2. Check Python
if ! command -v python &> /dev/null; then
    echo "❌ Python not found. Please install Python 3.9+"
    exit 1
fi
PYTHON_VERSION=$(python --version)
echo "✓ Python: $PYTHON_VERSION"

# 3. Install dependencies
if [ ! -d ".venv" ]; then
    echo "📦 Installing dependencies with uv..."
    if command -v uv &> /dev/null; then
        uv sync
    else
        echo "⚠️  uv not found. Falling back to pip..."
        pip install -r requirements.txt
    fi
    echo "   ✓ Dependencies installed"
else
    echo "   ✓ Virtual environment exists"
fi

# 4. Start infrastructure
echo ""
echo "🐳 Starting Docker services..."
if command -v docker-compose &> /dev/null; then
    docker-compose -f docker-compose.yml up -d postgres redis
    echo "   ✓ PostgreSQL and Redis starting (may take 10-15 seconds)"
    
    # Wait for services to be ready
    sleep 10
    
    # Create database
    echo "   🗄️  Creating database..."
    docker-compose exec -T postgres createdb -U stockuser stockmarket 2>/dev/null || true
    echo "   ✓ Database ready"
else
    echo "⚠️  Docker not found. Please start PostgreSQL and Redis manually."
    echo "   See docs/credentials.md for connection strings."
fi

# 5. Run migrations
echo ""
echo "🔄 Running database migrations..."
uv run alembic upgrade head
echo "   ✓ Migrations complete"

# 6. Test Reddit API
echo ""
echo "🔍 Configuration Check..."
if grep -q "your_reddit_client_id_here" .env; then
    echo "⚠️  REDDIT_CLIENT_ID not configured"
    echo "   → Get credentials from reddit.com/prefs/apps"
    echo "   → See docs/credentials.md#3-reddit-api for step-by-step"
else
    echo "   ✓ Reddit credentials configured"
fi

# 7. Summary
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "✅ Setup Complete!"
echo ""
echo "📚 Next Steps:"
echo "   1. Configure REDDIT_CLIENT_ID & REDDIT_CLIENT_SECRET in .env"
echo "      → Edit .env and follow: reddit.com/prefs/apps"
echo "      → Full guide: docs/credentials.md"
echo ""
echo "   2. Start the API server:"
echo "      → uv run uvicorn backend.api.main:app --reload"
echo ""
echo "   3. Start Celery worker (in another terminal):"
echo "      → celery -A backend.celery_app worker --loglevel=info"
echo ""
echo "📖 Documentation:"
echo "   • Setup Guide: docs/credentials.md"
echo "   • Task Roadmap: docs/task_implementation.md"
echo "   • Architecture: ARCHITECTURE.md"
echo ""
echo "💡 Quick Commands:"
echo "   make app         — Start API server"
echo "   make worker      — Start Celery worker"
echo "   make migrate     — Run DB migrations"
echo "   make test        — Run tests"
echo "   make shell       — Python REPL with models loaded"
echo ""
