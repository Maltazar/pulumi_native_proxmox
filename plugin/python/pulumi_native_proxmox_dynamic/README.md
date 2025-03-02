# Pulumi Dynamic Provider for Proxmox VE

This package provides a dynamic provider for Proxmox VE that allows you to create and manage VMs using Pulumi's Dynamic Providers mechanism in Python.

## Key Differences from the Full Provider

This dynamic provider:
- Is implemented directly in Python using Pulumi's Dynamic Resource API
- Does not require a separate plugin installation
- Can be used directly in your Pulumi Python programs
- Supports all the same features as the full provider

## Usage Options

You can use this provider in two ways:

1. **As a standalone Pulumi project** - Run Pulumi commands directly from this directory
2. **As an imported package** - Import it in your own Pulumi Python programs

## Installation

```bash
# Install with UV (recommended)
uv pip install pulumi_native_proxmox[dynamic]

# OR with pip
pip install pulumi_native_proxmox[dynamic]
```

## Standalone Project Usage

To use the dynamic provider as a standalone project:

```bash
# Navigate to this directory
cd pulumi_native_proxmox_dynamic

# Initialize a stack
pulumi stack init dev

# Configure your provider
pulumi config set endpoint https://proxmox.example.com:8006/api2/json
pulumi config set username root@pam
pulumi config set password --secret your-password
pulumi config set node pve
pulumi config set template_id 9000

# Deploy resources
pulumi up
```

## Configuration

The dynamic provider supports a comprehensive set of configuration options:

```yaml
# Provider configuration
endpoint: https://proxmox.example.com:8006/api2/json  # Proxmox API endpoint
username: root@pam                                    # Username for authentication
password: securepassword                              # Password for authentication
token_id: user@pam!token                              # API token ID (alternative to username/password)
token_secret: secret                                  # API token secret
node: pve                                             # Default Proxmox node to operate on
insecure: true                                        # Skip TLS verification
timeout: 300                                          # API timeout in seconds
debug: false                                          # Enable debug logging

# VM configuration
template_id: 9000                                     # Template ID to clone from
vmid: 900                                             # VM ID (optional, will be generated if not provided)
cores: 2                                              # Number of CPU cores
sockets: 1                                            # Number of CPU sockets
memory: 2048                                          # Memory in MB
disk_size: 32G                                        # Disk size
disk_storage: local-lvm                               # Storage ID for the disk
network_bridge: vmbr0                                 # Network bridge
vlan_tag: 10                                          # VLAN tag
start_on_create: true                                 # Start VM after creation
wait_for_ssh: true                                    # Wait for SSH to be available

# Cloud-init configuration
cloud_init:username: ubuntu                           # Cloud-init username
cloud_init:password: password                         # Cloud-init password
cloud_init:ssh_public_key: /path/to/id_rsa.pub        # SSH public key
cloud_init:ssh_private_key: /path/to/id_rsa           # SSH private key (for VM setup)
cloud_init:ssh_key_passphrase: passphrase             # SSH key passphrase (if any)

# VM user configuration
vm_user:create_admin_user: true                       # Create an admin user
vm_user:username: admin                               # Username for the admin user
vm_user:ssh_public_key: /path/to/id_rsa.pub           # SSH public key for the admin user
vm_user:ssh_private_key: /path/to/id_rsa              # SSH private key for the admin user
vm_user:ssh_key_passphrase: passphrase                # SSH key passphrase (if any)

# VM setup configuration
vm_setup:features:                                    # Features to enable (e.g., 'proxmox_agent')
  - proxmox_agent
vm_setup:scripts:                                     # Scripts to run on the VM
  - /path/to/script.sh
vm_setup:commands:                                    # Commands to run on the VM
  - apt-get update && apt-get install -y htop

# VM group configuration
vm_group:prefix: node                                 # Prefix for VM names
vm_group:count: 3                                     # Number of VMs to create
vm_group:vm_start_id: 900                             # Starting VM ID
vm_group:ip_range: 192.168.1.10-192.168.1.20          # IP range for VMs
vm_group:gateway: 192.168.1.1                         # Default gateway for VMs
```

## Usage Examples

### Basic VM Creation

