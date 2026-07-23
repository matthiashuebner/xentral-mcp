# Security Review: xentral-mcp

**Date:** 2026-07-23
**Scope:** Whole repository at merged `main` (commit `739b1ca`). Focus on the Flask HTTP MCP server (`mcp_server.py`, `mcp_protocol.py`, `config.py`, `xentral/`), with the stdio server (`server.py`) and CLI client (`mcp_client.py`) reviewed secondarily.
**Method:** Four-perspective AI code review (offensive, defensive, privacy, operational)

> **Remediation status (2026-07-23):** All 8 findings have been fixed in the
> same session. Key changes: bearer-token auth on every endpoint with a
> fail-closed startup guard (`security.py`, `mcp_server.py`, `config.py`),
> CORS removed, loopback-only default binding, SSRF/HTTPS validation of
> `api_url`, Werkzeug debug hard-disabled, secret redaction in logs, and a
> gunicorn/WSGI production path (`wsgi.py`). Verified by a 32-case security
> regression suite plus a live gunicorn smoke test. The findings below are
> retained as the audit record of the original state.

## Summary

The HTTP server exposes the **entire Xentral ERP API with no authentication whatsoever**, bound to all network interfaces and wrapped in wildcard CORS. Anyone who can reach the port — a co-tenant on the host, any device on the LAN, or *any website the operator visits in a browser* — can read all customer/financial PII and create or delete business records using the server's stored credentials. On top of that, an unauthenticated endpoint lets attackers repoint the API base URL (SSRF) and optionally enabling Flask debug mode turns exposure into remote code execution. These are not theoretical: the exploitation is a single unauthenticated `POST`. Fix the authentication and network-exposure issues before this is deployed anywhere.

| Severity     | Count |
|--------------|-------|
| 🔴 Critical  | 2     |
| 🟠 High      | 2     |
| 🟡 Medium    | 3     |
| 🟢 Low       | 1     |

## Findings

### 🔴 #1 — MCP HTTP server exposes the full Xentral API with no authentication, on all interfaces

- **Severity:** Critical
- **Perspective:** Offensive, Defensive
- **Location:** `mcp_server.py:235-266` (`handle_mcp_request`), `config.py:24` and `mcp_server.py:457-462` (host binding)

**What's wrong.** The `/mcp` endpoint accepts `tools/call` for any of the 341 registered tools and executes the corresponding Xentral API request using the server's configured Bearer token. There is no API key, no token check, no session, no IP allowlist — the handler goes straight from "is it JSON?" to executing the call. The server binds to `0.0.0.0` by default (`server_host` default in `config.py:24`), so it listens on every network interface, not just loopback.

**Why it matters.** The tool catalog includes reading all customers, suppliers, employees and contact data (PII), all invoices and financial exports, plus `POST`/`PATCH`/`DELETE` operations that create and destroy business documents. Any party who can open a TCP connection to the port — another user on a shared host, anything on the same LAN/VPN, or an attacker who reaches it through a misconfigured firewall — gets full read/write control of the company's ERP with zero credentials. This is complete data exfiltration and direct data-loss capability in one unauthenticated request.

**Recommendation.** Require authentication on every `/mcp` request (a shared secret in an `Authorization` header compared with `hmac.compare_digest`, or mTLS). Bind to `127.0.0.1` by default and force operators to opt in explicitly to any wider binding. If remote access is genuinely needed, place the server behind an authenticating reverse proxy and document that as the only supported deployment.

---

### 🔴 #2 — Wildcard CORS turns any website into a full ERP client (drive-by exfiltration)

- **Severity:** Critical
- **Perspective:** Offensive
- **Location:** `mcp_server.py:201` (`CORS(app)`)

**What's wrong.** `CORS(app)` with no arguments applies `Access-Control-Allow-Origin: *` to every route, including `/mcp` and `/config/credentials`. Because the server's authority is its *own* stored token (not a browser cookie), the usual "wildcard CORS can't be combined with credentials" limitation does not protect anything here — the malicious page doesn't need the victim's cookies, it just needs the request to execute.

