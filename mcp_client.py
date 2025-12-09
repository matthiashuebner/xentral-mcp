#!/usr/bin/env python3
"""
Xentral MCP CLI Client
Command-line tool for testing and interacting with the Xentral MCP server.

Usage:
    python mcp_client.py list-tools              # List all tools
    python mcp_client.py help search_customers   # Get help for a tool
    python mcp_client.py call search_customers --name "John" --city "Berlin"
"""

import sys
import argparse
import json
import requests
from typing import Optional, Dict, Any


class MCPClient:
    """Client for interacting with MCP server."""
    
    def __init__(self, server_url: str = "http://localhost:8888"):
        """
        Initialize MCP client.
        
        Args:
            server_url: MCP server URL
        """
        self.server_url = server_url
        self.mcp_endpoint = f"{server_url}/mcp"
        self.tools_endpoint = f"{server_url}/tools"
    
    def initialize(self) -> bool:
        """Initialize MCP protocol."""
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "mcp-cli-client",
                        "version": "1.0.0"
                    }
                }
            }
            
            response = requests.post(self.mcp_endpoint, json=payload)
            response.raise_for_status()
            
            print("✅ MCP Server initialized")
            return True
        
        except Exception as e:
            print(f"❌ Failed to initialize: {e}")
            return False
    
    def list_tools(self) -> Optional[list]:
        """List all available tools."""
        try:
            response = requests.get(self.tools_endpoint)
            response.raise_for_status()
            
            data = response.json()
            return data.get('tools', [])
        
        except Exception as e:
            print(f"❌ Failed to list tools: {e}")
            return None
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[str]:
        """
        Call a tool.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
        
        Returns:
            Tool output or None if failed
        """
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            response = requests.post(self.mcp_endpoint, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract content from response
            if 'result' in data and data['result']:
                content = data['result'].get('content', [])
                if content and len(content) > 0:
                    return content[0].get('text', '')
            
            if 'error' in data and data['error']:
                return f"❌ Error: {data['error'].get('message', 'Unknown error')}"
            
            return None
        
        except Exception as e:
            print(f"❌ Failed to call tool: {e}")
            return None


def print_tool_info(tool: Dict[str, Any]):
    """Print detailed tool information."""
    print(f"\n📋 Tool: {tool['name']}")
    print(f"   Description: {tool['description']}")
    
    if tool.get('parameters'):
        print(f"   Parameters:")
        for param in tool['parameters']:
            required = " (required)" if param.get('required') else ""
            print(f"      • {param['name']}: {param['type']}{required}")
    else:
        print(f"   Parameters: None")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Xentral MCP CLI Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all tools
  python mcp_client.py list-tools
  
  # Get help for a tool
  python mcp_client.py help search_customers
  
  # Call a tool with parameters
  python mcp_client.py call search_customers --name "John"
  
  # Use a custom server
  python mcp_client.py --server http://localhost:9999 list-tools
        """
    )
    
    parser.add_argument(
        '--server',
        default='http://localhost:8888',
        help='MCP server URL (default: http://localhost:8888)'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # list-tools command
    subparsers.add_parser('list-tools', help='List all available tools')
    
    # help command
    help_parser = subparsers.add_parser('help', help='Get help for a tool')
    help_parser.add_argument('tool', help='Tool name')
    
    # call command
    call_parser = subparsers.add_parser('call', help='Call a tool')
    call_parser.add_argument('tool', help='Tool name')
    call_parser.add_argument('arguments', nargs='*', help='Tool arguments (--key value format)')
    
    args = parser.parse_args()
    
    # Create client
    client = MCPClient(args.server)
    
    # Initialize
    if not client.initialize():
        return 1
    
    # Handle commands
    if args.command == 'list-tools':
        tools = client.list_tools()
        if tools:
            print(f"\n📚 Found {len(tools)} tools:\n")
            for tool in tools:
                print(f"  • {tool['name']}: {tool['description']}")
        else:
            print("❌ No tools found or failed to list tools")
            return 1
    
    elif args.command == 'help':
        tools = client.list_tools()
        if tools:
            tool = next((t for t in tools if t['name'] == args.tool), None)
            if tool:
                print_tool_info(tool)
            else:
                print(f"❌ Tool '{args.tool}' not found")
                return 1
        else:
            print("❌ Failed to list tools")
            return 1
    
    elif args.command == 'call':
        # Parse arguments
        tool_args = {}
        for i in range(0, len(args.arguments), 2):
            if i + 1 < len(args.arguments):
                key = args.arguments[i].lstrip('--')
                value = args.arguments[i + 1]
                
                # Try to convert to appropriate type
                if value.lower() == 'true':
                    tool_args[key] = True
                elif value.lower() == 'false':
                    tool_args[key] = False
                elif value.isdigit():
                    tool_args[key] = int(value)
                else:
                    tool_args[key] = value
        
        # Call tool
        result = client.call_tool(args.tool, tool_args)
        if result:
            print(f"\n✅ Tool executed successfully:\n")
            print(result)
        else:
            print(f"❌ Failed to execute tool '{args.tool}'")
            return 1
    
    else:
        parser.print_help()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
