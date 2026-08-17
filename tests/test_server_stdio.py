"""Tests für den stdio-Server (server.py): Rechnungs-Tools und 406-Accept-Fallback.

Der Mock-Xentral-Server beantwortet /invoices nur mit dem versionierten
Vendor-Media-Type korrekt (wie echte Xentral-Instanzen) und liefert für
alle anderen Pfade normales JSON.
"""
import asyncio
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

INVOICES = [
    {"id": 3, "invoice": "RE-2026-003", "date": "2026-07-20"},
    {"id": 2, "invoice": "RE-2026-002", "date": "2026-07-15"},
    {"id": 1, "invoice": "RE-2026-001", "date": "2026-07-01"},
]


ANALYTICS_DOCS = {
    "data": [
        {
            "label": "invoice_items",
            "shortDescription": "Items of invoices.",
            "columns": [{"name": "invoice_id"}, {"name": "net_revenue_item_total"}],
        },
        {
            "label": "products",
            "shortDescription": "All products.",
            "columns": [{"name": "product_id"}, {"name": "product_number"}],
        },
    ]
}

analytics_doc_requests = {"count": 0}


class MockXentralHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length).decode()) if length else {}

        if parsed.path.endswith("/analytics/query"):
            payload = {
                "data": {"header": ["n"], "rows": [["42"]]},
                "meta": {"query": body.get("query")},
            }
        else:
            payload = {"echo": {"path": parsed.path, "body": body}}

        out = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        accept = self.headers.get("Accept", "")

        if parsed.path.endswith("/analytics/credit"):
            payload = {"data": [{"totalCredits": 250, "usedCredits": 24}]}
            out = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
            return

        if parsed.path.endswith("/analytics/documentation"):
            analytics_doc_requests["count"] += 1
            out = json.dumps(ANALYTICS_DOCS).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
            return

        if parsed.path.rstrip("/").endswith("/customers"):
            # Wie die echte Instanz: Cursor-Pagination, page[...] wird abgelehnt.
            if any(k.startswith("page[") for k in query):
                out = json.dumps({
                    "type": "https://api.xentral.biz/problems/generic-validation",
                    "title": "Generic request validation failed.",
                    "messages": [""],
                }).encode()
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)
                return
            payload = {
                "data": [{"id": str(i), "general": {"name": f"Kunde {i}"}} for i in range(1, 11)],
                "extra": {
                    "totalCount": 2865,
                    "cursor": {"nextCursor": "MTY3", "size": 10},
                },
                "echo": {"query": query},
            }
            out = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
            return

        if parsed.path.rstrip("/").endswith("/invoices"):
            # Echte Xentral-Instanzen beantworten 'application/json'
            # hier mit 406 – nur der Vendor-Media-Type funktioniert.
            if "vnd.xentral" not in accept:
                self.send_response(406)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            payload = {"data": INVOICES, "echo": {"query": query, "accept": accept}}
        else:
            payload = {
                "data": [{"id": i} for i in range(1, 11)],
                "echo": {"path": parsed.path, "query": query},
            }

        out = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


server_http = HTTPServer(("127.0.0.1", 0), MockXentralHandler)
port = server_http.server_address[1]
threading.Thread(target=server_http.serve_forever, daemon=True).start()

os.environ["XENTRAL_BASE_URL"] = f"http://127.0.0.1:{port}/api/v1"
os.environ["XENTRAL_PAT"] = "test-pat-12345"

import server  # noqa: E402  (braucht die env vars von oben)


def call(name, arguments):
    result = asyncio.run(server.call_tool(name, arguments))
    assert len(result) == 1, f"expected 1 content item, got {len(result)}"
    return result[0].text


# --- tools/list enthält die neuen Tools ---
tools = asyncio.run(server.list_tools())
names = {t.name for t in tools}
for expected in ("xentral_list_invoices", "xentral_get_invoice", "xentral_raw_request"):
    assert expected in names, f"Tool {expected} fehlt in tools/list"
print(f"PASS: tools/list enthält {len(names)} Tools inkl. Rechnungs-Tools")

# --- list_invoices: 406-Fallback greift, Sortierung + limit=2 ---
text = call("xentral_list_invoices", {"limit": 2})
data = json.loads(text)
assert len(data["data"]) == 2, f"limit=2 nicht angewendet: {len(data['data'])} Einträge"
assert data["data"][0]["invoice"] == "RE-2026-003"
query = data["echo"]["query"]
assert query["order[0][field]"] == ["date"]
assert query["order[0][dir]"] == ["desc"]
assert query["page[size]"] == ["10"], "page[size] muss auf min. 10 geklemmt werden"
assert "vnd.xentral" in data["echo"]["accept"]
print("PASS: xentral_list_invoices mit 406-Accept-Fallback, Sortierung und limit")

