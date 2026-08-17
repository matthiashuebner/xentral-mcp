"""
Flask blueprint implementing the OAuth 2.1 surface a remote MCP client needs.

Endpoints served here:

    GET  /.well-known/oauth-protected-resource[/mcp]   RFC 9728 resource metadata
    GET  /.well-known/oauth-authorization-server[/mcp] RFC 8414 AS metadata
    POST /oauth/register                               RFC 7591 dynamic registration
    GET  /oauth/authorize                              consent form
    POST /oauth/authorize                              consent submission
    POST /oauth/token                                  code + refresh_token grants
    POST /oauth/revoke                                 RFC 7009 revocation

The authorization decision is a single operator password (`MCP_OAUTH_PASSWORD`),
not a user directory: this server fronts one Xentral instance with one API
credential, so there is exactly one principal to authorize. Registration is open
(clients must be able to self-register for the flow to work at all), which is
safe only because a registered client is worthless until the operator types that
password into the consent form — and the form names the client and its redirect
host, so a registration the operator did not initiate is visible as such.

The `/mcp` path variants of the two discovery documents exist because clients
differ on whether the resource path is appended to the well-known prefix.
"""

import logging
import secrets
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode, urlsplit, urlunsplit

from flask import Blueprint, Response, jsonify, redirect, request
from markupsafe import escape

from security import is_local_hostname

from .tokens import (
    TokenError,
    issue_access_token,
    pkce_s256_challenge,
    sign_payload,
    verify_payload,
)

logger = logging.getLogger(__name__)

SUPPORTED_SCOPES = ("mcp",)
DEFAULT_SCOPE = "mcp"
SUPPORTED_GRANT_TYPES = ("authorization_code", "refresh_token")
SUPPORTED_AUTH_METHODS = ("none", "client_secret_post", "client_secret_basic")

AUTH_CODE_TTL_SECONDS = 60
CONSENT_REQUEST_TTL_SECONDS = 600
CONSENT_FAILURE_WINDOW_SECONDS = 900
CONSENT_FAILURE_LIMIT = 5

_CONSENT_PURPOSE = "authorize-request"


# ---------------------------------------------------------------------------
# Redirect URI policy
# ---------------------------------------------------------------------------

def validate_redirect_uri(uri: str, allowed_hosts: Optional[List[str]] = None) -> bool:
    """
    Accept only redirect targets that cannot leak an authorization code.

    https anywhere (optionally narrowed to an operator allow-list), plus http on
    a loopback host because desktop MCP clients receive their callback on
    127.0.0.1. A fragment is rejected outright (RFC 6749 §3.1.2).
    """
    if not uri or len(uri) > 2048:
        return False

    parts = urlsplit(uri)
    if parts.fragment:
        return False
    if not parts.hostname:
        return False

    if parts.scheme == "http":
        if not is_local_hostname(parts.hostname):
            return False
    elif parts.scheme != "https":
        return False

    if allowed_hosts:
        host = parts.hostname.lower()
        allowed = {h.lower().lstrip("*.") for h in allowed_hosts}
        if is_local_hostname(host):
            return True
        if not any(host == a or host.endswith("." + a) for a in allowed):
            return False

    return True


def _append_query(uri: str, params: Dict[str, str]) -> str:
    parts = urlsplit(uri)
    query = f"{parts.query}&{urlencode(params)}" if parts.query else urlencode(params)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def _normalize_scope(requested: Optional[str]) -> str:
    """Keep the advertised scopes out of the requested set; never return empty."""
    if not requested:
        return DEFAULT_SCOPE
    granted = [s for s in requested.split() if s in SUPPORTED_SCOPES]
    dropped = [s for s in requested.split() if s not in SUPPORTED_SCOPES]
    if dropped:
        logger.info("Ignoring unsupported requested scope(s): %s", dropped)
    return " ".join(granted) if granted else DEFAULT_SCOPE


# ---------------------------------------------------------------------------
# Consent page
# ---------------------------------------------------------------------------

