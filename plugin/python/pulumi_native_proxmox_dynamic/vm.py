"""
Proxmox VM Dynamic Resource.

This module defines a dynamic resource for Proxmox VMs.
"""

import json
import time
import pulumi
import pulumi.dynamic
import paramiko
import os
import base64
from typing import Any, Dict, List, Optional, Union, Tuple, Callable
import logging
import urllib.parse
import io
import socket

from .proxmox_client import ProxmoxClient
from .provider import ProxmoxProvider

# Configure module logger
logger = logging.getLogger(__name__)

class VMProvider(pulumi.dynamic.ResourceProvider):
    """Dynamic resource provider for Proxmox VMs."""
    
    def create(self, props: Dict[str, Any]) -> pulumi.dynamic.CreateResult:
        """Create a new VM in Proxmox by cloning a template.
        
        Args:
            props: Resource properties
            
        Returns:
            CreateResult with VM properties
        """
        client = self._get_client(props)
        
        # Extract properties with defaults
        node = props.get('node') or client.node
        if not node:
            raise Exception("Node is required")
            
        template_id = props.get('template_id')
        if not template_id:
            raise Exception("Template ID is required")
        
        # Generate VM ID if not provided
        vmid = props.get('vmid')
        if not vmid:
            # Get the next available VM ID
            next_id = self._get_next_vmid(client)
            vmid = next_id
        else:
            # Ensure vmid is an integer
            vmid = int(vmid)
        
        # Clone the template
        self._clone_template(client, node, template_id, vmid, props)
        
        # Build initial configuration
        config = {}
        
        # Network configuration (ipconfig0)
        if 'ipconfig0' in props:
            logger.info(f"Setting static IP configuration for VM {vmid}")
            config['ipconfig0'] = props['ipconfig0']
            logger.debug(f"IP configuration: {props['ipconfig0']}")
        
        # Apply initial configuration if any
        if config:
            logger.info(f"Applying initial configuration to VM {vmid}")
            try:
                response = client.request(
                    'POST',
                    f'/nodes/{node}/qemu/{vmid}/config',
                    data=config
                )
                logger.debug(f"Initial configuration response: {response}")
                
                # Wait for configuration to be applied
                if isinstance(response, dict) and response.get('data'):
                    task_id = response['data']
                    logger.debug(f"Waiting for initial configuration task: {task_id}")
                    self._wait_for_specific_task(client, node, task_id)
            except Exception as e:
                raise Exception(f"Failed to apply initial configuration: {str(e)}")
        
        # Configure remaining VM settings
        self._configure_vm(client, node, vmid, props)
        
        # Start VM if requested - handle string or boolean value
        start_on_create = props.get('start_on_create')
        should_start = True  # default value
        if isinstance(start_on_create, str):
            should_start = start_on_create.lower() == 'true'
        elif isinstance(start_on_create, bool):
            should_start = start_on_create
            
        logger.debug(f"Start on create: {should_start} (raw value: {start_on_create})")
        
        if should_start:
            logger.debug(f"Starting VM {vmid}")
            self._start_vm(client, node, vmid)
            
            # Wait for VM to be ready if requested - handle string or boolean value
            wait_for_ssh = props.get('wait_for_ssh')
            should_wait = False  # default value
            if isinstance(wait_for_ssh, str):
                should_wait = wait_for_ssh.lower() == 'true'
            elif isinstance(wait_for_ssh, bool):
                should_wait = wait_for_ssh
                
            logger.debug(f"Wait for SSH: {should_wait} (raw value: {wait_for_ssh})")
            
            if should_wait:
                logger.debug(f"Waiting for IP address for VM {vmid}")
                ip_address = self._wait_for_ip_address(client, node, vmid)
                
                # Setup VM if cloud_init data is provided
                if any(k.startswith('cloud_init_') for k in props) or any(k.startswith('vm_user_') for k in props):
                    self._setup_vm(client, node, vmid, ip_address, props)
        
        # Return the resource ID and outputs
        outputs = {**props}
        
        # Add VM information to outputs
        outputs['vmid'] = vmid
        outputs['node'] = node
        
        # Try to get the IP address if the VM is running
        try:
            status = client.request('GET', f'/nodes/{node}/qemu/{vmid}/status/current')
            if status.get('status') == 'running':
                # Try to get agent info
                config = client.request('GET', f'/nodes/{node}/qemu/{vmid}/config')
                if config.get('agent', 0) == 1:
                    try:
                        agent_info = client.request('GET', f'/nodes/{node}/qemu/{vmid}/agent/network-get-interfaces')
                        # Extract IP addresses
                        ip_addresses = []
                        for iface in agent_info.get('result', []):
                            if 'ip-addresses' in iface:
                                for addr in iface['ip-addresses']:
                                    if addr.get('ip-address') and addr.get('ip-address-type') == 'ipv4':
                                        ip_addresses.append(addr.get('ip-address'))
                        if ip_addresses:
                            outputs['ip_address'] = ip_addresses[0]
                            outputs['ip_addresses'] = ip_addresses
                    except Exception as e:
                        # Agent might not be available yet
                        pass
        except Exception:
            # VM might not be running
            pass
        
        return pulumi.dynamic.CreateResult(
            id_=f"{node}/{vmid}",
            outs=outputs
        )
    
    def read(self, id: str, props: Dict[str, Any]) -> pulumi.dynamic.ReadResult:
        """Read an existing VM from Proxmox.
        
        Args:
            id: Resource ID
            props: Resource properties
            
        Returns:
            ReadResult with VM properties
        """
        # Parse VM ID from resource ID
        node, vmid_str = id.split('/')
        vmid = int(vmid_str)  # Explicitly convert to integer
        
        client = self._get_client(props)
        
        # Get VM configuration
        vm_config = client.request('GET', f'/nodes/{node}/qemu/{vmid}/config')
        
        # Get VM status
        vm_status = client.request('GET', f'/nodes/{node}/qemu/{vmid}/status/current')
        
        # Create outputs dictionary with all original props and updated values
        outputs = {**props}
        
        # Update with current values
        outputs.update({
            'vmid': vmid,
            'node': node,
            'status': vm_status.get('data', {}).get('status', 'unknown'),
            'name': vm_config.get('data', {}).get('name', ''),
            'cores': vm_config.get('data', {}).get('cores', 1),
            'memory': vm_config.get('data', {}).get('memory', 512),
        })
        
        # Try to get IP address if agent is enabled and VM is running
        if vm_status.get('status') == 'running' and vm_config.get('agent', 0) == 1:
            try:
                agent_info = client.request('GET', f'/nodes/{node}/qemu/{vmid}/agent/network-get-interfaces')
                # Extract IP addresses
                ip_addresses = []
                for iface in agent_info.get('result', []):
                    if 'ip-addresses' in iface:
                        for addr in iface['ip-addresses']:
                            if addr.get('ip-address') and addr.get('ip-address-type') == 'ipv4':
                                ip_addresses.append(addr.get('ip-address'))
                if ip_addresses:
                    outputs['ip_address'] = ip_addresses[0]
                    outputs['ip_addresses'] = ip_addresses
            except Exception:
                # Agent might not be available
                pass
        
        return pulumi.dynamic.ReadResult(id=id, outs=outputs)
    
    def update(self, id: str, olds: Dict[str, Any], news: Dict[str, Any]) -> pulumi.dynamic.UpdateResult:
        """Update an existing VM in Proxmox.
        
        Args:
            id: Resource ID
            olds: Old resource properties
            news: New resource properties
            
        Returns:
            UpdateResult with updated VM properties
        """
        # Parse VM ID from resource ID
        node, vmid_str = id.split('/')
        vmid = int(vmid_str)  # Explicitly convert to integer
        
        client = self._get_client(news)
        logger.debug(f"Updating VM {vmid} on node {node}")
        
        # Determine if we need to stop the VM to apply changes
        requires_stop = False
        
        # These properties require the VM to be stopped
        stop_required_props = ['cores', 'sockets', 'memory']
        
        for prop in stop_required_props:
            if prop in news and prop in olds and news[prop] != olds[prop]:
                requires_stop = True
                logger.debug(f"Property {prop} changed from {olds[prop]} to {news[prop]}, requires VM stop")
                break
        
        # Get VM status
        vm_status = client.request('GET', f'/nodes/{node}/qemu/{vmid}/status/current')
        was_running = vm_status.get('data', {}).get('status') == 'running'
        logger.debug(f"Current VM status: {vm_status.get('data', {}).get('status')}")
        
        # Stop VM if needed
        if requires_stop and was_running:
            logger.debug(f"Stopping VM {vmid} for update")
            response = client.request('POST', f'/nodes/{node}/qemu/{vmid}/status/stop')
            logger.debug(f"Stop response: {response}")
            
            # Wait for stop task to complete
            task_id = None
            if isinstance(response, dict):
                if 'data' in response:
                    task_id = response['data']
                    logger.debug(f"Found task ID in response['data']: {task_id}")
                else:
                    for key, value in response.items():
                        if key in ['upid', 'task_id']:
                            task_id = value
                            logger.debug(f"Found task ID in key '{key}': {task_id}")
            elif isinstance(response, str):
                task_id = response
                logger.debug(f"Response is string, using as task ID: {task_id}")

            if task_id:
                logger.debug(f"Waiting for stop task: {task_id}")
                self._wait_for_specific_task(client, node, task_id)
            else:
                logger.warning("No task ID found in stop response, waiting for all tasks to complete")
                self._wait_for_task_completion(client, node)
            
            self._wait_for_vm_state(client, node, vmid, 'stopped')
        
        # Update VM configuration
        config_updates = {}
        
        # Compute resources
        if 'cores' in news and news['cores'] != olds.get('cores'):
            config_updates['cores'] = news['cores']
        if 'sockets' in news and news['sockets'] != olds.get('sockets'):
            config_updates['sockets'] = news['sockets']
        if 'memory' in news and news['memory'] != olds.get('memory'):
            config_updates['memory'] = news['memory']
        
        # Network configuration
        if ('network_bridge' in news and news['network_bridge'] != olds.get('network_bridge')) or \
           ('vlan_tag' in news and news['vlan_tag'] != olds.get('vlan_tag')):
            net_config = f'model=virtio,bridge={news.get("network_bridge", "vmbr0")}'
            if news.get('vlan_tag'):
                net_config += f',tag={news.get("vlan_tag")}'
            config_updates['net0'] = net_config
        
        # Apply configuration updates if any
        if config_updates:
            logger.debug(f"Applying configuration updates: {config_updates}")
            response = client.request(
                'POST',
                f'/nodes/{node}/qemu/{vmid}/config',
                data=config_updates
            )
            logger.debug(f"Config update response: {response}")
            
            # Wait for config update task if one was returned
            if isinstance(response, dict) and 'data' in response and isinstance(response['data'], str):
                task_id = response['data']
                logger.debug(f"Waiting for config update task: {task_id}")
                self._wait_for_specific_task(client, node, task_id)
        
        # Disk size update (can be done while VM is running in newer Proxmox versions)
        if 'disk_size' in news and news['disk_size'] != olds.get('disk_size'):
            logger.debug(f"Resizing disk to {news['disk_size']}")
            response = client.request(
                'PUT',
                f'/nodes/{node}/qemu/{vmid}/resize',
                params={
                    'disk': 'scsi0',
                    'size': news['disk_size'],
                }
            )
            logger.debug(f"Disk resize response: {response}")
            
            # Wait for resize task to complete
            task_id = None
            if isinstance(response, dict):
                if 'data' in response:
                    task_id = response['data']
                    logger.debug(f"Found task ID in response['data']: {task_id}")
                else:
                    for key, value in response.items():
                        if key in ['upid', 'task_id']:
                            task_id = value
                            logger.debug(f"Found task ID in key '{key}': {task_id}")
            elif isinstance(response, str):
                task_id = response
                logger.debug(f"Response is string, using as task ID: {task_id}")

            if task_id:
                logger.debug(f"Waiting for resize task: {task_id}")
                self._wait_for_specific_task(client, node, task_id)
            else:
                logger.warning("No task ID found in resize response, waiting for all tasks to complete")
                self._wait_for_task_completion(client, node)

            # Verify disk size after resize
            try:
                config_response = client.request('GET', f'/nodes/{node}/qemu/{vmid}/config')
                if 'data' in config_response:
                    disk_size = config_response['data'].get('scsi0')
                    logger.debug(f"Current disk configuration after resize: {disk_size}")
            except Exception as e:
                logger.warning(f"Failed to verify disk size after resize: {e}")
        
        # Restart VM if it was running before
        if requires_stop and was_running:
            logger.debug(f"Starting VM {vmid} after update")
            response = client.request('POST', f'/nodes/{node}/qemu/{vmid}/status/start')
            logger.debug(f"Start response: {response}")
            
            # Wait for start task to complete
            task_id = None
            if isinstance(response, dict):
                if 'data' in response:
                    task_id = response['data']
                    logger.debug(f"Found task ID in response['data']: {task_id}")
                else:
                    for key, value in response.items():
                        if key in ['upid', 'task_id']:
                            task_id = value
                            logger.debug(f"Found task ID in key '{key}': {task_id}")
            elif isinstance(response, str):
                task_id = response
                logger.debug(f"Response is string, using as task ID: {task_id}")

            if task_id:
                logger.debug(f"Waiting for start task: {task_id}")
                self._wait_for_specific_task(client, node, task_id)
            else:
                logger.warning("No task ID found in start response, waiting for all tasks to complete")
                self._wait_for_task_completion(client, node)
            
            self._wait_for_vm_state(client, node, vmid, 'running')
        
        return pulumi.dynamic.UpdateResult(outs=news)
    
    def delete(self, id: str, props: Dict[str, Any]) -> None:
        """Delete a VM from Proxmox.
        
        Args:
            id: Resource ID
            props: Resource properties
        """
        # Parse VM ID from resource ID
        node, vmid_str = id.split('/')
        vmid = int(vmid_str)  # Explicitly convert to integer
        
        client = self._get_client(props)
        
        # Get VM status
        try:
            vm_status = client.request('GET', f'/nodes/{node}/qemu/{vmid}/status/current')
            current_status = vm_status.get('data', {}).get('status')
            logger.debug(f"Current VM status before deletion: {current_status}")
            
            # Stop VM if running
            if current_status == 'running':
                logger.debug(f"Stopping VM {vmid} before deletion")
                response = client.request('POST', f'/nodes/{node}/qemu/{vmid}/status/stop')
                logger.debug(f"Stop response: {response}")
                
                # Wait for stop task to complete
                task_id = None
                if isinstance(response, dict):
                    if 'data' in response:
                        task_id = response['data']
                        logger.debug(f"Found task ID in response['data']: {task_id}")
                    else:
                        for key, value in response.items():
                            if key in ['upid', 'task_id']:
                                task_id = value
                                logger.debug(f"Found task ID in key '{key}': {task_id}")
                elif isinstance(response, str):
                    task_id = response
                    logger.debug(f"Response is string, using as task ID: {task_id}")

                if task_id:
                    logger.debug(f"Waiting for stop task: {task_id}")
                    self._wait_for_specific_task(client, node, task_id)
                else:
                    logger.warning("No task ID found in stop response, waiting for all tasks to complete")
                    self._wait_for_task_completion(client, node)
                
                # Wait for VM to stop
                self._wait_for_vm_state(client, node, vmid, 'stopped')
            
            # Delete VM
            logger.debug(f"Deleting VM {vmid}")
            response = client.request('DELETE', f'/nodes/{node}/qemu/{vmid}')
            logger.debug(f"Delete response: {response}")
            
            # Wait for delete task to complete
            task_id = None
            if isinstance(response, dict):
                if 'data' in response:
                    task_id = response['data']
                    logger.debug(f"Found task ID in response['data']: {task_id}")
                else:
                    for key, value in response.items():
                        if key in ['upid', 'task_id']:
                            task_id = value
                            logger.debug(f"Found task ID in key '{key}': {task_id}")
            elif isinstance(response, str):
                task_id = response
                logger.debug(f"Response is string, using as task ID: {task_id}")

            if task_id:
                logger.debug(f"Waiting for delete task: {task_id}")
                self._wait_for_specific_task(client, node, task_id)
            else:
                logger.warning("No task ID found in delete response, waiting for all tasks to complete")
                self._wait_for_task_completion(client, node)
            
            # Verify VM is gone
            try:
                client.request('GET', f'/nodes/{node}/qemu/{vmid}/status/current')
                raise Exception(f"VM {vmid} still exists after deletion")
            except Exception as e:
                if "not found" in str(e).lower():
                    logger.debug(f"VM {vmid} successfully deleted")
                else:
                    raise
                    
        except Exception as e:
            if "not found" in str(e).lower():
                logger.debug(f"VM {vmid} already deleted")
            else:
                raise
    
    def _get_client(self, props: Dict[str, Any]) -> ProxmoxClient:
        """Get a Proxmox API client using the provided properties.
        
        Args:
            props: Resource properties
            
        Returns:
            A configured ProxmoxClient
        """
        return ProxmoxClient(
            endpoint=props.get('endpoint'),
            username=props.get('username'),
            password=props.get('password'),
            token_id=props.get('token_id'),
            token_secret=props.get('token_secret'),
            node=props.get('node'),
            insecure=props.get('insecure', False),
            timeout=props.get('timeout', 30),
            debug=props.get('debug', False),
        )
    
    def _get_next_vmid(self, client: ProxmoxClient) -> int:
        """Get the next available VM ID from Proxmox.
        
        Args:
            client: ProxmoxClient instance
            
        Returns:
            Next available VM ID
        """
        return client.request('GET', '/cluster/nextid')
    
    def _clone_template(self, client: ProxmoxClient, node: str, template_id: str, 
                        vmid: int, props: Dict[str, Any]) -> None:
        """Clone a template to create a new VM.
        
        Args:
            client: ProxmoxClient instance
            node: Proxmox node
            template_id: Template ID to clone from
            vmid: New VM ID
            props: Resource properties
        """
        # Basic clone parameters
        clone_params = {
            'newid': vmid,
            'full': 1,  # Full clone by default
            'name': props.get('name', f'vm-{vmid}'),
        }
        
        # Add storage if specified
        if props.get('disk_storage'):
            clone_params['storage'] = props.get('disk_storage')
        
        # Clone the template
        response = client.request(
            'POST',
            f'/nodes/{node}/qemu/{template_id}/clone',
            data=clone_params
        )
        
        # Debug log the response
        logger.debug(f"Clone response: {response}")
        
        # Wait for clone to complete - get the task ID from the response
        task_id = None
        
        # Handle different response formats
        if isinstance(response, dict):
            # If response is a dictionary
            if 'data' in response:
                task_id = response['data']
                logger.debug(f"Found task ID in response['data']: {task_id}")
            else:
                for key, value in response.items():
                    logger.debug(f"Key: {key}, Value: {value}")
                    if key in ['upid', 'task_id']:
                        task_id = value
                        logger.debug(f"Found task ID in key '{key}': {task_id}")
        elif isinstance(response, str):
            # If response is just a string, assume it's the task ID
            task_id = response
            logger.debug(f"Response is string, using as task ID: {task_id}")
        
        if not task_id:
            raise Exception("Failed to get task ID from clone response")
            
        logger.debug(f"Waiting for clone task: {task_id}")
        self._wait_for_specific_task(client, node, task_id)
        
        # Verify VM exists after clone
        try:
            client.request('GET', f'/nodes/{node}/qemu/{vmid}/config')
        except Exception as e:
            raise Exception(f"Failed to verify VM {vmid} exists after clone: {str(e)}")
    
    def _configure_vm(self, client: ProxmoxClient, node: str, vmid: int, props: dict):
        """Configure a VM with the given properties."""
        logger.info(f"Starting VM {vmid} configuration process")
        
        # Track configuration tasks
        tasks = {
            'compute': {'status': 'pending', 'subtasks': ['cores', 'sockets', 'memory']},
            'disk': {'status': 'pending', 'subtasks': ['resize']},
            'network': {'status': 'pending', 'subtasks': ['bridge', 'vlan']},
            'cloud_init': {'status': 'pending', 'subtasks': ['user', 'ssh_key']}
        }
        
        try:
            # Build configuration object
            config = {}
            
            # Compute resources
            logger.info(f"Configuring compute resources for VM {vmid}")
            tasks['compute']['status'] = 'in_progress'
            if props.get('cores'):
                logger.debug(f"Setting cores to {props.get('cores')}")
                config['cores'] = int(props.get('cores'))
                tasks['compute']['subtasks'][0] = 'cores ✓'
            if props.get('sockets'):
                logger.debug(f"Setting sockets to {props.get('sockets')}")
                config['sockets'] = int(props.get('sockets'))
                tasks['compute']['subtasks'][1] = 'sockets ✓'
            if props.get('memory'):
                logger.debug(f"Setting memory to {props.get('memory')}MB")
                config['memory'] = int(props.get('memory'))
                tasks['compute']['subtasks'][2] = 'memory ✓'
            tasks['compute']['status'] = 'completed'
            
            # Network configuration
            logger.info(f"Starting network configuration for VM {vmid}")
            tasks['network']['status'] = 'in_progress'
            
            if props.get('network_bridge'):
                net_config = f'model=virtio,bridge={props.get("network_bridge")}'
                if props.get('vlan_tag'):
                    logger.debug(f"Adding VLAN tag {props.get('vlan_tag')}")
                    net_config += f',tag={int(props.get("vlan_tag"))}'
                config['net0'] = net_config
                tasks['network']['subtasks'][0] = 'bridge ✓'
                if props.get('vlan_tag'):
                    tasks['network']['subtasks'][1] = f'vlan {props.get("vlan_tag")} ✓'
            tasks['network']['status'] = 'completed'
            
            # Apply configuration if any
            if config:
                logger.info(f"Applying configuration to VM {vmid}")
                response = client.request(
                    'POST',
                    f'/nodes/{node}/qemu/{vmid}/config',
                    data=config
                )
                logger.debug(f"Configuration response: {response}")
                
                # Wait for any configuration tasks to complete
                self._wait_for_task_completion(client, node)
            
            # Disk configuration
            logger.info(f"Starting disk configuration for VM {vmid}")
            tasks['disk']['status'] = 'in_progress'
            
            if props.get('disk_size'):
                logger.info(f"Initiating disk resize for VM {vmid} to {props.get('disk_size')}")
                tasks['disk']['subtasks'][0] = 'resize (in progress)'
                
                # First get current config to verify disk name
                config_response = client.request('GET', f'/nodes/{node}/qemu/{vmid}/config')
                disk_name = 'scsi0'  # default
                if 'data' in config_response:
                    # Find the first SCSI disk
                    for key in config_response['data'].keys():
                        if key.startswith('scsi'):
                            disk_name = key
                            break
                logger.debug(f"Using disk {disk_name} for resize operation")
                
                # Resize disk
                resize_response = client.request(
                    'PUT',
                    f'/nodes/{node}/qemu/{vmid}/resize',
                    params={
                        'disk': disk_name,
                        'size': props.get('disk_size'),
                    }
                )
                logger.debug(f"Disk resize response: {resize_response}")
                
                # Wait for resize task if one was created
                if isinstance(resize_response, dict) and resize_response.get('data'):
                    task_id = resize_response['data']
                    logger.info(f"Waiting for disk resize task {task_id}")
                    self._wait_for_specific_task(client, node, task_id)
                tasks['disk']['subtasks'][0] = 'resize ✓'
            
            # Cloud-init configuration
            logger.info(f"Starting cloud-init configuration for VM {vmid}")
            tasks['cloud_init']['status'] = 'in_progress'
            
            cloud_init_config = {}
            if props.get('cloud_init_user'):
                logger.debug(f"Setting cloud-init user to {props.get('cloud_init_user')}")
                cloud_init_config['ciuser'] = props.get('cloud_init_user')
                tasks['cloud_init']['subtasks'][0] = 'user ✓'
            
            if props.get('ssh_public_keys'):
                logger.debug("Processing SSH key for cloud-init")
                cloud_init_config['sshkeys'] = urllib.parse.quote(props.get('ssh_public_keys'))
                tasks['cloud_init']['subtasks'][1] = 'ssh_key ✓'
            
            if cloud_init_config:
                response = client.request(
                    'POST',
                    f'/nodes/{node}/qemu/{vmid}/config',
                    data=cloud_init_config
                )
                logger.debug(f"Cloud-init configuration response: {response}")
            tasks['cloud_init']['status'] = 'completed'
            
            # Log final configuration status
            logger.info("Configuration tasks completed:")
            for task_name, task_info in tasks.items():
                logger.info(f"- {task_name}: {task_info['status']}")
                for subtask in task_info['subtasks']:
                    if '✓' in subtask:
                        logger.info(f"  - {subtask}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed during VM configuration. Task status:")
            for task_name, task_info in tasks.items():
                logger.error(f"- {task_name}: {task_info['status']}")
                for subtask in task_info['subtasks']:
                    if '✓' in subtask:
                        logger.error(f"  - {subtask}")
            raise Exception(f"Failed to configure VM: {str(e)}")
    
    def _start_vm(self, client: ProxmoxClient, node: str, vmid: int) -> None:
        """Start a VM.
        
        Args:
            client: ProxmoxClient instance
            node: Proxmox node
            vmid: VM ID
        """
        logger.debug(f"Starting VM {vmid} on node {node}")
        response = client.request('POST', f'/nodes/{node}/qemu/{vmid}/status/start')
        logger.debug(f"Start response: {response}")
        
        # Wait for the start task to complete
        task_id = None
        if isinstance(response, dict):
            if 'data' in response:
                task_id = response['data']
                logger.debug(f"Found task ID in response['data']: {task_id}")
            else:
                for key, value in response.items():
                    if key in ['upid', 'task_id']:
                        task_id = value
                        logger.debug(f"Found task ID in key '{key}': {task_id}")
        elif isinstance(response, str):
            task_id = response
            logger.debug(f"Response is string, using as task ID: {task_id}")

        if task_id:
            logger.debug(f"Waiting for start task: {task_id}")
            self._wait_for_specific_task(client, node, task_id)
        else:
            logger.warning("No task ID found in start response, waiting for all tasks to complete")
            self._wait_for_task_completion(client, node)
        
        # Then wait for VM to reach running state
        self._wait_for_vm_state(client, node, vmid, 'running')
    
    def _wait_for_vm_state(self, client: ProxmoxClient, node: str, vmid: Union[int, float, str], 
                          state: str, timeout: int = 300) -> None:
        """Wait for VM to reach the specified state."""
        vmid = int(vmid)  # Ensure vmid is an integer
        start_time = time.time()
        while time.time() - start_time < timeout:
            current_state = self._get_vm_status(client, node, vmid)
            logging.info(f"VM {vmid} current state: {current_state}")
            if current_state == state:
                return
            time.sleep(5)
        raise Exception(f"Timeout waiting for VM {vmid} to reach state {state}")
    
    def _get_vm_status(self, client: ProxmoxClient, node: str, vmid: Union[int, float, str]) -> str:
        """Get the current status of the VM."""
        vmid = int(vmid)  # Ensure vmid is an integer
        response = client.request(
            "GET", 
            f"/nodes/{node}/qemu/{vmid}/status/current"
        )
        return response.get('data', {}).get('status', '')
    
    def _wait_for_ip_address(self, client: ProxmoxClient, node: str, vmid: Union[int, float, str], 
                            timeout: int = 300) -> Optional[str]:
        """Wait for VM to get an IP address."""
        vmid = int(vmid)  # Ensure vmid is an integer
        start_time = time.time()
        logger.info(f"Waiting for IP address for VM {vmid}")

        while time.time() - start_time < timeout:
            # Method 1: Try QEMU agent
            try:
                logger.debug("Attempting to get IP via QEMU agent")
                response = client.request(
                    "GET", 
                    f"/nodes/{node}/qemu/{vmid}/agent/network-get-interfaces"
                )
                
                interfaces = response.get('data', [])
                for interface in interfaces:
                    if interface.get('name') != 'lo':
                        logger.debug(f"Found interface: {interface.get('name')}")
                        for ip_info in interface.get('ip-addresses', []):
                            ip = ip_info.get('ip-address')
                            ip_type = ip_info.get('ip-address-type')
                            logger.debug(f"Found IP: {ip} (type: {ip_type})")
                            if ip_type == 'ipv4' and ip and not ip.startswith('127.'):
                                logger.info(f"Found IP address via QEMU agent: {ip}")
                                return ip
            except Exception as e:
                logger.debug(f"QEMU agent method failed: {str(e)}")
                
            # Method 2: Try cloud-init config
            try:
                logger.debug("Attempting to get IP from cloud-init config")
                response = client.request(
                    "GET", 
                    f"/nodes/{node}/qemu/{vmid}/config"
                )
                config = response.get('data', {})
                
                # Check ipconfig entries
                for key, value in config.items():
                    if key.startswith('ipconfig'):
                        logger.debug(f"Found ipconfig entry: {value}")
                        if value and 'ip=' in value:
                            ip = value.split('ip=')[1].split('/')[0]
                            if ip and not ip.startswith('127.'):
                                logger.info(f"Found IP address from cloud-init config: {ip}")
                                return ip
            except Exception as e:
                logger.debug(f"Cloud-init config method failed: {str(e)}")

            # Method 3: Try getting IP from VM status
            try:
                logger.debug("Attempting to get IP from VM status")
                response = client.request(
                    "GET",
                    f"/nodes/{node}/qemu/{vmid}/status/current"
                )
                status = response.get('data', {})
                if 'ip-address' in status:
                    ip = status['ip-address']
                    if ip and not ip.startswith('127.'):
                        logger.info(f"Found IP address from VM status: {ip}")
                        return ip
                
                # Also check network interfaces in status
                net = status.get('net', {})
                for iface in net.values():
                    if isinstance(iface, dict) and 'ip-addresses' in iface:
                        for ip in iface['ip-addresses']:
                            if ip and not ip.startswith('127.'):
                                logger.info(f"Found IP address from network status: {ip}")
                                return ip
            except Exception as e:
                logger.debug(f"VM status method failed: {str(e)}")

            # If we haven't found an IP yet, wait before retrying
            logger.debug(f"No IP address found yet for VM {vmid}, waiting...")
            time.sleep(5)
        
        logger.warning(f"Timeout waiting for VM {vmid} to get an IP address")
        return None
    
    def _setup_vm(self, client: ProxmoxClient, node: str, vmid: Union[int, float, str], 
                ip_address: Optional[str], props: Dict[str, Any]) -> None:
        """Setup VM after it has started."""
        vmid = int(vmid)  # Ensure vmid is an integer
        if not ip_address:
            raise Exception("Cannot set up VM without an IP address")
        
        # Get SSH credentials
        username = props.get('cloud_init_user')
        password = props.get('cloud_init_password')
        ssh_key_path = props.get('cloud_init_ssh_private_key')
        
        if not username:
            raise Exception("Cannot set up VM without a username")
        
        if not password and not ssh_key_path:
            raise Exception("Cannot set up VM without a password or SSH key")
        
        # Wait for SSH to be available
        self._wait_for_ssh(ip_address, username, password, ssh_key_path, 
                         props.get('cloud_init_ssh_key_passphrase'))
        
        # Create SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            # Try to connect with SSH key if provided
            if ssh_key_path:
                try:
                    # If the ssh_key is a file path, read it
                    if ssh_key_path.startswith('/') and os.path.exists(ssh_key_path):
                        logger.debug(f"Loading SSH key from file: {ssh_key_path}")
                        key = paramiko.RSAKey.from_private_key_file(
                            ssh_key_path,
                            password=props.get('cloud_init_ssh_key_passphrase')
                        )
                    else:
                        # Assume it's the actual key data
                        logger.debug("Loading SSH key from provided key data")
                        key_file = io.StringIO(ssh_key_path)
                        key = paramiko.RSAKey.from_private_key(
                            key_file,
                            password=props.get('cloud_init_ssh_key_passphrase')
                        )
                    
                    logger.debug(f"Attempting SSH connection to {ip_address} with key authentication")
                    ssh.connect(ip_address, username=username, pkey=key)
                    
                except (paramiko.ssh_exception.SSHException, 
                       paramiko.ssh_exception.PasswordRequiredException) as e:
                    logger.warning(f"Failed to load SSH key: {str(e)}")
                    if password:
                        logger.debug("Falling back to password authentication")
                        ssh.connect(ip_address, username=username, password=password)
                    else:
                        raise
            else:
                # Connect with password
                logger.debug(f"Attempting SSH connection to {ip_address} with password authentication")
                ssh.connect(ip_address, username=username, password=password)
            
            def run_command(command: str, check_exit: bool = True) -> Tuple[int, str, str]:
                """Run a command and return exit code, stdout, and stderr."""
                logger.debug(f"Running command: {command}")
                stdin, stdout, stderr = ssh.exec_command(command)
                exit_status = stdout.channel.recv_exit_status()
                out = stdout.read().decode().strip()
                err = stderr.read().decode().strip()
                
                if out:
                    logger.debug(f"Command output: {out}")
                if err:
                    logger.warning(f"Command error output: {err}")
                
                if check_exit and exit_status != 0:
                    raise Exception(f"Command failed with exit status {exit_status}: {err or out}")
                
                return exit_status, out, err
            
            # Install Proxmox agent if requested
            vm_setup_features = props.get('vm_setup_features', [])
            if isinstance(vm_setup_features, str):
                vm_setup_features = [vm_setup_features]
                
            if 'proxmox_agent' in vm_setup_features:
                logger.debug("Installing Proxmox guest agent")
                run_command('sudo DEBIAN_FRONTEND=noninteractive apt-get update')
                run_command('sudo DEBIAN_FRONTEND=noninteractive apt-get install -y qemu-guest-agent')
                run_command('sudo systemctl enable qemu-guest-agent')
                run_command('sudo systemctl start qemu-guest-agent')
            
            # Create admin user if requested
            if props.get('vm_user_create_admin_user', False) and props.get('vm_user_username'):
                admin_user = props.get('vm_user_username')
                logger.debug(f"Creating admin user: {admin_user}")
                
                # Check if user already exists
                exit_status, _, _ = run_command(f'id {admin_user}', check_exit=False)
                if exit_status != 0:
                    # Create user
                    run_command(f'sudo useradd -m -s /bin/bash {admin_user}')
                    
                    # Add to sudo group
                    run_command(f'sudo usermod -aG sudo {admin_user}')
                    
                    # Configure passwordless sudo
                    sudoers_content = f'{admin_user} ALL=(ALL) NOPASSWD:ALL'
                    run_command(f'echo "{sudoers_content}" | sudo tee /etc/sudoers.d/{admin_user}')
                    run_command(f'sudo chmod 440 /etc/sudoers.d/{admin_user}')
                
                # Configure SSH key if provided
                admin_ssh_key = props.get('vm_user_ssh_public_key')
                if admin_ssh_key:
                    logger.debug("Configuring SSH key for admin user")
                    # If the ssh_key is a file path, read it
                    if admin_ssh_key.startswith('/') and os.path.exists(admin_ssh_key):
                        with open(admin_ssh_key, 'r') as f:
                            admin_ssh_key = f.read().strip()
                    
                    # Create .ssh directory
                    run_command(f'sudo mkdir -p /home/{admin_user}/.ssh')
                    run_command(f'echo "{admin_ssh_key}" | sudo tee /home/{admin_user}/.ssh/authorized_keys')
                    run_command(f'sudo chown -R {admin_user}:{admin_user} /home/{admin_user}/.ssh')
                    run_command(f'sudo chmod 700 /home/{admin_user}/.ssh')
                    run_command(f'sudo chmod 600 /home/{admin_user}/.ssh/authorized_keys')
            
            # Execute custom setup commands if provided
            vm_setup_commands = props.get('vm_setup_commands', [])
            if isinstance(vm_setup_commands, str):
                vm_setup_commands = [vm_setup_commands]
                
            for cmd in vm_setup_commands:
                logger.debug(f"Running custom setup command: {cmd}")
                run_command(cmd)
            
            # Execute custom setup scripts if provided
            vm_setup_scripts = props.get('vm_setup_scripts', [])
            if isinstance(vm_setup_scripts, str):
                vm_setup_scripts = [vm_setup_scripts]
                
            for script in vm_setup_scripts:
                logger.debug(f"Running setup script")
                # If the script is a file path, read it
                script_content = None
                if script.startswith('/') and os.path.exists(script):
                    with open(script, 'r') as f:
                        script_content = f.read()
                else:
                    # Assume it's the actual script content
                    script_content = script
                
                # Create a temporary file
                temp_filename = f"/tmp/setup_{int(time.time())}.sh"
                run_command(f'cat > {temp_filename} << "EOF"\n{script_content}\nEOF')
                run_command(f'chmod +x {temp_filename}')
                run_command(f'sudo {temp_filename}')
                run_command(f'rm {temp_filename}')
                
        finally:
            # Always close the SSH connection
            ssh.close()
    
    def _wait_for_ssh(self, ip_address: str, username: str, password: Optional[str], 
                    ssh_key_path: Optional[str], ssh_key_passphrase: Optional[str], 
                    timeout: int = 300) -> None:
        """Wait for SSH to become available on a VM.
        
        Args:
            ip_address: VM IP address
            username: SSH username
            password: SSH password (only used if ssh_key_path is not provided)
            ssh_key_path: Path to or content of SSH private key
            ssh_key_passphrase: Passphrase to decrypt the SSH private key (if needed)
            timeout: Timeout in seconds
        """
        start_time = time.time()
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        while True:
            try:
                # Try to connect with SSH key if provided
                if ssh_key_path:
                    try:
                        # If the ssh_key is a file path, read it
                        if ssh_key_path.startswith('/') and os.path.exists(ssh_key_path):
                            logger.debug(f"Loading SSH key from file: {ssh_key_path}")
                            key = paramiko.RSAKey.from_private_key_file(
                                ssh_key_path,
                                password=ssh_key_passphrase
                            )
                        else:
                            # Assume it's the actual key data
                            logger.debug("Loading SSH key from provided key data")
                            key_file = io.StringIO(ssh_key_path)
                            key = paramiko.RSAKey.from_private_key(
                                key_file,
                                password=ssh_key_passphrase
                            )
                        
                        logger.debug(f"Attempting SSH connection to {ip_address} with key authentication")
                        ssh.connect(ip_address, username=username, pkey=key, timeout=10)
                        
                    except (paramiko.ssh_exception.SSHException, 
                           paramiko.ssh_exception.PasswordRequiredException) as e:
                        logger.warning(f"Failed to load SSH key: {str(e)}")
                        if password:
                            logger.debug("Falling back to password authentication")
                            ssh.connect(ip_address, username=username, password=password, timeout=10)
                        else:
                            raise
                else:
                    # Connect with password
                    logger.debug(f"Attempting SSH connection to {ip_address} with password authentication")
                    ssh.connect(ip_address, username=username, password=password, timeout=10)
                
                logger.debug("SSH connection successful")
                ssh.close()
                return
                
            except (socket.error, paramiko.ssh_exception.SSHException) as e:
                if time.time() - start_time > timeout:
                    raise Exception(f"Timed out waiting for SSH connection: {str(e)}")
                time.sleep(5)
    
    def _wait_for_specific_task(self, client: ProxmoxClient, node: str, task_id: str, 
                               timeout: int = 300) -> None:
        """Wait for a specific task to complete.
        
        Args:
            client: ProxmoxClient instance
            node: Proxmox node
            task_id: Task ID to wait for
            timeout: Timeout in seconds
        """
        start_time = time.time()
        logger.debug(f"Waiting for task {task_id} on node {node}")
        
        while True:
            try:
                # Get task status
                task_status = client.request('GET', f'/nodes/{node}/tasks/{task_id}/status')
                logger.debug(f"Task status response: {task_status}")
                
                # Extract status data - handle both direct response and nested data
                status_data = task_status.get('data', task_status)
                if not isinstance(status_data, dict):
                    logger.debug(f"Unexpected status data format: {status_data}")
                    status_data = {}
                
                # Get detailed status information
                task_status = status_data.get('status', 'unknown')
                task_type = status_data.get('type', 'unknown')
                task_exitstatus = status_data.get('exitstatus', 'unknown')
                task_msg = status_data.get('msg', '')
                
                logger.debug(f"Task details - Status: {task_status}, Type: {task_type}, Exit: {task_exitstatus}, Msg: {task_msg}")
                
                # Check if task has stopped
                if task_status == 'stopped':
                    if task_exitstatus == 'OK':
                        logger.debug(f"Task {task_id} completed successfully")
                        # Add a small delay after task completion to ensure Proxmox has fully processed it
                        time.sleep(2)
                        return
                    else:
                        error = task_msg or 'Unknown error'
                        raise Exception(f"Task {task_id} failed: {error} (exit status: {task_exitstatus})")
                
            except Exception as e:
                error_msg = str(e)
                # Handle task not found case
                if "not found" in error_msg.lower():
                    logger.debug(f"Task {task_id} not found, checking task history")
                    try:
                        # Get recent tasks
                        all_tasks = client.request('GET', f'/nodes/{node}/tasks')
                        tasks = all_tasks.get('data', [])
                        if not isinstance(tasks, list):
                            tasks = []
                        
                        # Look for our task in recent history
                        for task in tasks:
                            if task.get('upid') == task_id:
                                status = task.get('status')
                                exitstatus = task.get('exitstatus')
                                msg = task.get('msg', '')
                                
                                logger.debug(f"Found task in history - Status: {status}, Exit: {exitstatus}, Msg: {msg}")
                                
                                if status == 'stopped' and exitstatus == 'OK':
                                    logger.debug(f"Task {task_id} completed successfully (verified from task history)")
                                    # Add a small delay after task completion to ensure Proxmox has fully processed it
                                    time.sleep(2)
                                    return
                                elif status == 'stopped':
                                    raise Exception(f"Task {task_id} failed: {msg or 'Unknown error'}")
                                
                        logger.debug(f"Task {task_id} not found in recent history, continuing to wait")
                    except Exception as inner_e:
                        logger.debug(f"Error checking task history: {inner_e}")
                else:
                    logger.debug(f"Error checking task status: {error_msg}")
            
            # Check timeout
            if time.time() - start_time > timeout:
                raise Exception(f"Timeout waiting for task {task_id} to complete on node {node}")
            
            # Wait before checking again - increased interval to avoid overwhelming the API
            time.sleep(3)

    def _wait_for_task_completion(self, client: ProxmoxClient, node: str, 
                                 timeout: int = 300) -> None:
        """Wait for all tasks on a node to complete.
        
        Args:
            client: ProxmoxClient instance
            node: Proxmox node
            timeout: Timeout in seconds
        """
        start_time = time.time()
        
        while True:
            # List running tasks
            task_response = client.request('GET', f'/nodes/{node}/tasks')
            
            # Handle case where response is already a list (no 'data' key)
            tasks = task_response
            if isinstance(task_response, dict) and 'data' in task_response:
                tasks = task_response['data']
            
            # Filter for running tasks
            running_tasks = [t for t in tasks if t.get('status') == 'running']
            
            # If no running tasks, we're done
            if not running_tasks:
                return
            
            # Check timeout
            if time.time() - start_time > timeout:
                raise Exception(f"Timeout waiting for tasks to complete on node {node}")
            
            # Wait and check again
            time.sleep(2)


class VM(pulumi.dynamic.Resource):
    """A Proxmox VM resource."""
    
    def __init__(self,
                 name: str,
                 template_id: Optional[str] = None,
                 args: Optional[Dict[str, Any]] = None,
                 provider: Optional["ProxmoxProvider"] = None,
                 opts: Optional[pulumi.ResourceOptions] = None):
        """Create a new VM resource.
        
        Args:
            name: The unique name for the VM resource.
            template_id: The template ID to clone from.
            args: Additional arguments to configure the VM.
            provider: The ProxmoxProvider to use for API access.
            opts: Resource options.
        """
        if args is None:
            args = {}
            
        # Ensure template_id is set
        if template_id is not None:
            args['template_id'] = template_id
        elif 'template_id' not in args:
            raise ValueError("template_id is required")
        
        # Set resource name
        args['name'] = name
        
        # Add provider configuration to args if available
        if provider:
            provider_config = provider.get_config()
            for key, value in provider_config.items():
                if value is not None and key not in args:
                    args[key] = value
        
        # Initialize the dynamic resource
        super().__init__(
            VMProvider(),
            name,
            args,
            opts
        ) 