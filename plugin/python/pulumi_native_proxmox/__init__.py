"""Pulumi Native Provider for Proxmox VE

This module provides a native provider for Proxmox VE that allows you to create
and manage VMs using Pulumi and Python.
"""

import importlib.metadata
from pulumi.resource import ResourcePackage, ResourceModule

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


# This function is a Pulumi entrypoint, used by the SDK
def pulumi_resource_packages():
    """Return a map of resource package names to resource packages."""
    return {
        "proxmox": ResourcePackage("proxmox", {
            "vm": ResourceModule("vm", {
                "VM": VM,
                "VMGroup": VMGroup,
            }),
            "index": ResourceModule("index", {
                "Provider": Provider,
            }),
        }),
    } 