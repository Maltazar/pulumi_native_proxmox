#!/bin/bash

set -e

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Global variable for stack name
STACK_NAME=""

# Helper functions
print_header() {
    echo -e "\n${BLUE}$1${NC}"
    echo -e "${BLUE}$(printf '=%.0s' $(seq 1 ${#1}))${NC}\n"
}

print_success() {
    echo -e "${GREEN}$1${NC}"
}

print_warning() {
    echo -e "${YELLOW}$1${NC}"
}

print_error() {
    echo -e "${RED}$1${NC}"
}

# Check for required tools
check_dependencies() {
    if ! command -v pulumi &> /dev/null; then
        print_error "Pulumi CLI is not installed. Please install it first."
        exit 1
    fi

    if [ ! -f "Pulumi.yaml" ]; then
        print_error "Pulumi.yaml not found. Please run this script from the project root directory."
        exit 1
    fi
}

# Activate virtual environment if needed
ensure_virtualenv() {
    if [ -z "$VIRTUAL_ENV" ]; then
        if [ -d "../.venv" ]; then
            print_warning "Virtual environment is not activated. Activating now..."
            source "../.venv/bin/activate"
            print_success "Virtual environment activated."
        else
            print_error "No virtual environment found. Please create and activate it first."
            exit 1
        fi
    fi
}

