#!/usr/bin/env python3
"""
Cleanup script to delete VMs from Proxmox.
This script is useful for cleaning up VMs after failed Pulumi operations.
"""

import time
import sys
import getpass
from proxmox_client import ProxmoxClient

# Replace with your actual credentials
PROXMOX_URL = 'https://10.1.1.230:8006/api2/json'
USERNAME = 'root@pam'
PASSWORD = getpass.getpass("Password: ")
NODE = 'pvehost'
INSECURE = True  # Set to False in production environments

# VM IDs to delete
VM_IDS = [800, 801, 802]

def main():
    print(f"Connecting to Proxmox at {PROXMOX_URL}...")
    client = ProxmoxClient(PROXMOX_URL, USERNAME, PASSWORD, insecure=INSECURE)
    
    for vmid in VM_IDS:
        try:
            # Check if VM exists
            print(f"Checking VM {vmid}...")
            try:
                vm_status = client.request('GET', f'/nodes/{NODE}/qemu/{vmid}/status/current')
                vm_exists = True
            except Exception as e:
                if "not found" in str(e).lower():
                    print(f"VM {vmid} does not exist, skipping.")
                    vm_exists = False
                else:
                    raise
            
            if vm_exists:
                # Stop VM if running
                vm_status = vm_status.get('data', {}).get('status')
                if vm_status == 'running':
                    print(f"Stopping VM {vmid}...")
                    client.request('POST', f'/nodes/{NODE}/qemu/{vmid}/status/stop')
                    
                    # Wait for VM to stop (with timeout)
                    max_wait = 30  # seconds
                    start_time = time.time()
                    while True:
                        try:
                            current_status = client.request('GET', f'/nodes/{NODE}/qemu/{vmid}/status/current')
                            current_status = current_status.get('data', {}).get('status')
                            if current_status != 'running':
                                print(f"VM {vmid} stopped successfully.")
                                break
                        except Exception:
                            # If we can't get status, assume VM is gone
                            break
                            
                        if time.time() - start_time > max_wait:
                            print(f"Timeout waiting for VM {vmid} to stop. Proceeding with deletion...")
                            break
                            
                        print(f"Waiting for VM {vmid} to stop...")
                        time.sleep(2)
                
                # Delete VM
                print(f"Deleting VM {vmid}...")
                try:
                    client.request('DELETE', f'/nodes/{NODE}/qemu/{vmid}')
                    print(f"VM {vmid} deleted successfully.")
                except Exception as e:
                    print(f"Error deleting VM {vmid}: {e}")
        except Exception as e:
            print(f"Error processing VM {vmid}: {e}")
    
    print("Cleanup completed.")

if __name__ == "__main__":
    main() 