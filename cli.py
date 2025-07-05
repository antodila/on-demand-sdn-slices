#!/usr/bin/env python3
"""
Command-Line Interface (CLI) to interact with the Slicing Controller's REST API.
This script allows activating and deactivating network slices by sending POST requests.
"""

import argparse     # For parsing command-line arguments
import requests     # For making HTTP requests
import sys          # For system-specific parameters and functions

# -----------------------------------------------------------------------------
# Set up the command-line argument parser.
# -----------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="CLI for SDN Slices")
parser.add_argument('action', choices=['activate', 'deactivate'],
                    help="The action to perform.")  # User must specify action
parser.add_argument('slice', help="The name of the slice to target.")  # Slice name
parser.add_argument('--host', default='127.0.0.1',
                    help='IP address of the REST controller.')  # Controller IP
parser.add_argument('--port', default=8080, type=int,
                    help='Port of the REST controller.')        # Controller port
args = parser.parse_args()  # Parse the arguments

# -----------------------------------------------------------------------------
# Construct the request URL from the command-line arguments.
# -----------------------------------------------------------------------------
url = f"http://{args.host}:{args.port}/slice/{args.slice}/{args.action}"

try:
    # -------------------------------------------------------------------------
    # Send a POST request to the controller's API with a 5-second timeout.
    # -------------------------------------------------------------------------
    resp = requests.post(url, timeout=5)
    status = resp.status_code

    try:
        # ---------------------------------------------------------------------
        # Try to decode a JSON response from the server.
        # ---------------------------------------------------------------------
        data = resp.json()
        print(f"Success ({status}): {data}")
    except ValueError:
        # ---------------------------------------------------------------------
        # Handle cases where the response is not valid JSON.
        # ---------------------------------------------------------------------
        print(f"Received non-JSON response ({status}): {resp.text}")

except requests.exceptions.RequestException as e:
    # -------------------------------------------------------------------------
    # Handle network errors, such as connection refused.
    # -------------------------------------------------------------------------
    print(f"Connection error: {e}", file=sys.stderr)
    sys.exit(1)