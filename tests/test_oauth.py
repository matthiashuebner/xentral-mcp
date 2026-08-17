"""
Tests for the embedded OAuth 2.1 authorization server and the Streamable-HTTP
fixes that go with it.

Run with:  python tests/test_oauth.py
"""
import os
import re
import secrets
import sys
import tempfile
import time
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_STORE_PATH = os.path.join(tempfile.mkdtemp(prefix="xentral-oauth-test-"), "store.sqlite3")

# Configure BEFORE importing config: OAuth on, static token also on so the two
# credentials can be shown to coexist.
os.environ["MCP_AUTH_TOKEN"] = "s3cret-token-abcdefghijklmnop"
os.environ["XENTRAL_API_KEY"] = "test-api-key-12345"
os.environ["XENTRAL_API_URL"] = "https://example.com"
os.environ["MCP_SERVER_HOST"] = "127.0.0.1"
os.environ["MCP_OAUTH_ENABLED"] = "true"
os.environ["MCP_PUBLIC_URL"] = "https://mcp.example.com"
os.environ["MCP_OAUTH_PASSWORD"] = "operator-password-123"
os.environ["MCP_OAUTH_DB_PATH"] = _STORE_PATH

from config import XentralConfig, config
from mcp_oauth import OAuthStore, issue_access_token, verify_access_token, TokenError
from mcp_oauth.routes import validate_redirect_uri
from mcp_oauth.tokens import pkce_s256_challenge
from mcp_server import create_app

RESOURCE = "https://mcp.example.com/mcp"
ISSUER = "https://mcp.example.com"
REDIRECT_URI = "https://claude.ai/api/mcp/auth_callback"

fails = []


def check(name, cond):
    print(f"{'PASS' if cond else 'FAIL'}: {name}")
    if not cond:
        fails.append(name)


app = create_app()
client = app.test_client()
store = OAuthStore(_STORE_PATH)
SIGNING_KEY = store.signing_key()


# ---------------------------------------------------------------------------
# The 401 that starts the flow
# ---------------------------------------------------------------------------

response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
challenge = response.headers.get("WWW-Authenticate", "")
check("unauthenticated /mcp returns 401", response.status_code == 401)
check("401 carries a WWW-Authenticate challenge", challenge.startswith("Bearer "))
check(
    "challenge points at the protected-resource metadata",
    f'resource_metadata="{ISSUER}/.well-known/oauth-protected-resource"' in challenge,
)

# ---------------------------------------------------------------------------
# Discovery documents
# ---------------------------------------------------------------------------

for path in (
    "/.well-known/oauth-protected-resource",
    "/.well-known/oauth-protected-resource/mcp",
):
    doc = client.get(path)
    check(f"{path} is public and returns 200", doc.status_code == 200)
    check(f"{path} names the resource", doc.get_json().get("resource") == RESOURCE)
    check(
        f"{path} names the authorization server",
        doc.get_json().get("authorization_servers") == [ISSUER],
    )

for path in (
    "/.well-known/oauth-authorization-server",
    "/.well-known/oauth-authorization-server/mcp",
):
    doc = client.get(path)
    meta = doc.get_json()
    check(f"{path} is public and returns 200", doc.status_code == 200)
    check(f"{path} issuer matches", meta.get("issuer") == ISSUER)
    check(
        f"{path} advertises registration",
        meta.get("registration_endpoint") == f"{ISSUER}/oauth/register",
    )
    check(f"{path} requires PKCE S256", meta.get("code_challenge_methods_supported") == ["S256"])
    check(f"{path} does not offer plain PKCE", "plain" not in meta.get("code_challenge_methods_supported", []))

# ---------------------------------------------------------------------------
# Dynamic client registration
# ---------------------------------------------------------------------------

registration = client.post(
    "/oauth/register",
    json={"client_name": "Claude", "redirect_uris": [REDIRECT_URI]},
)
check("registration returns 201", registration.status_code == 201)
CLIENT_ID = registration.get_json().get("client_id", "")
check("registration returns a client_id", bool(CLIENT_ID))
check(
    "public client gets no secret",
    "client_secret" not in registration.get_json(),
)

