#!/bin/bash
set -e

# Setup script for installing the Pulumi Proxmox Dynamic Provider
echo "Setting up the Pulumi Proxmox Dynamic Provider..."

# Check if UV is installed
if ! command -v uv &> /dev/null; then
    echo "UV not found, installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Create a virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    uv venv
    uv sync
fi

# Install dependencies
echo "Installing dependencies..."
uv pip install -e ".[dynamic]"

echo "Installation complete!"
echo "You can now use the dynamic provider in two ways:"
echo ""
echo "1. As a standalone Pulumi project (run directly from the package directory):"
echo ""
echo "  cd pulumi_native_proxmox_dynamic"
echo "  pulumi stack init dev      # First time only"
echo "  pulumi config set ... # Configure as needed"
echo "  pulumi up"
echo ""
echo "2. As an imported package in your own Pulumi Python program:"
echo ""
echo "  from pulumi_native_proxmox_dynamic import ProxmoxProvider, VM, VMGroup"
echo ""
echo "Example projects are available in the examples directory:"
echo "  cd examples/simple_vm"
echo "  # OR"
echo "  cd examples/cluster_setup" 