"""FastAPI web application for job scraper UI."""

from fastapi import FastAPI

from app.tasks import lifespan
from app.web_routes import register_web_routes
from app.api_routes import register_api_routes

app = FastAPI(
    title="Telegram Job Scraper",
    description="Web UI for scraping and analyzing Telegram job postings",
    lifespan=lifespan,
)

# Register routes
register_web_routes(app)
register_api_routes(app)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
