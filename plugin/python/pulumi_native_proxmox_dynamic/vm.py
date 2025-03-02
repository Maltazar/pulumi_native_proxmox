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
from typing import Any, Dict, List, Optional, Union

from .proxmox_client import ProxmoxClient


class VMProvider(pulumi.dynamic.ResourceProvider):
    """Dynamic resource provider for Proxmox VMs."""
    
    def create(self, props: Dict[str, Any]) -> pulumi.dynamic.CreateResult:
        """Create a new VM in Proxmox.
        
        Args:
            props: Resource properties
            
        Returns:
            CreateResult with VM ID and other properties
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
        
        # Clone the template
        self._clone_template(client, node, template_id, vmid, props)
        
        # Configure VM
        self._configure_vm(client, node, vmid, props)
        
        # Start VM if requested
        if props.get('start_on_create', True):
            self._start_vm(client, node, vmid)
            
            # Wait for VM to be ready if requested
            if props.get('wait_for_ssh', False):
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
        node, vmid = id.split('/')
        vmid = int(vmid)
        
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
            'status': vm_status.get('status', 'unknown'),
            'name': vm_config.get('name', ''),
            'cores': vm_config.get('cores', 1),
            'memory': vm_config.get('memory', 512),
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
        node, vmid = id.split('/')
        vmid = int(vmid)
        
        client = self._get_client(news)
        
        # Determine if we need to stop the VM to apply changes
        requires_stop = False
        
        # These properties require the VM to be stopped
        stop_required_props = ['cores', 'sockets', 'memory']
        
        for prop in stop_required_props:
            if prop in news and prop in olds and news[prop] != olds[prop]:
                requires_stop = True
                break
        
        # Get VM status
        vm_status = client.request('GET', f'/nodes/{node}/qemu/{vmid}/status/current')
        was_running = vm_status.get('status') == 'running'
        
        # Stop VM if needed
        if requires_stop and was_running:
            client.request('POST', f'/nodes/{node}/qemu/{vmid}/status/stop')
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
            client.request(
                'POST',
                f'/nodes/{node}/qemu/{vmid}/config',
                data=config_updates
            )
        
        # Disk size update (can be done while VM is running in newer Proxmox versions)
        if 'disk_size' in news and news['disk_size'] != olds.get('disk_size'):
            client.request(
                'PUT',
                f'/nodes/{node}/qemu/{vmid}/resize',
                params={
                    'disk': 'scsi0',
                    'size': news['disk_size'],
                }
            )
        
        # Restart VM if it was running before
        if requires_stop and was_running:
            client.request('POST', f'/nodes/{node}/qemu/{vmid}/status/start')
            self._wait_for_vm_state(client, node, vmid, 'running')
        
        return pulumi.dynamic.UpdateResult(outs=news)
    
    def delete(self, id: str, props: Dict[str, Any]) -> None:
        """Delete a VM from Proxmox.
        
        Args:
            id: Resource ID
            props: Resource properties
        """
        # Parse VM ID from resource ID
        node, vmid = id.split('/')
        vmid = int(vmid)
        
        client = self._get_client(props)
        
        # Get VM status
        vm_status = client.request('GET', f'/nodes/{node}/qemu/{vmid}/status/current')
        
        # Stop VM if running
        if vm_status.get('status') == 'running':
            client.request('POST', f'/nodes/{node}/qemu/{vmid}/status/stop')
            
            # Wait for VM to stop
            self._wait_for_vm_state(client, node, vmid, 'stopped')
        
        # Delete VM
        client.request('DELETE', f'/nodes/{node}/qemu/{vmid}')
    
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
        client.request(
            'POST',
            f'/nodes/{node}/qemu/{template_id}/clone',
            data=clone_params
        )
        
        # Wait for clone to complete
        self._wait_for_task_completion(client, node)
    
    def _configure_vm(self, client: ProxmoxClient, node: str, vmid: int, 
                     props: Dict[str, Any]) -> None:
        """Configure a VM after cloning.
        
        Args:
            client: ProxmoxClient instance
            node: Proxmox node
            vmid: VM ID
            props: Resource properties
        """
        # Build configuration object
        config = {}
        
        # Compute resources
        if props.get('cores'):
            config['cores'] = props.get('cores')
        if props.get('sockets'):
            config['sockets'] = props.get('sockets')
        if props.get('memory'):
            config['memory'] = props.get('memory')
        
        # Disk configuration
        if props.get('disk_size'):
            # Resize disk
            client.request(
                'PUT',
                f'/nodes/{node}/qemu/{vmid}/resize',
                params={
                    'disk': 'scsi0',
                    'size': props.get('disk_size'),
                }
            )
        
        # Network configuration
        if props.get('network_bridge') or props.get('vlan_tag'):
            net_config = f'model=virtio,bridge={props.get("network_bridge", "vmbr0")}'
            if props.get('vlan_tag'):
                net_config += f',tag={props.get("vlan_tag")}'
            config['net0'] = net_config
        
        # Cloud-init configuration
        if props.get('cloud_init_user'):
            config['ciuser'] = props.get('cloud_init_user')
        if props.get('cloud_init_password'):
            config['cipassword'] = props.get('cloud_init_password')
        
        # Handle SSH key for cloud-init
        ssh_key = props.get('cloud_init_ssh_public_key')
        if ssh_key:
            # If ssh_key is a file path, read it
            if ssh_key.startswith('/') and os.path.exists(ssh_key):
                with open(ssh_key, 'r') as f:
                    ssh_key = f.read().strip()
            config['sshkeys'] = ssh_key.replace('\n', '\\n')
        
        # Enable Proxmox agent if requested in VM setup features
        vm_setup_features = props.get('vm_setup_features', [])
        if isinstance(vm_setup_features, str):
            vm_setup_features = [vm_setup_features]
            
        if 'proxmox_agent' in vm_setup_features:
            config['agent'] = 1
        
        # Apply configuration if any
        if config:
            client.request(
                'POST',
                f'/nodes/{node}/qemu/{vmid}/config',
                data=config
            )
    
    def _start_vm(self, client: ProxmoxClient, node: str, vmid: int) -> None:
        """Start a VM.
        
        Args:
            client: ProxmoxClient instance
            node: Proxmox node
            vmid: VM ID
        """
        client.request('POST', f'/nodes/{node}/qemu/{vmid}/status/start')
        self._wait_for_vm_state(client, node, vmid, 'running')
    
    def _wait_for_vm_state(self, client: ProxmoxClient, node: str, vmid: int, 
                          state: str, timeout: int = 300) -> None:
        """Wait for VM to reach a specific state.
        
        Args:
            client: ProxmoxClient instance
            node: Proxmox node
            vmid: VM ID
            state: Target state
            timeout: Timeout in seconds
        """
        start_time = time.time()
        while True:
            vm_status = client.request('GET', f'/nodes/{node}/qemu/{vmid}/status/current')
            if vm_status.get('status') == state:
                return
            
            if time.time() - start_time > timeout:
                raise Exception(f"Timeout waiting for VM {vmid} to reach state {state}")
            
            time.sleep(5)
    
    def _wait_for_ip_address(self, client: ProxmoxClient, node: str, vmid: int, 
                           timeout: int = 300) -> Optional[str]:
        """Wait for VM to get an IP address.
        
        Args:
            client: ProxmoxClient instance
            node: Proxmox node
            vmid: VM ID
            timeout: Timeout in seconds
            
        Returns:
            IP address if found, None otherwise
        """
        start_time = time.time()
        
        # First check if VM has agent enabled
        config = client.request('GET', f'/nodes/{node}/qemu/{vmid}/config')
        if config.get('agent', 0) == 1:
            # Try to get IP via agent
            while True:
                try:
                    agent_info = client.request('GET', f'/nodes/{node}/qemu/{vmid}/agent/network-get-interfaces')
                    # Extract IP addresses
                    for iface in agent_info.get('result', []):
                        if 'ip-addresses' in iface:
                            for addr in iface['ip-addresses']:
                                if addr.get('ip-address') and addr.get('ip-address-type') == 'ipv4':
                                    return addr.get('ip-address')
                except Exception:
                    # Agent might not be available yet
                    pass
                
                if time.time() - start_time > timeout:
                    break
                
                time.sleep(5)
        
        # Fallback to using DHCP leases if agent isn't available
        # This requires the VM to be using a bridge on the Proxmox host
        vm_name = config.get('name')
        network_bridge = None
        
        # Find the bridge from the VM config
        for key, value in config.items():
            if key.startswith('net') and 'bridge=' in value:
                parts = value.split(',')
                for part in parts:
                    if part.startswith('bridge='):
                        network_bridge = part.split('=')[1]
                        break
                if network_bridge:
                    break
        
        if network_bridge:
            while True:
                # Try to get DHCP leases
                try:
                    leases = client.request('GET', f'/nodes/{node}/network/{network_bridge}/dhcp')
                    for lease in leases:
                        if lease.get('hostname') == vm_name:
                            return lease.get('ip')
                except Exception:
                    # DHCP leases might not be available
                    pass
                
                if time.time() - start_time > timeout:
                    break
                
                time.sleep(5)
        
        return None
    
    def _setup_vm(self, client: ProxmoxClient, node: str, vmid: int, 
                 ip_address: Optional[str], props: Dict[str, Any]) -> None:
        """Set up a VM after it has been created and started.
        
        Args:
            client: ProxmoxClient instance
            node: Proxmox node
            vmid: VM ID
            ip_address: VM IP address
            props: Resource properties
        """
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
        
        # Connect to the VM
        try:
            # Try to connect with SSH key if provided
            if ssh_key_path:
                # If the ssh_key is a file path, read it
                key_data = None
                if ssh_key_path.startswith('/') and os.path.exists(ssh_key_path):
                    with open(ssh_key_path, 'rb') as f:
                        key_data = f.read()
                else:
                    # Assume it's the actual key data
                    key_data = ssh_key_path.encode('utf-8')
                
                key = paramiko.RSAKey.from_private_key(
                    paramiko.PKey.from_private_key_data(key_data, 
                                                      password=props.get('cloud_init_ssh_key_passphrase'))
                )
                ssh.connect(ip_address, username=username, pkey=key)
            else:
                # Connect with password
                ssh.connect(ip_address, username=username, password=password)
            
            # Install Proxmox agent if requested
            vm_setup_features = props.get('vm_setup_features', [])
            if isinstance(vm_setup_features, str):
                vm_setup_features = [vm_setup_features]
                
            if 'proxmox_agent' in vm_setup_features:
                # Install Proxmox agent
                stdin, stdout, stderr = ssh.exec_command('sudo apt-get update && sudo apt-get install -y qemu-guest-agent')
                stdout.channel.recv_exit_status()
                
                # Enable and start the agent
                stdin, stdout, stderr = ssh.exec_command('sudo systemctl enable qemu-guest-agent && sudo systemctl start qemu-guest-agent')
                stdout.channel.recv_exit_status()
            
            # Create admin user if requested
            if props.get('vm_user_create_admin_user', False) and props.get('vm_user_username'):
                admin_user = props.get('vm_user_username')
                
                # Create user
                stdin, stdout, stderr = ssh.exec_command(f'sudo useradd -m -s /bin/bash {admin_user}')
                stdout.channel.recv_exit_status()
                
                # Add to sudo group
                stdin, stdout, stderr = ssh.exec_command(f'sudo usermod -aG sudo {admin_user}')
                stdout.channel.recv_exit_status()
                
                # Configure SSH key if provided
                admin_ssh_key = props.get('vm_user_ssh_public_key')
                if admin_ssh_key:
                    # If the ssh_key is a file path, read it
                    if admin_ssh_key.startswith('/') and os.path.exists(admin_ssh_key):
                        with open(admin_ssh_key, 'r') as f:
                            admin_ssh_key = f.read().strip()
                    
                    # Create .ssh directory
                    stdin, stdout, stderr = ssh.exec_command(f'sudo mkdir -p /home/{admin_user}/.ssh')
                    stdout.channel.recv_exit_status()
                    
                    # Add the key
                    stdin, stdout, stderr = ssh.exec_command(f'echo "{admin_ssh_key}" | sudo tee /home/{admin_user}/.ssh/authorized_keys')
                    stdout.channel.recv_exit_status()
                    
                    # Set permissions
                    stdin, stdout, stderr = ssh.exec_command(f'sudo chown -R {admin_user}:{admin_user} /home/{admin_user}/.ssh')
                    stdout.channel.recv_exit_status()
                    stdin, stdout, stderr = ssh.exec_command(f'sudo chmod 700 /home/{admin_user}/.ssh')
                    stdout.channel.recv_exit_status()
                    stdin, stdout, stderr = ssh.exec_command(f'sudo chmod 600 /home/{admin_user}/.ssh/authorized_keys')
                    stdout.channel.recv_exit_status()
            
            # Execute custom setup commands if provided
            vm_setup_commands = props.get('vm_setup_commands', [])
            if isinstance(vm_setup_commands, str):
                vm_setup_commands = [vm_setup_commands]
                
            for cmd in vm_setup_commands:
                stdin, stdout, stderr = ssh.exec_command(cmd)
                stdout.channel.recv_exit_status()
            
            # Execute custom setup scripts if provided
            vm_setup_scripts = props.get('vm_setup_scripts', [])
            if isinstance(vm_setup_scripts, str):
                vm_setup_scripts = [vm_setup_scripts]
                
            for script in vm_setup_scripts:
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
                stdin, stdout, stderr = ssh.exec_command(f'echo "{script_content}" > {temp_filename}')
                stdout.channel.recv_exit_status()
                
                # Make it executable
                stdin, stdout, stderr = ssh.exec_command(f'chmod +x {temp_filename}')
                stdout.channel.recv_exit_status()
                
                # Execute it
                stdin, stdout, stderr = ssh.exec_command(f'sudo {temp_filename}')
                stdout.channel.recv_exit_status()
                
                # Clean up
                stdin, stdout, stderr = ssh.exec_command(f'rm {temp_filename}')
                stdout.channel.recv_exit_status()
        finally:
            ssh.close()
    
    def _wait_for_ssh(self, ip_address: str, username: str, password: Optional[str], 
                    ssh_key_path: Optional[str], ssh_key_passphrase: Optional[str], 
                    timeout: int = 300) -> None:
        """Wait for SSH to become available on a VM.
        
        Args:
            ip_address: VM IP address
            username: SSH username
            password: SSH password
            ssh_key_path: Path to SSH private key
            ssh_key_passphrase: Passphrase for SSH private key
            timeout: Timeout in seconds
        """
        start_time = time.time()
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        while True:
            try:
                # Try to connect with SSH key if provided
                if ssh_key_path:
                    # If the ssh_key is a file path, read it
                    key_data = None
                    if ssh_key_path.startswith('/') and os.path.exists(ssh_key_path):
                        with open(ssh_key_path, 'rb') as f:
                            key_data = f.read()
                    else:
                        # Assume it's the actual key data
                        key_data = ssh_key_path.encode('utf-8')
                    
                    key = paramiko.RSAKey.from_private_key(
                        paramiko.PKey.from_private_key_data(key_data, 
                                                          password=ssh_key_passphrase)
                    )
                    ssh.connect(ip_address, username=username, pkey=key, timeout=10)
                else:
                    # Connect with password
                    ssh.connect(ip_address, username=username, password=password, timeout=10)
                
                # If we get here, connection succeeded
                ssh.close()
                return
            except Exception:
                # Connection failed, wait and try again
                if time.time() - start_time > timeout:
                    raise Exception(f"Timeout waiting for SSH on {ip_address}")
                
                time.sleep(5)
    
    def _wait_for_task_completion(self, client: ProxmoxClient, node: str, 
                                 timeout: int = 300) -> None:
        """Wait for all tasks on a node to complete.
        
        Args:
            client: ProxmoxClient instance
            node: Proxmox node
            timeout: Timeout in seconds
        """
        # In a real implementation, we would track the specific task ID
        # This is a simplified version
        start_time = time.time()
        
        while True:
            # List running tasks
            tasks = client.request('GET', f'/nodes/{node}/tasks')
            
            # Filter for running tasks
            running_tasks = [t for t in tasks if t.get('status') == 'running']
            
            # If no running tasks, we're done
            if not running_tasks:
                return
            
            # Check timeout
            if time.time() - start_time > timeout:
                raise Exception(f"Timeout waiting for tasks to complete on node {node}")
            
            # Wait and check again
            time.sleep(5)


class VM(pulumi.dynamic.Resource):
    """A Proxmox VM resource."""
    
    def __init__(self,
                 name: str,
                 template_id: str,
                 args: Optional[Dict[str, Any]] = None,
                 opts: Optional[pulumi.ResourceOptions] = None):
        """Create a new VM resource.
        
        Args:
            name: The unique name for the VM resource.
            template_id: The template ID to clone from.
            args: Additional arguments to configure the VM.
            opts: Resource options.
        """
        if args is None:
            args = {}
            
        # Ensure template_id is set
        args['template_id'] = template_id
        
        # Set resource name
        args['name'] = name
        
        # Initialize the dynamic resource
        super().__init__(
            VMProvider(),
            name,
            args,
            opts
        ) 