"""
Table formatter for converting API responses to table format.
Supports both text tables and JSON output.
"""

from typing import List, Dict, Any, Optional
from tabulate import tabulate


class TableFormatter:
    """Format API responses as tables or JSON."""
    
    @staticmethod
    def format_as_table(
        data: List[Dict[str, Any]],
        columns: List[str],
        title: Optional[str] = None,
        total_count: Optional[int] = None
    ) -> str:
        """
        Format list of dictionaries as a readable table.
        
        Args:
            data: List of dictionaries to format
            columns: Column names to display (in order)
            title: Optional title for the table
            total_count: Optional total count of records
        
        Returns:
            str: Formatted table as string
        """
        if not data:
            return "❌ No results found."
        
        # Extract only requested columns
        table_data = []
        for item in data:
            row = []
            for col in columns:
                value = item.get(col, 'N/A')
                # Format value
                if value is None:
                    value = 'N/A'
                elif isinstance(value, bool):
                    value = '✓' if value else '✗'
                elif isinstance(value, (int, float)):
                    value = str(value)
                row.append(str(value)[:50])  # Limit cell width
            table_data.append(row)
        
        # Generate table
        output = []
        
        if title:
            output.append(f"\n📊 {title}\n")
        
        output.append(tabulate(table_data, headers=columns, tablefmt='grid'))
        
        if total_count is not None:
            output.append(f"\n📈 Total: {total_count} record(s)")
        else:
            output.append(f"\n📈 Total: {len(data)} record(s)")
        
        return '\n'.join(output)
    
    @staticmethod
    def format_as_json(data: Any) -> str:
        """
        Format data as JSON.
        
        Args:
            data: Data to format as JSON
        
        Returns:
            str: JSON formatted string
        """
        import json
        return json.dumps(data, indent=2, ensure_ascii=False)
    
    @staticmethod
    def format_single_record(
        data: Dict[str, Any],
        title: Optional[str] = None
    ) -> str:
        """
        Format a single record as a table.
        
        Args:
            data: Dictionary with key-value pairs
            title: Optional title
        
        Returns:
            str: Formatted record
        """
        output = []
        
        if title:
            output.append(f"\n📋 {title}\n")
        
        table_data = [[k, v] for k, v in data.items()]
        output.append(tabulate(table_data, headers=['Field', 'Value'], tablefmt='grid'))
        
        return '\n'.join(output)
    
    @staticmethod
    def format_error(error_message: str) -> str:
        """
        Format error message.
        
        Args:
            error_message: Error message
        
        Returns:
            str: Formatted error
        """
        return f"❌ Error: {error_message}"
