"""
Base class for Xentral API tool implementations.
All tool implementations should inherit from XentralAPIBase.
"""

import httpx
import logging
from typing import Dict, Any, Optional
from config import config

logger = logging.getLogger(__name__)


class XentralAPIError(Exception):
    """Custom exception for Xentral API errors."""
    pass


class XentralAPIBase:
    """Base class for all Xentral API tool implementations."""
    
    def __init__(self):
        """Initialize the base class with API configuration."""
        self.api_url = config.api_url
        self.api_key = config.api_key
        self.headers = config.get_auth_headers()
    
    def execute(self, arguments: Dict[str, Any]) -> str:
        """
        Execute the tool. Must be implemented by subclasses.
        
        Args:
            arguments: Tool arguments from MCP request
        
        Returns:
            str: Tool execution result
        """
        raise NotImplementedError("Subclasses must implement execute() method")
    
    def build_api_url(self, endpoint: str) -> str:
        """
        Build complete API URL from endpoint.
        
        Args:
            endpoint: Relative API endpoint (e.g., 'api/v2/customers')
        
        Returns:
            str: Complete API URL
        """
        base = self.api_url.rstrip('/')
        endpoint = endpoint.lstrip('/')
        return f"{base}/{endpoint}"
    
    def make_request(self, method: str, url: str, 
                    params: Optional[Dict[str, Any]] = None,
                    data: Optional[Dict[str, Any]] = None,
                    json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make HTTP request to Xentral API.
        
        Args:
            method: HTTP method (GET, POST, PATCH, DELETE)
            url: Complete API URL
            params: Query parameters
            data: Form data
            json_data: JSON body data
        
        Returns:
            Dict: API response as dictionary
        
        Raises:
            XentralAPIError: If API request fails
        """
        try:
            with httpx.Client(headers=self.headers, timeout=30.0) as client:
                response = client.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    json=json_data
                )
                
                response.raise_for_status()
                
                try:
                    return response.json()
                except ValueError:
                    return {"text": response.text}
        
        except httpx.HTTPStatusError as e:
            raise XentralAPIError(f"HTTP {e.response.status_code}: {e.response.text}")
        except Exception as e:
            raise XentralAPIError(f"API request failed: {str(e)}")
    
    def build_pagination(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build pagination parameters from arguments.
        
        Args:
            arguments: Tool arguments
        
        Returns:
            Dict: Pagination parameters
        """
        params = {}
        
        if 'page' in arguments:
            params['page[number]'] = arguments['page']
        
        if 'per_page' in arguments:
            params['page[size]'] = arguments['per_page']
        elif 'limit' in arguments:
            params['page[size]'] = arguments['limit']
        
        return params
    
    def build_sorting(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build sorting parameters from arguments.
        
        Args:
            arguments: Tool arguments
        
        Returns:
            Dict: Sorting parameters
        """
        params = {}
        
        if 'sort' in arguments:
            params['sort'] = arguments['sort']
        
        return params
    
    def build_filters(self, arguments: Dict[str, Any], 
                     param_mapping: Dict[str, str]) -> Dict[str, Any]:
        """
        Build filter parameters from arguments using parameter mapping.
        
        Args:
            arguments: Tool arguments
            param_mapping: Mapping of argument names to API filter keys
        
        Returns:
            Dict: Filter parameters
        """
        filters = {}
        
        for arg_name, api_key in param_mapping.items():
            if arg_name in arguments:
                filters[f'filter[{api_key}][value]'] = arguments[arg_name]
        
        return filters
    
    def format_error_response(self, error: Exception) -> str:
        """
        Format error response for display.
        
        Args:
            error: Exception that occurred
        
        Returns:
            str: Formatted error message
        """
        if isinstance(error, XentralAPIError):
            return f"❌ **API Error**: {str(error)}"
        else:
            return f"❌ **Error**: {str(error)}"
