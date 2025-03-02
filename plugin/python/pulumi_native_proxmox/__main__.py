"""
Example Pulumi program for creating Proxmox VMs.

This program demonstrates how to use the Pulumi Native Proxmox provider
to create VMs and VM groups in Proxmox.
"""

import pulumi
import pulumi_native_proxmox as proxmox

# Get configuration values
config = pulumi.Config()

# Create the provider instance
provider = proxmox.Provider("proxmox",
    endpoint=config.require("proxmox:endpoint"),
    username=config.get("proxmox:username"),
    password=config.get_secret("proxmox:password"),
    token_id=config.get("proxmox:token_id"),
    token_secret=config.get_secret("proxmox:token_secret"),
    node=config.get("proxmox:node"),
    insecure=config.get_bool("proxmox:insecure") or False,
    timeout=config.get_int("proxmox:timeout") or 30,
    debug=config.get_bool("proxmox:debug") or False
)

# Create a single VM
vm = proxmox.VM("example-vm",
    # Required fields
    template_id=config.require("vm:template_id"),
    vmid=config.get_int("vm:vmid"),
    
    # Compute
    cores=config.get_int("vm:cores") or 1,
    sockets=config.get_int("vm:sockets") or 1,
    memory=config.get_int("vm:memory") or 512,
    
    # Storage
    disk_size=config.get("vm:disk_size"),
    disk_storage=config.get("vm:disk_storage"),
    
    # Network
    network_bridge=config.get("vm:network_bridge") or "vmbr0",
    vlan_tag=config.get_int("vm:vlan_tag"),
    
    # Operation
    start_on_create=config.get_bool("vm:start_on_create") or True,
    wait_for_ssh=config.get_bool("vm:wait_for_ssh") or False,
    
    # Cloud-init
    cloud_init_user=config.get("cloud_init:username"),
    cloud_init_password=config.get_secret("cloud_init:password"),
    cloud_init_ssh_key=config.get("cloud_init:ssh_public_key"),
    
    # Post-provisioning
    commands=config.get_object("vm_setup:commands") or [],
    
    # Reference to the provider we created
    opts=pulumi.ResourceOptions(provider=provider)
)

# Create a VM group
vm_group = proxmox.VMGroup("example-vm-group",
    # Group configuration
    prefix=config.get("vm_group:prefix") or "vm",
    count=config.get_int("vm_group:count") or 1,
    vm_start_id=config.get_int("vm_group:vm_start_id") or 100,
    ip_range=config.get("vm_group:ip_range") or "dhcp",
    gateway=config.get("vm_group:gateway"),
    
    # VM configuration (passed to each VM)
    template_id=config.require("vm:template_id"),
    cores=config.get_int("vm:cores") or 1,
    memory=config.get_int("vm:memory") or 512,
    disk_size=config.get("vm:disk_size"),
    disk_storage=config.get("vm:disk_storage"),
    network_bridge=config.get("vm:network_bridge") or "vmbr0",
    vlan_tag=config.get_int("vm:vlan_tag"),
    
    # Cloud-init
    cloud_init_user=config.get("cloud_init:username"),
    cloud_init_password=config.get_secret("cloud_init:password"),
    cloud_init_ssh_key=config.get("cloud_init:ssh_public_key"),
    
    # Reference to the provider we created
    opts=pulumi.ResourceOptions(provider=provider)
)

# Export outputs
pulumi.export("vm_id", vm.vmid)
pulumi.export("vm_ip", vm.ip_address)
pulumi.export("vm_group_ids", vm_group.vm_ids)
pulumi.export("vm_group_ips", vm_group.vm_ips) 