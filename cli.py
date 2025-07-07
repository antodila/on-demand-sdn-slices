#!/usr/bin/env python3
"""
Command-Line Interface (CLI) to interact with the Slicing Controller's REST API.
This script allows activating and deactivating network slices by sending POST requests.
"""

import argparse     # For parsing command-line arguments
import requests     # For making HTTP requests
import sys          # For system-specific parameters and functions
import json         # For formatting JSON output

# -----------------------------------------------------------------------------
# Set up the command-line argument parser.
# -----------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="CLI for SDN Slices")
parser.add_argument('action', choices=['activate', 'deactivate', 'status'],
                    help="The action to perform.")  # User must specify action
parser.add_argument('slice', nargs='?', default=None, 
                    help="The name of the slice to target (not needed for 'status').")  # Slice name is now optional
parser.add_argument('--host', default='127.0.0.1',
                    help='IP address of the REST controller.')  # Controller IP
parser.add_argument('--port', default=8080, type=int,
                    help='Port of the REST controller.')        # Controller port
args = parser.parse_args()  # Parse the arguments

# -----------------------------------------------------------------------------
# Construct the request URL from the command-line arguments.
# -----------------------------------------------------------------------------
if args.action == 'status':
    url = f"http://{args.host}:{args.port}/slices/status"
else:
    if not args.slice:
        print("Error: slice name is required for 'activate' or 'deactivate'.", file=sys.stderr)
        sys.exit(1)
    url = f"http://{args.host}:{args.port}/slice/{args.slice}/{args.action}"

try:
    # -------------------------------------------------------------------------
    # Send a request to the controller's API with a 5-second timeout.
    # -------------------------------------------------------------------------
    if args.action == 'status':
        resp = requests.get(url, timeout=5)
    else:
        resp = requests.post(url, timeout=5)
    status = resp.status_code

    try:
        # ---------------------------------------------------------------------
        # Try to decode a JSON response from the server.
        # ---------------------------------------------------------------------
        data = resp.json()
        if args.action == 'status':
            # For status, print the raw JSON for better readability
            print(json.dumps(data, indent=2))
        else:
            # For activate/deactivate, print the message from the controller
            message = data.get('message', 'No message received.')
            print(f"Success ({status}): {message}")

    except (ValueError, json.JSONDecodeError):
        # ---------------------------------------------------------------------
        # Handle cases where the response is not valid JSON.
        # ---------------------------------------------------------------------
        # Check for a 409 Conflict status, which is an expected error
        if status == 409:
             print(f"Error ({status}): {resp.text}")
        else:
             print(f"Received non-JSON response ({status}): {resp.text}")

except requests.exceptions.RequestException as e:
    # -------------------------------------------------------------------------
    # Handle network errors, such as connection refused.
    # -------------------------------------------------------------------------
    print(f"Connection error: {e}", file=sys.stderr)
    sys.exit(1)