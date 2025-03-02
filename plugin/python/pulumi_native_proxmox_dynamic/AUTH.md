# Authentication with the Proxmox Provider

The Proxmox provider supports two authentication methods:

1. Username/Password Authentication
2. API Token Authentication

You only need to configure **one** of these methods in your Pulumi configuration.

## Username/Password Authentication

This is the simplest method to get started. Configure your `Pulumi.yaml` or `Pulumi.<stack>.yaml` file with:

```yaml
config:
  pulumi-native-proxmox-dynamic:endpoint: https://your-proxmox-host:8006/api2/json
  pulumi-native-proxmox-dynamic:username: root@pam
  pulumi-native-proxmox-dynamic:password:
    secure: YOUR_ENCRYPTED_PASSWORD
  # Other configuration options...
```

Make sure to use `pulumi config set --secret pulumi-native-proxmox-dynamic:password YOUR_PASSWORD` to securely store your password.

## API Token Authentication

For better security, you can use API tokens instead of your username/password:

```yaml
config:
  pulumi-native-proxmox-dynamic:endpoint: https://your-proxmox-host:8006/api2/json
  pulumi-native-proxmox-dynamic:token_id: your-user@pam!token-name
  pulumi-native-proxmox-dynamic:token_secret:
    secure: YOUR_ENCRYPTED_TOKEN_SECRET
  # Other configuration options...
```

Use `pulumi config set --secret pulumi-native-proxmox-dynamic:token_secret YOUR_TOKEN_SECRET` to securely store your token secret.

## Important Notes

1. DO NOT configure both authentication methods at the same time. The provider will prioritize token-based authentication if both methods are provided.

2. Make sure your Proxmox user has the necessary privileges to perform the operations you need.

3. If you get authentication errors, enable debug mode with:
   ```yaml
   config:
     pulumi-native-proxmox-dynamic:debug: true
   ```

4. For self-signed certificates, you can set `insecure: true` to skip SSL verification:
   ```yaml
   config:
     pulumi-native-proxmox-dynamic:insecure: true
   ```

## Troubleshooting Authentication Issues

If you encounter authentication issues, try the following steps:

1. **Verify your credentials**: Make sure your username, password, or token credentials are correct.

2. **Check the endpoint URL**: Ensure the endpoint URL is correct and includes the full path to the API (`/api2/json`).

3. **Test authentication directly**: Use the included `test_pulumi_auth.py` script to test your authentication:
   ```bash
   python3 test_pulumi_auth.py
   ```

4. **Check SSL settings**: If your Proxmox server uses a self-signed certificate, make sure to set `insecure: true`.

5. **Verify user permissions**: Ensure the user or token has the necessary permissions in Proxmox.

6. **Check for empty values**: Make sure your password or token secret is not empty. Use the following command to set a new password:
   ```bash
   pulumi config set --secret pulumi-native-proxmox-dynamic:password
   ```

## Creating a Proxmox API Token

1. Log in to the Proxmox web interface
2. Navigate to Datacenter → Permissions → API Tokens
3. Click "Add" to create a new token
4. Select the user, provide a token ID, and decide whether to enable privilege separation
5. Click "Add" and securely save the displayed token secret (it will only be shown once)

Remember that the token format is: `USER@REALM!TOKENID` 