# Features

- uses Pulumi SDK
- uses Proxmox API
- uses Python 3.12+

- use an interface to access the Proxmox API

VM Creation

- Clone VM Template
- Configure new VM
    - Configure Network, VLAN Tag, IP etc.
    - Configure Disks - Expand, Move to other datastore.
- Start VM
- Wait for VM to come up
- SSH into VM to install the Proxmox Agent

VM Destroy

- Force STOP VM
- Delete VM


## MAIN Design!

1. The pulumi_native_proxmox package should be a proper Pulumi provider plugin that:
 - Implements the gRPC interface required by Pulumi
 - Handles all resource operations (CRUD)
 - Contains all the Proxmox API logic
 - Can be installed directly via pulumi plugin install

## Folder Structure

```
pulumi_native_proxmox/
├── examples/             # Example Pulumi programs using the provider
├── plugin/
│   └── python/
│       └── pulumi_native_proxmox/  # Main provider package
```

## Config Idea

```yaml
config:
  # HOST access
  proxmox:endpoint: https://10.1.1.230:8006/api2/json
  proxmox:username: root@pam
  proxmox:password:
    secure: ******
  proxmox:token:
    secure: ******
  proxmox:node: pvehost
  proxmox:insecure: "true"

  # VM Setup
  vm:template: "9001"
  vm:cores: "2"
  vm:memory: "4096"
  vm:disk_size: 15G
  vm:network_bridge: vmbr0
  vm:disk_storage: nvme4tb
  vm:vlan_tag: "140"

  # cloud init initial user, to get access to the vm when it starts
  cloud_init:username: initial
  cloud_init:ssh_public_key: /home/ms/.ssh/id_rsa_initial.pub
  cloud_init:ssh_private_key: /home/ms/.ssh/id_rsa_initial
    # If not path
    secure: ****
  cloud_init:ssh_key_passphrase:
    secure: ****

  # New user after VM is created.
  vm_user:create_admin_user: "true"
  vm_user:ssh_public_key: /home/ms/.ssh/id_rsa_k3s.pub
  vm_user:ssh_private_key: /home/ms/.ssh/id_rsa_k3s.pub
    # If not path
    secure: ****
  vm_user:username: k3s
  vm_user:ssh_key_passphrase:
    secure: ****

  # VM Groups - to generate multiple VMs - can have one or more groups
  # This is not complete yet - somehow I think there are something missing, maybe disk or vlan id should be here to.
  create:
  - prefix: master
    count: 3
    ip_range: 10.1.20.80-10.1.20.85
    vm_start_id: 800
  
  - prefix: worker
    count: 3
    ip_range: 10.1.20.86-10.1.20.90
    vm_start_id: 810

  vm_setup:
    features:
      - proxmox_agent
    scripts:
      - path/url
    commands:
      - echo hello world
```


Pulumi Python and Toolchain

```yaml
runtime:
  name: python
  options:
    toolchain: uv
    virtualenv: .venv
```