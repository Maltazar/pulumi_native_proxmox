"""
A simple example of using the Pulumi Proxmox provider to create a single VM.
"""

import os
import pulumi
from pulumi_native_proxmox import Provider, VM

# Get configuration from Pulumi.yaml
config = pulumi.Config()

# Create a provider instance
proxmox = Provider("proxmox", {
    "endpoint": config.require("proxmox:endpoint"),
    "username": config.require("proxmox:username"),
    "password": config.require_secret("proxmox:password"),
    "node": config.require("proxmox:node"),
    "insecure": config.require_bool("proxmox:insecure"),
})

# Get VM configuration
vm_config = config.get_object("vm") or {}
cloud_init_config = config.get_object("cloud_init") or {}

# Create a single VM
vm = VM("my-vm", 
    {
        # Required properties
        "template_id": vm_config.get("template"),
        
        # Compute
        "cores": vm_config.get("cores", 1),
        "memory": vm_config.get("memory", 512),
        
        # Storage
        "disk_size": vm_config.get("disk_size"),
        "disk_storage": vm_config.get("disk_storage"),
        
        # Network
        "network_bridge": vm_config.get("network_bridge", "vmbr0"),
        "vlan_tag": vm_config.get("vlan_tag"),
        
        # Cloud-init
        "cloud_init_user": cloud_init_config.get("username"),
        "cloud_init_ssh_key": os.path.expanduser(cloud_init_config.get("ssh_public_key", "")),
        
        # Operation
        "start_on_create": True,
        "wait_for_ssh": True,
    },
    pulumi.ResourceOptions(provider=proxmox)
)

# Export the VM ID and IP address
pulumi.export("vm_id", vm.vmid)
pulumi.export("ip_address", vm.ip_address) 