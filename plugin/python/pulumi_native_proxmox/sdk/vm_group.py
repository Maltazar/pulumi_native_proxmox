"""Proxmox VM Group Resource

This module defines the VMGroup class for managing groups of Proxmox VMs.
"""

import pulumi
from typing import Dict, List, Optional, Any

from .vm import VM


class VMGroup(pulumi.ComponentResource):
    """A component resource for managing a group of Proxmox VMs."""
    
    def __init__(
        self,
        name: str,
        args: Dict[str, Any],
        opts: Optional[pulumi.ResourceOptions] = None
    ):
        """Create a new VM Group resource.
        
        Args:
            name: The unique name for the VM Group.
            args: The arguments to configure the VM Group.
            opts: Options for the VM Group.
        """
        super().__init__('proxmox:vm:VMGroup', name, {}, opts)
        
        # Set defaults
        args_with_defaults = {
            # Required
            'prefix': name,              # Prefix for VM names
            'count': 1,                  # Number of VMs to create
            'vm_start_id': 100,          # Starting VM ID
            
            # VM properties - passed to each VM
            'template_id': None,         # Template ID to clone from
            'cores': 1,                  # Number of CPU cores
            'sockets': 1,                # Number of CPU sockets
            'memory': 512,               # Memory in MB
            'disk_size': None,           # Disk size (e.g., '10G')
            'disk_storage': None,        # Storage ID for the disk
            'network_bridge': 'vmbr0',   # Network bridge
            'vlan_tag': None,            # VLAN tag (if any)
            'ip_range': 'dhcp',          # IP range (either 'dhcp' or a range like '10.0.0.10-10.0.0.20')
            'gateway': None,             # Gateway for static IPs
            'start_on_create': True,     # Start VMs after creation
            'wait_for_ssh': False,       # Wait for SSH to be available
            
            # Cloud-init
            'cloud_init_user': None,     # Cloud-init username
            'cloud_init_password': None, # Cloud-init password
            'cloud_init_ssh_key': None,  # Cloud-init SSH key
            
            # Post-provisioning
            'commands': [],              # Commands to run after VM is up
            'files': [],                 # Files to copy to the VM
        }
        
        # Update with user-provided args
        for k, v in args.items():
            args_with_defaults[k] = v
        
        # Validate required args
        if not args_with_defaults['template_id']:
            raise ValueError("template_id is required")
            
        # Parse IP range if not 'dhcp'
        ip_addresses = []
        if args_with_defaults['ip_range'] != 'dhcp':
            try:
                ip_addresses = self._parse_ip_range(args_with_defaults['ip_range'])
                
                # Make sure we have enough IPs
                if len(ip_addresses) < args_with_defaults['count']:
                    raise ValueError(f"IP range contains {len(ip_addresses)} addresses, but {args_with_defaults['count']} VMs requested")
            except Exception as e:
                raise ValueError(f"Invalid IP range: {e}")
        
        # Create VMs
        self.vms = []
        vm_start_id = args_with_defaults['vm_start_id']
        
        for i in range(args_with_defaults['count']):
            vm_name = f"{args_with_defaults['prefix']}-{i+1}"
            vm_id = vm_start_id + i
            
            # Build VM args
            vm_args = {
                'vmid': vm_id,
                'template_id': args_with_defaults['template_id'],
                'cores': args_with_defaults['cores'],
                'sockets': args_with_defaults['sockets'],
                'memory': args_with_defaults['memory'],
                'disk_size': args_with_defaults['disk_size'],
                'disk_storage': args_with_defaults['disk_storage'],
                'network_bridge': args_with_defaults['network_bridge'],
                'vlan_tag': args_with_defaults['vlan_tag'],
                'start_on_create': args_with_defaults['start_on_create'],
                'wait_for_ssh': args_with_defaults['wait_for_ssh'],
                'cloud_init_user': args_with_defaults['cloud_init_user'],
                'cloud_init_password': args_with_defaults['cloud_init_password'],
                'cloud_init_ssh_key': args_with_defaults['cloud_init_ssh_key'],
                'commands': args_with_defaults['commands'],
                'files': args_with_defaults['files'],
            }
            
            # Set static IP if provided
            if args_with_defaults['ip_range'] != 'dhcp' and i < len(ip_addresses):
                vm_args['ip_config'] = {
                    'ip': f"{ip_addresses[i]}/24",  # Assuming /24 subnet
                    'gateway': args_with_defaults['gateway']
                }
            
            # Create VM resource
            vm = VM(
                vm_name,
                vm_args,
                pulumi.ResourceOptions(parent=self)
            )
            
            self.vms.append(vm)
        
        # Register outputs
        self.register_outputs({
            'vms': self.vms,
            'count': args_with_defaults['count'],
            'prefix': args_with_defaults['prefix'],
            'vm_ids': [vm.id for vm in self.vms],
            'ip_addresses': [vm.ip_address for vm in self.vms]
        })
    
    def _parse_ip_range(self, ip_range: str) -> List[str]:
        """Parse an IP range into a list of IP addresses.
        
        Args:
            ip_range: IP range in format 'start-end' (e.g., '10.0.0.10-10.0.0.20')
            
        Returns:
            List of IP addresses
        """
        if '-' not in ip_range:
            return [ip_range]  # Single IP
            
        start, end = ip_range.split('-')
        
        # Parse start IP
        start_parts = [int(p) for p in start.split('.')]
        if len(start_parts) != 4:
            raise ValueError(f"Invalid IP format: {start}")
            
        # Parse end IP
        end_parts = [int(p) for p in end.split('.')]
        if len(end_parts) != 4:
            raise ValueError(f"Invalid IP format: {end}")
            
        # Validate IPs are in the same subnet
        if start_parts[:3] != end_parts[:3]:
            raise ValueError(f"Start and end IPs must be in the same /24 subnet")
            
        # Generate IPs
        ips = []
        for i in range(start_parts[3], end_parts[3] + 1):
            ips.append(f"{start_parts[0]}.{start_parts[1]}.{start_parts[2]}.{i}")
            
        return ips 