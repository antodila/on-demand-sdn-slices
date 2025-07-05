#!/bin/bash
# Deletes the HTB qdisc from a given interface.
# This effectively removes all QoS rules applied by queue_create.sh.

IFACE=$2    # The network interface from which to remove the qdisc.

# Check if the interface name was provided as an argument.
if [ -z "$IFACE" ]; then
    echo "Error: Interface name not provided."
    exit 1
fi

# Remove the root qdisc from the specified interface.
# This deletes all HTB classes and filters, removing all QoS configuration.
tc qdisc del dev $IFACE root

# Inform the user that QoS rules have been removed.
echo "QoS rules removed from $IFACE."
exit 0