_PAGE_CSS = """
:root { color-scheme: light dark;
        --bg:#f5f6f8; --card:#ffffff; --fg:#16181d; --muted:#5b6472;
        --border:#d8dde5; --accent:#1f4b7a; --accent-fg:#ffffff; --error:#b3261e; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#14161a; --card:#1d2025; --fg:#e8eaed; --muted:#9aa4b2;
          --border:#31363f; --accent:#5b93cc; --accent-fg:#0d1117; --error:#f2b8b5; }
}
* { box-sizing:border-box; }
body { margin:0; min-height:100vh; display:flex; align-items:center;
       justify-content:center; padding:2rem 1rem; background:var(--bg);
       color:var(--fg); font:15px/1.55 system-ui,-apple-system,Segoe UI,sans-serif; }
.card { width:100%; max-width:27rem; background:var(--card);
        border:1px solid var(--border); border-radius:12px; padding:1.75rem; }
h1 { margin:0 0 .35rem; font-size:1.2rem; }
p { margin:.4rem 0; color:var(--muted); font-size:.9rem; }
dl { margin:1.1rem 0; padding:.85rem 1rem; background:var(--bg);
     border:1px solid var(--border); border-radius:8px; font-size:.88rem; }
dt { color:var(--muted); font-size:.75rem; text-transform:uppercase;
     letter-spacing:.04em; margin-top:.6rem; }
dt:first-child { margin-top:0; }
dd { margin:.15rem 0 0; word-break:break-all; font-family:ui-monospace,monospace; }
label { display:block; margin:1.1rem 0 .35rem; font-weight:600; font-size:.88rem; }
input { width:100%; padding:.6rem .7rem; font-size:1rem; color:var(--fg);
        background:var(--bg); border:1px solid var(--border); border-radius:8px; }
input:focus-visible { outline:2px solid var(--accent); outline-offset:1px; }
button { width:100%; margin-top:1.1rem; padding:.65rem; font-size:1rem;
         font-weight:600; color:var(--accent-fg); background:var(--accent);
         border:0; border-radius:8px; cursor:pointer; }
button:focus-visible { outline:2px solid var(--fg); outline-offset:2px; }
.error { margin:1rem 0 0; padding:.65rem .8rem; border-radius:8px;
         font-size:.88rem; color:var(--error);
         border:1px solid var(--error); background:transparent; }
"""


def _page(title: str, body: str, status: int = 200) -> Response:
    html = (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{escape(title)}</title><style>{_PAGE_CSS}</style></head>"
        f"<body><main class=\"card\">{body}</main></body></html>"
    )
    response = Response(html, status=status, mimetype="text/html; charset=utf-8")
    # The consent page carries a password field and must never be cached or framed.
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'"
    )
    return response


def _error_page(title: str, message: str, status: int) -> Response:
    return _page(
        title,
        f"<h1>{escape(title)}</h1><p>{escape(message)}</p>",
        status=status,
    )


def _consent_page(
    *,
    client_name: str,
    redirect_uri: str,
    scope: str,
    signed_request: str,
    error: Optional[str] = None,
) -> Response:
    redirect_host = urlsplit(redirect_uri).netloc or redirect_uri
    error_html = f'<p class="error">{escape(error)}</p>' if error else ""
    body = f"""
      <h1>Connect to Xentral MCP</h1>
      <p>A client is asking for access to your Xentral MCP server. Approve it
         only if you started this connection.</p>
      <dl>
        <dt>Client</dt><dd>{escape(client_name)}</dd>
        <dt>Redirects to</dt><dd>{escape(redirect_host)}</dd>
        <dt>Scope</dt><dd>{escape(scope)}</dd>
      </dl>
      <form method="post" action="/oauth/authorize">
        <input type="hidden" name="request" value="{escape(signed_request)}">
        <label for="password">Operator password</label>
        <input id="password" name="password" type="password" autocomplete="current-password"
               autofocus required>
        <button type="submit">Approve access</button>
      </form>
      {error_html}
    """
    return _page("Connect to Xentral MCP", body)


