#!/bin/bash
set -e

# Colors for better readability
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to display section header
section() {
    echo -e "\n${BLUE}===${NC} ${CYAN}$1${NC} ${BLUE}===${NC}"
}

# Function to prompt for a value with a default
prompt() {
    local key=$1
    local description=$2
    local default=$3
    local secret=$4
    
    if [ -n "$default" ]; then
        echo -e "${YELLOW}$description${NC} ${GREEN}[$default]${NC}"
    else
        echo -e "${YELLOW}$description${NC}"
    fi
    
    read -p "> " value
    
    # Use default if no value provided
    if [ -z "$value" ] && [ -n "$default" ]; then
        value=$default
    fi
    
    # Skip if still empty
    if [ -z "$value" ]; then
        echo -e "${MAGENTA}Skipping $key${NC}"
        return
    fi
    
    # Set the config value
    if [ "$secret" = "true" ]; then
        pulumi config set --secret "$key" "$value"
        echo -e "${GREEN}Set secret value for${NC} ${CYAN}$key${NC}"
    else
        pulumi config set "$key" "$value"
        echo -e "${GREEN}Set${NC} ${CYAN}$key${NC} ${GREEN}to${NC} ${YELLOW}$value${NC}"
    fi
}

# Check if Pulumi is installed
if ! command -v pulumi &> /dev/null; then
    echo -e "${RED}Error: Pulumi CLI is not installed. Please install it first.${NC}"
    echo "Visit https://www.pulumi.com/docs/get-started/install/ for installation instructions."
    exit 1
fi

# Check if UV is installed
if ! command -v uv &> /dev/null; then
    echo -e "${RED}Error: UV is not installed. Please install it first.${NC}"
    echo "Visit https://github.com/astral-sh/uv for installation instructions."
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "Pulumi.yaml" ]; then
    echo -e "${RED}Error: Pulumi.yaml not found. Please run this script from the project root.${NC}"
    exit 1
fi

# Welcome message
echo -e "${GREEN}==================================================${NC}"
echo -e "${BLUE}   Pulumi Native Proxmox Provider Configuration   ${NC}"
echo -e "${GREEN}==================================================${NC}"
echo -e "\nThis script will help you set up the configuration for your Pulumi Proxmox provider."
echo -e "You can press Enter to use default values or leave empty to skip.\n"

# Prompt for stack name
echo -e "${YELLOW}Enter a name for your new Pulumi stack:${NC}"
read -p "> " stack_name

if [ -z "$stack_name" ]; then
    stack_name="dev"
    echo -e "${MAGENTA}Using default stack name: ${NC}${CYAN}$stack_name${NC}"
fi

# Create a new stack
echo -e "\n${BLUE}Creating new stack: ${CYAN}$stack_name${NC}"
pulumi stack init "$stack_name" || {
    echo -e "${RED}Failed to create stack. Does it already exist?${NC}"
    echo -e "${YELLOW}If you want to use an existing stack, select it with: ${NC}${CYAN}pulumi stack select $stack_name${NC}"
    read -p "Do you want to select this stack instead? (y/n) " select_stack
    if [[ $select_stack == "y" || $select_stack == "Y" ]]; then
        pulumi stack select "$stack_name" || {
            echo -e "${RED}Failed to select stack.${NC}"
            exit 1
        }
    else
        exit 1
    fi
}

# Provider Configuration
section "Provider Configuration"
prompt "proxmox:endpoint" "Proxmox API endpoint URL" "https://proxmox.example.com:8006/api2/json"
prompt "proxmox:username" "Username for Proxmox API (format: user@realm)" "root@pam"
prompt "proxmox:password" "Password for Proxmox API" "" "true"

echo -e "\n${YELLOW}Do you want to use API tokens instead of username/password? (y/n)${NC}"
read -p "> " use_token
if [[ $use_token == "y" || $use_token == "Y" ]]; then
    prompt "proxmox:token_id" "API token ID" ""
    prompt "proxmox:token_secret" "API token secret" "" "true"
fi

prompt "proxmox:node" "Default Proxmox node to use" "pve"
prompt "proxmox:insecure" "Skip TLS verification (true/false)" "false"
prompt "proxmox:timeout" "API timeout in seconds" "30"
prompt "proxmox:debug" "Enable debug logging (true/false)" "false"

