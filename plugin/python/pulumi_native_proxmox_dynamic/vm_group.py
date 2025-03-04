"""
Proxmox VM Group Dynamic Resource.

This module defines a dynamic resource for groups of Proxmox VMs.
"""

import re
import ipaddress
import pulumi
from typing import Any, Dict, List, Optional, Union
import logging

from .vm import VM
from .provider import ProxmoxProvider

logger = logging.getLogger(__name__)


class VMGroup(pulumi.ComponentResource):
    """A component resource for creating groups of Proxmox VMs."""
    
    def __init__(self,
                 name: str,
                 template_id: str,
                 prefix: Optional[str] = None,
                 count: Optional[int] = None,
                 vm_start_id: Optional[Union[int, float, str]] = None,
                 ip_range: Optional[str] = None,
                 gateway: Optional[str] = None,
                 args: Optional[Dict[str, Any]] = None,
                 provider: Optional["ProxmoxProvider"] = None,
                 opts: Optional[pulumi.ResourceOptions] = None):
        """Create a new VM group.
        
        Args:
            name: The unique name for the VM group resource.
            template_id: The template ID to clone from.
            prefix: The prefix to use for VM names.
            count: The number of VMs to create.
            vm_start_id: The starting VM ID.
            ip_range: The IP range for the VMs (e.g., '10.1.20.80-10.1.20.85').
            gateway: The default gateway for the VMs.
            args: Additional arguments to configure the VMs.
            provider: The ProxmoxProvider to use for API access.
            opts: Resource options.
        """
        # Initialize the component resource
        super().__init__('proxmox:vm:VMGroup', name, {}, opts)
        
        # Make sure required parameters are provided
        if prefix is None:
            prefix = name
        
        if count is None:
            count = 1
        
        if args is None:
            args = {}
        
        # Parse the IP range if provided
        ip_addresses = []
        if ip_range:
            ip_addresses = self._parse_ip_range(ip_range, count)
        
        # Create the specified number of VMs
        self.vms = []
        for i in range(count):
            vm_name = f"{prefix}-{i+1}"
            
            # Configure VM-specific properties
            vm_props = args.copy()
            
            # Set VM name
            vm_props['name'] = vm_name
            
            # Set VM ID if a starting ID is provided
            if vm_start_id is not None:
                # Ensure vm_start_id is an integer
                vm_start_id = int(vm_start_id)
                vm_props['vmid'] = vm_start_id + i
            
            # Set IP address if available
            if i < len(ip_addresses):
                logger.info(f"Configuring static IP for VM {vm_name}")
                # Format the IP configuration in Proxmox cloud-init format
                # Default to /24 netmask if not specified in the IP
                ip = ip_addresses[i]
                if '/' not in ip:
                    ip = f"{ip}/24"
                logger.debug(f"Using IP address: {ip}")
                
                # Set ipconfig0 in Proxmox cloud-init format
                ipconfig = f"ip={ip}"
                if gateway:
                    ipconfig += f",gw={gateway}"
                logger.debug(f"Final ipconfig0 value: {ipconfig}")
                
                # Set using the correct property name expected by Proxmox
                vm_props['ipconfig0'] = ipconfig
            else:
                logger.warning(f"No IP address available for VM {vm_name}")
            
            logger.debug(f"Final VM properties for {vm_name}: {vm_props}")
            
            # Create the VM
            vm = VM(
                f"{name}-{vm_name}",
                template_id=template_id,
                args=vm_props,
                provider=provider,
                opts=pulumi.ResourceOptions(parent=self)
            )
            self.vms.append(vm)
        
        # Register outputs
        self.register_outputs({
            'vms': self.vms,
            'count': count,
            'prefix': prefix,
            'template_id': template_id,
            'vm_start_id': vm_start_id,
            'ip_range': ip_range,
            'gateway': gateway,
        })
    
    def _parse_ip_range(self, ip_range: str, count: int) -> List[str]:
        """Parse an IP range string into a list of IP addresses.
        
        Args:
            ip_range: The IP range string (e.g., '10.1.20.80-10.1.20.85').
            count: The number of IPs to generate.
            
        Returns:
            A list of IP addresses.
        """
        # Check for CIDR notation (e.g., 192.168.1.0/24)
        if '/' in ip_range:
            network = ipaddress.ip_network(ip_range, strict=False)
            hosts = list(network.hosts())
            return [str(ip) for ip in hosts[:count]]
        
        # Check for range notation (e.g., 10.1.20.80-10.1.20.85)
        if '-' in ip_range:
            start, end = ip_range.split('-')
            start_ip = ipaddress.ip_address(start.strip())
            end_ip = ipaddress.ip_address(end.strip())
            
            # Generate IPs in the range
            ips = []
            current_ip = start_ip
            while len(ips) < count and current_ip <= end_ip:
                ips.append(str(current_ip))
                current_ip = ipaddress.ip_address(int(current_ip) + 1)
            
            return ips
        
        # Check for comma-separated list (e.g., 10.1.20.80, 10.1.20.81, 10.1.20.82)
        if ',' in ip_range:
            ips = [ip.strip() for ip in ip_range.split(',')]
            return ips[:count]
        
        # Single IP
        return [ip_range] * count 