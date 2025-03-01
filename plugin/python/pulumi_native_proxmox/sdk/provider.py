"""Pulumi Native Provider for Proxmox

This module defines the Provider class for the Pulumi Native Proxmox provider.
"""

import pulumi
from pulumi.provider import ProviderResource

class Provider(ProviderResource):
    """The provider type for the Proxmox package."""

    def __init__(self,
                 name: str,
                 props: pulumi.Inputs = None,
                 opts: pulumi.ResourceOptions = None):
        """Create a new Proxmox provider resource.
        
        Args:
            name: The unique name of the provider.
            props: The configuration properties for the provider.
            opts: Options for the provider.
        """
        if props is None:
            props = {}
        
        # Define provider properties with defaults
        props_with_defaults = {
            # Required
            'endpoint': None,           # Proxmox API endpoint URL
            
            # Authentication (either username+password or token)
            'username': None,           # Username in format user@realm
            'password': None,           # Password
            'token_id': None,           # API token ID
            'token_secret': None,       # API token secret
            
            # Optional
            'node': None,               # Default node to use
            'insecure': False,          # Skip TLS verification
            'timeout': 30,              # API timeout in seconds
            'debug': False,             # Enable debug logging
        }
        
        # Update with user-provided properties
        for k, v in props.items():
            props_with_defaults[k] = v
        
        super().__init__('proxmox', name, props_with_defaults, opts)
        
    def translate_output_property(self, prop):
        """Translate provider property names."""
        return prop
    
    def translate_input_property(self, prop):
        """Translate provider property names."""
        return prop 