repeat = client.post(
    "/oauth/register",
    json={"client_name": "Claude", "redirect_uris": [REDIRECT_URI]},
)
check(
    "identical public registration is reused, not duplicated",
    repeat.get_json().get("client_id") == CLIENT_ID,
)

bad_redirect = client.post(
    "/oauth/register",
    json={"client_name": "Evil", "redirect_uris": ["http://evil.example/callback"]},
)
check("plaintext non-loopback redirect_uri rejected", bad_redirect.status_code == 400)

no_redirect = client.post("/oauth/register", json={"client_name": "Evil"})
check("registration without redirect_uris rejected", no_redirect.status_code == 400)

confidential = client.post(
    "/oauth/register",
    json={
        "client_name": "Backend",
        "redirect_uris": ["https://backend.example/cb"],
        "token_endpoint_auth_method": "client_secret_post",
    },
)
check("confidential client gets a secret", bool(confidential.get_json().get("client_secret")))

# validate_redirect_uri unit checks
check("https redirect allowed", validate_redirect_uri("https://claude.ai/cb"))
check("loopback http redirect allowed", validate_redirect_uri("http://127.0.0.1:33418/cb"))
check("http non-loopback redirect rejected", not validate_redirect_uri("http://evil.example/cb"))
check("redirect with fragment rejected", not validate_redirect_uri("https://a.example/cb#x"))
check("non-http scheme redirect rejected", not validate_redirect_uri("javascript:alert(1)"))
check(
    "allow-list narrows https redirects",
    not validate_redirect_uri("https://other.example/cb", ["claude.ai"]),
)
check(
    "allow-list still permits loopback",
    validate_redirect_uri("http://localhost:9999/cb", ["claude.ai"]),
)

# ---------------------------------------------------------------------------
# Authorization endpoint
# ---------------------------------------------------------------------------

VERIFIER = secrets.token_urlsafe(48)
CHALLENGE = pkce_s256_challenge(VERIFIER)


def authorize_params(**overrides):
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "code_challenge": CHALLENGE,
        "code_challenge_method": "S256",
        "state": "state-value-xyz",
        "resource": RESOURCE,
        "scope": "mcp",
    }
    params.update(overrides)
    return {k: v for k, v in params.items() if v is not None}


unknown = client.get("/oauth/authorize", query_string=authorize_params(client_id="nope"))
check("unknown client gets an error page, not a redirect", unknown.status_code == 400)

mismatched = client.get(
    "/oauth/authorize", query_string=authorize_params(redirect_uri="https://evil.example/cb")
)
check(
    "unregistered redirect_uri is not redirected to (no open redirector)",
    mismatched.status_code == 400 and "Location" not in mismatched.headers,
)

no_pkce = client.get("/oauth/authorize", query_string=authorize_params(code_challenge=None))
check("missing PKCE redirects with an error", no_pkce.status_code == 302)
check(
    "missing PKCE error preserves state",
    "state=state-value-xyz" in no_pkce.headers.get("Location", ""),
)

plain_pkce = client.get(
    "/oauth/authorize", query_string=authorize_params(code_challenge_method="plain")
)
check("plain PKCE rejected", plain_pkce.status_code == 302 and "error=" in plain_pkce.headers["Location"])

wrong_resource = client.get(
    "/oauth/authorize", query_string=authorize_params(resource="https://elsewhere.example/mcp")
)
check(
    "foreign resource indicator rejected",
    wrong_resource.status_code == 302 and "invalid_target" in wrong_resource.headers["Location"],
)

consent = client.get("/oauth/authorize", query_string=authorize_params())
check("valid authorize request renders the consent form", consent.status_code == 200)
body = consent.get_data(as_text=True)
check("consent form names the client", "Claude" in body)
check("consent form is not cacheable", consent.headers.get("Cache-Control") == "no-store")
check("consent form refuses framing", consent.headers.get("X-Frame-Options") == "DENY")

signed_request = re.search(r'name="request" value="([^"]+)"', body).group(1)

# ---------------------------------------------------------------------------
# Consent submission
# ---------------------------------------------------------------------------

