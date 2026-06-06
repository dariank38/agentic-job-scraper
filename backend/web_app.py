"""FastAPI API application for job scraper."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.tasks import lifespan
from app.api_routes import register_api_routes

app = FastAPI(
    title="Telegram Job Scraper API",
    description="API for scraping and analyzing Telegram job postings",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
register_api_routes(app)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
