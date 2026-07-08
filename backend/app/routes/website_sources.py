"""Website source routes — thin hub delegating to focused sub-modules.

Sub-modules:
  app/routes/website_sources_crud.py — GET/POST/PUT/DELETE /api/website-sources, toggle
  app/routes/website_actions.py      — fetch, fetch-all, analyze, analyze-all, stop
"""
from app.routes.website_sources_crud import register_website_source_crud_routes, detect_site_type
from app.routes.website_actions import (
    register_website_action_routes
)


def register_website_source_routes(app):
    register_website_source_crud_routes(app)
    register_website_action_routes(app)
