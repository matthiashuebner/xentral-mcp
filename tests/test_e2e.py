"""End-to-end test: tool loading, tools/list, and tools/call against a mock API."""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Mock Xentral API server: echoes method, path, query, body ---
class EchoHandler(BaseHTTPRequestHandler):
    def _handle(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode() if length else ""
        payload = {
            "echo": {
                "method": self.command,
                "path": self.path,
                "auth": self.headers.get("Authorization"),
                "content_type": self.headers.get("Content-Type"),
                "body": json.loads(body) if body else None,
            },
            "data": [{"id": 1, "name": "Test"}],
        }
        out = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    do_GET = do_POST = do_PATCH = do_DELETE = do_PUT = _handle
    def log_message(self, *args): pass

server = HTTPServer(("127.0.0.1", 0), EchoHandler)
port = server.server_address[1]
threading.Thread(target=server.serve_forever, daemon=True).start()

os.environ["XENTRAL_API_URL"] = f"http://127.0.0.1:{port}"
os.environ["XENTRAL_API_KEY"] = "test-api-key-12345"

from config import config
config.update_credentials(f"http://127.0.0.1:{port}", "test-api-key-12345")

from mcp_server import initialize_tools, mcp_protocol

assert initialize_tools(), "initialize_tools failed"
print(f"PASS: {len(mcp_protocol.tools)} tools registered")

# --- tools/list ---
resp = json.loads(mcp_protocol.handle_request(json.dumps({
    "jsonrpc": "2.0", "id": 1, "method": "tools/list"
})))
tools = resp["result"]["tools"]
by_name = {t["name"]: t for t in tools}
assert "search_customers" in by_name, "hand-written tool missing"
assert "customer_list_v2" in by_name, "openapi tool customer_list_v2 missing"
assert "sales_order_import" in by_name, "openapi tool sales_order_import missing"
cl = by_name["customer_list_v2"]
assert "filter" in cl["inputSchema"]["properties"], "filter param missing in schema"
assert "page" in cl["inputSchema"]["properties"], "page param missing in schema"
print(f"PASS: tools/list returns {len(tools)} tools with full schemas")
print("  customer_list_v2 description:", cl["description"][:120])

# --- tools/call: GET with deepObject filter + page ---
resp = json.loads(mcp_protocol.handle_request(json.dumps({
    "jsonrpc": "2.0", "id": 2, "method": "tools/call",
    "params": {"name": "customer_list_v2", "arguments": {
        "filter": [{"key": "name", "op": "equals", "value": "Miller"}],
        "page": {"number": 1, "size": 20},
    }}
})))
text = resp["result"]["content"][0]["text"]
assert "filter%5B0%5D%5Bkey%5D=name" in text or "filter[0][key]=name" in text, f"deepObject filter not serialized: {text[:500]}"
assert "page%5Bnumber%5D=1" in text or "page[number]=1" in text, "page not serialized"
print("PASS: GET customer_list_v2 serializes filter[0][key]=name & page[number]=1")

# --- tools/call: path param substitution ---
resp = json.loads(mcp_protocol.handle_request(json.dumps({
    "jsonrpc": "2.0", "id": 3, "method": "tools/call",
    "params": {"name": "customer_view_v2", "arguments": {"id": 42}}
})))
text = resp["result"]["content"][0]["text"]
assert "/api/v2/customers/42" in text, f"path param not substituted: {text[:300]}"
print("PASS: GET customer_view_v2 substitutes path param -> /api/v2/customers/42")

# --- tools/call: POST with JSON body ---
resp = json.loads(mcp_protocol.handle_request(json.dumps({
    "jsonrpc": "2.0", "id": 4, "method": "tools/call",
    "params": {"name": "sales_order_import", "arguments": {
        "body": {"customer": {"id": "17"}, "positions": [{"product": {"id": "1"}, "amount": 2}]}
    }}
})))
text = resp["result"]["content"][0]["text"]
assert '"customer"' in text and '"id": "17"' in text, f"body not sent: {text[:500]}"
print("PASS: POST sales_order_import sends JSON body")

# --- tools/call: missing required path param -> clean error ---
resp = json.loads(mcp_protocol.handle_request(json.dumps({
    "jsonrpc": "2.0", "id": 5, "method": "tools/call",
    "params": {"name": "customer_view_v2", "arguments": {}}
})))
text = resp["result"]["content"][0]["text"]
assert "Missing required path parameter" in text, f"unexpected: {text[:300]}"
print("PASS: missing path param produces clean error message")

# --- tools/call: JSON-string argument tolerance ---
resp = json.loads(mcp_protocol.handle_request(json.dumps({
    "jsonrpc": "2.0", "id": 6, "method": "tools/call",
    "params": {"name": "customer_list_v2", "arguments": {
        "filter": '[{"key": "city", "op": "equals", "value": "Berlin"}]'
    }}
})))
text = resp["result"]["content"][0]["text"]
assert "city" in text and "Berlin" in text, f"JSON-string filter failed: {text[:300]}"
print("PASS: filter passed as JSON string is parsed and serialized")

server.shutdown()
print("\nALL TESTS PASSED")
