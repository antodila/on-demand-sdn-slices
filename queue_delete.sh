#!/bin/bash

# queue_delete.sh <unused_arg> <iface>
# removes all QoS rules (HTB qdisc, classes, filters) from the given interface

IFACE=$2    # network interface to clean up

# make sure interface was passed in as an argument
if [ -z "$IFACE" ]; then
    echo "Error: Interface name not provided."
    exit 1
fi

# nuke the root qdisc: this clears all QoS config on the interface
tc qdisc del dev $IFACE root

# done, inform the user
echo "QoS rules removed from $IFACE."
exit 0
