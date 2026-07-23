"""
Security utilities for the Xentral MCP server.

Centralizes the controls added in response to the security review:
- Constant-time bearer-token authentication (findings #1, #3)
- api_url validation to enforce HTTPS and block SSRF targets (#3, #7)
- Recursive redaction of secrets before logging (#5)
"""

import hmac
import ipaddress
import logging
import re
import socket
from typing import Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Hostnames that may legitimately use http:// and resolve to loopback,
# for local development only.
_LOCAL_HOSTNAMES = {"localhost", "127.0.0.1", "::1"}

# Keys whose values must never be written to logs.
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(pass|pwd|secret|token|api[_-]?key|authorization|bearer|"
    r"mfa|otp|credential|private)",
    re.IGNORECASE,
)

_MAX_LOGGED_STRING = 200


class ApiUrlValidationError(ValueError):
    """Raised when an api_url is rejected by validate_api_url."""


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def check_bearer_token(auth_header: Optional[str], expected_token: str) -> bool:
    """
    Validate an Authorization header against the expected bearer token.

    Uses hmac.compare_digest to avoid timing side channels. Returns True only
    when a well-formed `Bearer <token>` header matches the expected token.
    An empty expected_token means auth is disabled (caller decides whether
    that is acceptable for the current bind address).
    """
    if not expected_token:
        return True
    if not auth_header:
        return False
    parts = auth_header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False
    return hmac.compare_digest(parts[1].strip(), expected_token)


def is_local_hostname(hostname: Optional[str]) -> bool:
    """True if the hostname is a loopback name/address."""
    if not hostname:
        return False
    if hostname in _LOCAL_HOSTNAMES:
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# SSRF / transport validation for api_url
# ---------------------------------------------------------------------------

def _resolved_addresses(hostname: str) -> list[ipaddress._BaseAddress]:
    """Resolve a hostname to the list of IP addresses it points at."""
    addresses = []
    for info in socket.getaddrinfo(hostname, None):
        ip_str = info[4][0]
        # Strip IPv6 scope id if present (e.g. fe80::1%eth0)
        ip_str = ip_str.split("%", 1)[0]
        addresses.append(ipaddress.ip_address(ip_str))
    return addresses


def validate_api_url(url: str, allowed_hosts: Optional[list[str]] = None) -> str:
    """
    Validate a Xentral api_url before it is used for outbound requests.

    Enforces:
    - a parseable http/https URL with a hostname
    - https, except for explicitly-local hostnames (dev/testing)
    - the resolved host is not a private, loopback, link-local, reserved or
      multicast address (blocks cloud-metadata and internal-network SSRF),
      unless it is an allow-listed local host
    - if allowed_hosts is provided, the hostname must match one of them

    Returns the normalized URL (trailing slash stripped) or raises
    ApiUrlValidationError.
    """
    if not url or not isinstance(url, str):
        raise ApiUrlValidationError("api_url must be a non-empty string")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ApiUrlValidationError(
            f"api_url must use http or https, got '{parsed.scheme}'"
        )

    hostname = parsed.hostname
    if not hostname:
        raise ApiUrlValidationError("api_url must include a hostname")

    local = is_local_hostname(hostname)

    if parsed.scheme != "https" and not local:
        raise ApiUrlValidationError(
            "api_url must use https (http is only allowed for localhost)"
        )

    if allowed_hosts:
        normalized = hostname.lower()
        allowed = {h.lower() for h in allowed_hosts}
        if normalized not in allowed and not any(
            normalized == a or normalized.endswith("." + a.lstrip("*."))
            for a in allowed
        ):
            raise ApiUrlValidationError(
                f"api_url host '{hostname}' is not in the allowed host list"
            )

    if local:
        # Loopback explicitly permitted for local testing; skip the IP guard.
        return url.rstrip("/")

    try:
        addresses = _resolved_addresses(hostname)
    except (socket.gaierror, ValueError) as exc:
        raise ApiUrlValidationError(
            f"api_url host '{hostname}' could not be resolved: {exc}"
        )

    if not addresses:
        raise ApiUrlValidationError(
            f"api_url host '{hostname}' did not resolve to any address"
        )

    for ip in addresses:
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ApiUrlValidationError(
                f"api_url host '{hostname}' resolves to a non-routable/internal "
                f"address ({ip}); refusing to send requests there (SSRF guard)"
            )

    return url.rstrip("/")


# ---------------------------------------------------------------------------
# Log redaction
# ---------------------------------------------------------------------------

def redact(obj: Any, _depth: int = 0) -> Any:
    """
    Recursively redact secret-looking values so request payloads can be logged
    safely. Values under sensitive keys are replaced; long strings are trimmed.
    """
    if _depth > 6:
        return "…"
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            if _SENSITIVE_KEY_PATTERN.search(str(key)):
                result[key] = "***REDACTED***"
            else:
                result[key] = redact(value, _depth + 1)
        return result
    if isinstance(obj, (list, tuple)):
        trimmed = list(obj)[:20]
        return [redact(v, _depth + 1) for v in trimmed]
    if isinstance(obj, str) and len(obj) > _MAX_LOGGED_STRING:
        return obj[:_MAX_LOGGED_STRING] + "…"
    return obj


def redact_argument_keys(arguments: Any) -> Any:
    """Return just the argument key names for terse, safe logging."""
    if isinstance(arguments, dict):
        return sorted(arguments.keys())
    return type(arguments).__name__
