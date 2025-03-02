"""
Proxmox API Client.

This module provides a client for the Proxmox API.
"""

import json
import requests
import urllib3
import logging
from typing import Any, Dict, List, Optional, Union, Tuple

# Configure logging
logger = logging.getLogger(__name__)


class ProxmoxClient:
    """A client for the Proxmox API."""
    
    def __init__(self,
                 endpoint: Optional[str] = None,
                 username: Optional[str] = None,
                 password: Optional[str] = None,
                 token_id: Optional[str] = None,
                 token_secret: Optional[str] = None,
                 node: Optional[str] = None,
                 insecure: bool = False,
                 timeout: int = 30,
                 debug: bool = False):
        """Initialize a new Proxmox API client.
        
        Args:
            endpoint: Proxmox API endpoint URL
            username: Proxmox username (with realm, e.g., 'root@pam')
            password: Proxmox password
            token_id: Proxmox API token ID (alternative to username/password)
            token_secret: Proxmox API token secret
            node: Default Proxmox node to operate on
            insecure: Whether to skip TLS verification
            timeout: API request timeout in seconds
            debug: Enable debug logging
        """
        # Check if required parameters are provided
        if endpoint is None:
            raise ValueError("Endpoint is required")
            
        # Clean up and validate inputs
        if username == '':
            username = None
        if password == '':
            password = None
        if token_id == '' or token_id == 'string':
            token_id = None
        if token_secret == '' or token_secret == 'string':
            token_secret = None
            
        # Save configuration
        self.endpoint = endpoint.rstrip('/')
        self.username = username
        self.password = password
        self.token_id = token_id
        self.token_secret = token_secret
        self.node = node
        self.timeout = timeout
        self.insecure = insecure
        
        # Configure debug logging
        if debug:
            logging.basicConfig(level=logging.DEBUG)
            logger.setLevel(logging.DEBUG)
        
        # Disable SSL warnings if insecure
        if insecure:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Set up the session
        self.session = requests.Session()
        self.session.verify = not insecure
        
        # Authenticate
        self._authenticate()
    
    def _authenticate(self) -> None:
        """Authenticate with the Proxmox API."""
        # If using API token (both token_id and token_secret must be provided)
        if self.token_id is not None and self.token_secret is not None:
            print(f"Authenticating with token: {self.token_id}")
            self.session.headers.update({
                'Authorization': f'PVEAPIToken={self.token_id}={self.token_secret}'
            })
            return
        
        # If using username/password
        if self.username is not None and self.password is not None:
            print(f"Authenticating with username: {self.username}")
            auth_url = f"{self.endpoint}/access/ticket"
            print(f"Authentication URL: {auth_url}")
            print(f"Insecure: {self.insecure}")
            
            # Create authentication payload
            auth_data = {'username': self.username, 'password': self.password}
            print(f"Authentication payload: {{'username': '{self.username}', 'password': '***'}}")
            
            try:
                # Print session details for debugging
                print(f"Session verify: {not self.insecure}")
                print(f"Session timeout: {self.timeout}")
                
                response = self.session.post(
                    auth_url,
                    data=auth_data,
                    verify=not self.insecure,
                    timeout=self.timeout
                )
                
                print(f"Response status code: {response.status_code}")
                print(f"Response headers: {response.headers}")
                
                if response.status_code != 200:
                    # Print detailed error info for debugging
                    print(f"Authentication failed with status code {response.status_code}")
                    print(f"Response: {response.text}")
                    raise Exception(f"Authentication failed with status {response.status_code}: {response.text}")
                
                data = response.json().get('data')
                if not data or 'ticket' not in data or 'CSRFPreventionToken' not in data:
                    print(f"Unexpected response format: {response.text}")
                    raise Exception(f"Authentication succeeded but returned invalid data: {response.text}")
                    
                print("Authentication successful!")
                self.session.headers.update({
                    'CSRFPreventionToken': data['CSRFPreventionToken']
                })
                self.session.cookies.update({
                    'PVEAuthCookie': data['ticket']
                })
                return
            except Exception as e:
                print(f"Authentication error: {str(e)}")
                raise
        
        # If neither token nor username/password authentication method is provided
        raise Exception("No valid authentication credentials provided. Please configure either token_id/token_secret or username/password")
        
    def request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Make a request to the Proxmox API.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: API path (e.g., '/nodes/{node}/qemu/{vmid}/status/start')
            **kwargs: Additional arguments to pass to requests
            
        Returns:
            Response data
        """
        url = f"{self.endpoint}/{path.lstrip('/')}"
        
        try:
            logger.debug(f"Making request: {method}")
            if 'data' in kwargs:
                logger.debug(f"Request data: {kwargs['data']}")
            if 'params' in kwargs:
                logger.debug(f"Request params: {kwargs['params']}")
                
            response = self.session.request(
                method=method,
                url=url,
                timeout=self.timeout,
                **kwargs
            )
            
            response.raise_for_status()
            
            # Some endpoints return empty responses
            if not response.text:
                logger.debug("Empty response received")
                return {}
            
            # Parse the JSON response
            json_response = response.json()
            logger.debug(f"Response JSON: {json_response}")
            
            # Handle different Proxmox API response formats
            if 'data' in json_response:
                return json_response['data']
            else:
                # Return the full response if there's no 'data' key
                return json_response
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise 