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

# Setup Logging
logging.basicConfig(
    level=logging.DEBUG,
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


async def _make_request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    retries: int = 0,
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
        )
        
        # Versuchen, JSON zu lesen – sonst Text
        try:
            data = resp.json()
        except ValueError:
            data = resp.text
        
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
        return await _make_request(client, method, path, params, json_body, retries + 1)
    except httpx.RequestError as exc:
        logger.warning(f"Request error for {method} {path}: {exc}, retrying...")
        await asyncio.sleep(2 ** retries)
        return await _make_request(client, method, path, params, json_body, retries + 1)


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
    logger.info(f"Tool called: {name} with args: {arguments}")

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
        #   Low-level: xentral_raw_request
        # ---------------------------------------------------------------
        if name == "xentral_raw_request":
            method = str(arguments["method"]).upper()
            path = str(arguments["path"]).lstrip("/")
            params = arguments.get("params") or {}
            body_str = arguments.get("body")

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