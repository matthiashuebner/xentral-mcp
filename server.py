import os
import json
import asyncio
import sys
from typing import Any, Dict

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types


# ---------------------------------------------------------------------------
#   Konfiguration über Umgebungsvariablen
# ---------------------------------------------------------------------------

XENTRAL_BASE_URL = os.environ.get("XENTRAL_BASE_URL")
XENTRAL_PAT = os.environ.get("XENTRAL_PAT")

if not XENTRAL_BASE_URL or not XENTRAL_PAT:
    print(
        "[xentral-mcp] Bitte XENTRAL_BASE_URL und XENTRAL_PAT als Umgebungsvariablen setzen.",
        file=sys.stderr,
    )
    raise RuntimeError(
        "Umgebungsvariablen XENTRAL_BASE_URL und XENTRAL_PAT sind erforderlich."
    )

# dafür sorgen, dass genau ein '/' am Ende steht
XENTRAL_BASE_URL = XENTRAL_BASE_URL.rstrip("/") + "/"


def _auth_headers() -> Dict[str, str]:
    """Standard-Header für Xentral API-Calls."""
    return {
        "Authorization": f"Bearer {XENTRAL_PAT}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


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
            name="xentral_raw_request",
            description=(
                "Low-level Xentral-API-Request. "
                "Nur verwenden, wenn explizit vom Nutzer gewünscht. "
                "Für normale Aufgaben besser die spezialisieren Tools nutzen."
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

    async with httpx.AsyncClient(
        base_url=XENTRAL_BASE_URL,
        headers=_auth_headers(),
        timeout=30.0,
    ) as client:

        # ---------------------------------------------------------------
        #   Produkte: Liste
        # ---------------------------------------------------------------
        if name == "xentral_list_products":
            page_number = int(arguments.get("pageNumber", 1))
            page_size = int(arguments.get("pageSize", 20))
            name_contains = arguments.get("nameContains")
            sku_equals = arguments.get("skuEquals")

            params: Dict[str, Any] = {
                "page[number]": page_number,
                "page[size]": page_size,
            }

            # TODO: Filter-Mapping ggf. an deine echte Xentral-API-Doku anpassen
            if name_contains:
                    # Laut Fehlermeldung erwartet Xentral key/op/value
                params["filter[name][key]"] = "name"
                params["filter[name][op]"] = "contains"
                params["filter[name][value]"] = name_contains

            if sku_equals:
                params["filter[sku]"] = sku_equals

            resp = await client.get("products", params=params)
            # bei HTTP-Fehlern eine saubere Fehlermeldung zurückgeben
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                return [
                    types.TextContent(
                        type="text",
                        text=f"HTTP-Fehler von Xentral bei xentral_list_products: {exc} / Body: {resp.text}",
                    )
                ]

            data = resp.json()
            text = json.dumps(data, indent=2, ensure_ascii=False)
            return [types.TextContent(type="text", text=text)]

        # ---------------------------------------------------------------
        #   Produkte: Einzelnes Produkt
        # ---------------------------------------------------------------
        if name == "xentral_get_product":
            product_id = arguments["productId"]

            resp = await client.get(f"products/{product_id}")
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                return [
                    types.TextContent(
                        type="text",
                        text=f"HTTP-Fehler von Xentral bei xentral_get_product: {exc} / Body: {resp.text}",
                    )
                ]

            data = resp.json()
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

            params: Dict[str, Any] = {
                "page[number]": page_number,
                "page[size]": page_size,
            }

            # TODO: Filter-Mapping an Xentral-Doku anpassen
            if name_contains:
                params["filter[name][contains]"] = name_contains

            if email_contains:
                params["filter[email][contains]"] = email_contains

            resp = await client.get("customers", params=params)
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                return [
                    types.TextContent(
                        type="text",
                        text=f"HTTP-Fehler von Xentral bei xentral_list_customers: {exc} / Body: {resp.text}",
                    )
                ]

            data = resp.json()
            text = json.dumps(data, indent=2, ensure_ascii=False)
            return [types.TextContent(type="text", text=text)]

        # ---------------------------------------------------------------
        #   Kunden: Einzelner Kunde
        # ---------------------------------------------------------------
        if name == "xentral_get_customer":
            customer_id = arguments["customerId"]

            resp = await client.get(f"customers/{customer_id}")
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                return [
                    types.TextContent(
                        type="text",
                        text=f"HTTP-Fehler von Xentral bei xentral_get_customer: {exc} / Body: {resp.text}",
                    )
                ]

            data = resp.json()
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

            resp = await client.request(
                method=method,
                url=path,
                params=params,
                json=json_body,
            )

            # Versuchen, JSON zu lesen – sonst Text
            try:
                data = resp.json()
                text = json.dumps(data, indent=2, ensure_ascii=False)
            except ValueError:
                text = resp.text

            if resp.is_error:
                text = f"HTTP {resp.status_code} Fehler von Xentral:\n\n{text}"

            return [types.TextContent(type="text", text=text)]

    # Fallback bei unbekanntem Tool
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
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())