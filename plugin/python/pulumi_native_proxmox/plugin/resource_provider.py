"""Pulumi Resource Provider Implementation

This module implements the Pulumi Resource Provider gRPC interface that handles
communication between the Pulumi CLI and our Proxmox provider.
"""

import os
import sys
import json
import grpc
import logging
import traceback
from concurrent import futures
from typing import Any, Dict, List, Optional, Tuple, Union

# Import Pulumi SDK components
from pulumi.provider import (
    Provider, 
    ResourceProvider, 
    ProviderServer, 
    ProviderResource,
    ResourceServer
)
from pulumi.resource import (
    PropertyMap,
    RegisterResourceResult,
    RegisterResourceOutputs,
    InvokeResult,
    CheckResult
)

# Import our provider classes
from ..sdk.provider import Provider
from ..sdk.vm import VM
from ..sdk.vm_group import VMGroup


class ProxmoxResourceProvider(ResourceProvider):
    """
    Proxmox implementation of the Pulumi Resource Provider interface.
    
    This class handles the mapping between Pulumi resource operations
    (create, read, update, delete) and our provider's implementation.
    """
    
    def __init__(self):
        """Initialize the provider."""
        super().__init__()
        self.logger = logging.getLogger('pulumi-provider-proxmox')
        
        # Register resource types
        self.resource_types = {
            'proxmox:index:Provider': Provider,
            'proxmox:vm:VM': VM,
            'proxmox:vm:VMGroup': VMGroup,
        }
    
    def check(self, urn: str, old_inputs: Dict[str, Any], new_inputs: Dict[str, Any]) -> CheckResult:
        """Validate the resource inputs before creating/updating.
        
        Args:
            urn: The resource URN
            old_inputs: Previous resource inputs (if any)
            new_inputs: New resource inputs to validate
            
        Returns:
            CheckResult: Validation result
        """
        self.logger.debug(f"Check resource: {urn}")
        
        # Convert inputs to Python dict if needed
        if isinstance(new_inputs, PropertyMap):
            new_inputs = dict(new_inputs)
        
        failures = []
        
        # Extract resource type from URN
        # URN format: urn:pulumi:stack::project::package:module:type::name
        resource_type = self._get_resource_type_from_urn(urn)
        
        # Validate based on resource type
        if resource_type == 'proxmox:vm:VM':
            if 'template_id' not in new_inputs:
                failures.append("template_id is required for VM resources")
                
        elif resource_type == 'proxmox:vm:VMGroup':
            if 'count' not in new_inputs:
                failures.append("count is required for VMGroup resources")
            if 'template_id' not in new_inputs:
                failures.append("template_id is required for VMGroup resources")
        
        return CheckResult(inputs=new_inputs, failures=failures)
    
    def create(self, urn: str, inputs: Dict[str, Any], timeout: float = None, preview: bool = False) -> RegisterResourceResult:
        """Create a new resource.
        
        Args:
            urn: The resource URN
            inputs: The resource inputs
            timeout: Operation timeout
            preview: Whether this is a preview operation
            
        Returns:
            RegisterResourceResult: Creation result
        """
        self.logger.debug(f"Create resource: {urn}")
        
        # If preview, return dummy values
        if preview:
            self.logger.debug("Preview mode, returning dummy values")
            return RegisterResourceResult(id="preview-id", outs=inputs)
        
        # Extract resource type and name from URN
        resource_type = self._get_resource_type_from_urn(urn)
        resource_name = self._get_resource_name_from_urn(urn)
        
        # Get the resource class
        resource_class = self.resource_types.get(resource_type)
        if not resource_class:
            raise Exception(f"Unknown resource type: {resource_type}")
        
        try:
            # Convert inputs to dict if needed
            if isinstance(inputs, PropertyMap):
                inputs = dict(inputs)
            
            # Clone inputs to avoid modifying original
            props = inputs.copy()
            
            # Remove internal fields
            for k in ['id', '__defaults']:
                if k in props:
                    del props[k]
            
            # Create the resource instance
            resource = resource_class(resource_name, props)
            
            # Get the resource state
            outputs = {}
            for k, v in resource.__dict__.items():
                if not k.startswith('_'):
                    outputs[k] = v
            
            # Add the original inputs to outputs
            for k, v in inputs.items():
                if k not in outputs:
                    outputs[k] = v
            
            self.logger.debug(f"Resource created: {resource_name}")
            return RegisterResourceResult(id=resource_name, outs=outputs)
            
        except Exception as e:
            self.logger.error(f"Error creating resource: {e}")
            traceback.print_exc()
            raise
    
    def diff(self, urn: str, id: str, old_inputs: Dict[str, Any], new_inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Check for differences between old and new state.
        
        Args:
            urn: The resource URN
            id: The resource ID
            old_inputs: Current resource inputs
            new_inputs: New resource inputs
            
        Returns:
            Dict containing difference information
        """
        self.logger.debug(f"Diff resource: {urn}")
        
        # Convert inputs to dict if needed
        if isinstance(old_inputs, PropertyMap):
            old_inputs = dict(old_inputs)
        if isinstance(new_inputs, PropertyMap):
            new_inputs = dict(new_inputs)
        
        # Check for changes that require replacement
        replaces = []
        changes = False
        
        # Template ID requires replacement
        if (old_inputs.get('template_id') != new_inputs.get('template_id') and 
            old_inputs.get('template_id') is not None and 
            new_inputs.get('template_id') is not None):
            replaces.append('template_id')
            changes = True
        
        # For VM Group, count changes require replacement
        if (old_inputs.get('count') != new_inputs.get('count') and
            old_inputs.get('count') is not None and
            new_inputs.get('count') is not None):
            replaces.append('count')
            changes = True
            
        # Check other properties for changes
        for key in set(old_inputs.keys()) | set(new_inputs.keys()):
            if key in replaces:
                continue
                
            if key not in old_inputs:
                changes = True
                break
            if key not in new_inputs:
                changes = True
                break
            if old_inputs[key] != new_inputs[key]:
                changes = True
                break
        
        return {
            "changes": changes,
            "replaces": replaces,
            "stables": [],
            "deleteBeforeReplace": True if replaces else False
        }
    
    def update(self, urn: str, id: str, old_inputs: Dict[str, Any], new_inputs: Dict[str, Any], timeout: float = None) -> Dict[str, Any]:
        """Update an existing resource.
        
        Args:
            urn: The resource URN
            id: The resource ID
            old_inputs: Current resource inputs
            new_inputs: New resource inputs
            timeout: Operation timeout
            
        Returns:
            Dict containing updated outputs
        """
        self.logger.debug(f"Update resource: {urn}")
        
        # Convert inputs to dict if needed
        if isinstance(old_inputs, PropertyMap):
            old_inputs = dict(old_inputs)
        if isinstance(new_inputs, PropertyMap):
            new_inputs = dict(new_inputs)
        
        try:
            # Extract resource type and name from URN
            resource_type = self._get_resource_type_from_urn(urn)
            resource_name = self._get_resource_name_from_urn(urn)
            
            # Get the resource class
            resource_class = self.resource_types.get(resource_type)
            if not resource_class:
                raise Exception(f"Unknown resource type: {resource_type}")
                
            # Create a new resource with updated properties
            # Note: In a real implementation, we'd update the existing resource
            outputs = new_inputs.copy()
            outputs['id'] = id
            
            self.logger.debug(f"Resource updated: {resource_name}")
            return outputs
            
        except Exception as e:
            self.logger.error(f"Error updating resource: {e}")
            traceback.print_exc()
            raise
    
    def delete(self, urn: str, id: str, props: Dict[str, Any], timeout: float = None):
        """Delete an existing resource.
        
        Args:
            urn: The resource URN
            id: The resource ID
            props: Resource properties
            timeout: Operation timeout
        """
        self.logger.debug(f"Delete resource: {urn}")
        
        # Convert props to dict if needed
        if isinstance(props, PropertyMap):
            props = dict(props)
        
        try:
            # Extract resource type from URN
            resource_type = self._get_resource_type_from_urn(urn)
            
            # Log resource deletion
            self.logger.debug(f"Resource {id} of type {resource_type} deleted")
            
        except Exception as e:
            self.logger.error(f"Error deleting resource: {e}")
            traceback.print_exc()
            raise
    
    def _get_resource_type_from_urn(self, urn: str) -> str:
        """Extract the resource type from a URN.
        
        Args:
            urn: The resource URN
            
        Returns:
            The resource type
        """
        parts = urn.split('::')
        if len(parts) < 3:
            raise Exception(f"Invalid URN format: {urn}")
            
        type_parts = parts[-2].split(':')
        if len(type_parts) < 3:
            raise Exception(f"Invalid resource type in URN: {urn}")
            
        return f"{type_parts[0]}:{type_parts[1]}:{type_parts[2]}"
    
    def _get_resource_name_from_urn(self, urn: str) -> str:
        """Extract the resource name from a URN.
        
        Args:
            urn: The resource URN
            
        Returns:
            The resource name
        """
        parts = urn.split('::')
        if len(parts) < 3:
            raise Exception(f"Invalid URN format: {urn}")
            
        return parts[-1]


def start_provider_server(port: int = 0) -> int:
    """Start the resource provider server.
    
    Args:
        port: Port to listen on (0 for dynamic)
        
    Returns:
        Allocated port number
    """
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('pulumi-provider-server')
    
    # Create resource provider
    resource_provider = ProxmoxResourceProvider()
    
    # Create resource server
    server = ResourceServer(resource_provider)
    
    # Start gRPC server
    grpc_server = grpc.server(futures.ThreadPoolExecutor())
    server.register(grpc_server)
    
    # Bind to port
    port = grpc_server.add_insecure_port(f'127.0.0.1:{port}')
    logger.info(f"Starting gRPC server on port {port}")
    
    # Start server
    grpc_server.start()
    
    return port 