wrong_password = client.post(
    "/oauth/authorize", data={"request": signed_request, "password": "not-the-password"}
)
check("wrong password does not redirect", wrong_password.status_code == 200)
check("wrong password re-renders the form with an error", "Wrong password" in wrong_password.get_data(as_text=True))

tampered = client.post(
    "/oauth/authorize", data={"request": signed_request[:-3] + "aaa", "password": "operator-password-123"}
)
check("tampered authorization request rejected", tampered.status_code == 400)

granted = client.post(
    "/oauth/authorize", data={"request": signed_request, "password": "operator-password-123"}
)
check("correct password redirects back to the client", granted.status_code == 302)
location = granted.headers["Location"]
check("redirect goes to the registered redirect_uri", location.startswith(REDIRECT_URI))
query = parse_qs(urlsplit(location).query)
check("redirect carries the state unchanged", query.get("state") == ["state-value-xyz"])
CODE = query.get("code", [""])[0]
check("redirect carries an authorization code", bool(CODE))

# ---------------------------------------------------------------------------
# Token endpoint
# ---------------------------------------------------------------------------

wrong_verifier = client.post(
    "/oauth/token",
    data={
        "grant_type": "authorization_code",
        "code": CODE,
        "code_verifier": secrets.token_urlsafe(48),
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
    },
)
check("wrong PKCE verifier is rejected", wrong_verifier.status_code == 400)
check(
    "wrong PKCE verifier reports invalid_grant",
    wrong_verifier.get_json().get("error") == "invalid_grant",
)

# The failed exchange consumed the code (single use), so a fresh one is needed.
consent = client.get("/oauth/authorize", query_string=authorize_params())
signed_request = re.search(
    r'name="request" value="([^"]+)"', consent.get_data(as_text=True)
).group(1)
granted = client.post(
    "/oauth/authorize", data={"request": signed_request, "password": "operator-password-123"}
)
CODE = parse_qs(urlsplit(granted.headers["Location"]).query)["code"][0]

token_response = client.post(
    "/oauth/token",
    data={
        "grant_type": "authorization_code",
        "code": CODE,
        "code_verifier": VERIFIER,
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
    },
)
check("code exchange succeeds", token_response.status_code == 200)
payload = token_response.get_json()
ACCESS_TOKEN = payload.get("access_token", "")
REFRESH_TOKEN = payload.get("refresh_token", "")
check("token response carries an access token", bool(ACCESS_TOKEN))
check("token response carries a refresh token", bool(REFRESH_TOKEN))
check("token type is Bearer", payload.get("token_type") == "Bearer")
check("token response is not cacheable", token_response.headers.get("Cache-Control") == "no-store")

replay = client.post(
    "/oauth/token",
    data={
        "grant_type": "authorization_code",
        "code": CODE,
        "code_verifier": VERIFIER,
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
    },
)
check("replaying an authorization code fails", replay.status_code == 400)

unsupported = client.post(
    "/oauth/token", data={"grant_type": "password", "client_id": CLIENT_ID}
)
check(
    "unsupported grant type rejected",
    unsupported.get_json().get("error") == "unsupported_grant_type",
)

unknown_client = client.post(
    "/oauth/token", data={"grant_type": "authorization_code", "client_id": "nope"}
)
check("unknown client on token endpoint gets 401", unknown_client.status_code == 401)

# ---------------------------------------------------------------------------
# Using the access token
# ---------------------------------------------------------------------------

authorized = client.post(
    "/mcp",
    json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
    headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
)
check("access token authenticates an MCP request", authorized.status_code == 200)
check(
    "negotiated protocol version echoes the client's request",
    authorized.get_json()["result"]["protocolVersion"] == "2025-06-18",
)

old_client = client.post(
    "/mcp",
    json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
    headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
)
check(
    "older protocol revision is still honoured",
    old_client.get_json()["result"]["protocolVersion"] == "2024-11-05",
)

unknown_version = client.post(
    "/mcp",
    json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "1999-01-01"}},
    headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
)
check(
    "unknown protocol revision falls back to the newest supported",
    unknown_version.get_json()["result"]["protocolVersion"] == "2025-06-18",
)

