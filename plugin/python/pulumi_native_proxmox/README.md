# Pulumi Native Proxmox Provider

This directory contains the implementation for the Pulumi Native Proxmox Provider.

## Project Structure

The provider is organized into two main folders:

### SDK

The `sdk/` directory contains the user-facing classes that define Proxmox resources:

- `provider.py` - The Provider class for Proxmox configuration
- `vm.py` - The VM class for defining Proxmox virtual machines
- `vm_group.py` - The VMGroup class for defining groups of VMs
- `proxmox_client.py` - Client for communicating with the Proxmox API

These classes are what users import and use in their Pulumi programs.

### Plugin

The `plugin/` directory contains the internal implementation for the Pulumi provider infrastructure:

- `resource_provider.py` - Implements the Pulumi Resource Provider gRPC interface
- `provider_main.py` - Entry point for the provider executable

These components handle the communication between the Pulumi CLI and the Proxmox API.

## How to Use

Users can use this provider by importing the SDK classes in their Pulumi programs:

```python
from pulumi_native_proxmox import Provider, VM

# Create a provider instance
provider = Provider(
    endpoint="https://proxmox.example.com:8006/api2/json",
    username="user@pam",
    password="password",
    node="pve",
    insecure=True
)

# Create a VM
vm = VM(
    "my-vm",
    template_id="template-123",
    cores=2,
    memory=2048,
    disk_size=20,
    disk_storage="local-lvm",
    network_bridge="vmbr0",
    vlan_tag=10
)
```

Alternatively, users can define their infrastructure using Pulumi YAML files and reference this provider. 