```python
import pulumi
from pulumi_native_proxmox_dynamic import ProxmoxProvider, VM

# Create a provider instance
provider = ProxmoxProvider(
    endpoint="https://proxmox.example.com:8006/api2/json",
    username="root@pam",
    password="password",
    node="pve",
    insecure=True
)

# Create a VM
vm = VM(
    name="example-vm",
    template_id="9000",
    args={
        'endpoint': provider.endpoint,
        'username': provider.username,
        'password': provider.password,
        'node': provider.node,
        'insecure': provider.insecure,
        
        'cores': 2,
        'memory': 2048,
        'disk_size': "32G",
        'network_bridge': "vmbr0",
        'vlan_tag': 10,
        
        'cloud_init_user': "ubuntu",
        'cloud_init_ssh_public_key': "ssh-rsa AAAAB3...",
        
        'start_on_create': True,
        'wait_for_ssh': True,
    }
)

# Export the VM ID
pulumi.export("vmid", vm.vmid)
```

### Creating a VM Group

```python
import pulumi
from pulumi_native_proxmox_dynamic import ProxmoxProvider, VMGroup

# Create a provider instance
provider = ProxmoxProvider(...)

# Create a VM group
vm_group = VMGroup(
    name="k8s-master",
    template_id="9000",
    prefix="master",
    count=3,
    vm_start_id=800,
    ip_range="10.1.20.80-10.1.20.85",
    gateway="10.1.20.1",
    args={
        'endpoint': provider.endpoint,
        'username': provider.username,
        'password': provider.password,
        'node': provider.node,
        
        'cores': 2,
        'memory': 4096,
        'disk_size': "50G",
        'network_bridge': "vmbr0",
        'vlan_tag': 140,
        
        'cloud_init_user': "ubuntu",
        'cloud_init_ssh_public_key': "ssh-rsa AAAAB3...",
        
        'vm_user_create_admin_user': True,
        'vm_user_username': "k3s",
        'vm_user_ssh_public_key': "ssh-rsa AAAAB3...",
        
        'vm_setup_features': ["proxmox_agent"],
        'vm_setup_commands': [
            "apt-get update && apt-get install -y htop",
            "echo 'net.ipv4.ip_forward=1' | sudo tee -a /etc/sysctl.conf && sudo sysctl -p"
        ],
        
        'start_on_create': True,
        'wait_for_ssh': True,
    }
)

# Export the VM group IDs
vm_ids = []
for vm in vm_group.vms:
    vm_ids.append(vm.vmid)

pulumi.export("vm_ids", vm_ids)
```

### Creating a Complete Kubernetes Cluster

See the examples directory for a complete example of creating a Kubernetes cluster with master and worker nodes.

## Features

- Create VMs by cloning templates
- Configure VM resources (CPU, memory, disk, network)
- Start/stop VMs
- Install and configure Proxmox agent
- Create admin users with SSH keys
- Run custom commands and scripts during VM setup
- Create groups of VMs with sequential IDs and IP addresses
- Automatic IP address assignment
- Wait for VMs to be ready before marking as complete

## Limitations

- Works only with Python Pulumi programs
- Does not implement all Proxmox API features (focused on VM management)
- Requires SSH access to fully configure VMs

## Advanced Usage

### IP Ranges

The VMGroup supports several IP range formats:

- Range notation: `10.1.20.80-10.1.20.85`
- CIDR notation: `192.168.1.0/29`
- Comma-separated list: `10.1.20.80,10.1.20.81,10.1.20.82`
- Single IP (will be used for all VMs): `10.1.20.80`

### VM Setup

The provider can run setup commands on VMs after creating them. This requires SSH access to the VM, which can be configured using either password or SSH key authentication.

The setup process can:

1. Install the Proxmox guest agent
2. Create an admin user with sudo privileges
3. Configure SSH keys for the admin user
4. Run custom commands and scripts

### Cloud-Init

The provider uses cloud-init to initialize VMs. This requires a template with cloud-init properly configured. The provider can customize:

- Username and password
- SSH keys
- Network configuration

## Troubleshooting

### Common Issues

1. **"Connection refused" or "Connection timed out"**

   Check your Proxmox API endpoint and make sure it's accessible from your machine. You may need to set `insecure=True` if you're using a self-signed certificate.

2. **"Authentication failed"**

   Verify your credentials (username/password or token_id/token_secret). Make sure you're using the correct format for the username (e.g., `root@pam`).

3. **"Template not found"**

   Make sure the template ID you specified exists on your Proxmox server and is accessible by the user you're authenticating as.

### Getting Help

If you encounter issues not covered here, please open an issue on the GitHub repository with:

1. A description of the problem
2. The error message
3. The version of the provider you're using
4. Your Pulumi program code (with sensitive information removed)
5. The Pulumi command you're running 