#!/usr/bin/env python3
"""
Xentral MCP HTTP Server
A Model Context Protocol (MCP) HTTP server for Xentral ERP integration.

Features:
- Real MCP HTTP Server: Full JSON-RPC 2.0 compatible implementation
- 100+ Tools: Automatically discovered from xentral/ directory
- Runtime Configuration: Update API credentials dynamically
- Comprehensive Logging: All requests and responses logged
- CORS Support: Compatible with web-based MCP clients
"""

import os
import sys
import logging
import json
import importlib
import inspect
from pathlib import Path
from datetime import datetime

# Third-party imports
from flask import Flask, request, jsonify, Response, g

# Local imports
from config import config
from mcp_protocol import MCPProtocol, MCPTool, MCPToolParameter
from security import check_bearer_token, redact, ApiUrlValidationError
from xentral.openapi.loader import load_openapi_tools

# Setup logging
def setup_logging():
    """Configure logging for the MCP server."""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Create handlers list
    handlers = [logging.StreamHandler(sys.stderr)]
    
    # Only add file handler if we can write to the directory
    try:
        handlers.append(logging.FileHandler('mcp_server.log'))
    except (OSError, PermissionError):
        # Skip file logging if we can't write (e.g., read-only filesystem)
        pass
    
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format=log_format,
        handlers=handlers
    )
    
    # Set specific loggers
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    return logging.getLogger(__name__)

logger = setup_logging()

# Initialize MCP protocol handler
mcp_protocol = MCPProtocol(
    server_name=config.server_name,
    server_version=config.server_version
)


# =============================================================================
# TOOL DISCOVERY AND INITIALIZATION
# =============================================================================

def _class_name_to_tool_name(class_name: str) -> str:
    """Convert CamelCase class name to snake_case tool name."""
    result = ""
    for i, char in enumerate(class_name):
        if char.isupper() and i > 0:
            result += "_"
        result += char.lower()
    return result


def initialize_tools():
    """Initialize MCP tools by scanning the xentral directory for implementations."""
    try:
        logger.info("Initializing MCP tools by scanning xentral directory...")
        
        # Step 1: Discover implemented tools in xentral directory
        xentral_dir = Path("xentral")
        implemented_tools = {}
        
        if not xentral_dir.exists():
            logger.warning(f"Xentral directory {xentral_dir} does not exist")
            return False
        
        # Add current directory to Python path if not already there
        current_path = str(Path.cwd())
        if current_path not in sys.path:
            sys.path.insert(0, current_path)
        
        # Scan for Python files in xentral directory
        for py_file in xentral_dir.glob("*.py"):
            if py_file.name.startswith("__") or py_file.name == "base.py":
                continue
            
            module_name = py_file.stem
            try:
                # Import the module
                full_module_name = f"xentral.{module_name}"
                module = importlib.import_module(full_module_name)
                
                # Find classes that have an execute method (tool implementations)
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (hasattr(obj, 'execute') and
                        callable(getattr(obj, 'execute')) and
                        name != 'XentralAPIBase'):
                        
                        # Convert class name to tool name
                        tool_name = _class_name_to_tool_name(name)
                        implemented_tools[tool_name] = obj
                        logger.info(f"✅ Found implemented tool: {tool_name} ({name})")
            
            except Exception as e:
                logger.error(f"Error importing {full_module_name}: {e}")
                continue
        
        # Step 2: Create MCP tools for implemented tools
        all_tools = []
        
        for tool_name, tool_class in implemented_tools.items():
            # Infer parameters and description
            parameters = _infer_tool_parameters(tool_name)
            description = _infer_tool_description(tool_name)
            
            mcp_tool = MCPTool(
                name=tool_name,
                description=description,
                parameters=parameters
            )
            
            # Store reference to implementation class
            mcp_tool._implementation_class = tool_class
            mcp_tool._is_implemented = True
            
            all_tools.append(mcp_tool)
            logger.info(f"✅ Created MCP tool: {tool_name}")

        # Step 3: Load OpenAPI-generated tools for the full Xentral API.
        # Hand-written tools take precedence on name collisions.
        openapi_tools = load_openapi_tools(exclude_names=set(implemented_tools.keys()))
        all_tools.extend(openapi_tools)
        logger.info(f"✅ Loaded {len(openapi_tools)} OpenAPI-generated tools")

        if not all_tools:
            logger.warning("No implemented tools were found")
            return False
        
        # Register all tools with the MCP protocol
        mcp_protocol.register_tools(all_tools)
        
        logger.info(f"✅ Successfully initialized {len(all_tools)} MCP tools")
        return True
    
    except Exception as e:
        logger.error(f"Failed to initialize tools: {e}")
        return False


