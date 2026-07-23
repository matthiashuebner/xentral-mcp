"""
Xentral tool: Search customers
Search and find customers by various criteria including name, email, phone, city, etc.
"""

from typing import Dict, Any
from xentral.base import XentralAPIBase, XentralAPIError
from xentral.table_formatter import TableFormatter


class SearchCustomers(XentralAPIBase):
    """Search for customers in Xentral with comprehensive filtering options."""
    
    def execute(self, arguments: Dict[str, Any]) -> str:
        """
        Search for customers by various criteria.
        
        Args:
            arguments: Search filters including:
                - customer_id: Customer ID
                - customer_number: Customer Number
                - name: Customer Name (searches all name fields)
                - email: Email Address
                - phone: Phone Number
                - city: City
                - page: Page number
                - limit: Results limit
                - raw: Show raw API response
        
        Returns:
            str: Formatted search results
        """
        try:
            # Build API URL
            url = self.build_api_url('api/v2/customers')
            
            # Build parameters
            params = {}
            
            # Add filters if provided
            if 'customer_id' in arguments:
                params['filter[id][value]'] = arguments['customer_id']
            
            if 'customer_number' in arguments:
                params['filter[number][value]'] = arguments['customer_number']
            
            if 'name' in arguments:
                params['filter[name][value]'] = arguments['name']
            
            if 'email' in arguments:
                params['filter[email][value]'] = arguments['email']
            
            if 'phone' in arguments:
                params['filter[phone][value]'] = arguments['phone']
            
            if 'city' in arguments:
                params['filter[city][value]'] = arguments['city']
            
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
        Format API response as table.
        
        Args:
            api_data: API response data
        
        Returns:
            str: Formatted table
        """
        if not api_data.get('data'):
            return TableFormatter.format_error("No customers found")
        
        items = api_data['data']
        total = api_data.get('meta', {}).get('total', len(items))
        
        # Define columns for customer table
        columns = ['id', 'number', 'name', 'email', 'phone', 'city']
        
        return TableFormatter.format_as_table(
            items,
            columns=columns,
            title="Customer Search Results",
            total_count=total
        )
    
    def _format_raw_response(self, api_data: Dict[str, Any]) -> str:
        """
        Format raw API response.
        
        Args:
            api_data: API response data
        
        Returns:
            str: Raw response formatted
        """
        import json
        return f"```json\n{json.dumps(api_data, indent=2)}\n```"
