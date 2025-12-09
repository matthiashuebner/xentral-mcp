"""
Parser for mcp-tools-list.md to automatically generate MCP tool definitions.
Extracts tool names, descriptions, and parameters from the markdown documentation.
"""

import re
import logging
from typing import List, Dict, Optional
from pathlib import Path
from mcp_protocol import MCPTool, MCPToolParameter

logger = logging.getLogger(__name__)


class MCPToolsParser:
    """Parser for extracting MCP tools from markdown documentation."""
    
    def __init__(self, markdown_file: str = "mcp-tools-list.md"):
        """
        Initialize the parser.
        
        Args:
            markdown_file: Path to the markdown file containing tool definitions
        """
        self.markdown_file = Path(markdown_file)
        self.tools: List[MCPTool] = []
    
    def parse_tools(self) -> List[MCPTool]:
        """
        Parse all tools from the markdown file.
        
        Returns:
            List[MCPTool]: List of parsed MCP tools
        """
        if not self.markdown_file.exists():
            logger.error(f"Markdown file not found: {self.markdown_file}")
            return []
        
        try:
            with open(self.markdown_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.tools = self._extract_tools_from_content(content)
            logger.info(f"Parsed {len(self.tools)} tools from {self.markdown_file}")
            
            return self.tools
        
        except Exception as e:
            logger.error(f"Error parsing markdown file: {e}")
            return []
    
    def _extract_tools_from_content(self, content: str) -> List[MCPTool]:
        """
        Extract tool definitions from markdown content.
        
        Args:
            content: Markdown file content
        
        Returns:
            List[MCPTool]: Extracted tools
        """
        tools = []
        
        # Pattern to match tool definitions
        # Matches: - **`tool_name`** - Description
        tool_pattern = r'- \*\*`([^`]+)`\*\* - (.+?)(?=\n  -|\n- \*\*`|\n##|\Z)'
        
        # Find all tool matches
        tool_matches = re.finditer(tool_pattern, content, re.DOTALL)
        
        for match in tool_matches:
            tool_name = match.group(1).strip()
            tool_description = match.group(2).strip()
            
            # Extract the full tool block including parameters
            full_match = self._extract_full_tool_block(content, match.start())
            
            if full_match:
                parameters = self._extract_parameters(full_match)
                
                tool = MCPTool(
                    name=tool_name,
                    description=tool_description,
                    parameters=parameters
                )
                
                tools.append(tool)
                logger.debug(f"Parsed tool: {tool_name} with {len(parameters)} parameters")
        
        return tools
    
    def _extract_full_tool_block(self, content: str, start_pos: int) -> Optional[str]:
        """
        Extract the full tool block starting from the tool name.
        
        Args:
            content: Full markdown content
            start_pos: Starting position of the tool definition
        
        Returns:
            Optional[str]: Full tool block or None if not found
        """
        # Find the end of this tool block (next tool or section)
        remaining_content = content[start_pos:]
        
        # Look for the next tool or major section
        next_tool_pattern = r'\n- \*\*`[^`]+`\*\*'
        next_section_pattern = r'\n##'
        
        next_tool_match = re.search(next_tool_pattern, remaining_content[1:])
        next_section_match = re.search(next_section_pattern, remaining_content[1:])
        
        end_pos = len(remaining_content)
        
        if next_tool_match:
            end_pos = min(end_pos, next_tool_match.start() + 1)
        if next_section_match:
            end_pos = min(end_pos, next_section_match.start() + 1)
        
        return remaining_content[:end_pos]
    
    def _extract_parameters(self, tool_block: str) -> List[MCPToolParameter]:
        """
        Extract parameters from a tool block.
        
        Args:
            tool_block: Full tool block text
        
        Returns:
            List[MCPToolParameter]: List of parameters
        """
        parameters = []
        
        # Pattern to match parameter line
        param_pattern = r'Parameter:\s*(.+?)(?=\n|$)'
        param_match = re.search(param_pattern, tool_block, re.IGNORECASE)
        
        if not param_match:
            return parameters
        
        param_text = param_match.group(1).strip()
        
        # Parse parameter text
        parts = [p.strip() for p in param_text.split(',')]
        
        for part in parts:
            clean_param = self._clean_parameter_name(part)
            if clean_param:
                is_required = '(required)' in part
                param_type = self._infer_parameter_type(clean_param)
                description = self._generate_parameter_description(clean_param)
                
                param = MCPToolParameter(
                    name=clean_param,
                    type=param_type,
                    description=description,
                    required=is_required
                )
                parameters.append(param)
        
        return parameters
    
    def _clean_parameter_name(self, param: str) -> str:
        """
        Clean parameter name by removing markdown and extra text.
        
        Args:
            param: Raw parameter string
        
        Returns:
            str: Clean parameter name
        """
        # Remove backticks, required markers, and extra whitespace
        clean = re.sub(r'[`\']', '', param)
        clean = re.sub(r'\s*\(required\)\s*', '', clean)
        clean = clean.strip()
        
        return clean
    
    def _infer_parameter_type(self, param_name: str) -> str:
        """
        Infer parameter type from parameter name.
        
        Args:
            param_name: Parameter name
        
        Returns:
            str: Inferred type
        """
        name_lower = param_name.lower()
        
        # Type inference based on common patterns
        if any(keyword in name_lower for keyword in ['_id', 'id']):
            return "integer"
        elif any(keyword in name_lower for keyword in ['_number', 'number']):
            return "string"
        elif any(keyword in name_lower for keyword in ['_date', 'date']):
            return "string"
        elif any(keyword in name_lower for keyword in ['_range', 'range']):
            return "string"
        elif any(keyword in name_lower for keyword in ['quantity', 'amount', 'price', 'cost', 'count']):
            return "number"
        elif any(keyword in name_lower for keyword in ['email', 'phone', 'name', 'city', 'address']):
            return "string"
        elif any(keyword in name_lower for keyword in ['status', 'type', 'category', 'priority', 'level']):
            return "string"
        elif any(keyword in name_lower for keyword in ['active', 'enabled', 'required', 'expedite']):
            return "boolean"
        else:
            return "string"  # Default to string
    
    def _generate_parameter_description(self, param_name: str) -> str:
        """
        Generate a human-readable description for a parameter.
        
        Args:
            param_name: Parameter name
        
        Returns:
            str: Generated description
        """
        # Convert snake_case to readable format
        words = param_name.replace('_', ' ').split()
        capitalized = [word.capitalize() for word in words]
        
        return ' '.join(capitalized)
    
    def get_tools_by_category(self) -> Dict[str, List[MCPTool]]:
        """
        Group tools by category based on the markdown structure.
        
        Returns:
            Dict[str, List[MCPTool]]: Tools grouped by category
        """
        # This would require parsing the markdown headers to categorize tools
        # For now, return all tools under a general category
        return {"all": self.tools}
    
    def get_priority_tools(self) -> List[MCPTool]:
        """
        Get the priority tools for daily usage.
        
        Returns:
            List[MCPTool]: Priority tools for daily usage
        """
        priority_tool_names = [
            "search_customers",
            "get_order_overview",
            "get_customer_history",
            "track_order_progress",
            "create_ticket_from_call",
            "check_product_availability",
            "process_return",
            "send_customer_update",
            "quick_quote",
            "get_pricing_info"
        ]
        
        priority_tools = []
        for tool in self.tools:
            if tool.name in priority_tool_names:
                priority_tools.append(tool)
        
        return priority_tools
    
    def get_tools_count(self) -> int:
        """
        Get the total number of parsed tools.
        
        Returns:
            int: Number of tools
        """
        return len(self.tools)


# Global parser instance
tools_parser = MCPToolsParser()
