"""
Proxmox Dynamic Resource Provider.

This module implements the Proxmox resource provider using Pulumi's dynamic provider mechanism.
"""

import pulumi
from typing import Any, Dict, Optional


class ProxmoxProvider:
    """A Proxmox provider that can be used to create Proxmox resources."""
    
    def __init__(self, 
                 endpoint: Optional[str] = None,
                 username: Optional[str] = None,
                 password: Optional[pulumi.Input[str]] = None,
                 token_id: Optional[str] = None,
                 token_secret: Optional[pulumi.Input[str]] = None,
                 node: Optional[str] = None,
                 insecure: Optional[bool] = False,
                 timeout: Optional[int] = 30,
                 debug: Optional[bool] = False):
        """Initialize a new Proxmox provider.
        
        Args:
            endpoint: Proxmox API endpoint URL
            username: Proxmox username (with realm, e.g., 'root@pam')
            password: Proxmox password (sensitive)
            token_id: Proxmox API token ID (alternative to username/password)
            token_secret: Proxmox API token secret (sensitive)
            node: Default Proxmox node to operate on
            insecure: Whether to skip TLS verification
            timeout: API request timeout in seconds
            debug: Enable debug logging
        """
        self.endpoint = endpoint
        self.username = username
        self.password = password
        self.token_id = token_id
        self.token_secret = token_secret
        self.node = node
        self.insecure = insecure
        self.timeout = timeout
        self.debug = debug
        
    def get_config(self) -> Dict[str, Any]:
        """Get the provider configuration as a dictionary.
        
        Returns:
            Provider configuration dictionary
        """
        return {
            'endpoint': self.endpoint,
            'username': self.username,
            'password': self.password,
            'token_id': self.token_id,
            'token_secret': self.token_secret,
            'node': self.node,
            'insecure': self.insecure,
            'timeout': self.timeout,
            'debug': self.debug,
        } 