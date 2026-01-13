from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import posts
from backend.config.settings import settings

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

@app.get("/")
async def root():
    return {"message": "TFT Stock Trader API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "environment": settings.environment}

