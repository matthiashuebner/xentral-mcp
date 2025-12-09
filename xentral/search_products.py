"""
Xentral tool: Search products
Search and find products by various criteria including name, type, article number, etc.
"""

from typing import Dict, Any
from xentral.base import XentralAPIBase, XentralAPIError
from xentral.table_formatter import TableFormatter


class SearchProducts(XentralAPIBase):
    """Search for products in Xentral with comprehensive filtering options."""
    
    def execute(self, arguments: Dict[str, Any]) -> str:
        """
        Search for products by various criteria.
        
        Args:
            arguments: Search filters including:
                - product_id: Product ID
                - article_number: Article Number
                - name: Product Name (searches all name fields)
                - type: Product Type
                - device_type: Device Type
                - page: Page number
                - limit: Results limit
                - raw: Show raw API response
        
        Returns:
            str: Formatted search results
        """
        try:
            # Build API URL
            url = self.build_api_url('api/v2/products')
            
            # Build parameters
            params = {}
            
            # Add filters if provided
            if 'product_id' in arguments:
                params['filter[id][value]'] = arguments['product_id']
            
            if 'article_number' in arguments:
                params['filter[article_number][value]'] = arguments['article_number']
            
            if 'name' in arguments:
                params['filter[name][value]'] = arguments['name']
            
            if 'type' in arguments:
                params['filter[type][value]'] = arguments['type']
            
            if 'device_type' in arguments:
                params['filter[device_type][value]'] = arguments['device_type']
            
            # Add pagination
            pagination = self.build_pagination(arguments)
            params.update(pagination)
            
            # Make API request
            response_data = self.make_request('GET', url, params=params)
            
            # Return raw response if requested
            if arguments.get('raw'):
                return self._format_raw_response(response_data)
            
            # Format and return response
            return self._format_response(response_data)
        
        except XentralAPIError as e:
            return self.format_error_response(e)
        except Exception as e:
            return self.format_error_response(e)
    
    def _format_response(self, api_data: Dict[str, Any]) -> str:
        """
        Format API response as table with required product fields.
        
        Args:
            api_data: API response data
        
        Returns:
            str: Formatted table
        """
        if not api_data.get('data'):
            return TableFormatter.format_error("No products found")
        
        items = api_data['data']
        total = api_data.get('meta', {}).get('total', len(items))
        
        # Define columns for product table (as requested)
        # ID, Article Number, Product Name, Type, Device Type, Weight, Total Count
        columns = ['id', 'article_number', 'name', 'type', 'device_type', 'weight']
        
        return TableFormatter.format_as_table(
            items,
            columns=columns,
            title="Product Search Results",
            total_count=total
        )
    
    def _format_raw_response(self, api_data: Dict[str, Any]) -> str:
        """
        Return raw API response as JSON.
        
        Args:
            api_data: API response data
        
        Returns:
            str: JSON formatted response
        """
        return TableFormatter.format_as_json(api_data)