def _infer_tool_parameters(tool_name: str) -> list:
    """Infer parameters for a tool based on its name."""
    
    if "search" in tool_name:
        if "customer" in tool_name:
            return [
                MCPToolParameter("customer_id", "integer", "Customer ID", required=False),
                MCPToolParameter("customer_number", "string", "Customer Number", required=False),
                MCPToolParameter("name", "string", "Customer Name", required=False),
                MCPToolParameter("email", "string", "Email Address", required=False),
                MCPToolParameter("phone", "string", "Phone Number", required=False),
                MCPToolParameter("city", "string", "City", required=False),
                MCPToolParameter("page", "integer", "Page Number", required=False),
                MCPToolParameter("limit", "integer", "Results Limit", required=False),
                MCPToolParameter("raw", "boolean", "Show raw API response", required=False)
            ]
    
    # Default parameters for unknown tools
    return [
        MCPToolParameter("id", "integer", "Record ID", required=False),
        MCPToolParameter("page", "integer", "Page Number", required=False),
        MCPToolParameter("limit", "integer", "Results Limit", required=False),
        MCPToolParameter("raw", "boolean", "Show raw API response", required=False)
    ]


def _infer_tool_description(tool_name: str) -> str:
    """Infer description for a tool based on its name."""
    descriptions = {
        "search_customers": "Search and find customers by various criteria",
    }
    
    return descriptions.get(tool_name, f"Execute {tool_name.replace('_', ' ')} operation")


# =============================================================================
# FLASK APPLICATION SETUP
# =============================================================================

# Endpoints that do not require authentication. Everything else is gated.
PUBLIC_PATHS = frozenset({'/health'})


