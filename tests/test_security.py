"""Security regression tests for the fixes applied after the review."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure BEFORE importing config: enable auth, loopback bind.
os.environ["MCP_AUTH_TOKEN"] = "s3cret-token-abcdefghijklmnop"
os.environ["XENTRAL_API_KEY"] = "test-api-key-12345"
os.environ["XENTRAL_API_URL"] = "https://example.com"
os.environ["MCP_SERVER_HOST"] = "127.0.0.1"

import security
from config import XentralConfig, config

fails = []
def check(name, cond):
    print(f"{'PASS' if cond else 'FAIL'}: {name}")
    if not cond:
        fails.append(name)

# ---------------- security.validate_api_url ----------------
from security import validate_api_url, ApiUrlValidationError

def rejects(url, **kw):
    try:
        validate_api_url(url, **kw)
        return False
    except ApiUrlValidationError:
        return True

check("https public host allowed", validate_api_url("https://example.com") == "https://example.com")
check("http non-local rejected", rejects("http://demo.xentral.biz"))
check("http localhost allowed", validate_api_url("http://127.0.0.1:8899") == "http://127.0.0.1:8899")
check("SSRF metadata IP rejected", rejects("https://169.254.169.254"))
check("SSRF private 10.x rejected", rejects("https://10.0.0.5"))
check("SSRF loopback-by-name via http ok, but https internal rejected", rejects("https://192.168.1.1"))
check("non-http scheme rejected", rejects("file:///etc/passwd"))
check("allow-list enforced", rejects("https://github.com", allowed_hosts=["example.com"]))
check("allow-list subdomain match", validate_api_url("https://www.example.com", allowed_hosts=["example.com"]).endswith("example.com"))

# ---------------- security.check_bearer_token ----------------
from security import check_bearer_token
check("valid token accepted", check_bearer_token("Bearer abc123", "abc123"))
check("wrong token rejected", not check_bearer_token("Bearer nope", "abc123"))
check("missing header rejected", not check_bearer_token(None, "abc123"))
check("malformed header rejected", not check_bearer_token("abc123", "abc123"))
check("no expected token => open", check_bearer_token(None, ""))

# ---------------- security.redact ----------------
from security import redact
red = redact({"api_key": "SECRET", "password": "hunter2", "name": "Bob", "nested": {"token": "xyz"}})
check("api_key redacted", red["api_key"] == "***REDACTED***")
check("password redacted", red["password"] == "***REDACTED***")
check("nested token redacted", red["nested"]["token"] == "***REDACTED***")
check("non-secret preserved", red["name"] == "Bob")

# ---------------- exposure policy ----------------
c_local = XentralConfig()
os.environ_backup = dict(os.environ)

# non-local without token => fatal
os.environ["MCP_SERVER_HOST"] = "0.0.0.0"
os.environ["MCP_AUTH_TOKEN"] = ""
c_open = XentralConfig()
check("0.0.0.0 without token => exposure error", len(c_open.validate_exposure()) > 0)

os.environ["MCP_AUTH_TOKEN"] = "s3cret-token-abcdefghijklmnop"
c_ok = XentralConfig()
check("0.0.0.0 with token => no exposure error", c_ok.validate_exposure() == [])

os.environ["MCP_AUTH_TOKEN"] = "short"
c_short = XentralConfig()
check("short token => exposure error", len(c_short.validate_exposure()) > 0)

# restore
os.environ["MCP_SERVER_HOST"] = "127.0.0.1"
os.environ["MCP_AUTH_TOKEN"] = "s3cret-token-abcdefghijklmnop"

# ---------------- Flask app: auth gate + CORS ----------------
config.auth_token = "s3cret-token-abcdefghijklmnop"
config.server_host = "127.0.0.1"
config.update_credentials("https://example.com", "test-api-key-12345")

from mcp_server import create_app, initialize_tools
initialize_tools()
app = create_app()
client = app.test_client()

# health is public
r = client.get("/health")
check("/health public (200)", r.status_code == 200)

# /mcp without token => 401
r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
check("/mcp without token => 401", r.status_code == 401)

# /mcp with wrong token => 401
r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                headers={"Authorization": "Bearer wrong"})
check("/mcp wrong token => 401", r.status_code == 401)

# /mcp with correct token => 200
r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                headers={"Authorization": "Bearer s3cret-token-abcdefghijklmnop"})
check("/mcp correct token => 200", r.status_code == 200)
check("tools/list returns tools", len(r.get_json()["result"]["tools"]) > 300)

# no CORS header on response
check("no Access-Control-Allow-Origin header", "Access-Control-Allow-Origin" not in r.headers)

# /config/credentials requires auth
r = client.post("/config/credentials", json={"api_url": "https://example.com", "api_key": "x"})
check("/config/credentials without token => 401", r.status_code == 401)

# /config/credentials rejects SSRF target
r = client.post("/config/credentials",
                json={"api_url": "http://169.254.169.254", "api_key": "abcdefghijkl"},
                headers={"Authorization": "Bearer s3cret-token-abcdefghijklmnop"})
check("/config/credentials rejects metadata IP => 400", r.status_code == 400)

# /config/credentials rejects http non-local
r = client.post("/config/credentials",
                json={"api_url": "http://demo.xentral.biz", "api_key": "abcdefghijkl"},
                headers={"Authorization": "Bearer s3cret-token-abcdefghijklmnop"})
check("/config/credentials rejects http => 400", r.status_code == 400)

# /info does not leak api_url
r = client.get("/info", headers={"Authorization": "Bearer s3cret-token-abcdefghijklmnop"})
body = r.get_data(as_text=True)
check("/info requires auth then 200", r.status_code == 200)
check("/info does not contain api_url value", "example.com" not in body)

print()
if fails:
    print(f"{len(fails)} FAILURE(S): {fails}")
    sys.exit(1)
print("ALL SECURITY TESTS PASSED")