static_token = client.post(
    "/mcp",
    json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
    headers={"Authorization": "Bearer s3cret-token-abcdefghijklmnop"},
)
check("static MCP_AUTH_TOKEN still works alongside OAuth", static_token.status_code == 200)

garbage = client.post(
    "/mcp",
    json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
    headers={"Authorization": "Bearer not-a-real-token"},
)
check("garbage bearer token is rejected", garbage.status_code == 401)

# Audience and issuer binding
foreign_audience, _ = issue_access_token(
    SIGNING_KEY,
    issuer=ISSUER,
    subject="operator",
    client_id=CLIENT_ID,
    audience="https://other.example/mcp",
    scope="mcp",
    ttl_seconds=3600,
)
rejected = client.post(
    "/mcp",
    json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
    headers={"Authorization": f"Bearer {foreign_audience}"},
)
check("token minted for another resource is rejected", rejected.status_code == 401)

foreign_issuer, _ = issue_access_token(
    SIGNING_KEY,
    issuer="https://evil.example",
    subject="operator",
    client_id=CLIENT_ID,
    audience=RESOURCE,
    scope="mcp",
    ttl_seconds=3600,
)
rejected = client.post(
    "/mcp",
    json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
    headers={"Authorization": f"Bearer {foreign_issuer}"},
)
check("token from another issuer is rejected", rejected.status_code == 401)

wrong_key, _ = issue_access_token(
    b"x" * 32,
    issuer=ISSUER,
    subject="operator",
    client_id=CLIENT_ID,
    audience=RESOURCE,
    scope="mcp",
    ttl_seconds=3600,
)
rejected = client.post(
    "/mcp",
    json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
    headers={"Authorization": f"Bearer {wrong_key}"},
)
check("token signed with another key is rejected", rejected.status_code == 401)

expired, _ = issue_access_token(
    SIGNING_KEY,
    issuer=ISSUER,
    subject="operator",
    client_id=CLIENT_ID,
    audience=RESOURCE,
    scope="mcp",
    ttl_seconds=1,
    now=int(time.time()) - 3600,
)
rejected = client.post(
    "/mcp",
    json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
    headers={"Authorization": f"Bearer {expired}"},
)
check("expired token is rejected", rejected.status_code == 401)

no_scope, _ = issue_access_token(
    SIGNING_KEY,
    issuer=ISSUER,
    subject="operator",
    client_id=CLIENT_ID,
    audience=RESOURCE,
    scope="something-else",
    ttl_seconds=3600,
)
insufficient = client.post(
    "/mcp",
    json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
    headers={"Authorization": f"Bearer {no_scope}"},
)
check("token without the mcp scope gets 403", insufficient.status_code == 403)

# ---------------------------------------------------------------------------
# Refresh tokens
# ---------------------------------------------------------------------------

refreshed = client.post(
    "/oauth/token",
    data={
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN,
        "client_id": CLIENT_ID,
    },
)
check("refresh grant succeeds", refreshed.status_code == 200)
NEW_REFRESH = refreshed.get_json().get("refresh_token", "")
check("refresh token is rotated", NEW_REFRESH and NEW_REFRESH != REFRESH_TOKEN)

reused = client.post(
    "/oauth/token",
    data={
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN,
        "client_id": CLIENT_ID,
    },
)
check("reusing a rotated refresh token fails", reused.status_code == 400)

revoked = client.post("/oauth/revoke", data={"token": NEW_REFRESH})
check("revocation returns 200", revoked.status_code == 200)
after_revoke = client.post(
    "/oauth/token",
    data={
        "grant_type": "refresh_token",
        "refresh_token": NEW_REFRESH,
        "client_id": CLIENT_ID,
    },
)
check("revoked refresh token no longer works", after_revoke.status_code == 400)
check(
    "revoking an unknown token still returns 200 (no probing oracle)",
    client.post("/oauth/revoke", data={"token": "never-existed"}).status_code == 200,
)

# ---------------------------------------------------------------------------
# Streamable HTTP transport
# ---------------------------------------------------------------------------

