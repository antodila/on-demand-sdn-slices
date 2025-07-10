#!/usr/bin/env python3
"""
Topology for the network
"""

# imports 
from comnetsemu.cli import CLI
from comnetsemu.net import Containernet
from mininet.node import OVSKernelSwitch, RemoteController
from mininet.link import TCLink
from mininet.log import setLogLevel, info

def main():
    setLogLevel('info')
    info('*** Creating ComNetsEmu network\n')
    # initialize containernet network
    net = Containernet(switch=OVSKernelSwitch, link=TCLink, build=False, controller=None) # controller is added separately

    info('*** Adding controller\n')
    # add a remote controller to the network, Ryu is expected to be running already
    net.addController('c1', controller=RemoteController, ip='127.0.0.1', port=6633)

    info('*** Adding hosts\n')
    hosts = {}
    # define all hosts with their names and corresponding IPs
    host_defs = {
        'h1': '10.0.0.1/24', 'h2': '10.0.0.2/24', 'h3': '10.0.0.3/24',
        'h4': '10.0.0.4/24', 'h5': '10.0.0.5/24',
        'g1': '10.0.0.6/24', 'g2': '10.0.0.7/24',
        'gs': '10.0.0.8/24', 'ps': '10.0.0.9/24'
    }
    # create and add each host to the network
    for name, ip in host_defs.items():
        hosts[name] = net.addHost(name, ip=ip)

    info('*** Adding switches\n')
    switches = {}
    # create and add five switches to the network
    for i in range(1, 6):
        switches[f's{i}'] = net.addSwitch(f's{i}', protocols='OpenFlow13')

    info('*** Creating links (default 100Mbps)\n')
    # define the links between switches
    net.addLink(switches['s1'], switches['s2'], bw=100, intfName1='s1-eth1', intfName2='s2-eth1')
    net.addLink(switches['s1'], switches['s4'], bw=100, intfName1='s1-eth2', intfName2='s4-eth1')
    net.addLink(switches['s2'], switches['s3'], bw=100, intfName1='s2-eth2', intfName2='s3-eth1')
    net.addLink(switches['s2'], switches['s5'], bw=100, intfName1='s2-eth3', intfName2='s5-eth1')

    # define the links connecting hosts to switches each one with 100 mbps bandwidth
    net.addLink(hosts['h1'], switches['s1'], bw=100, intfName1='h1-eth0', intfName2='s1-eth3')
    net.addLink(hosts['h2'], switches['s1'], bw=100, intfName1='h2-eth0', intfName2='s1-eth4')
    net.addLink(hosts['g1'], switches['s1'], bw=100, intfName1='g1-eth0', intfName2='s1-eth5')
    net.addLink(hosts['h5'], switches['s2'], bw=100, intfName1='h5-eth0', intfName2='s2-eth4')
    net.addLink(hosts['h3'], switches['s3'], bw=100, intfName1='h3-eth0', intfName2='s3-eth2')
    net.addLink(hosts['h4'], switches['s3'], bw=100, intfName1='h4-eth0', intfName2='s3-eth3')
    net.addLink(hosts['g2'], switches['s3'], bw=100, intfName1='g2-eth0', intfName2='s3-eth4')
    net.addLink(hosts['gs'], switches['s4'], bw=100, intfName1='gs-eth0', intfName2='s4-eth2')
    net.addLink(hosts['ps'], switches['s5'], bw=100, intfName1='ps-eth0', intfName2='s5-eth2')

    info('*** Building and starting network\n')
    # build and start the network with the topology defined on top
    net.build()
    net.start()

    # disable IPv6 on all hosts to prevent unwanted traffic 
    info('*** Disabling IPv6 on all hosts\n')
    for host in net.hosts:
        host.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")
        host.cmd("sysctl -w net.ipv6.conf.default.disable_ipv6=1")
        host.cmd("sysctl -w net.ipv6.conf.lo.disable_ipv6=1")

    info('*** Running CLI (type exit to quit)\n')
    # start the mininet CLI for testing
    CLI(net)
    info('*** Stopping network\n')
    # stop the network and clean up all resources when exiting the CLI
    net.stop()

if __name__ == '__main__':
    main()