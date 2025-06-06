#!/bin/bash
# Kea Admin Installation Script

# Check if script is run as root
if [ "$(id -u)" -ne 0 ]; then
   echo "This script must be run as root" 
   exit 1
fi

# Check if kea-admin is already installed (idempotency)
if dpkg -l | grep -q "kea-admin"; then
    echo "kea-admin is already installed"
    exit 0
fi

# Update package lists
echo "Updating package lists..."
apt-get update -y

# Install kea-admin
echo "Installing kea-admin package..."
apt-get install -y kea-admin

# Verify installation
if dpkg -l | grep -q "kea-admin"; then
    echo "kea-admin installed successfully"
    exit 0
else
    echo "Failed to install kea-admin"
    exit 1
fi
