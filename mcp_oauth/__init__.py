"""
Embedded OAuth 2.1 authorization server for the Xentral MCP HTTP server.

Remote MCP clients (Claude's custom connectors among them) do not offer a field
for a static bearer token. They authenticate by discovery: an unauthenticated
request must come back as 401 carrying a `WWW-Authenticate` header that points
at RFC 9728 protected-resource metadata, from which the client finds an
authorization server, registers itself via RFC 7591 dynamic client
registration, and runs an authorization-code + PKCE flow. This package
implements exactly that surface so such a client can connect, while the static
`MCP_AUTH_TOKEN` path stays available for curl and CLI clients.

Everything here is off unless `MCP_OAUTH_ENABLED=true`.
"""

from .store import OAuthStore
from .tokens import (
    TokenError,
    issue_access_token,
    sign_payload,
    verify_access_token,
    verify_payload,
)

__all__ = [
    "OAuthStore",
    "TokenError",
    "issue_access_token",
    "sign_payload",
    "verify_access_token",
    "verify_payload",
]
