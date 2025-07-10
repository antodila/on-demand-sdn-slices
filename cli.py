#!/usr/bin/env python3

"""
CLI to talk to the Slicing Controller's REST API to activate, deactivate, or check the status of network slices.
"""

import argparse     
import requests    
import sys         
import json         


# set up what options the user can pass in
parser = argparse.ArgumentParser(description="CLI for SDN Slices")
parser.add_argument('action', choices=['activate', 'deactivate', 'status'],
                    help="What you want to do.")                                # must pick one of these
parser.add_argument('slice', nargs='?', default=None, 
                    help="Slice name (not needed for 'status').")               # optional unless activating/deactivating
parser.add_argument('--host', default='127.0.0.1',
                    help='Controller IP (default is localhost)')                # where to send the request
parser.add_argument('--port', default=8080, type=int,
                    help='Controller port (default is 8080)')                   # default port
args = parser.parse_args()                                                      # read in the arguments

# figure out the correct URL to hit
if args.action == 'status':
    url = f"http://{args.host}:{args.port}/slices/status"
else:
    if not args.slice:
        print("Error: You need to specify a slice name for 'activate' or 'deactivate'.", file=sys.stderr)
        sys.exit(1)
    url = f"http://{args.host}:{args.port}/slice/{args.slice}/{args.action}"

try:
    # make the actual API call
    if args.action == 'status':
        resp = requests.get(url, timeout=5)
    else:
        resp = requests.post(url, timeout=5)
    status = resp.status_code

    try:
        # try to parse the response as JSON
        data = resp.json()
        if args.action == 'status':
            # just print the full status output nicely
            print(json.dumps(data, indent=2))
        else:
            # show the message the controller gave back
            message = data.get('message', 'No message received.')
            print(f"Success ({status}): {message}")

    except (ValueError, json.JSONDecodeError):
        # server didn’t give back valid JSON
        if status == 409:
            # 409 usually means "already active" or something similar
            print(f"Error ({status}): {resp.text}")
        else:
            # something went wrong, and we don’t know what
            print(f"Received non-JSON response ({status}): {resp.text}")

except requests.exceptions.RequestException as e:
    # something went wrong with the network
    print(f"Connection error: {e}", file=sys.stderr)
    sys.exit(1)
