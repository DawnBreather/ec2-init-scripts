#!/bin/bash
# SSH Empty-password Tunnel Configuration Script

# Default values
TUNNEL_USER="tunnel"

# Parse named parameters
while [ $# -gt 0 ]; do
  case "$1" in
    --user=*)
      TUNNEL_USER="${1#*=}"
      ;;
    --user)
      TUNNEL_USER="$2"
      shift
      ;;
    *)
      echo "Unknown parameter: $1"
      echo "Usage: $0 [--user=username]"
      exit 1
      ;;
  esac
  shift
done

# Ensure script is run as root
if [ "$(id -u)" -ne 0 ]; then
   echo "This script must be run as root" 
   exit 1
fi

# Function to update sshd config
configure_ssh_server() {
    local config_file="/etc/ssh/sshd_config"
    local need_restart=false
    
    echo "Configuring SSH server for empty-password tunneling..."
    
    # Allow SSH tunnels globally
    if ! grep -q "^AllowTcpForwarding yes" "$config_file"; then
        if grep -q "^#AllowTcpForwarding" "$config_file"; then
            sed -i 's/^#AllowTcpForwarding.*/AllowTcpForwarding yes/' "$config_file"
        else
            echo "AllowTcpForwarding yes" >> "$config_file"
        fi
        need_restart=true
    fi
    
    # Enable GatewayPorts to allow remote connections to forwarded ports
    if ! grep -q "^GatewayPorts yes" "$config_file"; then
        if grep -q "^#GatewayPorts" "$config_file"; then
            sed -i 's/^#GatewayPorts.*/GatewayPorts yes/' "$config_file"
        else
            echo "GatewayPorts yes" >> "$config_file"
        fi
        need_restart=true
    fi
    
    # Create tunnel user configuration with empty password auth
    if ! grep -q "^Match User $TUNNEL_USER" "$config_file"; then
        cat >> "$config_file" << EOF

# Special tunnel user configuration
Match User $TUNNEL_USER
    PasswordAuthentication yes
    PermitEmptyPasswords yes
    AllowTcpForwarding yes
    GatewayPorts yes
    PubkeyAuthentication no
    PermitRootLogin no
EOF
        need_restart=true
    fi
    
    # Restart SSH server if needed
    if [ "$need_restart" = true ]; then
        echo "Restarting SSH server to apply changes..."
        systemctl restart sshd
    fi
}

# Function to create tunnel user
create_tunnel_user() {
    if ! id -u "$TUNNEL_USER" > /dev/null 2>&1; then
        echo "Creating tunnel user: $TUNNEL_USER..."
        useradd -m "$TUNNEL_USER"
        
        # Remove password authentication
        passwd -d "$TUNNEL_USER"
        
        echo "Tunnel user created"
    else
        echo "Tunnel user already exists"
        # Ensure no password is set
        passwd -d "$TUNNEL_USER"
    fi
    
    # Configure PAM to allow empty passwords
    if ! grep -q "nullok_secure" /etc/pam.d/common-auth; then
        sed -i 's/nullok/nullok_secure/' /etc/pam.d/common-auth
    fi
    
    # Add user to SSH group if it exists
    if getent group ssh > /dev/null; then
        usermod -a -G ssh "$TUNNEL_USER"
    fi
}

# Function to configure network settings for tunneling
configure_networking() {
    echo "Configuring network settings for tunneling..."
    
    # Enable IP forwarding (temporary - immediate effect)
    sysctl -w net.ipv4.ip_forward=1
    
    # Enable IP forwarding (permanent)
    echo "net.ipv4.ip_forward=1" | tee -a /etc/sysctl.conf
    
    # Configure reverse path filtering to allow asymmetric routing
    sysctl -w net.ipv4.conf.all.rp_filter=2
    sysctl -w net.ipv4.conf.default.rp_filter=2
    
    # Add to sysctl.conf for persistence
    if ! grep -q "net.ipv4.conf.all.rp_filter=2" /etc/sysctl.conf; then
        echo "net.ipv4.conf.all.rp_filter=2" | tee -a /etc/sysctl.conf
    fi
    
    if ! grep -q "net.ipv4.conf.default.rp_filter=2" /etc/sysctl.conf; then
        echo "net.ipv4.conf.default.rp_filter=2" | tee -a /etc/sysctl.conf
    fi
    
    # Apply changes
    sysctl -p
    
    echo "Network settings configured for tunneling"
}

# Main execution
echo "Setting up empty-password SSH tunneling..."

# Execute configuration steps
configure_ssh_server
create_tunnel_user
configure_networking

echo "Configuration complete!"
echo "You can now establish SSH tunnels using the '$TUNNEL_USER' user with an empty password"
echo "Example: ssh -N -R 13689:localhost:3689 $TUNNEL_USER@your-server"

exit 0