# VM Configuration
section "VM Configuration"
prompt "vm:template_id" "ID of the template to clone" ""
prompt "vm:cores" "Number of CPU cores" "2"
prompt "vm:sockets" "Number of CPU sockets" "1"
prompt "vm:memory" "Memory in MB" "4096"
prompt "vm:disk_size" "Disk size (e.g., '10G')" "15G"
prompt "vm:disk_storage" "Storage ID for the disk" "local-lvm"
prompt "vm:network_bridge" "Network bridge to use" "vmbr0"
prompt "vm:vlan_tag" "VLAN tag for the VM" ""
prompt "vm:start_on_create" "Start VM after creation (true/false)" "true"
prompt "vm:wait_for_ssh" "Wait for SSH to be available (true/false)" "false"

# Cloud-init Configuration
section "Cloud-init Configuration"
prompt "cloud_init:username" "Username for cloud-init" "admin"
prompt "cloud_init:password" "Password for cloud-init user" "" "true"
prompt "cloud_init:ssh_public_key" "Path to SSH public key for cloud-init" "~/.ssh/id_rsa.pub"
prompt "cloud_init:ssh_private_key" "Path to SSH private key for cloud-init" "~/.ssh/id_rsa" "true"
prompt "cloud_init:ssh_key_passphrase" "Passphrase for SSH private key (if protected)" "" "true"

# Ask if creating VM groups
echo -e "\n${YELLOW}Do you want to configure VM groups? (y/n)${NC}"
read -p "> " configure_groups
if [[ $configure_groups == "y" || $configure_groups == "Y" ]]; then
    # VM Group Configuration for Master nodes
    section "Master Nodes Group Configuration"
    prompt "master:count" "Number of master nodes to create" "3"
    prompt "master:vm_start_id" "Starting VM ID for master nodes" "800"
    prompt "master:ip_range" "IP range for master nodes (format: start-end)" "10.0.0.10-10.0.0.12"
    prompt "master:gateway" "Gateway for master nodes" "10.0.0.1"
    
    # VM Group Configuration for Worker nodes
    section "Worker Nodes Group Configuration"
    prompt "worker:count" "Number of worker nodes to create" "3"
    prompt "worker:vm_start_id" "Starting VM ID for worker nodes" "810"
    prompt "worker:ip_range" "IP range for worker nodes (format: start-end)" "10.0.0.20-10.0.0.22"
    prompt "worker:gateway" "Gateway for worker nodes" "10.0.0.1"
fi

# Post-provisioning Configuration
section "Post-provisioning Configuration"
echo -e "\n${YELLOW}Do you want to configure post-provisioning commands? (y/n)${NC}"
read -p "> " configure_commands
if [[ $configure_commands == "y" || $configure_commands == "Y" ]]; then
    echo -e "${YELLOW}Enter commands to run after VM is up (one per line, empty line to finish):${NC}"
    commands=()
    while true; do
        read -p "> " command
        if [ -z "$command" ]; then
            break
        fi
        commands+=("$command")
    done
    
    if [ ${#commands[@]} -gt 0 ]; then
        # Convert the array to a JSON array
        json_commands="["
        for i in "${!commands[@]}"; do
            if [ $i -gt 0 ]; then
                json_commands+=","
            fi
            json_commands+="\"${commands[$i]}\""
        done
        json_commands+="]"
        
        pulumi config set postprovision:commands "$json_commands"
        echo -e "${GREEN}Set${NC} ${CYAN}postprovision:commands${NC}"
    fi
fi

# Finish
section "Configuration Complete"
echo -e "${GREEN}Configuration has been saved to your Pulumi stack: ${CYAN}$stack_name${NC}"
echo -e "\nYou can now run:${NC}"
echo -e "  ${CYAN}pulumi preview${NC}   - to see what would be created"
echo -e "  ${CYAN}pulumi up${NC}        - to create resources"
echo -e "\n${YELLOW}Note: For package installation, use:${NC}"
echo -e "  ${CYAN}cd plugin/python && uv pip install -e .${NC}"
echo -e "  ${GREEN}rather than pip install -e .${NC}"

echo -e "\n${BLUE}Happy infrastructure building!${NC}" 