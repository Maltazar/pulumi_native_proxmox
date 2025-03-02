"""
Example Pulumi program for creating a cluster of VMs using the Proxmox dynamic provider.

This example creates a group of master nodes and worker nodes for a Kubernetes cluster.
"""

import pulumi
from pulumi_native_proxmox_dynamic import ProxmoxProvider, VM, VMGroup

# Get configuration values
config = pulumi.Config()
cloud_init_config = pulumi.Config("cloud_init")
vm_user_config = pulumi.Config("vm_user")
vm_setup_config = pulumi.Config("vm_setup")

# Create a list of VM groups to create
vm_groups_config = config.get_object("vm_groups") or []

# Create the provider instance
provider = ProxmoxProvider(
    endpoint=config.require("endpoint"),
    username=config.get("username"),
    password=config.get_secret("password"),
    token_id=config.get("token_id"),
    token_secret=config.get_secret("token_secret"),
    node=config.get("node"),
    insecure=config.get_bool("insecure") or False,
    timeout=config.get_int("timeout") or 30,
    debug=config.get_bool("debug") or False
)

# Build standard VM args from config
vm_args = {
    # Provider configuration
    'endpoint': provider.endpoint,
    'username': provider.username,
    'password': provider.password,
    'token_id': provider.token_id,
    'token_secret': provider.token_secret,
    'node': provider.node,
    'insecure': provider.insecure,
    'timeout': provider.timeout,
    'debug': provider.debug,
    
    # VM configuration
    'cores': config.get_int("cores") or 1,
    'sockets': config.get_int("sockets") or 1,
    'memory': config.get_int("memory") or 512,
    'disk_size': config.get("disk_size"),
    'disk_storage': config.get("disk_storage"),
    'network_bridge': config.get("network_bridge") or "vmbr0",
    'vlan_tag': config.get_int("vlan_tag"),
    
    # Cloud-init
    'cloud_init_user': cloud_init_config.get("username"),
    'cloud_init_password': cloud_init_config.get_secret("password"),
    'cloud_init_ssh_public_key': cloud_init_config.get("ssh_public_key"),
    'cloud_init_ssh_private_key': cloud_init_config.get_secret("ssh_private_key"),
    'cloud_init_ssh_key_passphrase': cloud_init_config.get_secret("ssh_key_passphrase"),
    
    # VM User
    'vm_user_create_admin_user': vm_user_config.get_bool("create_admin_user") or False,
    'vm_user_username': vm_user_config.get("username"),
    'vm_user_ssh_public_key': vm_user_config.get("ssh_public_key"),
    'vm_user_ssh_private_key': vm_user_config.get_secret("ssh_private_key"),
    'vm_user_ssh_key_passphrase': vm_user_config.get_secret("ssh_key_passphrase"),
    
    # VM Setup
    'vm_setup_features': vm_setup_config.get("features") or [],
    'vm_setup_scripts': vm_setup_config.get("scripts") or [],
    'vm_setup_commands': vm_setup_config.get("commands") or [],
    
    # Operation
    'start_on_create': config.get_bool("start_on_create") or True,
    'wait_for_ssh': config.get_bool("wait_for_ssh") or False,
}

# Create VM groups
vm_groups = []
for group_config in vm_groups_config:
    prefix = group_config.get("prefix")
    count = group_config.get("count")
    
    if not prefix or not count:
        continue
    
    # Create specific args for this group
    group_args = vm_args.copy()
    
    # Update cores and memory based on role
    if prefix.lower() == "master":
        group_args['cores'] = group_config.get("cores") or 2
        group_args['memory'] = group_config.get("memory") or 4096
    elif prefix.lower() == "worker":
        group_args['cores'] = group_config.get("cores") or 4
        group_args['memory'] = group_config.get("memory") or 8192
    
    # Create the VM group
    vm_group = VMGroup(
        name=f"k8s-{prefix}",
        template_id=config.require("template_id"),
        prefix=prefix,
        count=int(count),
        vm_start_id=group_config.get("vm_start_id"),
        ip_range=group_config.get("ip_range"),
        gateway=group_config.get("gateway"),
        args=group_args
    )
    
    vm_groups.append((prefix, vm_group))

# Export VM group information
for prefix, vm_group in vm_groups:
    # Export the VM group IDs
    vm_ids = []
    vm_names = []
    for vm in vm_group.vms:
        vm_ids.append(vm.vmid)
        vm_names.append(vm.name)
    
    pulumi.export(f'{prefix}_vm_ids', vm_ids)
    pulumi.export(f'{prefix}_vm_names', vm_names) 