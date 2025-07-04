#!/usr/bin/env bash
# queue_create.sh <slice_name> <pct> <ip_src> <ip_dst> <iface>
# This script sets up an HTB queue and filter for a specific slice on a given interface.

SLICE=$1      # Name of the slice
PCT=$2        # Bandwidth in Mbit/s to guarantee for the slice
IP_SRC=$3     # Source IP address for the flow
IP_DST=$4     # Destination IP address for the flow
IFACE=$5      # Network interface to apply QoS

if [ -z "$IFACE" ]; then
    echo "Error: Interface not specified."
    exit 1
fi

# Assign a unique class ID to the slice based on its name
CLASS_ID=$(echo -n $SLICE | od -An -tuC | awk '{print $1 % 50 + 10}')

echo "[QoS] Checking and configuring HTB on $IFACE..."

# Check if the root HTB qdisc already exists. If not, create it.
tc qdisc show dev $IFACE | grep -q "htb 1:"
if [ $? -ne 0 ]; then
    echo "[QoS] Creating HTB structure on $IFACE..."
    tc qdisc del dev $IFACE root 2>/dev/null
    tc qdisc add dev $IFACE root handle 1: htb default 10
    # Default class with high bandwidth for unclassified traffic
    tc class add dev $IFACE parent 1: classid 1:1 htb rate 1000mbit
    tc class add dev $IFACE parent 1:1 classid 1:10 htb rate 1000mbit
fi

# CLASS: Add a class for the new slice - THIS IS THE CORRECT CONFIGURATION
echo "[QoS] Adding class 1:${CLASS_ID} for slice '$SLICE' (${PCT}mbit) on $IFACE"
# Increase burst to allow TCP handshake on fast links
tc class add dev $IFACE parent 1:1 classid 1:${CLASS_ID} htb rate ${PCT}mbit ceil ${PCT}mbit burst 30k cburst 30k

# FILTER: Add the specific flow to the slice's class
echo "[QoS] Adding filter for ${IP_SRC}->${IP_DST} to class 1:${CLASS_ID}"
tc filter add dev $IFACE protocol ip parent 1:0 prio 1 u32 \
    match ip src ${IP_SRC}/32 match ip dst ${IP_DST}/32 \
    flowid 1:${CLASS_ID}

exit 0