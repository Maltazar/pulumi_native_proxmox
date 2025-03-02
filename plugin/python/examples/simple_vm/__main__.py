"""
Example Pulumi program using the Proxmox dynamic provider.
"""

import pulumi
from pulumi_native_proxmox_dynamic import ProxmoxProvider, VM, VMGroup

# Get configuration values
config = pulumi.Config()
cloud_init_config = pulumi.Config("cloud_init")
vm_user_config = pulumi.Config("vm_user")
vm_setup_config = pulumi.Config("vm_setup")
vm_group_config = pulumi.Config("vm_group")

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

# Create a single VM
single_vm = VM(
    name="example-vm",
    template_id=config.require("template_id"),
    args={
        # Set any additional specific properties for this VM
        'vmid': config.get_int("vmid"),
        # Include all standard VM args
        **vm_args
    }
)

# Create a VM group if configured
vm_group = None
if vm_group_config.get("count"):
    vm_group = VMGroup(
        name="example-cluster",
        template_id=config.require("template_id"),
        prefix=vm_group_config.get("prefix") or "node",
        count=vm_group_config.get_int("count") or 3,
        vm_start_id=vm_group_config.get_int("vm_start_id"),
        ip_range=vm_group_config.get("ip_range"),
        gateway=vm_group_config.get("gateway"),
        args=vm_args
    )

# Export important values
pulumi.export('single_vm_id', single_vm.vmid)
pulumi.export('single_vm_node', single_vm.node)

if vm_group:
    # Export the VM group IDs
    vm_ids = []
    for vm in vm_group.vms:
        vm_ids.append(vm.vmid)
    pulumi.export('vm_group_ids', vm_ids) 