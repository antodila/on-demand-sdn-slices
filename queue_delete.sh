#!/bin/bash
# Deletes the HTB qdisc from a given interface.
# This effectively removes all QoS rules applied by queue_create.sh.

IFACE=$2

if [ -z "$IFACE" ]; then
    echo "Error: Interface name not provided."
    exit 1
fi

# Delete the root qdisc. This removes the entire HTB structure.
tc qdisc del dev $IFACE root

echo "QoS rules removed from $IFACE."
exit 0