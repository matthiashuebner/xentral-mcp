import os
import json
import asyncio
import sys
import logging
from typing import Any, Dict, Optional

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

# Setup Logging. Default to INFO; DEBUG can leak request bodies containing
# secrets/PII, so it must be opted into explicitly via XENTRAL_LOG_LEVEL.
logging.basicConfig(
    level=getattr(logging, os.environ.get("XENTRAL_LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="[xentral-mcp] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#   Konfiguration über Umgebungsvariablen
# ---------------------------------------------------------------------------

XENTRAL_BASE_URL = os.environ.get("XENTRAL_BASE_URL")
XENTRAL_PAT = os.environ.get("XENTRAL_PAT")
XENTRAL_TIMEOUT = float(os.environ.get("XENTRAL_TIMEOUT", "30.0"))
XENTRAL_MAX_RETRIES = int(os.environ.get("XENTRAL_MAX_RETRIES", "3"))

if not XENTRAL_BASE_URL or not XENTRAL_PAT:
    error_msg = "[xentral-mcp] Bitte XENTRAL_BASE_URL und XENTRAL_PAT als Umgebungsvariablen setzen."
    print(error_msg, file=sys.stderr)
    logger.error(error_msg)
    raise RuntimeError(
        "Umgebungsvariablen XENTRAL_BASE_URL und XENTRAL_PAT sind erforderlich."
    )

# dafür sorgen, dass genau ein '/' am Ende steht
XENTRAL_BASE_URL = XENTRAL_BASE_URL.rstrip("/") + "/"
logger.info(f"Xentral MCP initialisiert mit Base-URL: {XENTRAL_BASE_URL}")


def _auth_headers() -> Dict[str, str]:
    """Standard-Header für Xentral API-Calls."""
    return {
        "Authorization": f"Bearer {XENTRAL_PAT}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


# Einige Xentral-Endpunkte (z.B. GET /invoices) beantworten
# 'Accept: application/json' mit HTTP 406 und verlangen einen
# versionierten Vendor-Media-Type. Bei 406 werden diese Accept-Werte
# der Reihe nach durchprobiert.
ACCEPT_FALLBACKS = [
    "application/vnd.xentral.default.v1+json",
    "application/vnd.xentral.default.v1-beta+json",
    "*/*",
]


async def _make_request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    retries: int = 0,
    headers: Optional[Dict[str, str]] = None,
) -> tuple[int, Any]:
    """
    Macht einen HTTP-Request zu Xentral mit Retry-Logik.
    Gibt (status_code, data) zurück.
    """
    if retries > XENTRAL_MAX_RETRIES:
        raise RuntimeError(
            f"Max retries ({XENTRAL_MAX_RETRIES}) exceeded for {method} {path}"
        )

    try:
        logger.debug(f"{method} {path} (attempt {retries + 1})")
        resp = await client.request(
            method=method,
            url=path,
            params=params,
            json=json_body,
            headers=headers,
        )

        # Versuchen, JSON zu lesen – sonst Text
        try:
            data = resp.json()
        except ValueError:
            data = resp.text

        if resp.status_code == 406 and headers is None:
            for accept in ACCEPT_FALLBACKS:
                status_code, data = await _make_request(
                    client, method, path, params, json_body,
                    retries=retries, headers={"Accept": accept},
                )
                if status_code != 406:
                    logger.info(f"Accept-Fallback '{accept}' erfolgreich für {method} {path}")
                    return (status_code, data)
            return (406, data)

        if resp.is_error:
            logger.warning(
                f"HTTP {resp.status_code} from Xentral {method} {path}: {data}"
            )
        else:
            logger.debug(f"Success: HTTP {resp.status_code}")

        return (resp.status_code, data)

    except httpx.TimeoutException:
        logger.warning(f"Timeout for {method} {path}, retrying...")
        await asyncio.sleep(2 ** retries)  # Exponential backoff
        return await _make_request(client, method, path, params, json_body, retries + 1, headers)
    except httpx.RequestError as exc:
        logger.warning(f"Request error for {method} {path}: {exc}, retrying...")
        await asyncio.sleep(2 ** retries)
        return await _make_request(client, method, path, params, json_body, retries + 1, headers)


def _clamp_page_size(requested: int) -> int:
    """Xentral verlangt page[size] zwischen 10 und 150."""
    return max(10, min(150, requested))


def _truncate_data(data: Any, limit: int) -> Any:
    """Kürzt die 'data'-Liste einer Xentral-Antwort auf 'limit' Einträge."""
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        data = {**data, "data": data["data"][:limit]}
    return data


# ---------------------------------------------------------------------------
#   MCP Server
# ---------------------------------------------------------------------------

app = Server("xentral-mcp")


# ---------------------------------------------------------------------------
#   Tools deklarieren (Claude lernt hier, welche Felder es gibt)
# ---------------------------------------------------------------------------

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="xentral_list_products",
            description=(
                "Listet Produkte aus Xentral. "
                "Verwende pageNumber und pageSize für Pagination. "
                "Optional kann nach Name oder SKU gefiltert werden."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "pageNumber": {
                        "type": "integer",
                        "description": "Seitenzahl ab 1 (wird auf page[number] gemappt).",
                        "minimum": 1,
                    },
                    "pageSize": {
                        "type": "integer",
                        "description": "Anzahl Produkte pro Seite (wird auf page[size] gemappt).",
                        "minimum": 1,
                        "maximum": 200,
                    },
                    "nameContains": {
                        "type": "string",
                        "description": "Optional: Filter nach Produktname (Teilstring).",
                    },
                    "skuEquals": {
                        "type": "string",
                        "description": "Optional: exakte Artikelnummer (SKU).",
                    },
                },
            },
        ),
        types.Tool(
            name="xentral_get_product",
            description="Liest ein einzelnes Produkt aus Xentral per Produkt-ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "productId": {
                        "type": "string",
                        "description": "Produkt-ID aus Xentral.",
                    }
                },
                "required": ["productId"],
            },
        ),
        types.Tool(
            name="xentral_list_customers",
            description=(
                "Listet Kunden aus Xentral. "
                "Verwende pageNumber und pageSize für Pagination. "
                "Optional kann nach Name oder E-Mail gefiltert werden."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "pageNumber": {
                        "type": "integer",
                        "description": "Seitenzahl ab 1 (wird auf page[number] gemappt).",
                        "minimum": 1,
                    },
                    "pageSize": {
                        "type": "integer",
                        "description": "Anzahl Kunden pro Seite (wird auf page[size] gemappt).",
                        "minimum": 1,
                        "maximum": 200,
                    },
                    "nameContains": {
                        "type": "string",
                        "description": "Optional: Filter nach Kundenname (Teilstring).",
                    },
                    "emailContains": {
                        "type": "string",
                        "description": "Optional: Filter nach E-Mail-Adresse (Teilstring).",
                    },
                },
            },
        ),
        types.Tool(
            name="xentral_get_customer",
            description="Liest einen einzelnen Kunden aus Xentral per Kunden-ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "customerId": {
                        "type": "string",
                        "description": "Kunden-ID aus Xentral.",
                    }
                },
                "required": ["customerId"],
            },
        ),
        types.Tool(
            name="xentral_list_invoices",
            description=(
                "Listet Rechnungen (Verkaufsrechnungen) aus Xentral, "
                "standardmäßig neueste zuerst (sortiert nach Datum absteigend). "
                "Für 'die letzten N Rechnungen' einfach limit=N setzen. "
                "Optional kann nach Kundenname, Rechnungsnummer oder Status gefiltert werden."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Anzahl zurückzugebender Rechnungen (Standard 20).",
                        "minimum": 1,
                        "maximum": 150,
                    },
                    "pageNumber": {
                        "type": "integer",
                        "description": "Seitenzahl ab 1 (wird auf page[number] gemappt).",
                        "minimum": 1,
                    },
                    "sortBy": {
                        "type": "string",
                        "enum": [
                            "date", "id", "invoice", "customerName",
                            "customerNumber", "amountNet", "paymentStatus", "status",
                        ],
                        "description": "Sortierfeld (Standard: date).",
                    },
                    "sortDir": {
                        "type": "string",
                        "enum": ["asc", "desc"],
                        "description": "Sortierrichtung (Standard: desc = neueste zuerst).",
                    },
                    "customerNameContains": {
                        "type": "string",
                        "description": "Optional: Filter nach Kundenname (Teilstring).",
                    },
                    "invoiceNumber": {
                        "type": "string",
                        "description": "Optional: Filter nach Rechnungsnummer.",
                    },
                    "status": {
                        "type": "string",
                        "description": "Optional: Filter nach Status (z.B. 'released', 'paid').",
                    },
                },
            },
        ),
        types.Tool(
            name="xentral_get_invoice",
            description="Liest eine einzelne Rechnung aus Xentral per Rechnungs-ID (inkl. Positionen).",
            inputSchema={
                "type": "object",
                "properties": {
                    "invoiceId": {
                        "type": "string",
                        "description": "Rechnungs-ID aus Xentral (nicht die Rechnungsnummer).",
                    }
                },
                "required": ["invoiceId"],
            },
        ),
        types.Tool(
            name="xentral_raw_request",
            description=(
                "Low-level Xentral-API-Request für Endpunkte ohne eigenes Tool. "
                "Pfad relativ zur Base-URL (…/api/v1), z.B. 'invoices/123/documents'. "
                "Bei HTTP 406 werden alternative Accept-Header automatisch probiert; "
                "mit 'accept' kann ein Media-Type explizit gesetzt werden. "
                "Für normale Aufgaben besser die spezialisierten Tools nutzen."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST", "PATCH", "DELETE"],
                        "description": "HTTP-Methode.",
                    },
                    "path": {
                        "type": "string",
                        "description": "Relativer API-Pfad, z.B. 'products', 'customers/123'.",
                    },
                    "params": {
                        "type": "object",
                        "description": "Optionale Query-Parameter als Key-Value-Objekt.",
                        "additionalProperties": True,
                    },
                    "body": {
                        "type": "string",
                        "description": "Optionaler JSON-Body als String.",
                    },
                    "accept": {
                        "type": "string",
                        "description": (
                            "Optionaler Accept-Header, z.B. "
                            "'application/vnd.xentral.default.v1+json'."
                        ),
                    },
                },
                "required": ["method", "path"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
#   Tool-Aufrufe behandeln
# ---------------------------------------------------------------------------

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> list[types.TextContent]:
    """Wird vom MCP-Client aufgerufen, wenn Claude ein Tool nutzt."""
    # Log argument keys only; values may contain secrets/PII.
    arg_keys = sorted(arguments.keys()) if isinstance(arguments, dict) else []
    logger.info(f"Tool called: {name} (argument keys: {arg_keys})")

    async with httpx.AsyncClient(
        base_url=XENTRAL_BASE_URL,
        headers=_auth_headers(),
        timeout=XENTRAL_TIMEOUT,
    ) as client:

        # ---------------------------------------------------------------
        #   Produkte: Liste
        # ---------------------------------------------------------------
        if name == "xentral_list_products":
            page_number = int(arguments.get("pageNumber", 1))
            page_size = int(arguments.get("pageSize", 20))
            name_contains = arguments.get("nameContains")
            sku_equals = arguments.get("skuEquals")

            # Validierung
            if page_number < 1:
                return [types.TextContent(type="text", text="pageNumber muss >= 1 sein")]
            if page_size < 1 or page_size > 200:
                return [types.TextContent(type="text", text="pageSize muss zwischen 1 und 200 liegen")]

            params: Dict[str, Any] = {
                "page[number]": page_number,
                "page[size]": page_size,
            }

            # TODO: Filter-Mapping an echte Xentral-API-Doku anpassen
            if name_contains:
                params["filter[name][key]"] = "name"
                params["filter[name][op]"] = "contains"
                params["filter[name][value]"] = name_contains

            if sku_equals:
                params["filter[sku][key]"] = "sku"
                params["filter[sku][op]"] = "eq"
                params["filter[sku][value]"] = sku_equals

            status_code, data = await _make_request(client, "GET", "products", params=params)
            
            if status_code >= 400:
                return [
                    types.TextContent(
                        type="text",
                        text=f"HTTP-Fehler {status_code} von Xentral bei xentral_list_products: {data}",
                    )
                ]

            text = json.dumps(data, indent=2, ensure_ascii=False)
            return [types.TextContent(type="text", text=text)]

        # ---------------------------------------------------------------
        #   Produkte: Einzelnes Produkt
        # ---------------------------------------------------------------
        if name == "xentral_get_product":
            product_id = arguments["productId"]
            
            if not product_id or not str(product_id).strip():
                return [types.TextContent(type="text", text="productId darf nicht leer sein")]

            status_code, data = await _make_request(client, "GET", f"products/{product_id}")
            
            if status_code >= 400:
                return [
                    types.TextContent(
                        type="text",
                        text=f"HTTP-Fehler {status_code} von Xentral bei xentral_get_product: {data}",
                    )
                ]

            text = json.dumps(data, indent=2, ensure_ascii=False)
            return [types.TextContent(type="text", text=text)]

        # ---------------------------------------------------------------
        #   Kunden: Liste
        # ---------------------------------------------------------------
        if name == "xentral_list_customers":
            page_number = int(arguments.get("pageNumber", 1))
            page_size = int(arguments.get("pageSize", 20))
            name_contains = arguments.get("nameContains")
            email_contains = arguments.get("emailContains")

            # Validierung
            if page_number < 1:
                return [types.TextContent(type="text", text="pageNumber muss >= 1 sein")]
            if page_size < 1 or page_size > 200:
                return [types.TextContent(type="text", text="pageSize muss zwischen 1 und 200 liegen")]

            params: Dict[str, Any] = {
                "page[number]": page_number,
                "page[size]": page_size,
            }

            # TODO: Filter-Mapping an Xentral-Doku anpassen
            if name_contains:
                params["filter[name][key]"] = "name"
                params["filter[name][op]"] = "contains"
                params["filter[name][value]"] = name_contains

            if email_contains:
                params["filter[email][key]"] = "email"
                params["filter[email][op]"] = "contains"
                params["filter[email][value]"] = email_contains

            status_code, data = await _make_request(client, "GET", "customers", params=params)
            
            if status_code >= 400:
                return [
                    types.TextContent(
                        type="text",
                        text=f"HTTP-Fehler {status_code} von Xentral bei xentral_list_customers: {data}",
                    )
                ]

            text = json.dumps(data, indent=2, ensure_ascii=False)
            return [types.TextContent(type="text", text=text)]

        # ---------------------------------------------------------------
        #   Kunden: Einzelner Kunde
        # ---------------------------------------------------------------
        if name == "xentral_get_customer":
            customer_id = arguments["customerId"]
            
            if not customer_id or not str(customer_id).strip():
                return [types.TextContent(type="text", text="customerId darf nicht leer sein")]

            status_code, data = await _make_request(client, "GET", f"customers/{customer_id}")
            
            if status_code >= 400:
                return [
                    types.TextContent(
                        type="text",
                        text=f"HTTP-Fehler {status_code} von Xentral bei xentral_get_customer: {data}",
                    )
                ]

            text = json.dumps(data, indent=2, ensure_ascii=False)
            return [types.TextContent(type="text", text=text)]

        # ---------------------------------------------------------------
        #   Rechnungen: Liste
        # ---------------------------------------------------------------
        if name == "xentral_list_invoices":
            limit = int(arguments.get("limit", 20))
            page_number = int(arguments.get("pageNumber", 1))
            sort_by = arguments.get("sortBy", "date")
            sort_dir = arguments.get("sortDir", "desc")
            customer_name = arguments.get("customerNameContains")
            invoice_number = arguments.get("invoiceNumber")
            status = arguments.get("status")

            if limit < 1 or limit > 150:
                return [types.TextContent(type="text", text="limit muss zwischen 1 und 150 liegen")]
            if page_number < 1:
                return [types.TextContent(type="text", text="pageNumber muss >= 1 sein")]

            params: Dict[str, Any] = {
                "page[number]": str(page_number),
                # Xentral akzeptiert nur page[size] zwischen 10 und 150;
                # bei kleinerem limit wird die Antwort unten gekürzt.
                "page[size]": str(_clamp_page_size(limit)),
                "order[0][field]": sort_by,
                "order[0][dir]": sort_dir,
            }

            filters = []
            if customer_name:
                filters.append(("customerName", "contains", customer_name))
            if invoice_number:
                filters.append(("invoice", "contains", invoice_number))
            if status:
                filters.append(("status", "equals", status))
            for i, (key, op, value) in enumerate(filters):
                params[f"filter[{i}][key]"] = key
                params[f"filter[{i}][op]"] = op
                params[f"filter[{i}][value]"] = value

            status_code, data = await _make_request(client, "GET", "invoices", params=params)

            if status_code >= 400:
                return [
                    types.TextContent(
                        type="text",
                        text=f"HTTP-Fehler {status_code} von Xentral bei xentral_list_invoices: {data}",
                    )
                ]

            data = _truncate_data(data, limit)
            text = json.dumps(data, indent=2, ensure_ascii=False)
            return [types.TextContent(type="text", text=text)]

        # ---------------------------------------------------------------
        #   Rechnungen: Einzelne Rechnung
        # ---------------------------------------------------------------
        if name == "xentral_get_invoice":
            invoice_id = arguments["invoiceId"]

            if not invoice_id or not str(invoice_id).strip():
                return [types.TextContent(type="text", text="invoiceId darf nicht leer sein")]

            status_code, data = await _make_request(client, "GET", f"invoices/{invoice_id}")

            if status_code >= 400:
                return [
                    types.TextContent(
                        type="text",
                        text=f"HTTP-Fehler {status_code} von Xentral bei xentral_get_invoice: {data}",
                    )
                ]

            text = json.dumps(data, indent=2, ensure_ascii=False)
            return [types.TextContent(type="text", text=text)]

        # ---------------------------------------------------------------
        #   Low-level: xentral_raw_request
        # ---------------------------------------------------------------
        if name == "xentral_raw_request":
            method = str(arguments["method"]).upper()
            path = str(arguments["path"]).lstrip("/")
            params = arguments.get("params") or {}
            body_str = arguments.get("body")
            accept = arguments.get("accept")

            if method not in ["GET", "POST", "PATCH", "DELETE"]:
                return [types.TextContent(type="text", text=f"Ungültige HTTP-Methode: {method}")]

            json_body = None
            if body_str:
                try:
                    json_body = json.loads(body_str)
                except json.JSONDecodeError as exc:
                    return [
                        types.TextContent(
                            type="text",
                            text=f"Body ist kein gültiges JSON: {exc}",
                        )
                    ]

            status_code, data = await _make_request(
                client,
                method=method,
                path=path,
                params=params,
                json_body=json_body,
                headers={"Accept": str(accept)} if accept else None,
            )

            if status_code >= 400:
                text = f"HTTP {status_code} Fehler von Xentral:\n\n{json.dumps(data, indent=2, ensure_ascii=False)}"
            else:
                text = json.dumps(data, indent=2, ensure_ascii=False) if isinstance(data, dict) else str(data)

            return [types.TextContent(type="text", text=text)]

    # Fallback bei unbekanntem Tool
    logger.error(f"Unknown tool called: {name}")
    return [
        types.TextContent(
            type="text",
            text=f"Unbekanntes Tool: {name}",
        )
    ]


# ---------------------------------------------------------------------------
#   main / stdio-Transport
# ---------------------------------------------------------------------------

async def main() -> None:
    logger.info("Starting Xentral MCP server...")
    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options(),
            )
    except Exception as exc:
        logger.error(f"Server error: {exc}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())