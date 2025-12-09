"""
Configuration management for Xentral MCP Server.
Handles API credentials and server settings with runtime updates.
"""

import os
from typing import Optional
from dotenv import load_dotenv


class XentralConfig:
    """Configuration class for Xentral MCP Server with runtime credential updates."""
    
    def __init__(self):
        """Initialize configuration by loading from environment variables."""
        # Load .env file if it exists
        load_dotenv()
        
        # API Configuration
        self.api_url = os.getenv('XENTRAL_API_URL', 'https://api.xentral.com')
        self.api_key = os.getenv('XENTRAL_API_KEY', '')
        
        # Server Configuration
        self.server_host = os.getenv('MCP_SERVER_HOST', '0.0.0.0')
        self.server_port = int(os.getenv('MCP_SERVER_PORT', '8888'))
        self.debug_mode = os.getenv('MCP_DEBUG', 'false').lower() == 'true'
        
        # Logging Configuration
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        self.log_requests = os.getenv('LOG_REQUESTS', 'true').lower() == 'true'
        
        # MCP Protocol Configuration
        self.mcp_version = "2024-11-05"
        self.server_name = "xentral-mcp-server"
        self.server_version = "1.0.0"
    
    def update_credentials(self, api_url: str, api_key: str) -> None:
        """
        Update API credentials at runtime.
        
        Args:
            api_url: New API URL for Xentral
            api_key: New API key for authentication
        """
        self.api_url = api_url.rstrip('/')  # Remove trailing slash
        self.api_key = api_key
    
    def is_configured(self) -> bool:
        """
        Check if the configuration has minimum required settings.
        
        Returns:
            bool: True if API URL and key are configured
        """
        return bool(self.api_url and self.api_key)
    
    def get_auth_headers(self) -> dict:
        """
        Get authentication headers for API requests.
        
        Returns:
            dict: Headers dictionary with authorization
        """
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'User-Agent': f'{self.server_name}/{self.server_version}'
        }
    
    def validate_config(self) -> list[str]:
        """
        Validate current configuration and return any errors.
        
        Returns:
            list[str]: List of validation error messages
        """
        errors = []
        
        if not self.api_url:
            errors.append("XENTRAL_API_URL is required")
        elif not self.api_url.startswith(('http://', 'https://')):
            errors.append("XENTRAL_API_URL must start with http:// or https://")
        
        if not self.api_key:
            errors.append("XENTRAL_API_KEY is required")
        elif len(self.api_key) < 10:
            errors.append("XENTRAL_API_KEY appears to be too short")
        
        if not (1 <= self.server_port <= 65535):
            errors.append("MCP_SERVER_PORT must be between 1 and 65535")
        
        return errors
    
    def __str__(self) -> str:
        """String representation of config (without sensitive data)."""
        return (
            f"XentralConfig(\n"
            f"  api_url='{self.api_url}',\n"
            f"  api_key='{'*' * min(len(self.api_key), 8) if self.api_key else 'NOT_SET'}',\n"
            f"  server_host='{self.server_host}',\n"
            f"  server_port={self.server_port},\n"
            f"  debug_mode={self.debug_mode}\n"
            f")"
        )


# Global configuration instance
config = XentralConfig()
