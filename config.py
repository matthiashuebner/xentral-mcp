"""
Configuration management for Xentral MCP Server.
Handles API credentials and server settings with runtime updates.
"""

import hashlib
import hmac
import logging
import os
from typing import Optional
from urllib.parse import urlsplit
from dotenv import load_dotenv

from security import validate_api_url, ApiUrlValidationError, is_local_hostname

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

        # ------------------------------------------------------------------
        # OAuth 2.1 (for remote MCP clients that cannot send a static token)
        # ------------------------------------------------------------------
        # Off by default: an existing deployment keeps behaving exactly as before
        # until the operator opts in, same flag pattern as the rest of the config.
        self.oauth_enabled = os.getenv('MCP_OAUTH_ENABLED', 'false').strip().lower() in (
            '1', 'true', 'yes', 'on'
        )
        # Externally reachable base URL. Cannot be derived from the request: the
        # OAuth issuer must be one fixed string, and behind a reverse proxy the
        # Host header is attacker-influenced. Required when OAuth is enabled.
        self.public_url = os.getenv('MCP_PUBLIC_URL', '').strip().rstrip('/')
        # The single authorization decision this server can make is "the operator
        # said yes", and this password is how the operator says it.
        self.oauth_password = os.getenv('MCP_OAUTH_PASSWORD', '')
        self.oauth_db_path = os.getenv('MCP_OAUTH_DB_PATH', 'oauth-store.sqlite3')
        # Optional: pin the hosts a client may be redirected back to. Loopback
        # stays allowed regardless, because desktop clients need it.
        oauth_hosts = os.getenv('MCP_OAUTH_ALLOWED_REDIRECT_HOSTS', '').strip()
        self.oauth_allowed_redirect_hosts = [
            h.strip() for h in oauth_hosts.split(',') if h.strip()
        ]
        self.oauth_access_token_ttl = int(os.getenv('MCP_OAUTH_ACCESS_TOKEN_TTL', '3600'))
        self.oauth_refresh_token_ttl = int(
            os.getenv('MCP_OAUTH_REFRESH_TOKEN_TTL', str(30 * 24 * 3600))
        )
        self.oauth_max_clients = int(os.getenv('MCP_OAUTH_MAX_CLIENTS', '50'))
        # Optional explicit signing key. Left empty, the store generates one and
        # persists it, which is what a single-host deployment wants. Set it
        # explicitly when several hosts must verify each other's tokens.
        signing_key = os.getenv('MCP_OAUTH_SIGNING_KEY', '').strip()
        self.oauth_signing_key_bytes = signing_key.encode('utf-8') if signing_key else b''

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

    def is_oauth_enabled(self) -> bool:
        """True if the embedded OAuth authorization server is active."""
        return bool(self.oauth_enabled)

    def is_any_auth_enabled(self) -> bool:
        """
        True if *some* authentication is in force.

        The exposure guard uses this rather than is_auth_enabled(): an
        OAuth-only deployment has no static token, and refusing to bind it to a
        public interface would make the OAuth path useless.
        """
        return self.is_auth_enabled() or self.is_oauth_enabled()

    @property
    def oauth_issuer(self) -> str:
        """The OAuth issuer identifier — the server's external base URL."""
        return self.public_url

    @property
    def mcp_resource_url(self) -> str:
        """The resource identifier tokens are audience-bound to (RFC 8707)."""
        return f"{self.public_url}/mcp"

    def verify_oauth_password(self, presented: str) -> bool:
        """
        Constant-time check of the consent password.

        Compares digests rather than the raw strings so the comparison cost does
        not depend on the password length.
        """
        if not self.oauth_password or not presented:
            return False
        return hmac.compare_digest(
            hashlib.sha256(presented.encode('utf-8')).digest(),
            hashlib.sha256(self.oauth_password.encode('utf-8')).digest(),
        )

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
        if not self.is_local_only() and not self.is_any_auth_enabled():
            errors.append(
                f"Refusing to bind to '{self.server_host}' without authentication. "
                "Set MCP_AUTH_TOKEN to a strong secret, enable MCP_OAUTH_ENABLED, "
                "or bind to 127.0.0.1."
            )
        if self.auth_token and len(self.auth_token) < 16:
            errors.append(
                "MCP_AUTH_TOKEN is too short; use at least 16 random characters."
            )

        # OAuth boot guard. A half-configured authorization server is worse than
        # none: the client would run the whole discovery/registration dance and
        # then fail at the consent step, which reads as the same opaque
        # authorization error the operator was trying to fix.
        if self.is_oauth_enabled():
            if not self.public_url:
                errors.append(
                    "MCP_OAUTH_ENABLED requires MCP_PUBLIC_URL (the externally "
                    "reachable base URL, e.g. https://mcp.example.com) — it is the "
                    "OAuth issuer and cannot be inferred from the request."
                )
            else:
                parsed = urlsplit(self.public_url)
                if parsed.scheme == 'http' and not is_local_hostname(parsed.hostname):
                    errors.append(
                        "MCP_PUBLIC_URL must use https (http is only allowed for "
                        "localhost); OAuth tokens must never travel in plaintext."
                    )
                elif parsed.scheme not in ('http', 'https') or not parsed.hostname:
                    errors.append(
                        f"MCP_PUBLIC_URL '{self.public_url}' is not a valid http(s) URL."
                    )
                elif parsed.query or parsed.fragment:
                    errors.append(
                        "MCP_PUBLIC_URL must be a bare base URL without query or fragment."
                    )

            if len(self.oauth_password) < 12:
                errors.append(
                    "MCP_OAUTH_ENABLED requires MCP_OAUTH_PASSWORD with at least 12 "
                    "characters — it is the only gate on the authorization flow."
                )
            if self.oauth_signing_key_bytes and len(self.oauth_signing_key_bytes) < 32:
                errors.append(
                    "MCP_OAUTH_SIGNING_KEY is too short; use at least 32 characters "
                    "or leave it empty to let the server generate and persist one."
                )
            if self.oauth_access_token_ttl < 60:
                errors.append("MCP_OAUTH_ACCESS_TOKEN_TTL must be at least 60 seconds.")

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
