"""Proxmox VM Resource

This module defines the VM class for managing Proxmox VMs.
"""

import json
import time
import pulumi
import paramiko
from typing import Any, Dict, List, Optional, Union

from .proxmox_client import ProxmoxClient


class VM(pulumi.CustomResource):
    """A Proxmox VM resource."""
    
    def __init__(
        self,
        name: str,
        args: pulumi.Inputs,
        opts: Optional[pulumi.ResourceOptions] = None
    ):
        """Create a new VM resource.
        
        Args:
            name: The unique name for the VM resource.
            args: The arguments to configure the VM.
            opts: Options for the VM.
        """
        # Define properties with defaults
        props = {
            # Required
            'vmid': None,               # VM ID (int), if None one will be generated
            'template_id': None,        # Template ID to clone from
            
            # Compute
            'cores': 1,                 # Number of CPU cores
            'sockets': 1,               # Number of CPU sockets
            'memory': 512,              # Memory in MB
            
            # Storage
            'disk_size': None,          # Disk size (e.g., '10G')
            'disk_storage': None,       # Storage ID for the disk
            
            # Network
            'network_bridge': 'vmbr0',  # Network bridge
            'vlan_tag': None,           # VLAN tag (if any)
            'ip_config': {},            # IP configuration
            
            # Operation
            'start_on_create': True,    # Start VM after creation
            'wait_for_ssh': False,      # Wait for SSH to be available
            
            # Cloud-init
            'cloud_init_user': None,    # Cloud-init username
            'cloud_init_password': None, # Cloud-init password
            'cloud_init_ssh_key': None, # Cloud-init SSH key
            
            # Post-provisioning
            'commands': [],             # Commands to run after VM is up
            'files': [],                # Files to copy to the VM
            
            # Provider config - if not passed, will use provider configuration
            'endpoint': None,           # Proxmox API endpoint
            'username': None,           # Username
            'password': None,           # Password
            'token_id': None,           # API token ID
            'token_secret': None,       # API token secret
            'node': None,               # Node to create VM on
            'insecure': None,           # Skip TLS verification
            'timeout': None,            # API timeout
            'debug': None,              # Enable debug logging
        }
        
        # Update with user-provided properties
        for k, v in args.items():
            props[k] = v
        
        # Initialize the resource
        super().__init__(
            'proxmox:vm:VM',
            name,
            props,
            opts
        )
        
    def _get_client(self, props: Dict[str, Any]) -> ProxmoxClient:
        """Get a Proxmox API client using provider or resource properties.
        
        Args:
            props: Resource properties
            
        Returns:
            A configured ProxmoxClient
        """
        # Use provider configuration if available
        provider = self.get_provider('proxmox')
        
        # Merge provider and resource config with resource taking precedence
        client_props = {}
        if provider:
            for k in ['endpoint', 'username', 'password', 'token_id', 'token_secret', 'node', 'insecure', 'timeout', 'debug']:
                client_props[k] = provider.get(k)
                
        # Resource props override provider props
        for k in ['endpoint', 'username', 'password', 'token_id', 'token_secret', 'node', 'insecure', 'timeout', 'debug']:
            if props.get(k) is not None:
                client_props[k] = props.get(k)
        
        return ProxmoxClient(**client_props) 