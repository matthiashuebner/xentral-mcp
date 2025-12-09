import os
import json
import asyncio

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
import httpx

# --- Konfiguration über Umgebungsvariablen -----------------------------

XENTRAL_BASE_URL = os.environ.get("XENTRAL_BASE_URL")
XENTRAL_PAT = os.environ.get("XENTRAL_PAT")

if not XENTRAL_BASE_URL or not XENTRAL_PAT:
    raise RuntimeError(
        "Bitte setze die Umgebungsvariablen XENTRAL_BASE_URL "
        "und XENTRAL_PAT, z.B. in deinem MCP-Host oder im Terminal."
    )

# dafür sorgen, dass genau ein '/' am Ende steht
XENTRAL_BASE_URL = XENTRAL_BASE_URL.rstrip("/") + "/"

# --- MCP Server --------------------------------------------------------

app = Server("xentral-mcp")


def _auth_headers() -> dict:
    """Standard-Header für Xentral API-Calls."""
    return {
        "Authorization": f"Bearer {XENTRAL_PAT}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


# 1) Dem Client mitteilen, welche Tools es gibt
@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="xentral_list_products",
            description="Listet Produkte aus Xentral (V2) auf.",
            inputSchema={
                "type": "object",
                "properties": {
                    "params": {
                        "type": "object",
                        "description": (
                            "Optionale Query-Parameter der Xentral API, "
                            "z.B. Filter/Pagination."
                        ),
                        "additionalProperties": True,
                    }
                },
            },
        ),
        types.Tool(
            name="xentral_get_product",
            description="Liest ein einzelnes Produkt per ID aus.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Produkt-ID aus Xentral.",
                    }
                },
                "required": ["id"],
            },
        ),
        types.Tool(
            name="xentral_raw_request",
            description=(
                "Low-level: beliebigen Xentral-API-Request ausführen "
                "(z.B. /products, /customers, ...)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "HTTP-Methode (GET, POST, PATCH, DELETE, ...).",
                    },
                    "path": {
                        "type": "string",
                        "description": (
                            "Relativer API-Pfad, z.B. 'products', "
                            "'customers/123', 'sales-orders'"
                        ),
                    },
                    "params": {
                        "type": "object",
                        "description": "Optionale Query-Parameter.",
                        "additionalProperties": True,
                    },
                    "body": {
                        "type": "string",
                        "description": (
                            "Optionaler JSON-Body als String, z.B. '{\"name\": \"Test\"}'. "
                            "Wird für POST/PATCH verwendet."
                        ),
                    },
                },
                "required": ["method", "path"],
            },
        ),
    ]


# 2) Tool-Aufrufe behandeln
@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Wird vom MCP-Client aufgerufen, wenn das LLM ein Tool nutzt."""

    async with httpx.AsyncClient(
        base_url=XENTRAL_BASE_URL,
        headers=_auth_headers(),
        timeout=30.0,
    ) as client:
        # -------------------------
        # Tool: xentral_list_products
        # -------------------------
        if name == "xentral_list_products":
            params = arguments.get("params") or {}

            resp = await client.get("products", params=params)
            resp.raise_for_status()
            data = resp.json()

            text = json.dumps(data, indent=2, ensure_ascii=False)
            return [
                types.TextContent(
                    type="text",
                    text=text,
                )
            ]

        # -------------------------
        # Tool: xentral_get_product
        # -------------------------
        if name == "xentral_get_product":
            product_id = arguments["id"]
            resp = await client.get(f"products/{product_id}")
            resp.raise_for_status()
            data = resp.json()

            text = json.dumps(data, indent=2, ensure_ascii=False)
            return [
                types.TextContent(
                    type="text",
                    text=text,
                )
            ]

        # -------------------------
        # Tool: xentral_raw_request
        # -------------------------
        if name == "xentral_raw_request":
            method = arguments["method"].upper()
            path = arguments["path"].lstrip("/")  # relativ zum base_url-Pfad
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

            # Fehler hübsch zurückgeben
            try:
                data = resp.json()
                text = json.dumps(data, indent=2, ensure_ascii=False)
            except ValueError:
                text = resp.text

            if resp.is_error:
                text = (
                    f"HTTP {resp.status_code} Fehler von Xentral:\n\n{text}"
                )

            return [
                types.TextContent(
                    type="text",
                    text=text,
                )
            ]

    # Unbekanntes Tool
    return [
        types.TextContent(
            type="text",
            text=f"Unbekanntes Tool: {name}",
        )
    ]


# --- main: stdio-Server starten ---------------------------------------


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())