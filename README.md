# Pulumi Native Proxmox Provider

A Pulumi Native Provider for Proxmox VE that allows you to create and manage VMs using Pulumi and Python.

## Features

- Create individual VMs in Proxmox
- Create groups of VMs with similar configuration
- Clone from VM templates
- Configure VM resources (CPU, memory, disk)
- Configure networking including VLAN tags
- Set up Cloud-Init for initial access
- Support for SSH key based authentication
- Install Proxmox agent on VMs
- Create admin users on VMs

## Installation

The project uses [UV](https://github.com/astral-sh/uv) for dependency management and virtual environments.

### Install UV

```bash
# Install UV if you don't have it already
curl -fsSL https://astral.sh/uv/install.sh | bash
```

### Local Development Setup

To develop and test this package locally:

```bash
# Clone the repository
git clone https://github.com/maltazar/pulumi_native_proxmox.git
cd pulumi_native_proxmox

# Install the provider
cd plugin/python
uv pip install -e .
cd ../..
```

## Configuration

The provider includes an interactive configuration script that helps you:

1. Create a new Pulumi stack
2. Configure all provider settings with sensible defaults
3. Set up VM resources, networking, and cloud-init settings

### Using the Configuration Script

```bash
# Run the configuration script from the project root
./configure.sh
```

This will guide you through setting up all necessary configuration parameters with helpful prompts and sensible defaults.

For detailed information about all configuration options, see [CONFIGURATION.md](CONFIGURATION.md).

## Examples

The `examples` directory contains ready-to-use Pulumi stacks:

- `simple-vm`: Deploy a single VM with custom settings
- `vm-group`: Deploy a group of VMs (e.g., for a Kubernetes cluster)

To use an example:

```bash
cd examples/simple-vm

# Create and configure a new stack
../../configure.sh

# Preview and deploy
pulumi preview
pulumi up
```

## Documentation

- [CONFIGURATION.md](CONFIGURATION.md) - Detailed configuration guide
- [Features.md](Features.md) - Complete feature list and roadmap
- [examples/README.md](examples/README.md) - Examples documentation

## License

This project is licensed under the [MIT License](LICENSE).
