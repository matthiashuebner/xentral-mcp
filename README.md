[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/matthiashuebner-xentral-mcp-badge.png)](https://mseep.ai/app/matthiashuebner-xentral-mcp)

# Xentral MCP HTTP Server

A Model Context Protocol (MCP) HTTP server for Xentral ERP integration that
exposes the **complete Xentral API** — every endpoint of the official
[Xentral OpenAPI specification](https://github.com/xentral/api-spec-public)
— as MCP tools, plus curated convenience tools for daily ERP workflows.

## 🚀 Features

- **Full API coverage**: 339 tools covering all documented
  Xentral API endpoints (customers, products, sales orders, invoices,
  warehousing, accounting, analytics, POS, production, …)
- **Curated tools**: Hand-written convenience tools with table-formatted
  output (`search_customers`, `search_products`) — they override generated
  tools on name collisions
- **Real MCP HTTP Server**: Full JSON-RPC 2.0 compatible MCP implementation
- **Xentral-native filtering**: deepObject query serialization
  (`filter[0][key]=name&filter[0][op]=equals&filter[0][value]=Miller`),
  pagination (`page[number]`, `page[size]`) and sorting (`order[0][field]`)
- **Binary downloads**: PDF/CSV/ZIP responses (e.g. invoice PDFs) are saved
  to `downloads/` instead of flooding the context window
- **Response truncation**: Large list responses are trimmed with a hint to
  use filters/pagination
- **Authenticated by default**: Bearer-token auth on every endpoint; binds to
  loopback only and refuses to expose itself to the network without a token
- **OAuth 2.1 for remote clients**: optional embedded authorization server
  (metadata discovery, dynamic client registration, authorization code + PKCE)
  so connectors that cannot send a static token — Claude's among them — can
  connect
- **SSRF-hardened**: API base URL is validated (HTTPS, host allow-list,
  internal/metadata addresses blocked) before any request is sent
- **Runtime Configuration**: Update API credentials dynamically without restart
- **Redacted Logging**: Request method, tool name and argument *keys* are
  logged — never secret values or PII

## 📋 Requirements

- Python 3.9 or higher
- Xentral instance with API access ([create a personal access token](https://developer.xentral.com/))

## 🛠️ Installation

```bash
git clone https://github.com/matthiashuebner/xentral-mcp.git
cd xentral-mcp
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set XENTRAL_API_URL (instance base URL, no /api suffix),
# XENTRAL_API_KEY (personal access token), and MCP_AUTH_TOKEN
```

Generate an auth token:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 🔒 Security model

- **Loopback by default.** `MCP_SERVER_HOST` defaults to `127.0.0.1`. The
  server **refuses to start** on any other interface unless `MCP_AUTH_TOKEN`
  is set — never expose it without a token.
- **Token auth.** Every endpoint except `/health` requires
  `Authorization: Bearer <MCP_AUTH_TOKEN>`. Without a token configured, access
  is tolerated only on loopback (with a startup warning).
- **OAuth is opt-in and additive.** With `MCP_OAUTH_ENABLED=true` the server
  additionally accepts access tokens it issued itself; the static token keeps
  working. Enabling it also unlocks binding to a public interface without a
  static token, since OAuth is then the authentication in force.
- **No CORS.** Cross-origin access is disabled so a website cannot drive the
  API from the operator's browser.
- **SSRF guard.** `XENTRAL_API_URL` must be HTTPS (except localhost) and must
  not resolve to a private/loopback/link-local/metadata address. Set
  `XENTRAL_ALLOWED_HOSTS` to pin the allowed host(s).
- **No debug server.** The Werkzeug interactive debugger is never enabled.

## 🏃 Running the Server

Local development (loopback, dev server):

```bash
python mcp_server.py
```

Production — use a real WSGI server behind a TLS-terminating, authenticating
reverse proxy. **Do not** expose the Flask development server directly:

```bash
gunicorn --bind 127.0.0.1:8888 wsgi:app
```

The server registers 341 tools. Authenticated calls carry the bearer token:

```bash
curl -H "Authorization: Bearer $MCP_AUTH_TOKEN" http://localhost:8888/info
```

## 🔌 Connecting an MCP client

### Clients that can send a fixed header

curl, the CLI client and Claude Code can send the static token directly — no
OAuth needed:

```bash
claude mcp add --transport http xentral https://mcp.your-company.example/mcp \
  --header "Authorization: Bearer $MCP_AUTH_TOKEN"
```

### Remote connectors (Claude's custom connectors)

A remote connector is given a URL and nothing else — there is no field for a
bearer token. It authenticates by discovery instead: it expects an
unauthenticated request to come back as `401` with a `WWW-Authenticate` header
pointing at protected-resource metadata, from which it finds an authorization
server, registers itself, and runs an authorization-code flow. Without that, the
connector can only report an authorization error. Enable the embedded
authorization server to satisfy it:

```bash
MCP_OAUTH_ENABLED=true
MCP_PUBLIC_URL=https://mcp.your-company.example   # exact external URL, https
MCP_OAUTH_PASSWORD=<long passphrase>              # your consent password
```

The server must be reachable from the internet over HTTPS at `MCP_PUBLIC_URL` —
a loopback deployment cannot work here, since the client fetches the discovery
documents itself. Then add `https://mcp.your-company.example/mcp` as a custom
connector. Your browser opens a consent page naming the client and its redirect
host; enter `MCP_OAUTH_PASSWORD` to approve, and the connector completes the
handshake.

What the flow provides:

| Endpoint | Purpose |
|---|---|
| `GET /.well-known/oauth-protected-resource` | RFC 9728 resource metadata |
| `GET /.well-known/oauth-authorization-server` | RFC 8414 AS metadata |
| `POST /oauth/register` | RFC 7591 dynamic client registration |
| `GET,POST /oauth/authorize` | consent page and approval |
| `POST /oauth/token` | authorization code + refresh grants |
| `POST /oauth/revoke` | RFC 7009 revocation |

Notes on the design:

- **PKCE (S256) is mandatory** and `plain` is not offered.
- **Access tokens are stateless** (HMAC-signed, 1h default) so the MCP hot path
  costs no database read. They cannot be revoked before expiry — hence the short
  TTL. Refresh tokens are stored, rotate on every use, and are revocable.
- **Tokens are audience-bound** to `MCP_PUBLIC_URL/mcp` (RFC 8707), so a token
  obtained by another MCP server cannot be replayed here.
- **Registration is open, approval is not.** Any client may register; none gets
  access until you type the consent password, and the consent page names the
  client and the host it redirects to.
- **State lives in SQLite** (`MCP_OAUTH_DB_PATH`), so the flow works across
  gunicorn workers. Codes, refresh tokens and client secrets are stored as
  SHA-256 hashes only. Back it up or accept that clients re-register after loss.
- No new dependencies: everything uses the standard library plus Flask.

## 🔧 Tool Catalog (auto-generated API tools)

All API tools are compiled from the official OpenAPI spec into
`xentral/openapi/catalog.json` (committed to the repo). When Xentral
publishes API changes, regenerate it with:

```bash
python scripts/generate_catalog.py            # downloads the latest spec
python scripts/generate_catalog.py --spec my-spec.json   # or use a local file
```

Tool names follow the spec's operation IDs: `customer.list.v2` →
`customer_list_v2`, `salesOrder.actions.cancel` → `sales_order_actions_cancel`.
See [mcp-tools-list.md](mcp-tools-list.md) for the full list grouped by
resource.

### Tool arguments

- **Path parameters** (e.g. `id`) are top-level arguments
- **`filter`**: array of `{key, op, value}` objects — allowed keys/operators
  are embedded in each tool's schema
- **`page`**: `{"number": "1", "size": "20"}`
- **`order`**: array of `{field, dir}` objects (`dir`: `asc`/`desc`)
- **`body`**: JSON request body for create/update operations (schema included)
- **`content_type`**: optional vendor content type for special behavior
  (e.g. `application/vnd.xentral.upsert+json` on `product_create`)

## 🔍 Testing

The suites are standalone scripts and need no external services:

```bash
python tests/test_security.py      # auth gate, SSRF guard, log redaction
python tests/test_oauth.py         # OAuth flow, token binding, HTTP transport
python tests/test_e2e.py           # tool execution against a local stub API
python tests/test_server_stdio.py  # the legacy stdio server (server.py)
```

All endpoints except `/health` require the bearer token when `MCP_AUTH_TOKEN`
is set.

```bash
# Health check (public)
curl http://localhost:8888/health

# List all tools
curl -X POST http://localhost:8888/mcp \
  -H "Authorization: Bearer $MCP_AUTH_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

# Call a tool: list customers named Miller
curl -X POST http://localhost:8888/mcp \
  -H "Authorization: Bearer $MCP_AUTH_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"customer_list_v2","arguments":{"filter":[{"key":"name","op":"equals","value":"Miller"}],"page":{"number":"1","size":"10"}}}}'
```

## 📁 Project Structure

- `mcp_server.py` - Main Flask HTTP server & tool discovery
- `mcp_protocol.py` - MCP JSON-RPC protocol implementation
- `config.py` - Configuration management
- `scripts/generate_catalog.py` - Compiles the OpenAPI spec into the tool catalog
- `xentral/openapi/` - Generated tool catalog + generic API executor
  - `catalog.json` - Compiled tool definitions (339 endpoints)
  - `executor.py` - Generic HTTP executor (paths, deepObject queries, bodies)
  - `loader.py` - Builds MCP tools from the catalog
- `xentral/*.py` - Hand-written convenience tools (auto-discovered)
- `mcp_oauth/` - Embedded OAuth 2.1 authorization server
  - `routes.py` - Discovery, registration, consent, token and revocation endpoints
  - `tokens.py` - HMAC-signed access tokens and PKCE helpers
  - `store.py` - SQLite store for clients, codes and refresh tokens
- `mcp_client.py` - CLI testing client
- `mcp-tools-list.md` - Generated overview of all tools
- `.env.example` - Configuration template

## 🌐 HTTP Endpoints

- `POST /mcp` - Main MCP JSON-RPC endpoint (initialize, tools/list, tools/call)
- `GET /health` - Health check
- `GET /info` - Server information
- `GET /tools` - List all tools (plain JSON)
- `POST /config/credentials` - Update API credentials at runtime
- OAuth endpoints (only when `MCP_OAUTH_ENABLED=true`) — see
  [Connecting an MCP client](#-connecting-an-mcp-client)

`GET` and `DELETE` on `/mcp` answer `405`: this server is stateless, so there is
no server-initiated event stream to open and no session to terminate. A POST is
answered with JSON, or with a single SSE frame for clients that accept only
`text/event-stream`.

## 📞 Support

For issues, check logs in `mcp_server.log`. API errors returned by Xentral
(including validation details) are passed through to the MCP client.

Happy ERP automation! 🚀
