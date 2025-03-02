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
                 endpoint: str,
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
        # If using API token
        if self.token_id and self.token_secret:
            self.session.headers.update({
                'Authorization': f'PVEAPIToken={self.token_id}={self.token_secret}'
            })
            return
        
        # If using username/password
        if self.username and self.password:
            auth_url = f"{self.endpoint}/access/ticket"
            response = self.session.post(
                auth_url,
                data={'username': self.username, 'password': self.password},
                verify=not self.insecure,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                raise Exception(f"Authentication failed: {response.text}")
            
            data = response.json()['data']
            self.session.headers.update({
                'CSRFPreventionToken': data['CSRFPreventionToken']
            })
            self.session.cookies.update({
                'PVEAuthCookie': data['ticket']
            })
            return
        
        raise Exception("Either token_id and token_secret or username and password must be provided")
        
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
            response = self.session.request(
                method=method,
                url=url,
                timeout=self.timeout,
                **kwargs
            )
            
            response.raise_for_status()
            
            # Some endpoints return empty responses
            if not response.text:
                return {}
                
            return response.json()['data']
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise 