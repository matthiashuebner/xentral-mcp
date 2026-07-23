"""
Configuration management for Xentral MCP Server.
Handles API credentials and server settings with runtime updates.
"""

import logging
import os
from typing import Optional
from dotenv import load_dotenv

from security import validate_api_url, ApiUrlValidationError

logger = logging.getLogger(__name__)


class XentralConfig:
    """Configuration class for Xentral MCP Server with runtime credential updates."""

    def __init__(self):
        """Initialize configuration by loading from environment variables."""
        # Load .env file if it exists
        load_dotenv()

        # Optional allow-list of hostnames the api_url may point at (comma
        # separated). When set, only these hosts are accepted (SSRF defense).
        allowed = os.getenv('XENTRAL_ALLOWED_HOSTS', '').strip()
        self.allowed_hosts = [h.strip() for h in allowed.split(',') if h.strip()]

        # API Configuration. The env-provided URL is validated up front so an
        # http:// or internal target never receives the Bearer token.
        self.api_url = os.getenv('XENTRAL_API_URL', 'https://api.xentral.com')
        self.api_key = os.getenv('XENTRAL_API_KEY', '')
        if self.api_url:
            try:
                self.api_url = validate_api_url(self.api_url, self.allowed_hosts or None)
            except ApiUrlValidationError as exc:
                logger.warning(
                    "Ignoring invalid XENTRAL_API_URL (%s); set a valid https "
                    "URL via env or POST /config/credentials.", exc,
                )
                self.api_url = ''

        # Shared secret required on every MCP/admin request. If unset, the
        # server refuses to bind to a non-loopback interface (see validate_config).
        self.auth_token = os.getenv('MCP_AUTH_TOKEN', '')

        # Server Configuration. Default to loopback only; operators must opt in
        # explicitly to a wider binding AND set an auth token to do so.
        self.server_host = os.getenv('MCP_SERVER_HOST', '127.0.0.1')
        self.server_port = int(os.getenv('MCP_SERVER_PORT', '8888'))
        # Flask/Werkzeug debug (interactive debugger) is a remote-code-execution
        # risk and is intentionally NOT exposed as a runtime option. Application
        # log verbosity is controlled separately via LOG_LEVEL.
        self.debug_mode = False

        # Logging Configuration
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        self.log_requests = os.getenv('LOG_REQUESTS', 'true').lower() == 'true'

        # MCP Protocol Configuration
        self.mcp_version = "2024-11-05"
        self.server_name = "xentral-mcp-server"
        self.server_version = "1.0.0"

    def update_credentials(self, api_url: str, api_key: str) -> None:
        """
        Update API credentials at runtime.

        Args:
            api_url: New API URL for Xentral (validated against the SSRF/HTTPS
                policy and the optional allow-list)
            api_key: New API key for authentication

        Raises:
            ApiUrlValidationError: if api_url is rejected by the policy
        """
        # Raises ApiUrlValidationError on a disallowed URL; caller surfaces it.
        self.api_url = validate_api_url(api_url, self.allowed_hosts or None)
        self.api_key = api_key

    def is_auth_enabled(self) -> bool:
        """True if a shared secret is configured for request authentication."""
        return bool(self.auth_token)

    def is_local_only(self) -> bool:
        """True if the server binds to a loopback interface only."""
        return self.server_host in ('127.0.0.1', '::1', 'localhost')
    
    def is_configured(self) -> bool:
        """
        Check if the configuration has minimum required settings.
        
        Returns:
            bool: True if API URL and key are configured
        """
        return bool(self.api_url and self.api_key)
    
    def get_auth_headers(self) -> dict:
        """
        Get authentication headers for API requests.
        
        Returns:
            dict: Headers dictionary with authorization
        """
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'User-Agent': f'{self.server_name}/{self.server_version}'
        }
    
    def validate_config(self) -> list[str]:
        """
        Validate current configuration and return any errors.
        
        Returns:
            list[str]: List of validation error messages
        """
        errors = []

        if not self.api_url:
            errors.append("XENTRAL_API_URL is required")
        else:
            try:
                validate_api_url(self.api_url, self.allowed_hosts or None)
            except ApiUrlValidationError as exc:
                errors.append(f"XENTRAL_API_URL invalid: {exc}")

        if not self.api_key:
            errors.append("XENTRAL_API_KEY is required")
        elif len(self.api_key) < 10:
            errors.append("XENTRAL_API_KEY appears to be too short")

        if not (1 <= self.server_port <= 65535):
            errors.append("MCP_SERVER_PORT must be between 1 and 65535")

        return errors

    def validate_exposure(self) -> list[str]:
        """
        Validate the network-exposure policy. These are fatal: the server must
        not bind to a non-loopback interface without an authentication token.

        Returns:
            list[str]: Fatal errors that must prevent startup.
        """
        errors = []
        if not self.is_local_only() and not self.is_auth_enabled():
            errors.append(
                f"Refusing to bind to '{self.server_host}' without MCP_AUTH_TOKEN. "
                "Set MCP_AUTH_TOKEN to a strong secret, or bind to 127.0.0.1."
            )
        if self.auth_token and len(self.auth_token) < 16:
            errors.append(
                "MCP_AUTH_TOKEN is too short; use at least 16 random characters."
            )
        return errors
    
    def __str__(self) -> str:
        """String representation of config (without sensitive data)."""
        return (
            f"XentralConfig(\n"
            f"  api_url='{self.api_url}',\n"
            f"  api_key='{'*' * min(len(self.api_key), 8) if self.api_key else 'NOT_SET'}',\n"
            f"  server_host='{self.server_host}',\n"
            f"  server_port={self.server_port},\n"
            f"  debug_mode={self.debug_mode}\n"
            f")"
        )


# Global configuration instance
config = XentralConfig()