# ---------------------------------------------------------------------------
# Blueprint factory
# ---------------------------------------------------------------------------

def create_oauth_blueprint(config: Any, store: Any) -> Blueprint:
    """Build the OAuth blueprint bound to a config object and a store instance."""
    blueprint = Blueprint("oauth", __name__)

    def signing_key() -> bytes:
        return config.oauth_signing_key_bytes or store.signing_key()

    def acceptable_resources() -> set:
        return {config.mcp_resource_url.rstrip("/"), config.oauth_issuer.rstrip("/")}

    def token_error(
        error: str, description: str, status: int = 400
    ) -> Tuple[Response, int]:
        payload = {"error": error, "error_description": description}
        response = jsonify(payload)
        response.headers["Cache-Control"] = "no-store"
        return response, status

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def _protected_resource_metadata() -> Response:
        response = jsonify(
            {
                "resource": config.mcp_resource_url,
                "authorization_servers": [config.oauth_issuer],
                "scopes_supported": list(SUPPORTED_SCOPES),
                "bearer_methods_supported": ["header"],
                "resource_name": config.server_name,
                "resource_documentation": "https://github.com/matthiashuebner/xentral-mcp",
            }
        )
        response.headers["Cache-Control"] = "public, max-age=3600"
        return response

    def _authorization_server_metadata() -> Response:
        issuer = config.oauth_issuer
        response = jsonify(
            {
                "issuer": issuer,
                "authorization_endpoint": f"{issuer}/oauth/authorize",
                "token_endpoint": f"{issuer}/oauth/token",
                "registration_endpoint": f"{issuer}/oauth/register",
                "revocation_endpoint": f"{issuer}/oauth/revoke",
                "scopes_supported": list(SUPPORTED_SCOPES),
                "response_types_supported": ["code"],
                "response_modes_supported": ["query"],
                "grant_types_supported": list(SUPPORTED_GRANT_TYPES),
                "token_endpoint_auth_methods_supported": list(SUPPORTED_AUTH_METHODS),
                "revocation_endpoint_auth_methods_supported": list(SUPPORTED_AUTH_METHODS),
                # S256 only: 'plain' would let a network observer who sees the
                # authorization request replay the code exchange.
                "code_challenge_methods_supported": ["S256"],
                "service_documentation": "https://github.com/matthiashuebner/xentral-mcp",
            }
        )
        response.headers["Cache-Control"] = "public, max-age=3600"
        return response

    blueprint.add_url_rule(
        "/.well-known/oauth-protected-resource",
        "protected_resource_metadata",
        _protected_resource_metadata,
        methods=["GET"],
    )
    blueprint.add_url_rule(
        "/.well-known/oauth-protected-resource/mcp",
        "protected_resource_metadata_mcp",
        _protected_resource_metadata,
        methods=["GET"],
    )
    blueprint.add_url_rule(
        "/.well-known/oauth-authorization-server",
        "authorization_server_metadata",
        _authorization_server_metadata,
        methods=["GET"],
    )
    blueprint.add_url_rule(
        "/.well-known/oauth-authorization-server/mcp",
        "authorization_server_metadata_mcp",
        _authorization_server_metadata,
        methods=["GET"],
    )

    # ------------------------------------------------------------------
    # Dynamic client registration
    # ------------------------------------------------------------------

    @blueprint.route("/oauth/register", methods=["POST"])
    def register_client():
        metadata = request.get_json(silent=True)
        if not isinstance(metadata, dict):
            return token_error(
                "invalid_client_metadata", "Request body must be a JSON object"
            )

        redirect_uris = metadata.get("redirect_uris")
        if not isinstance(redirect_uris, list) or not redirect_uris:
            return token_error(
                "invalid_redirect_uri", "redirect_uris must be a non-empty array"
            )
        if len(redirect_uris) > 10:
            return token_error("invalid_redirect_uri", "too many redirect_uris")

        for uri in redirect_uris:
            if not isinstance(uri, str) or not validate_redirect_uri(
                uri, config.oauth_allowed_redirect_hosts or None
            ):
                return token_error(
                    "invalid_redirect_uri",
                    f"redirect_uri '{uri}' is not allowed (https, or http on loopback)",
                )

        auth_method = metadata.get("token_endpoint_auth_method", "none")
        if auth_method not in SUPPORTED_AUTH_METHODS:
            return token_error(
                "invalid_client_metadata",
                f"token_endpoint_auth_method must be one of {list(SUPPORTED_AUTH_METHODS)}",
            )

        grant_types = metadata.get("grant_types") or ["authorization_code", "refresh_token"]
        if not isinstance(grant_types, list) or any(
            g not in SUPPORTED_GRANT_TYPES for g in grant_types
        ):
            return token_error(
                "invalid_client_metadata",
                f"grant_types must be a subset of {list(SUPPORTED_GRANT_TYPES)}",
            )

        response_types = metadata.get("response_types") or ["code"]
        if not isinstance(response_types, list) or set(response_types) != {"code"}:
            return token_error(
                "invalid_client_metadata", "response_types must be ['code']"
            )

        client_name = str(metadata.get("client_name") or "Unnamed MCP client")[:120]
        scope = _normalize_scope(metadata.get("scope"))

        if auth_method == "none":
            existing = store.find_public_client(client_name, redirect_uris)
            if existing is not None:
                logger.info(
                    "Reusing existing public client registration for '%s'", client_name
                )
                return _registration_response(existing, None, status=200)

        if store.count_clients() >= config.oauth_max_clients:
            logger.warning(
                "Refusing client registration: %d clients registered (cap %d)",
                store.count_clients(),
                config.oauth_max_clients,
            )
            return token_error(
                "invalid_client_metadata",
                "client registration limit reached; remove stale clients from the "
                "OAuth store or raise MCP_OAUTH_MAX_CLIENTS",
                status=403,
            )

        client = store.register_client(
            client_name=client_name,
            redirect_uris=redirect_uris,
            grant_types=grant_types,
            response_types=response_types,
            token_endpoint_auth_method=auth_method,
            scope=scope,
        )
        logger.info(
            "Registered OAuth client '%s' (%s, auth=%s)",
            client_name,
            client["client_id"],
            auth_method,
        )
        return _registration_response(client, client.get("client_secret"), status=201)

    def _registration_response(
        client: Dict[str, Any], client_secret: Optional[str], status: int
    ) -> Tuple[Response, int]:
        payload = {
            "client_id": client["client_id"],
            "client_id_issued_at": client["created_at"],
            "client_name": client["client_name"],
            "redirect_uris": client["redirect_uris"],
            "grant_types": client["grant_types"],
            "response_types": client["response_types"],
            "token_endpoint_auth_method": client["token_endpoint_auth_method"],
            "scope": client["scope"],
        }
        if client_secret:
            payload["client_secret"] = client_secret
            payload["client_secret_expires_at"] = 0  # never expires
        response = jsonify(payload)
        response.headers["Cache-Control"] = "no-store"
        return response, status

    # ------------------------------------------------------------------
    # Authorization endpoint
    # ------------------------------------------------------------------

    @blueprint.route("/oauth/authorize", methods=["GET"])
    def authorize():
        client_id = request.args.get("client_id", "")
        redirect_uri = request.args.get("redirect_uri", "")

        # Client and redirect_uri are validated before anything is redirected:
        # bouncing an error off an unverified redirect_uri would turn this
        # endpoint into an open redirector.
        client = store.get_client(client_id) if client_id else None
        if client is None:
            return _error_page(
                "Unknown client",
                "This client is not registered with this server. Remove the "
                "connector in your client and add it again so it can register.",
                400,
            )
        if not redirect_uri or redirect_uri not in client["redirect_uris"]:
            return _error_page(
                "Invalid redirect URI",
                "The redirect_uri does not exactly match one registered by this client.",
                400,
            )

        state = request.args.get("state", "")

        def redirect_error(code: str, description: str) -> Response:
            params = {"error": code, "error_description": description}
            if state:
                params["state"] = state
            return redirect(_append_query(redirect_uri, params), code=302)

        if request.args.get("response_type") != "code":
            return redirect_error(
                "unsupported_response_type", "only response_type=code is supported"
            )

        code_challenge = request.args.get("code_challenge", "")
        if not code_challenge:
            return redirect_error(
                "invalid_request", "code_challenge is required (PKCE is mandatory)"
            )
        if request.args.get("code_challenge_method", "plain") != "S256":
            return redirect_error(
                "invalid_request", "code_challenge_method must be S256"
            )

        resource = request.args.get("resource") or config.mcp_resource_url
        if resource.rstrip("/") not in acceptable_resources():
            return redirect_error(
                "invalid_target",
                f"resource must be {config.mcp_resource_url}",
            )

        scope = _normalize_scope(request.args.get("scope"))

        # The pending request travels through the form signed rather than stored:
        # no server-side session, and the parameters cannot be edited in the
        # browser between rendering and submission.
        signed_request = sign_payload(
            signing_key(),
            {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "code_challenge": code_challenge,
                "scope": scope,
                "state": state,
                "resource": config.mcp_resource_url,
            },
            purpose=_CONSENT_PURPOSE,
            ttl_seconds=CONSENT_REQUEST_TTL_SECONDS,
        )

        return _consent_page(
            client_name=client["client_name"],
            redirect_uri=redirect_uri,
            scope=scope,
            signed_request=signed_request,
        )

    @blueprint.route("/oauth/authorize", methods=["POST"])
    def authorize_submit():
        signed_request = request.form.get("request", "")
        password = request.form.get("password", "")
        client_ip = request.remote_addr or "unknown"

        try:
            pending = verify_payload(
                signed_request, signing_key(), purpose=_CONSENT_PURPOSE
            )
        except TokenError as exc:
            logger.info("Rejected consent submission: %s", exc)
            return _error_page(
                "Request expired",
                "This authorization request is no longer valid. Start the "
                "connection again from your client.",
                400,
            )

        if store.count_consent_failures(client_ip, CONSENT_FAILURE_WINDOW_SECONDS) >= (
            CONSENT_FAILURE_LIMIT
        ):
            logger.warning("Consent throttle active for %s", client_ip)
            return _error_page(
                "Too many attempts",
                "Too many failed attempts. Wait 15 minutes and try again.",
                429,
            )

        if not config.verify_oauth_password(password):
            store.record_consent_failure(client_ip)
            logger.warning("Failed consent password attempt from %s", client_ip)
            client = store.get_client(pending["client_id"])
            return _consent_page(
                client_name=client["client_name"] if client else "Unknown client",
                redirect_uri=pending["redirect_uri"],
                scope=pending["scope"],
                signed_request=signed_request,
                error="Wrong password.",
            )

        store.clear_consent_failures(client_ip)

        code = secrets.token_urlsafe(32)
        store.store_auth_code(
            code,
            client_id=pending["client_id"],
            redirect_uri=pending["redirect_uri"],
            code_challenge=pending["code_challenge"],
            scope=pending["scope"],
            resource=pending["resource"],
            ttl_seconds=AUTH_CODE_TTL_SECONDS,
        )
        store.purge_expired()

        params = {"code": code}
        if pending.get("state"):
            params["state"] = pending["state"]

        logger.info(
            "Authorization granted to client %s", pending["client_id"]
        )
        return redirect(_append_query(pending["redirect_uri"], params), code=302)

    # ------------------------------------------------------------------
    # Token endpoint
    # ------------------------------------------------------------------

    def _authenticate_client(client_id_param: str) -> Tuple[Optional[Dict], Optional[Tuple]]:
        """
        Resolve and authenticate the client on a token request.

        Returns (client, None) on success or (None, error_response) on failure.
        """
        client_id = client_id_param
        client_secret = request.form.get("client_secret")

        # HTTP Basic (client_secret_basic) takes precedence when present.
        if request.authorization and request.authorization.type == "basic":
            client_id = request.authorization.username or client_id
            client_secret = request.authorization.password or client_secret

        if not client_id:
            return None, token_error("invalid_client", "client_id is required", 401)

        client = store.get_client(client_id)
        if client is None:
            return None, token_error("invalid_client", "unknown client_id", 401)

        if client["token_endpoint_auth_method"] != "none":
            if not client_secret or not store.verify_client_secret(client, client_secret):
                return None, token_error("invalid_client", "client authentication failed", 401)

        return client, None

    def _issue_tokens(
        *, client_id: str, scope: str, resource: str
    ) -> Tuple[Response, int]:
        access_token, expires_in = issue_access_token(
            signing_key(),
            issuer=config.oauth_issuer,
            subject="operator",
            client_id=client_id,
            audience=resource,
            scope=scope,
            ttl_seconds=config.oauth_access_token_ttl,
        )
        refresh_token = secrets.token_urlsafe(40)
        store.store_refresh_token(
            refresh_token,
            client_id=client_id,
            scope=scope,
            resource=resource,
            ttl_seconds=config.oauth_refresh_token_ttl,
        )

        response = jsonify(
            {
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": expires_in,
                "refresh_token": refresh_token,
                "scope": scope,
            }
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        return response, 200

    @blueprint.route("/oauth/token", methods=["POST"])
    def token():
        grant_type = request.form.get("grant_type", "")

        client, error = _authenticate_client(request.form.get("client_id", ""))
        if error is not None:
            return error

        if grant_type == "authorization_code":
            code = request.form.get("code", "")
            verifier = request.form.get("code_verifier", "")
            redirect_uri = request.form.get("redirect_uri", "")

            if not code or not verifier:
                return token_error(
                    "invalid_request", "code and code_verifier are required"
                )

            record = store.consume_auth_code(code)
            if record is None:
                return token_error(
                    "invalid_grant", "authorization code is invalid, expired or already used"
                )
            if record["client_id"] != client["client_id"]:
                return token_error("invalid_grant", "code was issued to another client")
            if redirect_uri and redirect_uri != record["redirect_uri"]:
                return token_error("invalid_grant", "redirect_uri mismatch")
            if pkce_s256_challenge(verifier) != record["code_challenge"]:
                return token_error("invalid_grant", "PKCE verification failed")

            return _issue_tokens(
                client_id=client["client_id"],
                scope=record["scope"],
                resource=record["resource"],
            )

        if grant_type == "refresh_token":
            presented = request.form.get("refresh_token", "")
            if not presented:
                return token_error("invalid_request", "refresh_token is required")

            record = store.consume_refresh_token(presented)
            if record is None:
                return token_error(
                    "invalid_grant", "refresh token is invalid, expired or already used"
                )
            if record["client_id"] != client["client_id"]:
                return token_error(
                    "invalid_grant", "refresh token was issued to another client"
                )

            requested_scope = request.form.get("scope")
            scope = record["scope"]
            if requested_scope:
                # A refresh must never widen scope beyond the original grant.
                narrowed = [s for s in requested_scope.split() if s in scope.split()]
                if not narrowed:
                    return token_error("invalid_scope", "requested scope exceeds the grant")
                scope = " ".join(narrowed)

            return _issue_tokens(
                client_id=client["client_id"], scope=scope, resource=record["resource"]
            )

        return token_error(
            "unsupported_grant_type",
            f"grant_type must be one of {list(SUPPORTED_GRANT_TYPES)}",
        )

    # ------------------------------------------------------------------
    # Revocation
    # ------------------------------------------------------------------

    @blueprint.route("/oauth/revoke", methods=["POST"])
    def revoke():
        # RFC 7009: the response is 200 whether or not the token existed, so a
        # caller cannot use this endpoint to probe which tokens are valid.
        presented = request.form.get("token", "")
        if presented:
            if store.revoke_refresh_token(presented):
                logger.info("Refresh token revoked")
        response = jsonify({})
        response.headers["Cache-Control"] = "no-store"
        return response, 200

    return blueprint
