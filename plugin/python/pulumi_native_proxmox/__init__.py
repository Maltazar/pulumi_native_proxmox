"""Pulumi Native Provider for Proxmox VE

This module provides a native provider for Proxmox VE that allows you to create
and manage VMs using Pulumi and Python.
"""

import importlib.metadata
from pulumi.runtime.rpc import ResourcePackage, ResourceModule
from typing import Optional, Dict, Any

# Export public classes from the SDK
from .sdk.provider import Provider
from .sdk.vm import VM
from .sdk.vm_group import VMGroup

# Package version
try:
    __version__ = importlib.metadata.version("pulumi_native_proxmox")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.1.0"

# Public exports
__all__ = ['Provider', 'VM', 'VMGroup']


# Define proper ResourcePackage and ResourceModule implementations
class ProxmoxResourcePackage(ResourcePackage):
    """Resource package for Proxmox resources."""
    
    def __init__(self):
        self._modules = {
            "vm": ProxmoxVMModule(),
            "index": ProxmoxIndexModule(),
        }
    
    def version(self) -> Optional[Any]:
        return None  # None means any version is compatible
    
    def construct_provider(self, name: str, typ: str, urn: str) -> Provider:
        return Provider(name)


class ProxmoxVMModule(ResourceModule):
    """Resource module for Proxmox VM resources."""
    
    def version(self) -> Optional[Any]:
        return None  # None means any version is compatible
    
    def construct(self, name: str, typ: str, urn: str) -> Any:
        if typ == "VM":
            return VM(name)
        elif typ == "VMGroup":
            return VMGroup(name)
        else:
            raise ValueError(f"Unknown resource type: {typ}")


class ProxmoxIndexModule(ResourceModule):
    """Resource module for Proxmox index resources."""
    
    def version(self) -> Optional[Any]:
        return None  # None means any version is compatible
    
    def construct(self, name: str, typ: str, urn: str) -> Any:
        if typ == "Provider":
            return Provider(name)
        else:
            raise ValueError(f"Unknown resource type: {typ}")


# This function is a Pulumi entrypoint, used by the SDK
def pulumi_resource_packages():
    """Return a map of resource package names to resource packages."""
    return {
        "proxmox": ProxmoxResourcePackage(),
    } 