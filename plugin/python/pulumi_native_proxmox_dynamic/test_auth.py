#!/usr/bin/env python3
"""
Simple script to test authentication with Proxmox API.
"""

import requests
import urllib3
import sys
import getpass

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_auth(endpoint, username, password, insecure=True):
    """Test authentication with Proxmox API."""
    # Create session
    session = requests.Session()
    
    # Set up authentication URL
    auth_url = f"{endpoint.rstrip('/')}/access/ticket"
    print(f"Authentication URL: {auth_url}")
    print(f"Username: {username}")
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
    # Get authentication details
    endpoint = input("Proxmox API endpoint (e.g., https://10.1.1.230:8006/api2/json): ")
    username = input("Username (e.g., root@pam): ")
    password = getpass.getpass("Password: ")
    insecure = input("Skip SSL verification? (y/n): ").lower() == 'y'
    
    # Test authentication
    success = test_auth(endpoint, username, password, insecure)
    
    if success:
        print("\nAuthentication test PASSED")
        sys.exit(0)
    else:
        print("\nAuthentication test FAILED")
        sys.exit(1) 