# --- list_invoices: Filter werden indexiert übergeben ---
text = call("xentral_list_invoices", {"limit": 10, "customerNameContains": "Miller", "status": "paid"})
query = json.loads(text)["echo"]["query"]
assert query["filter[0][key]"] == ["customerName"]
assert query["filter[0][op]"] == ["contains"]
assert query["filter[0][value]"] == ["Miller"]
assert query["filter[1][key]"] == ["status"]
assert query["filter[1][op]"] == ["equals"]
print("PASS: xentral_list_invoices Filter-Mapping")

# --- get_invoice ---
text = call("xentral_get_invoice", {"invoiceId": "3"})
assert "/api/v1/invoices/3" in json.loads(text)["echo"]["path"]
print("PASS: xentral_get_invoice")

# --- raw_request mit explizitem accept ---
text = call("xentral_raw_request", {
    "method": "GET",
    "path": "invoices",
    "accept": "application/vnd.xentral.default.v1+json",
})
assert "RE-2026-003" in text
print("PASS: xentral_raw_request mit explizitem Accept-Header")

# --- raw_request ohne accept: Fallback greift automatisch ---
text = call("xentral_raw_request", {"method": "GET", "path": "invoices"})
assert "RE-2026-003" in text
print("PASS: xentral_raw_request mit automatischem 406-Fallback")

# --- analytics_query: führt SQL aus und hängt Credit-Stand an ---
text = call("xentral_analytics_query", {"sql": "SELECT COUNT(*) AS n FROM invoice_items"})
assert '"rows"' in text and "42" in text
assert "24/250" in text, f"Credit-Stand fehlt in Antwort: {text[-200:]}"
print("PASS: xentral_analytics_query mit Credit-Stand")

# --- analytics_query: leeres SQL wird abgelehnt ---
text = call("xentral_analytics_query", {"sql": "  "})
assert "darf nicht leer sein" in text
print("PASS: xentral_analytics_query Validierung")

# --- analytics_tables: Liste ohne Suchbegriff ---
text = call("xentral_analytics_tables", {})
assert "invoice_items" in text and "products" in text
assert "2 Analytics-Tabellen" in text
print("PASS: xentral_analytics_tables Liste")

# --- analytics_tables: Suche matcht Tabelle + Spalten, Doku wird gecacht ---
text = call("xentral_analytics_tables", {"search": "revenue"})
assert "invoice_items" in text and "net_revenue_item_total" in text
assert "products" not in text.replace("net_revenue_item_total", "")
text = call("xentral_analytics_tables", {"search": "gibtsnicht"})
assert "Keine Analytics-Tabelle" in text
assert analytics_doc_requests["count"] == 1, (
    f"Doku muss gecacht werden, wurde aber {analytics_doc_requests['count']}x geladen"
)
print("PASS: xentral_analytics_tables Suche + Cache")

# --- list_customers: Cursor-Pagination statt page[], limit-Kürzung ---
text = call("xentral_list_customers", {"limit": 3, "nameContains": "Braun"})
data = json.loads(text)
assert len(data["data"]) == 3, f"limit=3 nicht angewendet: {len(data['data'])}"
assert data["extra"]["totalCount"] == 2865
query = data["echo"]["query"]
assert query["cursor[size]"] == ["10"], "cursor[size] muss auf min. 10 geklemmt werden"
assert "page[number]" not in query and "page[size]" not in query
assert query["filter[0][key]"] == ["name"]
assert query["filter[0][op]"] == ["contains"]
assert query["filter[0][value]"] == ["Braun"]
print("PASS: xentral_list_customers Cursor-Pagination + Filter + limit")

# --- list_customers: cursor wird durchgereicht ---
text = call("xentral_list_customers", {"limit": 10, "cursor": "MTY3"})
query = json.loads(text)["echo"]["query"]
assert query["cursor[nextCursor]"] == ["MTY3"]
print("PASS: xentral_list_customers Folgeseite per cursor")

