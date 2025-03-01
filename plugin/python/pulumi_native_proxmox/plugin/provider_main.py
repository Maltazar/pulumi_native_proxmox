#!/usr/bin/env python3
"""
Pulumi Provider Entry Point

This script is the main entry point for the Pulumi provider. It starts
the gRPC server that Pulumi will connect to.
"""

import os
import sys
import logging
import argparse
from .resource_provider import start_provider_server


def main():
    """Main entry point."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Pulumi Proxmox Provider')
    parser.add_argument('--port', type=int, default=0, help='Port to listen on (0 for dynamic)')
    parser.add_argument('--log-level', type=str, default='INFO', 
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Logging level')
    args = parser.parse_args()
    
    # Configure logging
    log_level = getattr(logging, args.log_level)
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger('pulumi-provider-proxmox')
    
    try:
        # Start the server
        port = start_provider_server(args.port)
        
        # Print the port number for Pulumi to connect to
        print(port)
        sys.stdout.flush()
        
        # Keep the program running until interrupted
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down provider server")
            
    except Exception as e:
        logger.error(f"Error starting provider server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 