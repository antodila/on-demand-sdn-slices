#!/usr/bin/env bash

# queue_create.sh <slice_name> <pct> <ip_src> <ip_dst> <iface>
# sets up an HTB queue + filter for a specific slice on a given interface

SLICE=$1      # name of the slice
PCT=$2        # guaranteed bandwidth (in Mbit/s)
IP_SRC=$3     # source IP address
IP_DST=$4     # destination IP address
IFACE=$5      # network interface to apply QoS

# make sure interface was passed in
if [ -z "$IFACE" ]; then
    echo "Error: Interface not specified."
    exit 1
fi

# generate a unique class ID based on slice name
CLASS_ID=$(echo -n $SLICE | od -An -tuC | awk '{print $1 % 50 + 10}')

echo "[QoS] Checking and configuring HTB on $IFACE..."

# if HTB root doesn't exist yet, set it up
tc qdisc show dev $IFACE | grep -q "htb 1:"
if [ $? -ne 0 ]; then
    echo "[QoS] Creating HTB structure on $IFACE..."
    tc qdisc del dev $IFACE root 2>/dev/null
    tc qdisc add dev $IFACE root handle 1: htb default 10

    # default class for unclassified traffic that maxes out at 1Gbit
    tc class add dev $IFACE parent 1: classid 1:1 htb rate 1000mbit
    tc class add dev $IFACE parent 1:1 classid 1:10 htb rate 1000mbit
fi

# add a class for this slice with the given bandwidth (burst is increased to allow TCP handshake even on fast links)
echo "[QoS] Adding class 1:${CLASS_ID} for slice '$SLICE' (${PCT}mbit) on $IFACE"
tc class add dev $IFACE parent 1:1 classid 1:${CLASS_ID} htb rate ${PCT}mbit ceil ${PCT}mbit burst 30k cburst 30k

# add filter: traffic from src to dst IP gets tied to this class
echo "[QoS] Adding filter for ${IP_SRC}->${IP_DST} to class 1:${CLASS_ID}"
tc filter add dev $IFACE protocol ip parent 1:0 prio 1 u32 \
    match ip src ${IP_SRC}/32 match ip dst ${IP_DST}/32 \
    flowid 1:${CLASS_ID}

exit 0
