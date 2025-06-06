# SSH Infrastructure Scripts

This directory contains utility scripts for setting up SSH tunneling infrastructure.

## Scripts

### SSH Tunnel Server Setup (`ssh_tunnel_server_setup.sh`)

Configures an SSH server to accept passwordless tunnel connections from a specific user.

**Usage:**
```bash
sudo ./ssh_tunnel_server_setup.sh [tunnel_username]
```

**Parameters:**
- `tunnel_username`: Optional. The username for tunnel connections (default: "tunnel")

**Features:**
- Creates a dedicated user for SSH tunneling
- Configures SSH server to allow passwordless authentication for this user
- Enables TCP forwarding and gateway ports
- Makes settings persisting across reboots

**Example:**
```bash
# Set up with default username "tunnel"
sudo ./ssh_tunnel_server_setup.sh

# Set up with custom username "proxy-user"
sudo ./ssh_tunnel_server_setup.sh proxy-user
```

### SSH Tunnel Setup (`ssh_tunnel_setup.sh`)

Creates a persistent SSH tunnel from a local port to a remote port on an SSH tunnel server.

**Usage:**
```bash
sudo ./ssh_tunnel_setup.sh <server_address> <local_port> <remote_port> [username]
```

**Parameters:**
- `server_address`: IP address, hostname, or domain of the SSH tunnel server
- `local_port`: Local port to be forwarded (on localhost)
- `remote_port`: Remote port to expose on the SSH tunnel server
- `username`: Optional username for SSH connection (default: "tunnel")

**Features:**
- Creates a systemd service for a persistent SSH tunnel
- Automatically restarts the tunnel if it fails
- Idempotent (won't create duplicate tunnels)
- Provides status feedback

**Example:**
```bash
# Expose local port 8080 as port 80 on the server
sudo ./ssh_tunnel_setup.sh tunnel-server.example.com 8080 80

# Expose local port 3389 as port 3389 on the server with custom username
sudo ./ssh_tunnel_setup.sh 10.0.0.1 3389 3389 myuser
```

### Serveo Tunnel Setup (`serveo_setup.sh`)

Sets up an HTTP web service tunnel using Serveo.

**Usage:**
```bash
./serveo_setup.sh [command]
```

**Commands:**
- `setup`: Set up a new Serveo tunnel
- `status`: Check if tunnel is running
- `info`: Extract connection information
- `ensure`: Ensure tunnel is running, restart if needed
- `help`: Show usage information (default)

**Environment Variables:**
- `WEB_SERVICE_LOCALHOST_PORT`: Local web service port to forward (default: 8080)
- `LOG_FILE`: Log file location (default: /tmp/serveo_output.txt)

**Example:**
```bash
# Set up with default settings (port 8080)
./serveo_setup.sh setup

# Set up with custom port
WEB_SERVICE_LOCALHOST_PORT=3000 ./serveo_setup.sh setup

# Check tunnel status
./serveo_setup.sh status
```

## Using with Terraform

These scripts can be used with the Terraform infrastructure by:

1. Store the repository file at a publicly accessible URL
2. Configure your Terraform variables:
   ```hcl
   scripts_repository_url = "https://example.com/path/to/repository.txt"
   script_aliases = ["ssh-tunnel-server", "serveo-tunnel"]
   ```

The EC2 instance will automatically download and execute these scripts during initialization.