**Why it matters.** While an operator runs the server locally (the documented default is `localhost:8888`) and browses the web, any page they visit can run `fetch('http://localhost:8888/mcp', {method:'POST', headers:{'Content-Type':'application/json'}, body: '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"customer_list_v2","arguments":{}}}'})`. The preflight passes (flask-cors answers the `OPTIONS` with `*`), the call executes against the real Xentral instance, and `Access-Control-Allow-Origin: *` lets the attacker's JavaScript **read the response** cross-origin — so it can both act (create/delete records) and exfiltrate the returned PII to an attacker server. No network position is required; the operator merely has to have a browser tab open. This is why it is rated Critical alongside #1 rather than as a mere amplifier.

**Recommendation.** Remove `CORS(app)`. An MCP server driven by a local client or a server-side proxy does not need permissive cross-origin access at all. If a specific browser-based client must call it, allowlist that exact origin and pair it with the authentication from #1 — never `*`.

---

### 🟠 #3 — Unauthenticated credential-update endpoint enables SSRF and integration hijack

- **Severity:** High
- **Perspective:** Offensive
- **Location:** `mcp_server.py:333-361` (`/config/credentials`), `config.py:37-46` (`update_credentials`), `xentral/openapi/executor.py:88-101` (URL built from `config.api_url`)

**What's wrong.** `POST /config/credentials` overwrites the runtime `api_url` and `api_key` for the whole process with no authentication. Every subsequent tool call builds its request URL from that attacker-controlled `api_url`.

**Why it matters.** Two concrete abuses. (1) **SSRF** — an attacker sets `api_url` to an internal address (`http://169.254.169.254/…` for cloud metadata, or an internal admin service), then calls any read tool; the server dutifully issues the request from its own network position and returns the response body in the tool result, using the server as a proxy past the network perimeter. (2) **Integration hijack / DoS** — overwriting the credentials silently breaks the legitimate integration, or repoints all future traffic (including any bodies the operator submits) at a host the attacker chose. Combined with #1/#2 this needs no credentials at all.

**Recommendation.** Put this endpoint behind the same authentication as #1 (at minimum). Validate that `api_url` resolves to the expected Xentral host(s) via an allowlist, reject private/link-local IP ranges, and prefer configuring credentials only via environment/secret store rather than a live mutation endpoint. Disable `httpx` redirect-following (it already defaults off — keep it) so a permitted host can't 302 the request onward.

---

### 🟠 #4 — Flask debug mode is one env var away from remote code execution

- **Severity:** High
- **Perspective:** Offensive, Defensive
- **Location:** `mcp_server.py:457-462` (`app.run(..., debug=config.debug_mode)`), `config.py:26` (`MCP_DEBUG`)

**What's wrong.** The server runs the Werkzeug development server with `debug=config.debug_mode`, sourced from the `MCP_DEBUG` environment variable. When debug is on, an unhandled exception renders the Werkzeug interactive traceback, which includes a Python console.

