# Pulumi Native Proxmox Provider

This package provides a Pulumi provider for Proxmox VE that allows you to create and manage VMs using Pulumi.

## Provider Options

This repository offers two provider implementations:

### 1. Dynamic Provider (Recommended for Python Programs)

The dynamic provider is implemented directly in Python using Pulumi's Dynamic Providers mechanism. It's simpler to use, doesn't require a separate plugin installation, and can be used directly in your Python Pulumi programs.

Located in: `pulumi_native_proxmox_dynamic`

You can use it in two ways:
- **As a standalone Pulumi project**: Run Pulumi commands directly from the package directory
- **As an imported package**: Import it in your own Pulumi Python programs

### 2. Full Provider (Under Development)

The full provider is implemented as a gRPC service that follows the Pulumi provider plugin protocol. It's more complex but can be used from any programming language that Pulumi supports.

Located in: `pulumi_native_proxmox`

## Quick Start (Dynamic Provider)

```bash
# Clone the repository
git clone https://github.com/maltazar/pulumi_native_proxmox.git
cd pulumi_native_proxmox/plugin/python

# Run the setup script
./setup.sh
```

### Option 1: Run as a Standalone Project

```bash
# Navigate to the package directory
cd pulumi_native_proxmox_dynamic

# Initialize a stack (first time only)
pulumi stack init dev

# Configure your provider
pulumi config set endpoint https://your-proxmox-server:8006/api2/json
pulumi config set username root@pam
pulumi config set password --secret your-password
pulumi config set node your-node
pulumi config set template_id your-template-id

# Deploy resources
pulumi up
```

### Option 2: Use in Your Own Pulumi Project

```bash
# Navigate to one of the example directories
cd examples/simple_vm
# OR
cd examples/cluster_setup

# Initialize a stack (first time only)
pulumi stack init dev

# Configure your provider 
pulumi config set --path 'proxmox-dynamic-provider-example:endpoint' 'https://your-proxmox-server:8006/api2/json'
pulumi config set --path 'proxmox-dynamic-provider-example:username' 'root@pam'
pulumi config set --path 'proxmox-dynamic-provider-example:password' --secret 'your-password'
pulumi config set --path 'proxmox-dynamic-provider-example:node' 'your-node'
pulumi config set --path 'proxmox-dynamic-provider-example:template_id' 'your-template-id'

# Deploy resources
pulumi up
```

## Features

Both providers support:

- Creating VMs by cloning templates
- Configuring VM resources (CPU, memory, disk, network)
- Starting/stopping VMs
- Installing and configuring Proxmox agent
- Creating admin users with SSH keys
- Running custom commands and scripts during VM setup
- Creating groups of VMs with sequential IDs and IP addresses

## Configuration

See the example Pulumi.yaml files in the examples directory for configuration options.

## Requirements

- Python 3.12+
- Proxmox VE 8+
- Pulumi 3+
- UV (recommended for package management)

## Documentation

See the README.md files in each provider directory for detailed documentation:

- [Dynamic Provider Documentation](./pulumi_native_proxmox_dynamic/README.md)
- [Full Provider Documentation](./pulumi_native_proxmox/README.md)

## Example Projects

The repository includes two example projects:

1. **Simple VM Example** (`examples/simple_vm`): Creates a single VM and optionally a group of VMs with basic configuration.

2. **Cluster Setup Example** (`examples/cluster_setup`): Creates a Kubernetes cluster with separate node groups for master and worker nodes, each with their own configuration settings.

To run an example:

```bash
cd examples/simple_vm  # or examples/cluster_setup
pulumi stack init dev
# Configure settings in Pulumi.dev.yaml or via command line
pulumi up
```