"""
Provider module for Xentral MCP tools.
Handles tool discovery, initialization, and execution.
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class ToolProvider:
    """Provides and manages MCP tools."""
    
    def __init__(self):
        """Initialize tool provider."""
        self.tools: Dict[str, Any] = {}
        self.implementations: Dict[str, type] = {}
    
    def register_tool(self, tool_name: str, tool_class: type) -> None:
        """
        Register a tool implementation.
        
        Args:
            tool_name: Name of the tool
            tool_class: Class implementing the tool
        """
        self.implementations[tool_name] = tool_class
        logger.debug(f"Registered tool: {tool_name}")
    
    def get_tool(self, tool_name: str) -> Optional[type]:
        """
        Get tool implementation by name.
        
        Args:
            tool_name: Name of the tool
        
        Returns:
            Tool class or None if not found
        """
        return self.implementations.get(tool_name)
    
    def list_tools(self) -> List[str]:
        """
        List all registered tools.
        
        Returns:
            List of tool names
        """
        return list(self.implementations.keys())
    
    def is_tool_implemented(self, tool_name: str) -> bool:
        """
        Check if tool is implemented.
        
        Args:
            tool_name: Name of the tool
        
        Returns:
            True if implemented, False otherwise
        """
        return tool_name in self.implementations


# Global provider instance
tool_provider = ToolProvider()