**Why it matters.** With the server already reachable on `0.0.0.0` (#1) and no auth, flipping `MCP_DEBUG=true` — an easy thing to do while troubleshooting — exposes an interactive Python console to anyone who can trigger an exception. The modern Werkzeug console is PIN-gated, but the PIN is derivable/brute-forceable in many setups and the debugger is explicitly not a security boundary. This is a direct path to RCE on the host. It is High rather than Critical only because it requires the debug flag to be enabled.

**Recommendation.** Never run the Werkzeug dev server for anything reachable. Serve via a production WSGI server (gunicorn/uwsgi) with `debug=False` hard-wired, and drop the `MCP_DEBUG`-controlled debug path entirely (keep debug logging separate from Flask's `debug=`).

---

### 🟡 #5 — Full request bodies and tool arguments (including plaintext secrets) written to logs

- **Severity:** Medium
- **Perspective:** Defensive, Privacy
- **Location:** `mcp_server.py:207-229` (`log_request`), `mcp_protocol.py:290` (`logger.info(... arguments ...)`), `server.py:14-19,252` (stdio server logs args at DEBUG)

**What's wrong.** The request-logging middleware logs the entire JSON body of every `/mcp` request, and the protocol layer logs the full tool arguments. These go to stderr and, when writable, to `mcp_server.log` on disk. Several catalog operations carry secrets in their arguments — e.g. `user_update` accepts an `application/vnd.xentral.password+json` body (password changes), and token/auth operations carry credentials.

**Why it matters.** Password changes, tokens and customer PII passed through tool arguments end up in a plaintext logfile and console output. Anyone with read access to the log (backup systems, log shippers, another user on the host, an error tracker that ingests stderr) harvests live credentials and personal data. `mcp_server.log` is now git-ignored so it won't be committed, but it still sits unencrypted on disk with no redaction or rotation.

**Recommendation.** Redact known-sensitive fields (password, token, secret, Authorization) before logging, and log tool *names* plus argument *keys* rather than full values at INFO. Lower the stdio server off blanket `DEBUG`. Ensure whatever ships logs onward treats this stream as containing secrets.

---

### 🟡 #6 — Development server presented and shipped as "production ready"

- **Severity:** Medium
- **Perspective:** Operational
- **Location:** `mcp_server.py:456-462` (`app.run(...)`), `README.md` ("Production Ready")

**What's wrong.** The only documented way to run the server is `python mcp_server.py`, which launches the single-purpose Werkzeug development server, while the README advertises the project as "Production Ready." There is no WSGI server, no process manager, no TLS termination in the shipped setup.

**Why it matters.** The dev server is not built for untrusted exposure or load — it has known limitations around concurrency, resource limits and robustness, and its debug facilities (see #4) are dangerous. Labeling it production-ready invites operators to expose it directly, compounding #1–#4. This is textbook security-theater risk: the docs imply a hardening posture the code doesn't have.

**Recommendation.** Ship and document a real deployment path (gunicorn behind a TLS-terminating, authenticating reverse proxy), and correct the README to state the dev server is for local use only.

---

### 🟡 #7 — Plaintext HTTP permitted for API traffic; no transport security enforced

- **Severity:** Medium
- **Perspective:** Defensive, Privacy
- **Location:** `config.py:80-82` (`validate_config` accepts `http://`), `xentral/base.py:74-89` and `xentral/openapi/executor.py:104-117` (request execution), server has no TLS

**What's wrong.** `validate_config` explicitly accepts an `api_url` beginning with `http://`, and the Bearer token is attached to every request regardless of scheme. The Flask server itself also serves plain HTTP while binding to all interfaces (#1).

**Why it matters.** If an operator configures an `http://` base URL (or a proxy downgrades), the Xentral Bearer token and all PII/financial payloads travel in cleartext, harvestable by anyone on the path. Because the server also listens on `0.0.0.0` over HTTP, tokens and data crossing the network to reach it are equally exposed.

**Recommendation.** Reject non-HTTPS `api_url` values (allow `http://localhost` only for explicit local testing). Terminate TLS in front of the server and refuse to attach the Bearer token over plaintext transport.

---

### 🟢 #8 — Upstream error bodies and configuration reflected verbatim to clients

- **Severity:** Low
- **Perspective:** Defensive, Privacy
- **Location:** `xentral/base.py:91-94`, `xentral/openapi/executor.py:246-258` (`_format_http_error`), `mcp_server.py:299-309` (`/info` returns `api_url`)

**What's wrong.** HTTP errors from Xentral are passed back to the caller with the full upstream response body, and `/info` (unauthenticated GET) returns the configured `api_url`. The API key is correctly masked in `/info`, so this is limited to non-secret detail.

**Why it matters.** Verbose upstream errors can leak internal identifiers, stack traces or schema details that help an attacker map the system, and `/info` discloses the exact Xentral instance URL to any unauthenticated caller. Low impact on its own, but it aids reconnaissance for the higher-severity findings.

**Recommendation.** Return a generic error to the client and log the detail server-side. Put `/info` (and `/health`, `/tools`) behind the same auth as #1, or strip environment-specific detail from their responses.

---

## Note on the stdio server (`server.py`)

`server.py` is a separate MCP server over stdio, driven by a local MCP client rather than the network, so its exposure is much lower. Its `xentral_raw_request` tool grants the connected LLM arbitrary API calls — acceptable given the transport is local and that is the tool's stated purpose, but worth keeping in mind if this server is ever wrapped in a network transport. Its blanket `DEBUG` logging of tool arguments is folded into finding #5.
