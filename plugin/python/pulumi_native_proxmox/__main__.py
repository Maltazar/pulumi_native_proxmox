"""
Example Pulumi program for creating Proxmox VMs.

This program demonstrates how to use the Pulumi Native Proxmox provider
to create VMs and VM groups in Proxmox.
"""

import pulumi
import pulumi_native_proxmox as proxmox

# Get configuration values
config = pulumi.Config()
cloud_init_config = pulumi.Config("cloud_init")
vm_user_config = pulumi.Config("vm_user")
vm_group_config = pulumi.Config("vm_group")
vm_setup_config = pulumi.Config("vm_setup")

# Create the provider instance with a props dictionary
provider_props = {
    'endpoint': config.require("endpoint"),
    'username': config.get("username"),
    'password': config.get_secret("password"),
    'token_id': config.get("token_id"),
    'token_secret': config.get_secret("token_secret"),
    'node': config.get("node"),
    'insecure': config.get_bool("insecure") or False,
    'timeout': config.get_int("timeout") or 30,
    'debug': config.get_bool("debug") or False
}

provider = proxmox.Provider("proxmox", provider_props)

# Create a single VM
vm = proxmox.VM("example-vm",
    # Required fields
    template_id=config.require("template_id"),
    vmid=config.get_int("vmid"),
    
    # Compute
    cores=config.get_int("cores") or 1,
    sockets=config.get_int("sockets") or 1,
    memory=config.get_int("memory") or 512,
    
    # Storage
    disk_size=config.get("disk_size"),
    disk_storage=config.get("disk_storage"),
    
    # Network
    network_bridge=config.get("network_bridge") or "vmbr0",
    vlan_tag=config.get_int("vlan_tag"),
    
    # Operation
    start_on_create=config.get_bool("start_on_create") or True,
    wait_for_ssh=config.get_bool("wait_for_ssh") or False,
    
    # Cloud-init
    cloud_init_user=cloud_init_config.get("username"),
    cloud_init_password=cloud_init_config.get_secret("password"),
    cloud_init_ssh_key=cloud_init_config.get("ssh_public_key"),
    
    # Post-provisioning
    commands=vm_setup_config.get_object("commands") or [],
    
    # Reference to the provider we created
    opts=pulumi.ResourceOptions(provider=provider)
)

# Create a VM group
vm_group = proxmox.VMGroup("example-vm-group",
    # Group configuration
    prefix=vm_group_config.get("prefix") or "vm",
    count=vm_group_config.get_int("count") or 1,
    vm_start_id=vm_group_config.get_int("vm_start_id") or 100,
    ip_range=vm_group_config.get("ip_range") or "dhcp",
    gateway=vm_group_config.get("gateway"),
    
    # VM configuration (passed to each VM)
    template_id=config.require("template_id"),
    cores=config.get_int("cores") or 1,
    memory=config.get_int("memory") or 512,
    disk_size=config.get("disk_size"),
    disk_storage=config.get("disk_storage"),
    network_bridge=config.get("network_bridge") or "vmbr0",
    vlan_tag=config.get_int("vlan_tag"),
    
    # Cloud-init
    cloud_init_user=cloud_init_config.get("username"),
    cloud_init_password=cloud_init_config.get_secret("password"),
    cloud_init_ssh_key=cloud_init_config.get("ssh_public_key"),
    
    # Reference to the provider we created
    opts=pulumi.ResourceOptions(provider=provider)
)

# Export outputs
pulumi.export("vm_id", vm.vmid)
pulumi.export("vm_ip", vm.ip_address)
pulumi.export("vm_group_ids", vm_group.vm_ids)
pulumi.export("vm_group_ips", vm_group.vm_ips) 