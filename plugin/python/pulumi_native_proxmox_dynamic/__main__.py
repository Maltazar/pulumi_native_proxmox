"""
Pulumi program for creating Proxmox VMs using the Dynamic Provider.
This file allows the package directory to also act as a Pulumi project.
"""

import pulumi
import os
import sys

# Fix imports to work both when imported as a module and when run directly
if __name__ == '__main__':
    # When running directly with 'pulumi up'
    # Add the parent directory to the path so we can import the package
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    from pulumi_native_proxmox_dynamic import ProxmoxProvider, VM, VMGroup
else:
    # When imported as a module
    from . import ProxmoxProvider, VM, VMGroup

# Get configuration values
config = pulumi.Config("pulumi-native-proxmox-dynamic")
cloud_init_config = pulumi.Config("cloud_init")
vm_user_config = pulumi.Config("vm_user")
vm_setup_config = pulumi.Config("vm_setup")
vm_group_config = pulumi.Config("vm_group")

# Create the provider instance
# Get authentication parameters
endpoint = config.require("endpoint")
username = config.get("username")
password = config.get_secret("password")
token_id = config.get("token_id")
token_secret = config.get_secret("token_secret")

# Determine which authentication method to use
# If token parameters are provided and are not placeholder values, use tokens
# Otherwise, fallback to username/password
use_token_auth = token_id and token_secret and token_id != "string" and token_secret != "string"
if use_token_auth:
    print("Using token-based authentication")
    provider_auth = {
        "token_id": token_id,
        "token_secret": token_secret,
        # Set username/password to None to avoid confusion
        "username": None,
        "password": None
    }
else:
    print("Using username/password authentication")
    provider_auth = {
        "username": username,
        "password": password,
        # Set token values to None to avoid confusion
        "token_id": None,
        "token_secret": None
    }

# Create provider with the selected authentication method
provider = ProxmoxProvider(
    endpoint=endpoint,
    **provider_auth,
    node=config.get("node"),
    insecure=config.get_bool("insecure") or False,
    timeout=config.get_int("timeout") or 30,
    debug=config.get_bool("debug") or False
)

# Check if we need to create a VM
template_id = config.get("template_id")
if template_id:
    # Create VM arguments from configuration
    vm_args = {
        'template_id': template_id,
        'vmid': config.get_int("vmid"),
        'cores': config.get_int("cores") or 1,
        'sockets': config.get_int("sockets") or 1,
        'memory': config.get_int("memory") or 512,
        'disk_size': config.get("disk_size"),
        'disk_storage': config.get("disk_storage"),
        'network_bridge': config.get("network_bridge") or "vmbr0",
        'vlan_tag': config.get_int("vlan_tag"),
        'start_on_create': config.get_bool("start_on_create") or True,
        'wait_for_ssh': config.get_bool("wait_for_ssh") or True,
    }

    # Add cloud-init configuration if provided
    cloud_init_user = cloud_init_config.get("username")
    if cloud_init_user:
        vm_args['cloud_init_user'] = cloud_init_user
        vm_args['cloud_init_password'] = cloud_init_config.get_secret("password")
        vm_args['cloud_init_ssh_public_key'] = cloud_init_config.get_secret("ssh_public_key")
        vm_args['cloud_init_ssh_private_key'] = cloud_init_config.get_secret("ssh_private_key")
        vm_args['cloud_init_ssh_key_passphrase'] = cloud_init_config.get_secret("ssh_key_passphrase")

    # Add VM user configuration if provided
    create_admin_user = vm_user_config.get_bool("create_admin_user")
    if create_admin_user:
        vm_args['vm_user_create_admin_user'] = True
        vm_args['vm_user_username'] = vm_user_config.get("username")
        vm_args['vm_user_ssh_public_key'] = vm_user_config.get_secret("ssh_public_key")
        vm_args['vm_user_ssh_private_key'] = vm_user_config.get_secret("ssh_private_key")
        vm_args['vm_user_ssh_key_passphrase'] = vm_user_config.get_secret("ssh_key_passphrase")

    # Add VM setup configuration if provided
    features = vm_setup_config.get("features")
    if features:
        if isinstance(features, str):
            vm_args['vm_setup_features'] = [feature.strip() for feature in features.split(',')]
        else:
            vm_args['vm_setup_features'] = features
    
    scripts = vm_setup_config.get("scripts")
    if scripts:
        if isinstance(scripts, str):
            vm_args['vm_setup_scripts'] = [script.strip() for script in scripts.split(',')]
        else:
            vm_args['vm_setup_scripts'] = scripts
            
    commands = vm_setup_config.get("commands") 
    if commands:
        if isinstance(commands, str):
            vm_args['vm_setup_commands'] = [command.strip() for command in commands.split(',')]
        else:
            vm_args['vm_setup_commands'] = commands
    
    # Check if we should create a VM group instead of a single VM
    vm_group_prefix = vm_group_config.get("prefix")
    if vm_group_prefix:
        # Create a VM group
        vm_group = VMGroup(
            name="vm-group",
            template_id=template_id,
            prefix=vm_group_prefix,
            count=vm_group_config.get_int("count", 1),
            vm_start_id=vm_group_config.get_int("vm_start_id"),
            ip_range=vm_group_config.get("ip_range"),
            gateway=vm_group_config.get("gateway"),
            args=vm_args,
            provider=provider
        )
        
        # Export the VM IDs only
        vms_data = []
        for i, vm in enumerate(vm_group.vms):
            vms_data.append({
                "name": f"{vm_group_prefix}-{i+1}",
                "vmid": vm.vmid
            })
        pulumi.export("vms", vms_data)
        
    else:
        # Create a single VM
        vm = VM("vm", args=vm_args, provider=provider)
        
        # Export only the VM ID
        pulumi.export("vmid", vm.vmid) 