#!/bin/bash
# SSH Tunnel Setup Script for EC2 instances

# Default parameters
SERVER_ADDRESS=""
LOCAL_PORT=""
REMOTE_PORT=""
USERNAME="tunnel"

# Parse named parameters
while [ $# -gt 0 ]; do
  case "$1" in
    --server=*)
      SERVER_ADDRESS="${1#*=}"
      ;;
    --server)
      SERVER_ADDRESS="$2"
      shift
      ;;
    --local-port=*)
      LOCAL_PORT="${1#*=}"
      ;;
    --local-port)
      LOCAL_PORT="$2"
      shift
      ;;
    --remote-port=*)
      REMOTE_PORT="${1#*=}"
      ;;
    --remote-port)
      REMOTE_PORT="$2"
      shift
      ;;
    --username=*)
      USERNAME="${1#*=}"
      ;;
    --username)
      USERNAME="$2"
      shift
      ;;
    *)
      echo "Unknown parameter: $1"
      echo "Usage: $0 --server=SERVER_ADDRESS --local-port=LOCAL_PORT --remote-port=REMOTE_PORT [--username=USERNAME]"
      exit 1
      ;;
  esac
  shift
done

# Check if required parameters are provided
if [ -z "$SERVER_ADDRESS" ] || [ -z "$LOCAL_PORT" ] || [ -z "$REMOTE_PORT" ]; then
    echo "Error: Missing required parameters"
    echo "Usage: $0 --server=SERVER_ADDRESS --local-port=LOCAL_PORT --remote-port=REMOTE_PORT [--username=USERNAME]"
    exit 1
fi

# Name for the systemd service
SERVICE_NAME="ssh-tunnel-${REMOTE_PORT}"

# Check if tunnel already exists (idempotency)
if systemctl is-active --quiet ${SERVICE_NAME}; then
    echo "SSH tunnel to ${SERVER_ADDRESS}:${REMOTE_PORT} is already running"
    exit 0
fi

# Create systemd service file
create_service_file() {
    cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=SSH tunnel from localhost:${LOCAL_PORT} to ${SERVER_ADDRESS}:${REMOTE_PORT}
After=network.target

[Service]
Type=simple
User=ubuntu
ExecStart=/usr/bin/ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes -N -R ${REMOTE_PORT}:0.0.0.0:${LOCAL_PORT} ${USERNAME}@${SERVER_ADDRESS}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd to recognize the new service
    systemctl daemon-reload
}

# Enable and start the service
start_tunnel_service() {
    systemctl enable ${SERVICE_NAME}
    systemctl start ${SERVICE_NAME}
    
    # Check if service started successfully
    if systemctl is-active --quiet ${SERVICE_NAME}; then
        echo "SSH tunnel to ${SERVER_ADDRESS}:${REMOTE_PORT} established successfully"
    else
        echo "Failed to establish SSH tunnel"
        exit 1
    fi
}

# Main execution
echo "Setting up persistent SSH tunnel..."
create_service_file
start_tunnel_service

exit 0
