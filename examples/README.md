# Pulumi Native Proxmox Provider Examples

This directory contains example Pulumi programs that demonstrate how to use the `pulumi_native_proxmox` provider. Each example is a standalone Pulumi project that can be deployed independently.

## Prerequisites

- [Pulumi CLI](https://www.pulumi.com/docs/get-started/install/)
- Python 3.12+
- [UV](https://github.com/astral-sh/uv) for Python dependency management
- A running Proxmox VE server
- A VM template in your Proxmox server that supports cloud-init

## Examples

### simple-vm

A basic example that demonstrates how to create a single VM in Proxmox using the provider.

```bash
cd simple-vm
pulumi stack init dev
# Copy configuration from root directory or set your own configuration
pulumi config set proxmox:endpoint https://your-proxmox-server:8006/api2/json
pulumi config set proxmox:username root@pam
pulumi config set --secret proxmox:password your-password
pulumi config set proxmox:node your-node-name
# Add more configuration as needed...
pulumi up
```

### vm-group

An advanced example that demonstrates how to create groups of VMs in Proxmox. This is useful for creating clusters or groups of related machines.

```bash
cd vm-group
pulumi stack init dev
# Copy configuration from root directory or set your own configuration
pulumi config set proxmox:endpoint https://your-proxmox-server:8006/api2/json
pulumi config set proxmox:username root@pam
pulumi config set --secret proxmox:password your-password
pulumi config set proxmox:node your-node-name
# Add more configuration as needed...
pulumi up
```

## Configuration

All examples can be configured using a `Pulumi.dev.yaml` file in the project root or via the Pulumi CLI. The configuration options are:

### Provider Configuration

- `proxmox:endpoint` - The Proxmox API endpoint URL
- `proxmox:username` - The username for authenticating with Proxmox (format: user@realm)
- `proxmox:password` - The password for authenticating with Proxmox (secret)
- `proxmox:node` - The Proxmox node name
- `proxmox:insecure` - Whether to skip TLS verification (boolean)

### VM Configuration

- `vm:template_id` - The ID of the template to clone
- `vm:cores` - The number of CPU cores
- `vm:memory` - The amount of memory in MB
- `vm:disk_size` - The disk size (e.g., "15G")
- `vm:network_bridge` - The network bridge to use
- `vm:disk_storage` - The storage ID for the disk
- `vm:vlan_tag` - The VLAN tag

### Cloud-init Configuration

- `cloud_init:username` - The username for cloud-init
- `cloud_init:ssh_public_key` - The SSH public key for cloud-init
- `cloud_init:ssh_private_key` - The SSH private key for cloud-init (secret)

### VM Group Configuration (for vm-group example)

- `master:count` - The number of master nodes
- `master:vm_start_id` - The starting VM ID for master nodes
- `master:ip_range` - The IP range for master nodes (format: start-end)
- `master:gateway` - The gateway for master nodes

- `worker:count` - The number of worker nodes
- `worker:vm_start_id` - The starting VM ID for worker nodes
- `worker:ip_range` - The IP range for worker nodes (format: start-end)
- `worker:gateway` - The gateway for worker nodes

## Using with Your Own Projects

To use this provider in your own Pulumi YAML projects, simply reference the provider resources in your Pulumi.yaml file:

```yaml
resources:
  # Create the provider instance
  provider:
    type: proxmox:index:Provider
    properties:
      endpoint: ${proxmox:endpoint}
      username: ${proxmox:username}
      password: ${proxmox:password}
      node: ${proxmox:node}
      insecure: ${proxmox:insecure}
  
  # Create a VM
  my-vm:
    type: proxmox:vm:VM
    properties:
      template_id: ${vm:template_id}
      cores: ${vm:cores}
      memory: ${vm:memory}
      # Additional properties...
```
