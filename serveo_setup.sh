#!/bin/bash

# Serveo tunnel setup for HTTP web services

# Configuration
# Serveo only allows HTTP (80) port for tunnels
SERVEO_PORT=80  # Fixed to HTTP port
: ${WEB_SERVICE_LOCALHOST_PORT:=8080}
: ${LOG_FILE:="/tmp/serveo_output.txt"}

# Function to establish Serveo tunnel
setup_serveo_tunnel() {
    local log_file="$2"
    
    echo "[$(date)] Setting up Serveo tunnel for HTTP web service on port $WEB_SERVICE_LOCALHOST_PORT..."
    
    # Kill any existing Serveo process
    pkill -f "ssh.*serveo.net" || true
    
    # Start new tunnel in background
    ssh -o StrictHostKeyChecking=no \
        -o UserKnownHostsFile=/dev/null \
        -o ServerAliveInterval=30 \
        -o ServerAliveCountMax=3 \
        -R "$SERVEO_PORT:localhost:$WEB_SERVICE_LOCALHOST_PORT" \
        serveo.net 2>&1 | tee "$log_file" &
    
    # Give it time to establish
    sleep 5
    
    # Check if tunnel is working
    if pgrep -f "serveo.net" > /dev/null; then
        echo "[$(date)] Serveo tunnel established successfully"
        extract_connection_info "$log_file"
    else
        echo "[$(date)] Failed to establish Serveo tunnel" | tee -a "$log_file"
        return 1
    fi
}

# Function to extract connection information
extract_connection_info() {
    local log_file="$1"
    
    echo "[$(date)] Extracting connection information..."
    
    # Look for forwarding information
    local forwarding_info=$(grep -E "Forwarding HTTP traffic from" "$log_file" | tail -1)
    
    if [ -z "$forwarding_info" ]; then
        echo "[$(date)] No forwarding information found yet. Check log file."
        return 1
    fi
    
    echo "[$(date)] Connection info: $forwarding_info"
    
    # Extract hostname if available
    if echo "$forwarding_info" | grep -q "https://"; then
        local url=$(echo "$forwarding_info" | grep -o "https://[^ ]*")
        
        echo "[$(date)] Web service is accessible at:"
        echo "$url"
    fi
}

# Function to check tunnel status
check_tunnel_status() {
    echo "[$(date)] Checking Serveo tunnel status..."
    
    if pgrep -f "serveo.net" > /dev/null; then
        echo "[$(date)] Serveo tunnel is active"
        ps aux | grep -i serveo | grep -v grep
        return 0
    else
        echo "[$(date)] Serveo tunnel is NOT active"
        return 1
    fi
}

# Function to restart tunnel if needed
ensure_tunnel_running() {
    if ! check_tunnel_status > /dev/null; then
        echo "[$(date)] Tunnel not running, restarting..."
        setup_serveo_tunnel "$SERVEO_PORT" "$LOG_FILE"
    else
        echo "[$(date)] Tunnel is already running"
    fi
}

# Main execution
case "${1:-help}" in
    setup)
        setup_serveo_tunnel "$SERVEO_PORT" "$LOG_FILE"
        ;;
    status)
        check_tunnel_status
        ;;
    info)
        extract_connection_info "$LOG_FILE"
        ;;
    ensure)
        ensure_tunnel_running
        ;;
    help|*)
        echo "Usage: $0 [setup|status|info|ensure]"
        echo "  setup  - Set up a new Serveo tunnel"
        echo "  status - Check if tunnel is running"
        echo "  info   - Extract connection information"
        echo "  ensure - Ensure tunnel is running, restart if needed"
        echo ""
        echo "Environment variables:"
        echo "  WEB_SERVICE_LOCALHOST_PORT - Local web service port to forward (default: 8080)"
        echo "  LOG_FILE                   - Log file location (default: /tmp/serveo_output.txt)"
        echo ""
        echo "Note: Serveo only allows HTTP port (80) for tunnels."
        ;;
esac

exit 0
