# Xentral MCP HTTP Server

A Model Context Protocol (MCP) HTTP server for Xentral ERP integration, providing powerful tools for daily ERP workflows.

## 🚀 Features

- **Real MCP HTTP Server**: Full JSON-RPC 2.0 compatible MCP implementation
- **Auto-Discovery**: Tools automatically discovered from `xentral/` directory
- **100+ Tools**: Comprehensive tool library for all ERP workflows (framework ready)
- **Runtime Configuration**: Update API credentials dynamically without restart
- **Comprehensive Logging**: All MCP requests, responses, and tool calls logged
- **Health Monitoring**: Built-in health checks and server information endpoints
- **CORS Support**: Compatible with web-based MCP clients
- **Production Ready**: Structured codebase with proper error handling

## 📋 Requirements

- Python 3.8 or higher
- Xentral ERP system with API access
- Valid Xentral API credentials

## 🛠️ Installation

### 1. Clone or Download

```bash
git clone https://github.com/yourusername/xentral-mcp.git
cd xentral-mcp
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Create `.env` file with your Xentral credentials:

```bash
cp .env.example .env
# Edit .env with your Xentral API URL and key
```

## 🏃 Running the Server

```bash
python mcp_server.py
```

## 🔍 Testing

```bash
# List all tools
python mcp_client.py list-tools

# Call a tool
python mcp_client.py call search_customers --name "Miller"
```

## 📁 Project Structure

- `mcp_server.py` - Main Flask HTTP server
- `config.py` - Configuration management
- `mcp_protocol.py` - MCP JSON-RPC protocol
- `mcp_tools_parser.py` - Tool documentation parser
- `mcp_client.py` - CLI testing client
- `xentral/` - Tool implementations directory
- `mcp-tools-list.md` - Tool documentation
- `.env.example` - Configuration template

## 📞 Support

For issues, check the troubleshooting section in the full README or review logs in `mcp_server.log`.

Happy ERP automation! 🚀
