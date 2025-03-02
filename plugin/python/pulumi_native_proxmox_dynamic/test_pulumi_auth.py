#!/usr/bin/env python3
"""
Script to test authentication with Proxmox API using values from Pulumi configuration.
"""

import requests
import urllib3
import json
import subprocess
import sys

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_pulumi_config():
    """Get Proxmox configuration from Pulumi."""
    try:
        # Get endpoint
        endpoint_cmd = subprocess.run(
            ["pulumi", "config", "get", "pulumi-native-proxmox-dynamic:endpoint"],
            capture_output=True, text=True, check=True
        )
        endpoint = endpoint_cmd.stdout.strip()
        
        # Get username
        username_cmd = subprocess.run(
            ["pulumi", "config", "get", "pulumi-native-proxmox-dynamic:username"],
            capture_output=True, text=True, check=True
        )
        username = username_cmd.stdout.strip()
        
        # Get password (this will prompt for the config passphrase)
        password_cmd = subprocess.run(
            ["pulumi", "config", "get", "--show-secrets", "pulumi-native-proxmox-dynamic:password"],
            capture_output=True, text=True
        )
        password = password_cmd.stdout.strip()
        
        # Get insecure setting
        insecure_cmd = subprocess.run(
            ["pulumi", "config", "get", "pulumi-native-proxmox-dynamic:insecure"],
            capture_output=True, text=True
        )
        insecure = insecure_cmd.stdout.strip().lower() == "true"
        
        return {
            "endpoint": endpoint,
            "username": username,
            "password": password,
            "insecure": insecure
        }
    except subprocess.CalledProcessError as e:
        print(f"Error getting Pulumi config: {e}")
        sys.exit(1)

def test_auth(endpoint, username, password, insecure=True):
    """Test authentication with Proxmox API."""
    # Create session
    session = requests.Session()
    
    # Set up authentication URL
    auth_url = f"{endpoint.rstrip('/')}/access/ticket"
    print(f"Authentication URL: {auth_url}")
    print(f"Username: {username}")
    print(f"Password length: {len(password)} characters")
    print(f"Insecure: {insecure}")
    
    try:
        # Authenticate
        response = session.post(
            auth_url,
            data={'username': username, 'password': password},
            verify=not insecure,
            timeout=30
        )
        
        print(f"Response status code: {response.status_code}")
        print(f"Response headers: {response.headers}")
        print(f"Response body: {response.text}")
        
        if response.status_code == 200:
            print("Authentication successful!")
            data = response.json().get('data')
            if data and 'ticket' in data and 'CSRFPreventionToken' in data:
                print("Got valid ticket and CSRF token")
                return True
            else:
                print("Response did not contain expected data")
                return False
        else:
            print(f"Authentication failed with status {response.status_code}")
            return False
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

if __name__ == "__main__":
    print("Getting Pulumi configuration...")
    config = get_pulumi_config()
    
    print("\nTesting authentication with Proxmox API...")
    success = test_auth(
        config["endpoint"],
        config["username"],
        config["password"],
        config["insecure"]
    )
    
    if success:
        print("\nAuthentication test PASSED")
        sys.exit(0)
    else:
        print("\nAuthentication test FAILED")
        sys.exit(1) 