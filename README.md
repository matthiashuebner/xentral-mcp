# Xentral MCP HTTP Server

A Model Context Protocol (MCP) HTTP server for Xentral ERP integration that
exposes the **complete Xentral API** — every endpoint of the official
[Xentral OpenAPI specification](https://github.com/xentral/api-spec-public)
— as MCP tools, plus curated convenience tools for daily ERP workflows.

## 🚀 Features

- **Full API coverage**: 339 auto-generated tools covering all documented
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
- **Runtime Configuration**: Update API credentials dynamically without restart
- **Comprehensive Logging**: All MCP requests, responses, and tool calls logged

## 📋 Requirements

- Python 3.9 or higher
- Xentral instance with API access ([create a personal access token](https://developer.xentral.com/))

## 🛠️ Installation

```bash
git clone https://github.com/yourusername/xentral-mcp.git
cd xentral-mcp
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set XENTRAL_API_URL (instance base URL, no /api suffix)
# and XENTRAL_API_KEY (personal access token)
```

## 🏃 Running the Server

```bash
python mcp_server.py
```

The server starts on `http://0.0.0.0:8888` by default and registers 341 tools.

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

```bash
# Health check
curl http://localhost:8888/health

# List all tools
curl -X POST http://localhost:8888/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

# Call a tool: list customers named Miller
curl -X POST http://localhost:8888/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"customer_list_v2","arguments":{"filter":[{"key":"name","op":"equals","value":"Miller"}],"page":{"number":"1","size":"10"}}}}'

# CLI client
python mcp_client.py list-tools
python mcp_client.py call search_customers --name "Miller"
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
- `mcp_client.py` - CLI testing client
- `mcp-tools-list.md` - Generated overview of all tools
- `.env.example` - Configuration template

## 🌐 HTTP Endpoints

- `POST /mcp` - Main MCP JSON-RPC endpoint (initialize, tools/list, tools/call)
- `GET /health` - Health check
- `GET /info` - Server information
- `GET /tools` - List all tools (plain JSON)
- `POST /config/credentials` - Update API credentials at runtime

## 📞 Support

For issues, check logs in `mcp_server.log`. API errors returned by Xentral
(including validation details) are passed through to the MCP client.

Happy ERP automation! 🚀