# Handle stack selection or creation
manage_stacks() {
    print_header "Pulumi Stack Management"
    
    # Get available stacks
    local stacks=()
    local stack_list_output
    
    # Capture the full output of pulumi stack ls for debugging if needed
    stack_list_output=$(pulumi stack ls 2>/dev/null || echo "")
    
    # If debug output is needed, uncomment these lines
    # echo "Debug: Full 'pulumi stack ls' output:"
    # echo "$stack_list_output"
    # echo "------------------------------------"
    
    # Skip the header line and parse stack names correctly
    # The format is "NAME LAST UPDATE RESOURCE COUNT" with stack names like "dev*"
    while IFS= read -r line; do
        # Skip the header line
        if [[ "$line" =~ ^NAME ]]; then
            continue
        fi
        # Match stack names, handling the case where the asterisk is at the end of the name
        if [[ "$line" =~ ^([[:alnum:]/._-]+)\*? ]]; then
            stacks+=("${BASH_REMATCH[1]}")
            # Debug output
            # echo "Found stack: ${BASH_REMATCH[1]}"
        fi
    done <<< "$stack_list_output"
    
    # Display the number of stacks found for clarity
    if [ ${#stacks[@]} -gt 0 ]; then
        print_success "Found ${#stacks[@]} existing stack(s)"
    fi
    
    # If no stacks found, create a new one
    if [ ${#stacks[@]} -eq 0 ]; then
        print_warning "No stacks found."
        read -p "Enter a name for a new stack: " new_stack
        
        if [ -z "$new_stack" ]; then
            print_error "Stack name cannot be empty."
            exit 1
        fi
        
        print_warning "Creating new stack: $new_stack"
        # Let Pulumi handle its own prompting for passphrase
        pulumi stack init "$new_stack" --non-interactive=false
        if [ $? -ne 0 ]; then
            print_error "Failed to create stack. Please try again."
            exit 1
        fi
        print_success "Stack created successfully"
        
        STACK_NAME="$new_stack"
    else
        # Display available stacks
        echo "Available stacks:"
        for i in "${!stacks[@]}"; do
            echo "$((i+1)). ${stacks[$i]}"
        done
        
        echo "$((${#stacks[@]}+1)). Create a new stack"
        
        read -p "Select a stack (1-$((${#stacks[@]}+1))): " selection
        
        # Validate selection
        if ! [[ "$selection" =~ ^[0-9]+$ ]] || [ "$selection" -lt 1 ] || [ "$selection" -gt $((${#stacks[@]}+1)) ]; then
            print_error "Invalid selection. Please try again."
            exit 1
        fi
        
        # Create new stack if selected
        if [ "$selection" -eq $((${#stacks[@]}+1)) ]; then
            read -p "Enter a name for a new stack: " new_stack
            
            if [ -z "$new_stack" ]; then
                print_error "Stack name cannot be empty."
                exit 1
            fi
            
            print_warning "Creating new stack: $new_stack"
            # Let Pulumi handle its own prompting for passphrase
            pulumi stack init "$new_stack" --non-interactive=false
            if [ $? -ne 0 ]; then
                print_error "Failed to create stack. Please try again."
                exit 1
            fi
            print_success "Stack created successfully"
            
            STACK_NAME="$new_stack"
        else
            # Select existing stack
            local selected_stack="${stacks[$((selection-1))]}"
            print_warning "Selecting stack: $selected_stack"
            pulumi stack select "$selected_stack"
            STACK_NAME="$selected_stack"
        fi
    fi
}

# Dynamically read the Pulumi.yaml file and extract configuration keys
extract_config_keys() {
    local in_config=false
    local config_keys=()
    local is_secret=()
    
    # Uncomment for debugging
    # echo "DEBUG: Starting to parse Pulumi.yaml for configuration keys..."
    
    # Read Pulumi.yaml line by line
    while IFS= read -r line; do
        # Skip empty lines
        if [[ -z "$line" ]]; then
            continue
        fi
        
        # Start of config section
        if [[ "$line" == "config:"* ]]; then
            in_config=true
            # Uncomment for debugging
            # echo "DEBUG: Found config section"
            continue
        fi
        
        # Exit config section on unindented line that's not a comment
        if [[ "$in_config" == true && "$line" =~ ^[a-zA-Z] && ! "$line" =~ ^# ]]; then
            in_config=false
            # Uncomment for debugging
            # echo "DEBUG: Exiting config section"
            continue
        fi
        
        # Only process lines in config section
        if [[ "$in_config" == true ]]; then
            # Skip comment lines
            if [[ "$line" =~ ^[[:space:]]*# ]]; then
                continue
            fi
            
            # Match actual configuration keys (looking for format like "  proxmox:endpoint: string")
            # This pattern specifically looks for indented lines with section:key: format
            if [[ "$line" =~ ^[[:space:]]+([a-zA-Z0-9_]+:[a-zA-Z0-9_]+):[[:space:]]+(.*) ]]; then
                local key="${BASH_REMATCH[1]}"
                local value="${BASH_REMATCH[2]}"
                
                # Uncomment for debugging
                # echo "DEBUG: Found potential config key: $key"
                
                # Check if this key has "secret: true" property in the next lines
                local is_secret_value="false"
                
                # Automatically mark certain keys as secrets based on name
                if [[ "$key" =~ password|token|key|secret ]]; then
                    is_secret_value="true"
                else
                    # We'll check the next few lines directly from the file
                    local line_num=$(grep -n "^[[:space:]]\+$key:" Pulumi.yaml | head -1 | cut -d: -f1)
                    if [ -n "$line_num" ]; then
                        # Check the next 3 lines for a secret property
                        for i in $(seq 1 3); do
                            local check_line=$(sed -n "$((line_num + i))p" Pulumi.yaml 2>/dev/null)
                            if [[ "$check_line" =~ ^[[:space:]]+secret:[[:space:]]+true ]]; then
                                is_secret_value="true"
                                break
                            fi
                            # Break if we see a line that is another config key or less indented
                            if [[ "$check_line" =~ ^[[:space:]]+[a-zA-Z0-9_]+:[a-zA-Z0-9_]+: || "$check_line" =~ ^[a-zA-Z] ]]; then
                                break
                            fi
                        done
                    fi
                fi
                
                # Add the key to our arrays
                config_keys+=("$key")
                is_secret+=("$is_secret_value")
                
                # Uncomment for debugging
                # echo "DEBUG: Added config key: $key (Secret: $is_secret_value)"
            fi
        fi
    done < "Pulumi.yaml"
    
    # Check if we found any keys
    if [ ${#config_keys[@]} -eq 0 ]; then
        # Uncomment for debugging
        # echo "DEBUG: No configuration keys found in Pulumi.yaml"
        echo ""
        echo ""
        return
    fi
    
    # Output the extracted keys and secret status
    echo "${config_keys[@]}"
    echo "${is_secret[@]}"
}

# Configure the stack with dynamically extracted configuration keys
configure_stack() {
    local stack_name=$1
    print_header "Configuring Stack: $stack_name"
    
    print_warning "Reading configuration from Pulumi.yaml..."
    
    # Extract configuration keys (capture both outputs in one call)
    local config_output
    config_output=$(extract_config_keys)
    
    # Check if we got any output
    if [ -z "$config_output" ]; then
        print_error "No configuration keys found in Pulumi.yaml. Please check the format of your Pulumi.yaml file."
        print_warning "Your Pulumi.yaml should have a 'config:' section with entries like:"
        echo -e "config:"
        echo -e "  proxmox:endpoint: string"
        echo -e "  proxmox:username: string"
        echo -e "  proxmox:password: string"
        echo -e "  proxmox:token_id: string"
        return
    fi
    
    # Parse the output to get the keys and secrets status
    local config_keys_str=$(echo "$config_output" | head -1)
    local is_secret_str=$(echo "$config_output" | tail -1)
    
    # Convert space-separated strings to arrays
    IFS=' ' read -ra config_keys <<< "$config_keys_str"
    IFS=' ' read -ra is_secret <<< "$is_secret_str"
    
    # Check if we got any configuration keys
    if [ ${#config_keys[@]} -eq 0 ]; then
        print_error "No configuration keys found in Pulumi.yaml. Please check the format of your configuration section."
        return
    fi
    
    print_success "Found ${#config_keys[@]} configuration keys in Pulumi.yaml"
    
    # Get current config values
    declare -A current_values
    while IFS= read -r line; do
        if [[ $line =~ ^([a-zA-Z0-9_:]+)[[:space:]]+(.*)$ ]]; then
            key="${BASH_REMATCH[1]}"
            value="${BASH_REMATCH[2]}"
            
            # If it's a secret value
            if [[ "$value" == "[secret]" ]]; then
                current_values["$key"]="__ALREADY_SET_SECRET__"
            else
                current_values["$key"]="$value"
            fi
        fi
    done < <(pulumi config 2>/dev/null || echo "")
    
    # Ask if user wants to see all keys first
    read -p "Would you like to see all configuration keys before setting values? (y/N): " show_all
    if [[ "$show_all" =~ ^[Yy] ]]; then
        echo -e "\n${BLUE}Available Configuration Keys:${NC}"
        for i in "${!config_keys[@]}"; do
            local key="${config_keys[$i]}"
            local secret="${is_secret[$i]}"
            local secure_indicator=""
            if [ "$secret" = "true" ]; then
                secure_indicator=" ${RED}[SECRET]${NC}"
            fi
            echo -e "  - ${YELLOW}${key}${NC}${secure_indicator}"
        done
        echo
    fi
    
    # Process each configuration key
    for i in "${!config_keys[@]}"; do
        local key="${config_keys[$i]}"
        local secret="${is_secret[$i]}"
        
        # Force secrets for keys containing sensitive terms
        if [[ "$key" =~ password|token|key|secret ]]; then
            secret="true"
        fi
        
        local current_value="${current_values["$key"]}"
        
        # Format the key name nicely for display
        local key_display="${key}"
        if [ "$secret" = "true" ]; then
            key_display="${key} ${RED}[SECRET]${NC}"
        fi
        
        # Display the key name
        echo -e "\n${YELLOW}${key_display}${NC}"
        
        # Show current value if it exists
        local prompt_text=""
        if [ "$current_value" = "__ALREADY_SET_SECRET__" ]; then
            echo -e "${GREEN}Current value is set (secret)${NC}"
            prompt_text="Enter new value for ${key} (leave empty to keep current): "
        elif [ -n "$current_value" ]; then
            echo -e "Current value: ${GREEN}$current_value${NC}"
            prompt_text="Enter new value for ${key} (leave empty to keep current): "
        else
            prompt_text="Enter value for ${key}: "
        fi
        
        # Prompt for value
        local value=""
        
        if [ "$secret" = "true" ]; then
            read -s -p "$prompt_text" value
            echo # Add newline after secret input
        else
            read -p "$prompt_text" value
        fi
        
        # Skip if empty (use existing value)
        if [ -z "$value" ]; then
            if [ -n "$current_value" ]; then
                print_warning "Empty value provided, keeping current value..."
                continue
            else
                print_warning "Empty value provided, skipping..."
                continue
            fi
        fi
        
        # Set the value
        if [ "$secret" = "true" ]; then
            if pulumi config set --secret "$key" "$value"; then
                print_success "Secret value set for $key"
            else
                print_error "Failed to set secret value for $key"
            fi
        else
            if pulumi config set "$key" "$value"; then
                print_success "Value set for $key"
            else
                print_error "Failed to set value for $key"
            fi
        fi
    done
    
    print_success "Configuration completed for stack: $stack_name"
    
    # Show a summary of what's been set
    echo -e "\n${BLUE}Configuration Summary:${NC}"
    pulumi config
}

# Main function
main() {
    print_header "Pulumi Native Proxmox Configuration"
    
    # Check for required tools
    check_dependencies
    
    # Activate virtual environment if needed
    ensure_virtualenv
    
    # Let user know about passphrase requirement
    print_warning "Note: You may need to set the PULUMI_CONFIG_PASSPHRASE environment variable to create a new stack."
    print_warning "Example: export PULUMI_CONFIG_PASSPHRASE='your-secure-passphrase'"
    
    # Manage stacks (select or create) - Now uses global STACK_NAME variable
    manage_stacks
    
    if [ -z "$STACK_NAME" ]; then
        print_error "Failed to get stack name. Exiting."
        exit 1
    fi
    
    # Configure the selected stack with dynamically extracted keys
    configure_stack "$STACK_NAME"
    
    # Ask if user wants to run pulumi up
    print_header "Deployment"
    read -p "Do you want to run 'pulumi up' now? (y/N): " run_up
    
    if [[ "$run_up" =~ ^[Yy] ]]; then
        print_warning "Running 'pulumi up'..."
        pulumi up
    else
        print_warning "Skipping 'pulumi up'. You can run it manually later with 'pulumi up'."
    fi
    
    print_success "Configuration complete! Your stack is ready for use."
}

# Run the main function
main 