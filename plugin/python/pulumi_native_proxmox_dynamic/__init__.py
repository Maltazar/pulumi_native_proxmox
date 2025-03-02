"""
Pulumi Dynamic Provider for Proxmox VE.

This module provides a dynamic provider for Proxmox VE that allows you to create
and manage VMs using Pulumi's Dynamic Providers mechanism.
"""

import importlib.metadata

# Export public classes
from .provider import ProxmoxProvider
from .vm import VM
from .vm_group import VMGroup

# Package version
try:
    __version__ = importlib.metadata.version("pulumi_native_proxmox_dynamic")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.1.0"

# Public exports
__all__ = ['ProxmoxProvider', 'VM', 'VMGroup'] 