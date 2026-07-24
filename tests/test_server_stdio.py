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
            payload = {"data": [{"id": 1}], "echo": {"path": parsed.path}}

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

print("ALL TESTS PASSED")