def create_app():
    """Create and configure Flask application."""
    app = Flask(__name__)
    # NOTE: CORS is intentionally NOT enabled. This server is driven by a local
    # MCP client or a server-side proxy; permissive cross-origin access would
    # let any website the operator visits drive the API (see security review).
    # If a specific browser origin must be supported, add a narrowly-scoped
    # allow-list here paired with the auth token — never a wildcard.

    # =============================================================================
    # AUTHENTICATION GATE
    # =============================================================================

    @app.before_request
    def authenticate():
        """Require a valid bearer token on every non-public request."""
        if request.method == 'OPTIONS':
            return None
        if request.path in PUBLIC_PATHS:
            return None
        if not config.is_auth_enabled():
            # No token configured: only tolerated on loopback (enforced at
            # startup by validate_exposure). Local, same-origin requests pass.
            return None
        if not check_bearer_token(request.headers.get('Authorization'), config.auth_token):
            logger.warning(
                "Rejected unauthenticated request: %s %s from %s",
                request.method, request.path, request.remote_addr,
            )
            return jsonify({
                "jsonrpc": "2.0",
                "error": {"code": -32001, "message": "Unauthorized"},
            }), 401
        return None

    # =============================================================================
    # REQUEST LOGGING MIDDLEWARE
    # =============================================================================

    @app.before_request
    def log_request():
        """Log incoming MCP requests with secrets redacted."""
        if config.log_requests and (request.path == '/mcp' or request.path.startswith('/mcp/')):
            timestamp = datetime.now().isoformat()

            logger.info(f"[{timestamp}] MCP Request: {request.method} {request.path}")

            if request.is_json and request.get_json(silent=True):
                request_data = request.get_json(silent=True)

                if isinstance(request_data, dict) and 'method' in request_data:
                    mcp_method = request_data['method']
                    logger.info(f"[{timestamp}] MCP Method: {mcp_method}")

                    if mcp_method == 'tools/call' and 'params' in request_data:
                        params = request_data['params'] or {}
                        tool_name = params.get('name', 'unknown')
                        # Log argument keys only; values may contain secrets/PII.
                        tool_args = params.get('arguments', {})
                        logger.info(f"[{timestamp}] Tool Call: {tool_name}")
                        if isinstance(tool_args, dict):
                            logger.info(
                                f"[{timestamp}] Tool Argument keys: "
                                f"{sorted(tool_args.keys())}"
                            )
                elif logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        f"[{timestamp}] Request Data: {redact(request_data)}"
                    )
    
    # =============================================================================
    # MCP HTTP ENDPOINTS
    # =============================================================================
    
    @app.route('/mcp', methods=['POST'])
    def handle_mcp_request():
        """Handle MCP JSON-RPC requests."""
        try:
            if not request.is_json:
                return jsonify({
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32700,
                        "message": "Request must be JSON"
                    }
                }), 400
            
            # Process the MCP request
            request_data = request.get_data(as_text=True)
            response_json = mcp_protocol.handle_request(request_data)

            return Response(
                response_json,
                mimetype='application/json',
            )
        
        except Exception as e:
            logger.exception(f"Error handling MCP request: {e}")
            return jsonify({
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": "Internal server error"
                }
            }), 500
    
    # Alternative endpoints for different MCP client implementations
    @app.route('/mcp/list_tools', methods=['POST'])
    def list_tools():
        """Alternative endpoint for listing tools."""
        return handle_mcp_request()
    
    @app.route('/mcp/call_tool', methods=['POST'])
    def call_tool():
        """Alternative endpoint for calling tools."""
        return handle_mcp_request()
    
    @app.route('/mcp/initialize', methods=['POST'])
    def initialize():
        """Alternative endpoint for initialization."""
        return handle_mcp_request()
    
    # =============================================================================
    # HEALTH & INFO ENDPOINTS
    # =============================================================================
    
    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint."""
        return jsonify({
            "status": "healthy",
            "server": config.server_name,
            "version": config.server_version,
            "initialized": mcp_protocol.initialized,
            "tools_count": len(mcp_protocol.tools)
        }), 200
    
    @app.route('/info', methods=['GET'])
    def server_info():
        """Server information endpoint (authenticated)."""
        return jsonify({
            "server": mcp_protocol.get_server_info(),
            "config": {
                "api_configured": bool(config.api_url and config.api_key),
                "auth_enabled": config.is_auth_enabled(),
            }
        }), 200
    
    @app.route('/tools', methods=['GET'])
    def list_all_tools():
        """List all available tools."""
        tools_list = []
        for tool in mcp_protocol.tools.values():
            tools_list.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "required": p.required
                    } for p in tool.parameters
                ]
            })
        
        return jsonify({
            "total": len(tools_list),
            "tools": tools_list
        }), 200
    
    @app.route('/config/credentials', methods=['POST'])
    def update_credentials():
        """Update API credentials at runtime (authenticated + validated)."""
        try:
            data = request.get_json(silent=True)

            if not data:
                return jsonify({"error": "Request body is required"}), 400

            api_url = data.get('api_url')
            api_key = data.get('api_key')

            if not api_url or not api_key:
                return jsonify({"error": "Both api_url and api_key are required"}), 400

            # Validates the URL against the SSRF/HTTPS/allow-list policy;
            # rejects internal/metadata targets and plaintext transport.
            try:
                config.update_credentials(api_url, api_key)
            except ApiUrlValidationError as exc:
                logger.warning("Rejected credential update: %s", exc)
                return jsonify({"error": f"Invalid api_url: {exc}"}), 400

            logger.info("✅ API credentials updated successfully")

            return jsonify({
                "status": "success",
                "message": "API credentials updated",
            }), 200

        except Exception as e:
            logger.error(f"Error updating credentials: {e}")
            return jsonify({"error": "Failed to update credentials"}), 500
    
    # =============================================================================
    # ERROR HANDLERS
    # =============================================================================
    
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors."""
        return jsonify({
            "error": "Endpoint not found",
            "available_endpoints": [
                "/mcp (POST) - Main MCP JSON-RPC endpoint",
                "/health (GET) - Health check",
                "/info (GET) - Server information",
                "/tools (GET) - List all tools",
                "/config/credentials (POST) - Update API credentials"
            ]
        }), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors."""
        logger.exception(f"Internal server error: {error}")
        return jsonify({
            "error": "Internal server error",
            "message": "Check server logs for details"
        }), 500
    
    return app


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def validate_configuration():
    """Validate server configuration before starting."""
    errors = config.validate_config()
    
    if errors:
        print("⚠️  Configuration Issues:")
        for error in errors:
            print(f"   - {error}")
        print("\n💡 You can update credentials later via POST /config/credentials")
        return False
    
    return True


def main():
    """Main entry point for the MCP server."""
    try:
        app = create_app()
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return 1
    
    print("=" * 60)
    print("🚀 Xentral MCP HTTP Server")
    print("=" * 60)
    
    # Display configuration
    print(f"Server: {config.server_name} v{config.server_version}")
    print(f"API Key: {'✓ Configured' if config.api_key else '✗ Not configured'}")
    print(f"Host: {config.server_host}")
    print(f"Port: {config.server_port}")
    print(f"Auth: {'✓ Token required' if config.is_auth_enabled() else '✗ DISABLED'}")
    print("-" * 60)

    # Fatal exposure checks: never bind to the network without authentication.
    exposure_errors = config.validate_exposure()
    if exposure_errors:
        print("❌ Refusing to start due to insecure exposure:")
        for error in exposure_errors:
            print(f"   - {error}")
        return 1

    if not config.is_auth_enabled():
        print("⚠️  WARNING: no MCP_AUTH_TOKEN set. The server is reachable without")
        print("   authentication and is bound to loopback only. Set MCP_AUTH_TOKEN")
        print("   before exposing it beyond this machine.")
        print("-" * 60)

    # Validate configuration
    if not validate_configuration():
        print("\n💡 Update credentials via POST /config/credentials endpoint")
        print("-" * 60)

    # Initialize tools
    if not initialize_tools():
        print("❌ Failed to initialize tools. Server will start but may not function properly.")
        return 1
    
    print(f"✅ Loaded {len(mcp_protocol.tools)} MCP tools")
    print("-" * 60)
    
    # Start server
    print(f"🌐 Starting MCP server on http://{config.server_host}:{config.server_port}")
    print("📋 Available MCP endpoints:")
    print("   - POST /mcp - Main MCP JSON-RPC endpoint")
    print("   - GET  /health - Health check")
    print("   - GET  /info - Server information")
    print("   - GET  /tools - List all tools")
    print("   - POST /config/credentials - Update API credentials")
    print()
    print("=" * 60)
    
    try:
        # debug is hard-disabled: the Werkzeug interactive debugger is an RCE
        # vector and must never run on a reachable server.
        app.run(
            host=config.server_host,
            port=config.server_port,
            debug=False,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