# --- list_products: indexierte Filter, page[size]-Klemmung, Kürzung ---
text = call("xentral_list_products", {"pageSize": 5, "nameContains": "Lexmark", "skuEquals": "125512"})
data = json.loads(text)
assert len(data["data"]) <= 5
query = data["echo"]["query"]
assert query["page[size]"] == ["10"], "page[size] muss auf min. 10 geklemmt werden"
assert query["filter[0][key]"] == ["name"]
assert query["filter[0][op]"] == ["contains"]
assert query["filter[1][key]"] == ["number"]
assert query["filter[1][op]"] == ["equals"]
print("PASS: xentral_list_products Filter-Format + Klemmung")

# --- Robustheit: ungültige Zahlen-Argumente geben klare Meldung statt Exception ---
text = call("xentral_list_invoices", {"limit": "abc"})
assert "muss eine Zahl sein" in text, f"unerwartete Antwort: {text[:120]}"
print("PASS: ungültiges Zahlenargument wird sauber abgewiesen")

# --- Robustheit: fehlende Pflichtfelder geben klare Meldung statt KeyError ---
text = call("xentral_get_product", {})
assert "darf nicht leer sein" in text
text = call("xentral_raw_request", {"method": "GET"})
assert "erforderlich" in text
print("PASS: fehlende Pflichtfelder werden sauber abgewiesen")

# --- Robustheit: unerwartete Exceptions werden abgefangen ---
original = server._format_analytics_tables
server._format_analytics_tables = lambda *a: (_ for _ in ()).throw(RuntimeError("Boom"))
try:
    text = call("xentral_analytics_tables", {})
finally:
    server._format_analytics_tables = original
assert "Interner Fehler im Tool xentral_analytics_tables" in text and "Boom" in text
print("PASS: unerwartete Exception wird als saubere Fehlermeldung gemeldet")

# --- Robustheit: nicht erreichbares Xentral gibt 599-Meldung statt Exception ---
original_url, original_retries = server.XENTRAL_BASE_URL, server.XENTRAL_MAX_RETRIES
server.XENTRAL_BASE_URL = "http://127.0.0.1:9/"  # Port 9 (discard): nicht erreichbar
server.XENTRAL_MAX_RETRIES = 0
try:
    text = call("xentral_get_product", {"productId": "1"})
finally:
    server.XENTRAL_BASE_URL, server.XENTRAL_MAX_RETRIES = original_url, original_retries
assert "599" in text and "nicht erreichbar" in text, f"unerwartete Antwort: {text[:200]}"
print("PASS: Verbindungsfehler wird nach Retries als Meldung zurückgegeben")

# --- Echter stdio-Handshake gegen einen Subprozess ---
#
# Die Checks oben rufen list_tools()/call_tool() direkt auf und würden auch
# grün bleiben, wenn die Anbindung an das SDK gar nicht mehr passt — genau so
# ist die Decorator-Registrierung beim Sprung auf SDK 2.0 unbemerkt gebrochen.
# Dieser Check spricht daher als echter MCP-Client über stdin/stdout mit einem
# frisch gestarteten server.py.

async def _stdio_handshake():
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    async def _run():
        return await _drive_session(StdioServerParameters, stdio_client, ClientSession)

    # Hard timeout so a hung handshake fails the suite instead of blocking CI.
    return await asyncio.wait_for(_run(), timeout=60)


async def _drive_session(StdioServerParameters, stdio_client, ClientSession):
    params = StdioServerParameters(
        command=sys.executable,
        args=["server.py"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        env={
            **os.environ,
            "XENTRAL_BASE_URL": os.environ["XENTRAL_BASE_URL"],
            "XENTRAL_PAT": os.environ["XENTRAL_PAT"],
        },
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            init = await session.initialize()
            listed = await session.list_tools()
            called = await session.call_tool("xentral_get_product", {"productId": "1"})
            return init, listed, called


init_result, listed_result, call_result = asyncio.run(_stdio_handshake())
assert init_result.server_info.name == "xentral-mcp", init_result.server_info
print(f"PASS: stdio-Handshake erfolgreich (Protokoll {init_result.protocol_version})")

handshake_names = {t.name for t in listed_result.tools}
assert handshake_names == names, (
    f"tools/list über stdio weicht ab: {handshake_names ^ names}"
)
print(f"PASS: tools/list über stdio liefert dieselben {len(handshake_names)} Tools")

assert call_result.content and call_result.content[0].text, call_result
assert not call_result.is_error, call_result
print("PASS: tools/call über stdio liefert Inhalt")

print("ALL TESTS PASSED")
