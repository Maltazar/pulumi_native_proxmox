"""Proxmox API Client

This module provides a client for interacting with the Proxmox API.
"""

import json
import logging
import requests
import urllib3
from typing import Any, Dict, List, Optional, Union


class ProxmoxClient:
    """Client for interacting with the Proxmox API."""
    
    def __init__(
        self,
        endpoint: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        token_id: Optional[str] = None,
        token_secret: Optional[str] = None,
        node: Optional[str] = None,
        insecure: bool = False,
        timeout: int = 30,
        debug: bool = False
    ):
        """Initialize the Proxmox client.
        
        Args:
            endpoint: The Proxmox API endpoint (e.g., https://proxmox.example.com:8006/api2/json)
            username: The username in the format user@realm
            password: The password for the user
            token_id: The API token ID
            token_secret: The API token secret
            node: The default node to use
            insecure: Whether to skip TLS verification
            timeout: The API timeout in seconds
            debug: Whether to enable debug logging
        """
        self.endpoint = endpoint.rstrip('/')
        self.username = username
        self.password = password
        self.token_id = token_id
        self.token_secret = token_secret
        self.node = node
        self.timeout = timeout
        self.debug = debug
        
        # Configure logging
        self.logger = logging.getLogger("proxmox-client")
        if debug:
            self.logger.setLevel(logging.DEBUG)
        
        # Configure session
        self.session = requests.Session()
        
        if insecure:
            # Disable TLS verification warnings
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            self.session.verify = False
        
        # Authenticate
        self.ticket = None
        self.csrf_token = None
        
        if username and password:
            self._authenticate_with_password()
        elif token_id and token_secret:
            self._authenticate_with_token()
        else:
            raise ValueError("Either username/password or token_id/token_secret must be provided")
    
    def _authenticate_with_password(self) -> None:
        """Authenticate with username and password."""
        auth_url = f"{self.endpoint}/access/ticket"
        data = {
            "username": self.username,
            "password": self.password
        }
        
        self.logger.debug(f"Authenticating with username: {self.username}")
        response = self.session.post(auth_url, data=data, timeout=self.timeout)
        
        if response.status_code != 200:
            raise Exception(f"Authentication failed: {response.text}")
        
        result = response.json()
        self.ticket = result["data"]["ticket"]
        self.csrf_token = result["data"]["CSRFPreventionToken"]
        
        # Configure session cookies
        self.session.cookies.set("PVEAuthCookie", self.ticket)
        self.session.headers.update({"CSRFPreventionToken": self.csrf_token})
        
        self.logger.debug("Authentication successful")
    
    def _authenticate_with_token(self) -> None:
        """Authenticate with API token."""
        self.logger.debug(f"Using API token: {self.token_id}")
        
        # API token authentication is handled through headers on each request
        self.session.headers.update({
            "Authorization": f"PVEAPIToken={self.token_id}={self.token_secret}"
        })
    
    def _build_url(self, path: str) -> str:
        """Build a URL for the Proxmox API.
        
        Args:
            path: The API path
            
        Returns:
            The full API URL
        """
        return f"{self.endpoint}/{path}"
    
    def get(self, path: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send a GET request to the Proxmox API.
        
        Args:
            path: The API path
            params: Query parameters
            
        Returns:
            The API response data
        """
        url = self._build_url(path)
        self.logger.debug(f"GET {url} {params}")
        
        response = self.session.get(url, params=params, timeout=self.timeout)
        return self._process_response(response)
    
    def post(self, path: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send a POST request to the Proxmox API.
        
        Args:
            path: The API path
            data: Request data
            
        Returns:
            The API response data
        """
        url = self._build_url(path)
        self.logger.debug(f"POST {url} {data}")
        
        response = self.session.post(url, data=data, timeout=self.timeout)
        return self._process_response(response)
    
    def put(self, path: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send a PUT request to the Proxmox API.
        
        Args:
            path: The API path
            data: Request data
            
        Returns:
            The API response data
        """
        url = self._build_url(path)
        self.logger.debug(f"PUT {url} {data}")
        
        response = self.session.put(url, data=data, timeout=self.timeout)
        return self._process_response(response)
    
    def delete(self, path: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send a DELETE request to the Proxmox API.
        
        Args:
            path: The API path
            params: Query parameters
            
        Returns:
            The API response data
        """
        url = self._build_url(path)
        self.logger.debug(f"DELETE {url} {params}")
        
        response = self.session.delete(url, params=params, timeout=self.timeout)
        return self._process_response(response)
    
    def _process_response(self, response: requests.Response) -> Dict[str, Any]:
        """Process an API response.
        
        Args:
            response: The API response
            
        Returns:
            The API response data
            
        Raises:
            Exception: If the API returns an error
        """
        if response.status_code >= 400:
            self.logger.error(f"API error: {response.status_code} {response.text}")
            try:
                error = response.json()
                raise Exception(f"API error: {error.get('errors', response.text)}")
            except json.JSONDecodeError:
                raise Exception(f"API error: {response.status_code} {response.text}")
        
        try:
            return response.json()
        except json.JSONDecodeError:
            return {"data": response.text} 