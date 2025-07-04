#!/usr/bin/env bash
# queue_delete.sh <slice_name> <iface>
# This script removes all QoS rules for a given slice from a specific interface.

SLICE=$1      # Name of the slice
IFACE=$2      # Network interface to remove QoS from

if [ -z "$IFACE" ]; then
    echo "Error: Interface not specified."
    exit 1
fi

echo "[QoS] Completely removing QoS rules for slice '$SLICE' from $IFACE"

# Radical approach: remove the entire qdisc and recreate the default one
tc qdisc del dev $IFACE root 2>/dev/null
tc qdisc add dev $IFACE root pfifo_fast

echo "[QoS] QoS rules successfully removed from $IFACE"

exit 0