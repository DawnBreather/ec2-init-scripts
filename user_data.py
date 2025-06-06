#!/usr/bin/env python3

import os
import sys
import json
import time
import urllib.request
import urllib.error
import subprocess
import datetime
import base64
import argparse

# Set up argument parser
parser = argparse.ArgumentParser(description='EC2 User Data Script')
parser.add_argument('--instance-name', required=True, help='Name of the EC2 instance')
parser.add_argument('--environment', required=True, help='Environment tag')
parser.add_argument('--scripts-repository-url', required=False, default='', help='URL to scripts repository')
parser.add_argument('--script-aliases', required=False, default='', help='Space-separated list of script aliases')
parser.add_argument('--script-parameters', required=False, default='{}', help='JSON map of script parameters')
parser.add_argument('--webhook-url', required=False, default='', help='Webhook URL for notifications')
parser.add_argument('--init-script', required=False, default='', help='Custom initialization script')

# Parse arguments
args = parser.parse_args()

# Set up logging to append to the same file
log_file = open('/var/log/user-data.log', 'a')
sys.stdout = log_file
sys.stderr = log_file

print("\n\n===== PYTHON SCRIPT STARTED =====\n")

def run_command(command, shell=True):
    """Run a shell command and return output and exit code"""
    try:
        result = subprocess.run(
            command,
            shell=shell,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        return "", str(e), 1

# Update system
print("Updating system...")
run_command("apt-get -qq update -y")

# Install required packages
print("Installing required packages...")
run_command("apt-get -qq install -y openssh-client curl wget jq")
print("Package installation completed")

# Verify jq is installed
stdout, stderr, exit_code = run_command("which jq")
if exit_code != 0:
    print("jq not installed, trying again...")
    run_command("apt-get install -y jq")
    stdout, stderr, exit_code = run_command("which jq")
    if exit_code != 0:
        print("ERROR: Failed to install jq. Exiting.")
        sys.exit(1)

print("jq is installed and available")

# Initialize status report
timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
instance_name = args.instance_name
script_status_report = {
    "timestamp": timestamp,
    "instance_name": instance_name,
    "scripts": {}
}

def get_instance_metadata(field, token):
    """Helper to get instance metadata with error handling"""
    try:
        headers = {"X-aws-ec2-metadata-token": token}
        req = urllib.request.Request(
            f"http://169.254.169.254/latest/meta-data/{field}",
            headers=headers
        )
        with urllib.request.urlopen(req) as response:
            return response.read().decode('utf-8')
    except:
        return "unknown" if field != "public-ipv4" else "N/A"

def send_status_report():
    """Send status report to webhook"""
    webhook_url = args.webhook_url
    if not webhook_url:
        print("No webhook URL provided, skipping status report")
        return

    print("Sending script execution status report to webhook...")
    
    # Get IMDSv2 token
    try:
        token_request = urllib.request.Request(
            "http://169.254.169.254/latest/api/token",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"},
            method="PUT"
        )
        with urllib.request.urlopen(token_request) as response:
            token = response.read().decode('utf-8')
        
        # Get instance metadata
        instance_id = get_instance_metadata("instance-id", token)
        private_ip = get_instance_metadata("local-ipv4", token)
        public_ip = get_instance_metadata("public-ipv4", token)
        
        # Add to final report
        final_report = script_status_report.copy()
        final_report["instance_id"] = instance_id
        final_report["private_ip"] = private_ip
        final_report["public_ip"] = public_ip
        
        # Send report
        report_data = json.dumps(final_report).encode('utf-8')
        req = urllib.request.Request(
            webhook_url,
            data=report_data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        with urllib.request.urlopen(req) as response:
            print("Status report sent to webhook")
            response_text = response.read().decode('utf-8')
            print(response_text)
    
    except Exception as e:
        print(f"Error sending status report: {str(e)}")

def download_repository(url):
    """Download and parse the repository file"""
    try:
        with urllib.request.urlopen(url) as response:
            content = response.read().decode('utf-8')
            with open("/tmp/scripts/repository.json", "w") as f:
                f.write(content)
            
            print("Successfully downloaded repository file.")
            # Print first 100 chars to confirm content without bloating logs
            print(f"Content preview: {content[:100]}...")
            script_status_report["repository_status"] = "success"
            
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                print("Error: Repository content is not valid JSON")
                script_status_report["repository_status"] = "failed"
                return None
    except Exception as e:
        print(f"Failed to download repository: {str(e)}")
        script_status_report["repository_status"] = "failed"
        return None

def download_script(alias, script_url):
    """Download a script from URL and return the file path"""
    script_file = f"/tmp/scripts/{alias}.sh"
    
    print(f"Downloading script to {os.path.basename(script_file)}")
    try:
        with urllib.request.urlopen(script_url) as response:
            script_content = response.read().decode('utf-8')
            
            # Prepend parameter parsing helper
            param_helper = """#!/bin/bash
# Parameter parsing helper
parse_parameters() {
    # Initialize variables to default values
    local params=()
    
    # Loop through all command line arguments
    while [[ $# -gt 0 ]]; do
        key="$1"
        case $key in
            --*) # Handle parameters in format --param-name value
                param_name="${key#--}"  # Remove -- prefix
                param_name="${param_name//-/_}"  # Convert hyphens to underscores
                param_name=$(echo "$param_name" | tr '[:lower:]' '[:upper:]')  # Convert to uppercase
                if [[ -z "$2" || "$2" == --* ]]; then
                    # Parameter with no value (flag)
                    declare -g "$param_name"="true"
                else
                    # Parameter with value
                    declare -g "$param_name"="$2"
                    shift  # Extra shift for the value
                fi
                ;;
            *) # Collect positional parameters
                params+=("$1")
                ;;
        esac
        shift
    done
    
    # Make positional parameters available as PARAM1, PARAM2, etc.
    for i in "${!params[@]}"; do
        declare -g "PARAM$((i+1))"="${params[$i]}"
    done
    
    # For backward compatibility
    # If environment variables are set but not command line parameters, we still want to use them
    # This enables both styles of passing parameters
}

# Parse parameters automatically
parse_parameters "$@"

# Original script follows
"""
            
            # Add the helper and the original script content
            with open(script_file, "w") as f:
                # Check if the script already has a shebang line
                if script_content.startswith("#!"):
                    # Extract the shebang line
                    shebang_line = script_content.split("\n")[0]
                    rest_of_script = "\n".join(script_content.split("\n")[1:])
                    # Combine shebang, helper, and rest of script
                    param_helper_without_shebang = param_helper.split('\n', 1)[1]
                    f.write(f"{shebang_line}\n{param_helper_without_shebang}{rest_of_script}")
                else:
                    # Use the complete helper with shebang
                    f.write(f"{param_helper}{script_content}")
            
            # Make script executable
            os.chmod(script_file, 0o755)
            return script_file
    except Exception as e:
        print(f"Failed to download script: {str(e)}")
        raise

def execute_script(alias, script_file, params_map):
    """Execute a script with parameters and return results"""
    # Extract parameters
    print(f"Setting up parameters for script {alias}")
    param_args = ""
    param_details = ""
    
    # Set environment variables for parameters (for backward compatibility)
    # And build named command-line arguments
    for param_name, param_value in params_map.items():
        print(f"Using parameter {param_name}={param_value}")
        param_details += f"\n  - {param_name} = '{param_value}'"
        
        # Set as environment variable (backward compatibility)
        os.environ[param_name] = str(param_value)
        
        # Convert parameter name to kebab-case for command line
        # First to lowercase, then replace underscores with hyphens
        param_name_kebab = param_name.lower().replace('_', '-')
        
        # Format with equals sign: --param-name="value"
        param_args += f" --{param_name_kebab}=\"{param_value}\""
    
    # Execute script
    print(f"=== EXECUTING SCRIPT: {alias} at {datetime.datetime.utcnow().strftime('%H:%M:%S')} ===")
    
    # Capture script output
    script_output_file = f"/tmp/scripts/{alias}_output.txt"
    cmd = f"{script_file}{param_args}"
    stdout, stderr, exit_code = run_command(cmd)
    
    with open(script_output_file, "w") as f:
        f.write(stdout)
        if stderr:
            f.write("\n\nSTDERR:\n")
            f.write(stderr)
    
    # Get script output (limited to first 20 lines)
    with open(script_output_file, "r") as f:
        script_output = "".join(f.readlines()[:20])
    
    print(f"=== SCRIPT {alias} COMPLETED (exit: {exit_code}) ===")
    
    return exit_code, script_output

def download_and_execute_scripts():
    """Download and execute scripts from repository"""
    repository_url = args.scripts_repository_url
    script_aliases = args.script_aliases
    
    if not repository_url:
        print("No scripts repository URL provided, skipping script downloads")
        return
    
    if not script_aliases:
        print("No script aliases provided, skipping script downloads")
        return
    
    # Combine log messages to reduce verbosity
    print(f"Starting script execution with repository: '{repository_url}' and aliases: '{script_aliases}'")
    print(f"Downloading scripts repository from {repository_url}")
    
    # Create scripts directory
    os.makedirs("/tmp/scripts", exist_ok=True)
    
    # Download repository file
    print("Downloading repository...")
    repository = download_repository(repository_url)
    if not repository:
        return
    
    # Parse script parameters
    script_parameters_json = args.script_parameters
    try:
        script_parameters = json.loads(script_parameters_json)
    except json.JSONDecodeError:
        print("Warning: Script parameters is not valid JSON, using empty dict")
        script_parameters = {}
    
    # Process script aliases
    aliases = script_aliases.split()
    
    for alias in aliases:
        print(f"Processing script alias: {alias}")
        
        # Initialize script status
        script_status = "pending"
        start_time = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        
        try:
            # Find URL for this alias
            script_url = repository.get(alias)
            
            # Convert GitHub URLs to raw URLs if needed
            if script_url and "github.com" in script_url and "raw.githubusercontent.com" not in script_url:
                print(f"Converting GitHub URL: {script_url.split('/')[-1]}")
                script_url = script_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
            
            if not script_url:
                print(f"Warning: No URL found for alias {alias}")
                script_status = "error"
                error_message = "No URL found for alias"
                script_status_report["scripts"][alias] = {
                    "status": script_status,
                    "error": error_message,
                    "start_time": start_time,
                    "end_time": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                }
                continue
            
            # Download script
            print(f"Downloading script from {script_url}")
            script_file = download_script(alias, script_url)
            
            # Get parameters for this script
            script_params_map = script_parameters.get(alias, {})
            
            # Execute script
            exit_code, script_output = execute_script(alias, script_file, script_params_map)
            end_time = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            
            if exit_code == 0:
                script_status = "success"
                print(f"Script {alias} completed successfully")
            else:
                script_status = "failed"
                print(f"Script {alias} failed with exit code {exit_code}")
            
            # Update status report
            script_status_report["scripts"][alias] = {
                "status": script_status,
                "exit_code": exit_code,
                "output": script_output,
                "start_time": start_time,
                "end_time": end_time
            }
            
        except Exception as e:
            print(f"Failed to process script {alias}: {str(e)}")
            script_status = "error"
            error_message = str(e)
            script_status_report["scripts"][alias] = {
                "status": script_status,
                "error": error_message,
                "start_time": start_time,
                "end_time": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            }

# Download and execute scripts
if args.scripts_repository_url and args.script_aliases:
    download_and_execute_scripts()
else:
    print("Skipping script download and execution because:")
    if not args.scripts_repository_url:
        print("  - scripts_repository_url is empty")
    if not args.script_aliases:
        print("  - script_aliases is empty")

# Run custom init script if provided
init_script_content = args.init_script
init_script_status = "not_executed"

if init_script_content.strip():
    print("Running custom initialization script...")
    with open("/tmp/custom_init.sh", "w") as f:
        f.write(init_script_content)
    
    os.chmod("/tmp/custom_init.sh", 0o755)
    
    init_start_time = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    stdout, stderr, init_exit_code = run_command("/tmp/custom_init.sh")
    init_end_time = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    
    with open("/tmp/init_script_output.txt", "w") as f:
        f.write(stdout)
        if stderr:
            f.write("\n\nSTDERR:\n")
            f.write(stderr)
    
    if init_exit_code == 0:
        init_script_status = "success"
    else:
        init_script_status = "failed"
    
    with open("/tmp/init_script_output.txt", "r") as f:
        init_output = "".join(f.readlines()[:20])
    
    script_status_report["init_script"] = {
        "status": init_script_status,
        "exit_code": init_exit_code,
        "output": init_output,
        "start_time": init_start_time,
        "end_time": init_end_time
    }

# Signal completion
with open("/tmp/user_data_complete", "w") as f:
    f.write("")

# Send final status report
if args.webhook_url:
    send_status_report()

# Print a completion message
print("\n===== PYTHON SCRIPT COMPLETED =====\n")

# Close log file
log_file.close()
