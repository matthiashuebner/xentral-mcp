"""
MCP (Model Context Protocol) implementation for HTTP transport.
Handles the JSON-RPC protocol structure and standard MCP operations.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class MCPError:
    """MCP error response structure."""
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None


@dataclass
class MCPToolParameter:
    """MCP tool parameter definition."""
    name: str
    type: str
    description: str
    required: bool = False
    enum: Optional[List[str]] = None


@dataclass
class MCPTool:
    """MCP tool definition."""
    name: str
    description: str
    parameters: List[MCPToolParameter]


@dataclass
class MCPRequest:
    """MCP request structure."""
    jsonrpc: str
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None


@dataclass
class MCPResponse:
    """MCP response structure."""
    jsonrpc: str
    id: Optional[Union[str, int]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[MCPError] = None


class MCPProtocol:
    """MCP Protocol implementation for HTTP transport."""
    
    # Standard MCP error codes
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    TOOL_NOT_FOUND = -32000
    TOOL_EXECUTION_ERROR = -32001
    
    def __init__(self, server_name: str, server_version: str):
        """
        Initialize MCP protocol handler.
        
        Args:
            server_name: Name of the MCP server
            server_version: Version of the MCP server
        """
        self.server_name = server_name
        self.server_version = server_version
        self.tools: Dict[str, MCPTool] = {}
        self.initialized = False
    
    def register_tool(self, tool: MCPTool) -> None:
        """
        Register a tool with the MCP server.
        
        Args:
            tool: MCPTool instance to register
        """
        self.tools[tool.name] = tool
        logger.debug(f"Registered MCP tool: {tool.name}")
    
    def register_tools(self, tools: List[MCPTool]) -> None:
        """
        Register multiple tools with the MCP server.
        
        Args:
            tools: List of MCPTool instances to register
        """
        for tool in tools:
            self.register_tool(tool)
    
    def parse_request(self, request_data: str) -> MCPRequest:
        """
        Parse incoming JSON-RPC request.
        
        Args:
            request_data: Raw JSON request string
        
        Returns:
            MCPRequest: Parsed request object
        
        Raises:
            ValueError: If request is invalid JSON or malformed
        """
        try:
            data = json.loads(request_data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
        
        if not isinstance(data, dict):
            raise ValueError("Request must be a JSON object")
        
        # Validate required fields
        if data.get('jsonrpc') != '2.0':
            raise ValueError("jsonrpc field must be '2.0'")
        
        if 'method' not in data:
            raise ValueError("method field is required")
        
        return MCPRequest(
            jsonrpc=data['jsonrpc'],
            method=data['method'],
            params=data.get('params'),
            id=data.get('id')
        )
    
    def create_response(self, request_id: Optional[Union[str, int]], 
                       result: Optional[Dict[str, Any]] = None,
                       error: Optional[MCPError] = None) -> MCPResponse:
        """
        Create MCP response object.
        
        Args:
            request_id: ID from the original request
            result: Success result data
            error: Error information if request failed
        
        Returns:
            MCPResponse: Response object
        """
        return MCPResponse(
            jsonrpc="2.0",
            id=request_id,
            result=result,
            error=error
        )
    
    def create_error_response(self, request_id: Optional[Union[str, int]], 
                             code: int, message: str, 
                             data: Optional[Dict[str, Any]] = None) -> MCPResponse:
        """
        Create error response.
        
        Args:
            request_id: ID from the original request
            code: Error code
            message: Error message
            data: Additional error data
        
        Returns:
            MCPResponse: Error response object
        """
        error = MCPError(code=code, message=message, data=data)
        return self.create_response(request_id, error=error)
    
    def handle_initialize(self, request: MCPRequest) -> MCPResponse:
        """
        Handle MCP initialize request.
        
        Args:
            request: Initialize request
        
        Returns:
            MCPResponse: Initialize response
        """
        logger.info("MCP initialize request received")
        
        self.initialized = True
        
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {
                    "listChanged": False
                }
            },
            "serverInfo": {
                "name": self.server_name,
                "version": self.server_version
            }
        }
        
        return self.create_response(request.id, result=result)
    
    def handle_list_tools(self, request: MCPRequest) -> MCPResponse:
        """
        Handle list_tools request.
        
        Args:
            request: List tools request
        
        Returns:
            MCPResponse: List of available tools
        """
        logger.info(f"MCP list_tools request received, returning {len(self.tools)} tools")
        
        tools_list = []
        for tool in self.tools.values():
            # Convert to MCP tool schema format
            tool_schema = {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
            
            # Add parameters to schema
            for param in tool.parameters:
                prop_def = {
                    "type": param.type,
                    "description": param.description
                }
                
                if param.enum:
                    prop_def["enum"] = param.enum
                
                tool_schema["inputSchema"]["properties"][param.name] = prop_def
                
                if param.required:
                    tool_schema["inputSchema"]["required"].append(param.name)
            
            tools_list.append(tool_schema)
        
        result = {"tools": tools_list}
        return self.create_response(request.id, result=result)
    
    def handle_call_tool(self, request: MCPRequest) -> MCPResponse:
        """
        Handle call_tool request.
        
        Args:
            request: Tool call request
        
        Returns:
            MCPResponse: Tool execution result
        """
        if not request.params:
            return self.create_error_response(
                request.id,
                self.INVALID_PARAMS,
                "call_tool requires parameters"
            )
        
        tool_name = request.params.get('name')
        tool_arguments = request.params.get('arguments', {})
        
        if not tool_name:
            return self.create_error_response(
                request.id,
                self.INVALID_PARAMS,
                "tool name is required"
            )
        
        if tool_name not in self.tools:
            return self.create_error_response(
                request.id,
                self.TOOL_NOT_FOUND,
                f"Tool '{tool_name}' not found"
            )
        
        # Get the tool object
        tool = self.tools[tool_name]
        
        # Log the tool call
        logger.info(f"MCP tool call: {tool_name} with arguments: {tool_arguments}")
        
        try:
            # Check if this is an implemented tool or skeleton tool
            if hasattr(tool, '_implementation_class') and hasattr(tool, '_is_implemented'):
                if tool._is_implemented:
                    # Execute implemented tool
                    tool_instance = tool._implementation_class()
                    result_text = tool_instance.execute(tool_arguments)
                else:
                    # Execute skeleton tool
                    result_text = tool._implementation_class.execute(tool_arguments)
            else:
                # Fallback: try dynamic loading (legacy support)
                tool_handler = self._load_tool_handler(tool_name)
                if tool_handler:
                    result_text = tool_handler.execute(tool_arguments)
                else:
                    # Create basic skeleton response
                    result_text = self._create_basic_skeleton_text(tool_name, tool_arguments)
            
            result = {
                "content": [
                    {
                        "type": "text",
                        "text": result_text
                    }
                ],
                "isError": False
            }
            
            return self.create_response(request.id, result=result)
        
        except Exception as e:
            logger.exception(f"Error executing tool '{tool_name}': {e}")
            return self.create_error_response(
                request.id,
                self.TOOL_EXECUTION_ERROR,
                f"Tool execution failed: {str(e)}"
            )
    
    def _load_tool_handler(self, tool_name: str):
        """
        Dynamically load tool handler from xentral package.
        
        Args:
            tool_name: Name of the tool to load
        
        Returns:
            Tool handler instance or None if not found
        """
        try:
            # Convert tool name to module name
            module_name = tool_name
            
            # Convert to class name (e.g., search_customers -> SearchCustomers)
            class_name = ''.join(word.capitalize() for word in tool_name.split('_'))
            
            # Try to import the specific tool module
            module = __import__(f'xentral.{module_name}', fromlist=[class_name])
            tool_class = getattr(module, class_name)
            
            # Create and return tool instance
            return tool_class()
        
        except (ImportError, AttributeError) as e:
            logger.debug(f"Tool implementation not found for '{tool_name}': {e}")
            return None
        except Exception as e:
            logger.warning(f"Error loading tool '{tool_name}': {e}")
            return None
    
    def _create_basic_skeleton_text(self, tool_name: str, tool_arguments: Dict[str, Any]) -> str:
        """
        Create basic skeleton text response for unimplemented tools.
        
        Args:
            tool_name: Name of the tool
            tool_arguments: Tool arguments
        
        Returns:
            String with skeleton response text
        """
        param_info = []
        if tool_arguments:
            for key, value in tool_arguments.items():
                param_info.append(f"  • {key}: {value}")
        
        result = f"🚧 **{tool_name}** - Tool not yet implemented\n"
        result += f"📝 This tool is planned for future implementation.\n\n"
        
        if param_info:
            result += "📋 **Received parameters:**\n"
            result += "\n".join(param_info) + "\n\n"
        
        result += "💡 The skeleton shows what parameters would be accepted. "
        result += f"To implement this tool, create the corresponding class in `xentral/{tool_name}.py`."
        
        return result
    
    def handle_request(self, request_data: str) -> str:
        """
        Handle incoming MCP request and return JSON response.
        
        Args:
            request_data: Raw JSON request string
        
        Returns:
            str: JSON response string
        """
        try:
            request = self.parse_request(request_data)
            
            # Route to appropriate handler
            if request.method == "initialize":
                response = self.handle_initialize(request)
            elif request.method == "tools/list":
                response = self.handle_list_tools(request)
            elif request.method == "tools/call":
                response = self.handle_call_tool(request)
            elif request.method == "notifications/initialized":
                # Notifications don't expect a response
                return ""
            elif request.method.startswith("notifications/"):
                # Handle other notifications silently
                return ""
            else:
                response = self.create_error_response(
                    request.id,
                    self.METHOD_NOT_FOUND,
                    f"Method '{request.method}' not found"
                )
        
        except ValueError as e:
            response = self.create_error_response(
                None,
                self.PARSE_ERROR,
                str(e)
            )
        except Exception as e:
            logger.exception(f"Unexpected error handling MCP request: {e}")
            response = self.create_error_response(
                None,
                self.INTERNAL_ERROR,
                "Internal server error"
            )
        
        # Convert response to JSON
        response_dict = asdict(response)
        # Remove None values for cleaner JSON
        response_dict = {k: v for k, v in response_dict.items() if v is not None}
        
        return json.dumps(response_dict)
    
    def get_server_info(self) -> Dict[str, Any]:
        """
        Get server information.
        
        Returns:
            Dict containing server information
        """
        return {
            "name": self.server_name,
            "version": self.server_version,
            "protocol_version": "2024-11-05",
            "tools_count": len(self.tools),
            "initialized": self.initialized
        }
