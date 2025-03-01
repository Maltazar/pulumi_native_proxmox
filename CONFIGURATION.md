# Pulumi Native Proxmox Provider Configuration

This document explains how to configure and use the Pulumi Native Proxmox Provider.

## Prerequisites

Before you begin, make sure you have:

1. [Pulumi CLI](https://www.pulumi.com/docs/get-started/install/) installed
2. [UV](https://github.com/astral-sh/uv) installed for Python dependency management
3. Access to a Proxmox VE server
4. A VM template that supports cloud-init

## Installation

To install the provider, run:

```bash
# Navigate to the plugin directory
cd plugin/python

# Install with UV in development mode
uv pip install -e .

# Return to the project root
cd ../..
```

## Configuration

The provider includes a configuration script to help you set up your Pulumi stack. The script will:

1. Create a new Pulumi stack
2. Prompt you for configuration values with sensible defaults
3. Save these values to your Pulumi stack configuration

### Running the Configuration Script

From the project root directory, run:

```bash
./configure.sh
```

The script will guide you through the configuration process with colorful prompts.

### Configuration Categories

The script will walk you through several configuration categories:

1. **Provider Configuration**: Proxmox API endpoint, credentials, and connection settings
2. **VM Configuration**: Default settings for VMs including CPU, memory, disk, and network
3. **Cloud-init Configuration**: User accounts and SSH keys for VM initialization
4. **VM Group Configuration** (optional): Settings for creating groups of VMs
5. **Post-provisioning Configuration** (optional): Commands to run after VM creation

### Key Configuration Parameters

#### Provider Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `proxmox:endpoint` | Proxmox API endpoint URL | https://proxmox.example.com:8006/api2/json |
| `proxmox:username` | Username for Proxmox API | root@pam |
| `proxmox:password` | Password for Proxmox API (secret) | - |
| `proxmox:token_id` | API token ID (alternative to username/password) | - |
| `proxmox:token_secret` | API token secret (alternative to username/password) | - |
| `proxmox:node` | Default Proxmox node | pve |
| `proxmox:insecure` | Skip TLS verification | false |
| `proxmox:timeout` | API timeout in seconds | 30 |
| `proxmox:debug` | Enable debug logging | false |

#### VM Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `vm:template_id` | ID of the template to clone | - |
| `vm:cores` | Number of CPU cores | 2 |
| `vm:sockets` | Number of CPU sockets | 1 |
| `vm:memory` | Memory in MB | 4096 |
| `vm:disk_size` | Disk size | 15G |
| `vm:disk_storage` | Storage ID for the disk | local-lvm |
| `vm:network_bridge` | Network bridge to use | vmbr0 |
| `vm:vlan_tag` | VLAN tag for the VM | - |
| `vm:start_on_create` | Start VM after creation | true |
| `vm:wait_for_ssh` | Wait for SSH to be available | false |

#### Cloud-init Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `cloud_init:username` | Username for cloud-init | admin |
| `cloud_init:password` | Password for cloud-init user (secret) | - |
| `cloud_init:ssh_public_key` | Path to SSH public key | ~/.ssh/id_rsa.pub |
| `cloud_init:ssh_private_key` | Path to SSH private key (secret) | ~/.ssh/id_rsa |
| `cloud_init:ssh_key_passphrase` | Passphrase for SSH private key (secret) | - |

## Using Default Values

For many parameters, the script provides sensible defaults. You can accept these defaults by simply pressing Enter at the prompt.

## Skipping Optional Parameters

For optional parameters, you can leave the value empty to skip setting that parameter.

## After Configuration

Once you've completed configuration, you can:

1. Preview your deployment: `pulumi preview`
2. Deploy your infrastructure: `pulumi up`
3. Destroy resources when finished: `pulumi destroy`

## Manual Configuration

If you prefer to configure Pulumi manually, you can set configuration values directly using the Pulumi CLI:

```bash
# Create a new stack
pulumi stack init dev

# Set configuration values
pulumi config set proxmox:endpoint https://your-proxmox-server:8006/api2/json
pulumi config set proxmox:username root@pam
pulumi config set --secret proxmox:password your-password
# ... and so on for other configuration values
```

## Configuration Structure

The configuration parameters are structured hierarchically with namespaces:

- `proxmox:*` - Provider configuration 
- `vm:*` - VM configuration
- `cloud_init:*` - Cloud-init configuration
- `master:*` - Master node group configuration
- `worker:*` - Worker node group configuration
- `postprovision:*` - Post-provisioning configuration

## Examples

Check the `examples` directory for sample Pulumi programs using this provider:

- `simple-vm` - Deploy a single VM
- `vm-group` - Deploy a group of VMs (e.g., for a Kubernetes cluster)

## Troubleshooting

If you encounter issues with the configuration:

1. Check for typos in parameter names or values
2. Verify your Proxmox credentials and API endpoint
3. Ensure your VM template exists and is properly configured for cloud-init
4. Check Pulumi logs with `pulumi logs`
5. Enable debug logging with `pulumi config set proxmox:debug true` 