notification = client.post(
    "/mcp",
    json={"jsonrpc": "2.0", "method": "notifications/initialized"},
    headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
)
check("notification answers 202 with no body", notification.status_code == 202)
check("notification body is empty", notification.get_data(as_text=True) == "")

sse = client.post(
    "/mcp",
    json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
    headers={"Authorization": f"Bearer {ACCESS_TOKEN}", "Accept": "text/event-stream"},
)
check("SSE-only client gets an event stream", sse.mimetype == "text/event-stream")
check("SSE payload is a data frame", sse.get_data(as_text=True).startswith("event: message\ndata: "))

both = client.post(
    "/mcp",
    json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
    headers={
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Accept": "application/json, text/event-stream",
    },
)
check("client accepting both gets JSON", both.mimetype == "application/json")

get_mcp = client.get("/mcp", headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
check("GET /mcp returns 405", get_mcp.status_code == 405)
check("405 advertises the allowed method", get_mcp.headers.get("Allow") == "POST")

delete_mcp = client.delete("/mcp", headers={"Authorization": f"Bearer {ACCESS_TOKEN}"})
check("DELETE /mcp returns 405", delete_mcp.status_code == 405)

health = client.get("/health")
check("/health stays public", health.status_code == 200)

# ---------------------------------------------------------------------------
# Boot guard
# ---------------------------------------------------------------------------

def exposure_errors(**env):
    saved = {k: os.environ.get(k) for k in env}
    os.environ.update({k: v for k, v in env.items() if v is not None})
    for k, v in env.items():
        if v is None:
            os.environ.pop(k, None)
    try:
        return XentralConfig().validate_exposure()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


check(
    "OAuth without MCP_PUBLIC_URL is fatal",
    any("MCP_PUBLIC_URL" in e for e in exposure_errors(MCP_PUBLIC_URL="")),
)
check(
    "OAuth over plaintext http is fatal",
    any("https" in e for e in exposure_errors(MCP_PUBLIC_URL="http://mcp.example.com")),
)
check(
    "OAuth with a short password is fatal",
    any("MCP_OAUTH_PASSWORD" in e for e in exposure_errors(MCP_OAUTH_PASSWORD="short")),
)
check(
    "OAuth on localhost http is allowed for development",
    not exposure_errors(MCP_PUBLIC_URL="http://localhost:8888"),
)
check(
    "public bind with OAuth but no static token is allowed",
    not exposure_errors(MCP_SERVER_HOST="0.0.0.0", MCP_AUTH_TOKEN=None),
)
check(
    "public bind with neither credential is still fatal",
    any(
        "Refusing to bind" in e
        for e in exposure_errors(
            MCP_SERVER_HOST="0.0.0.0", MCP_AUTH_TOKEN=None, MCP_OAUTH_ENABLED="false"
        )
    ),
)

# ---------------------------------------------------------------------------
# Token helper edge cases
# ---------------------------------------------------------------------------

valid, _ = issue_access_token(
    SIGNING_KEY,
    issuer=ISSUER,
    subject="operator",
    client_id=CLIENT_ID,
    audience=RESOURCE,
    scope="mcp",
    ttl_seconds=3600,
)


def token_rejected(token, **kwargs):
    params = {"issuer": ISSUER, "audiences": [RESOURCE]}
    params.update(kwargs)
    try:
        verify_access_token(token, SIGNING_KEY, **params)
        return False
    except TokenError:
        return True


check("well-formed token verifies", not token_rejected(valid))
check("truncated token rejected", token_rejected(valid.rsplit(".", 1)[0]))
check("token with flipped signature byte rejected", token_rejected(valid[:-1] + ("A" if valid[-1] != "A" else "B")))
check("empty token rejected", token_rejected(""))
check("PKCE challenge is stable", pkce_s256_challenge("abc") == pkce_s256_challenge("abc"))
check("PKCE challenge differs per verifier", pkce_s256_challenge("abc") != pkce_s256_challenge("abd"))

# ---------------------------------------------------------------------------

print("-" * 60)
if fails:
    print(f"{len(fails)} check(s) FAILED:")
    for name in fails:
        print(f"  - {name}")
    sys.exit(1)
print("All OAuth checks passed.")
