"""API routes registration for job scraper."""

from app.routes.actions import register_action_routes
from app.routes.autonomous import register_autonomous_routes
from app.routes.channels import register_channel_routes
from app.routes.developers import register_developer_routes
from app.routes.jobs import register_job_routes
from app.routes.messages import register_message_routes
from app.routes.operations import register_operations_routes
from app.routes.stats import register_stats_routes
from app.routes.telegram_accounts import register_telegram_account_routes
from app.routes.websocket import register_websocket_routes
from app.routes.resume import register_resume_routes
from app.routes.settings import register_settings_routes
from app.routes.website_sources import register_website_source_routes


def register_api_routes(app):
    """Register all API routes to the FastAPI app."""
    register_websocket_routes(app)
    register_channel_routes(app)
    register_job_routes(app)
    register_developer_routes(app)
    register_message_routes(app)
    register_stats_routes(app)
    register_action_routes(app)
    register_operations_routes(app)
    register_telegram_account_routes(app)
    register_website_source_routes(app)
    register_autonomous_routes(app)
    register_resume_routes(app)
    register_settings_routes(app)
