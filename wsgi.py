"""
WSGI entry point for production deployment.

Run with a real WSGI server instead of the Flask development server, e.g.:

    gunicorn --bind 127.0.0.1:8888 wsgi:app

Place a TLS-terminating, authenticating reverse proxy in front for any
non-local exposure, and set MCP_AUTH_TOKEN. The same fail-closed exposure
checks as the CLI entry point are enforced here before the app is served.
"""

import sys

from config import config
from mcp_server import create_app, initialize_tools


def _build_app():
    exposure_errors = config.validate_exposure()
    if exposure_errors:
        for error in exposure_errors:
            print(f"❌ {error}", file=sys.stderr)
        raise SystemExit(
            "Refusing to start: insecure network exposure (see errors above)."
        )

    application = create_app()
    if not initialize_tools():
        raise SystemExit("Failed to initialize MCP tools.")
    return application


app = _build_app()
