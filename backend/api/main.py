from fastapi import FastAPI, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import posts, stocks
from backend.config.settings import settings
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from datetime import datetime
from backend.database.config import get_db


app = FastAPI(
    title="TFT Stock Trader API",
    version="1.0.0",
    description="Reddit sentiment-based stock prediction API"
)

# CORS - allow frontend to call API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(posts.router, prefix="/api")
app.include_router(stocks.router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "TFT Stock Trader API", "status": "running"}

@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check with database connectivity"""
    try:
        # Test database connection
        await db.execute(text("SELECT 1"))
        
        # Get stats
        from backend.models.reddit import RedditPost
        result = await db.execute(select(func.count(RedditPost.id)))
        post_count = result.scalar()
        
        return {
            "status": "healthy",
            "database": "connected",
            "environment": settings.environment,
            "total_posts": post_count,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )
