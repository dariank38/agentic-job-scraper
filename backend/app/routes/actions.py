"""Action-related API routes — thin hub delegating to focused sub-modules.

Sub-modules:
  app/routes/fetch_actions.py    — /api/fetch, /api/fetch-all, /api/telegram-dialogs
  app/routes/analyze_actions.py  — /api/analyze, /api/analyze-all, /api/reanalyze*, /api/stop-analyze, /api/bulk/stop, /api/cleanup/old-messages
  app/routes/cron.py             — /api/cron/*, /api/auto-analyze
  app/routes/listener_routes.py  — /api/listener/*
"""

from app.routes.fetch_actions import register_fetch_action_routes
from app.routes.analyze_actions import register_analyze_action_routes
from app.routes.cron import register_cron_routes
from app.routes.listener_routes import register_listener_routes


def register_action_routes(app):
    register_fetch_action_routes(app)
    register_analyze_action_routes(app)
    register_cron_routes(app)
    register_listener_routes(app)
