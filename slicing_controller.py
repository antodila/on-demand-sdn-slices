#!/usr/bin/env python3
"""
On-Demand SDN Slicing Controller - Implements a controller for managing network slices in a software-defined network (SDN) environment.
"""

import os
import yaml
import threading
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import networkx as nx

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ether_types

# Import necessary topology components from Ryu.
from ryu.topology import event
from ryu.topology.api import get_switch, get_link

# Static mapping of hostnames to their IP addresses.
IP_MAP = {
    'h1': '10.0.0.1', 'h2': '10.0.0.2', 'h3': '10.0.0.3',
    'h4': '10.0.0.4', 'h5': '10.0.0.5',
    'g1': '10.0.0.6', 'g2': '10.0.0.7',
    'gs': '10.0.0.8', 'ps': '10.0.0.9'
}

class SlicingController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SlicingController, self).__init__(*args, **kwargs)
        # Load slice definitions from the YAML file.
        path = os.path.join(os.path.dirname(__file__), 'slices.yaml')
        with open(path, 'r') as f:
            self.slices = yaml.safe_load(f)
        self.logger.info("Controller started. Slices loaded: %s", list(self.slices.keys()))
        
        # Initialize state variables.
        self.mac_to_port = {}  # Stores MAC address to port mappings for each switch.
        self.active_slices = {} # Tracks currently active slices and their interfaces.
        self.net = nx.DiGraph() # A directed graph to store the network topology.

        # Start the HTTP server in a separate thread to handle API requests.
        threading.Thread(target=self._start_http_server, daemon=True).start()
        self.logger.info("API server started on http://0.0.0.0:8080")

    @set_ev_cls(event.EventSwitchEnter)
    def handler_switch_enter(self, ev):
        # When a new switch connects, ensure the static topology is loaded.
        self.get_topology_data()

    @set_ev_cls(event.EventLinkAdd)
    def handler_link_add(self, ev):
        # Ignore dynamic link events to rely solely on the static topology for consistency.
        pass

    def get_topology_data(self):
        # Use a static, hardcoded topology to prevent timing issues with Ryu's discovery.
        if self.net.edges():
            return  # Load the topology only once.

        self.logger.info("Loading static topology...")
        
        # Static definition of links between switches, based on topology.py.
        # Ports are explicitly defined to avoid ambiguity.
        static_links = [
            (1, 2, {'port': 1}), (2, 1, {'port': 1}),
            (1, 4, {'port': 2}), (4, 1, {'port': 1}),
            (2, 3, {'port': 2}), (3, 2, {'port': 1}),
            (2, 5, {'port': 3}), (5, 2, {'port': 1}),
        ]
        # Add the switch nodes to the graph.
        switches = [1, 2, 3, 4, 5]
        self.net.add_nodes_from(switches)
        self.net.add_edges_from(static_links)

        # Initialize link capacities and used bandwidth.
        for u, v in self.net.edges():
            self.net.edges[u, v]['capacity'] = 100  # Assuming 100 Mbit/s links
            self.net.edges[u, v]['used_bw'] = 0
        
        self.logger.info("Static topology loaded: Nodes=%s, Edges=%s", self.net.nodes(), self.net.edges())

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        # When a switch connects, install a default flow rule to send all unmatched packets to the controller.
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions) # Priority 0 (lowest).

    def add_flow(self, datapath, priority, match, actions):
        # Helper function to create and send a flow modification message to a switch.
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority, match=match, instructions=inst)
        datapath.send_msg(mod)

    def remove_flow(self, datapath, priority, match):
        """Helper function to remove a flow rule from a switch."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        mod = parser.OFPFlowMod(datapath=datapath,
                                command=ofproto.OFPFC_DELETE,
                                out_port=ofproto.OFPP_ANY,
                                out_group=ofproto.OFPG_ANY,
                                priority=priority,
                                match=match)
        datapath.send_msg(mod)
    
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        # This handler acts as a simple L2 learning switch for non-slice traffic.
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        # Ignore LLDP and IPv6 multicast packets.
        if eth.ethertype == ether_types.ETH_TYPE_LLDP or eth.dst.startswith('33:33:'):
            return

        dst = eth.dst
        src = eth.src
        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port # Learn the MAC address of the source.

        # Determine the output port.
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD # Flood if the destination is unknown.

        actions = [parser.OFPActionOutput(out_port)]

        # Install a flow rule for this L2 traffic to avoid future packet-ins.
        # This rule has a low priority (1) so that slice-specific rules (priority 10) take precedence.
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
            if not self.is_slice_flow(src, dst): # A simple check for robustness.
                 self.add_flow(datapath, 1, match, actions)

        # Send the packet out.
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data
        
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

    def is_slice_flow(self, mac_src, mac_dst):
        # Helper method to check if a MAC flow is part of an active slice.
        # This is a simplification; a real solution would map IPs to MACs.
        # Since slices are IP-based, this method is not strictly necessary
        # if priorities are handled correctly, but it adds clarity.
        return False

    def get_host_location(self, host_name):
        # Static mapping of hosts to their directly connected switch DPID.
        host_to_switch_map = {
            'h1': 1, 'h2': 1, 'g1': 1, 'h5': 2, 'h3': 3, 'h4': 3,
            'g2': 3, 'gs': 4, 'ps': 5
        }
        return host_to_switch_map.get(host_name)

    def _start_http_server(self):
        # A simple HTTP server to handle REST API calls for slice management.
        controller = self
        class RequestHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                parts = self.path.strip('/').split('/')
                if len(parts) == 3 and parts[0] == 'slice':
                    slice_name, action = parts[1], parts[2]
                    if action in ['activate', 'deactivate']:
                        # Capture the return value for feedback.
                        success, message = getattr(controller, f"{action}_slice")(slice_name)
                        if success:
                            self.send_response(200)
                            response = {'status': 'ok', 'message': message}
                        else:
                            self.send_response(409) # 409 Conflict
                            response = {'status': 'error', 'message': message}
                        
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps(response).encode())
                    else:
                        self.send_error(400)
                else:
                    self.send_error(404)
        server = HTTPServer(('0.0.0.0', 8080), RequestHandler)
        server.serve_forever()

    def activate_slice(self, slice_name):
        # Activate a slice if it is defined and not already active.
        if slice_name not in self.slices:
            msg = f"Slice '{slice_name}' not found."
            self.logger.error(msg)
            return False, msg
        
        if slice_name in self.active_slices:
            msg = f"Slice '{slice_name}' is already active."
            self.logger.warning(msg)
            return False, msg

        self.logger.info("--- Activating slice '%s' ---", slice_name)

        # Get slice specifications.
        spec = self.slices[slice_name]
        required_bw = spec['capacity_pct']
        priority = spec.get('priority', 0) # Get priority, default to 0 if not specified
        
        all_paths = []
        victims_to_preempt = set()

        # Phase 1: Check for bandwidth and identify potential victims for preemption.
        for flow in spec['flows']:
            src_host, dst_host = flow['src'], flow['dst']
            src_dpid = self.get_host_location(src_host)
            dst_dpid = self.get_host_location(dst_host)
            
            try:
                path = nx.shortest_path(self.net, src_dpid, dst_dpid)
                all_paths.append({'path': path, 'flow': flow})
                
                for i in range(len(path) - 1):
                    u, v = path[i], path[i+1]
                    available_bw = self.net.edges[u, v]['capacity'] - self.net.edges[u, v]['used_bw']
                    
                    if required_bw > available_bw:
                        self.logger.info(f"Link s{u}-s{v} is a bottleneck. Checking for preemption...")
                        # Find active slices on this link with lower priority.
                        preemptable_slices = []
                        for active_slice_name, slice_info in self.active_slices.items():
                            active_slice_priority = self.slices[active_slice_name].get('priority', 0)
                            if active_slice_priority < priority:
                                for active_path in slice_info['paths']:
                                    if (u, v) in zip(active_path, active_path[1:]):
                                        preemptable_slices.append((active_slice_name, slice_info['bw'], active_slice_priority))
                                        break # Avoid adding the same slice multiple times for one link
                        
                        # Sort victims by priority (lowest first) to minimize impact.
                        preemptable_slices.sort(key=lambda x: x[2])
                        
                        freed_bw = 0
                        victims_for_this_link = set()
                        for victim_name, victim_bw, _ in preemptable_slices:
                            if available_bw + freed_bw >= required_bw:
                                break
                            freed_bw += victim_bw
                            victims_for_this_link.add(victim_name)
                        
                        if available_bw + freed_bw >= required_bw:
                            self.logger.info(f"Found victims on s{u}-s{v}: {list(victims_for_this_link)}. Preemption is possible.")
                            victims_to_preempt.update(victims_for_this_link)
                        else:
                            msg = f"Cannot activate slice '{slice_name}': Insufficient bandwidth on link s{u}-s{v} even after preemption. Required: {required_bw}, Available+Preemptable: {available_bw + freed_bw}"
                            self.logger.error(msg)
                            return False, msg

            except nx.NetworkXNoPath:
                msg = f"No path found for flow {src_host}->{dst_host}"
                self.logger.error(msg)
                return False, msg

        # Phase 2: Deactivate victim slices if any were identified.
        if victims_to_preempt:
            self.logger.warning(f"Preempting slices {list(victims_to_preempt)} to activate '{slice_name}'.")
            for victim_name in list(victims_to_preempt):
                self.deactivate_slice(victim_name)

        # Phase 3: If all checks passed, reserve bandwidth and install rules.
        self.active_slices[slice_name] = {'ifaces': set(), 'paths': [], 'bw': required_bw}
        for item in all_paths:
            path = item['path']
            self.active_slices[slice_name]['paths'].append(path) # Store the path
            # Reserve bandwidth
            for i in range(len(path) - 1):
                u, v = path[i], path[i+1]
                self.net.edges[u, v]['used_bw'] += required_bw
                self.logger.info(f"Link s{u}-s{v} usage: {self.net.edges[u, v]['used_bw']}/{self.net.edges[u, v]['capacity']} Mbps")
            
            # Install flow rules
            self.install_path(path, item['flow'], slice_name, required_bw)
        
        msg = f"Slice '{slice_name}' activated successfully."
        self.logger.info(msg)
        return True, msg

    def install_path(self, path, flow, slice_name, pct):
        """ Installs forwarding and isolation rules for a slice path and applies QoS. """
        src_host, dst_host = flow['src'], flow['dst']
        switches = get_switch(self, None)
        datapath_list = {sw.dp.id: sw.dp for sw in switches}

        # Install FORWARD PATH RULES for the slice.
        for i in range(len(path) - 1):
            hop_src, hop_dst = path[i], path[i+1]
            datapath = datapath_list.get(hop_src)
            if not datapath:
                continue
            out_port = self.net[hop_src][hop_dst]['port']
            parser = datapath.ofproto_parser
            match = parser.OFPMatch(eth_type=0x0800, ipv4_src=IP_MAP[src_host], ipv4_dst=IP_MAP[dst_host])
            actions = [parser.OFPActionOutput(out_port)]
            self.add_flow(datapath, 10, match, actions)
            self.logger.info("FORWARD rule on s%d: %s->%s via port %d", hop_src, src_host, dst_host, out_port)

        # Install FORWARD ISOLATION RULE (DROP) at the first hop.
        dp_first_hop = datapath_list.get(path[0])
        if dp_first_hop:
            parser = dp_first_hop.ofproto_parser
            match = parser.OFPMatch(eth_type=0x0800, ipv4_src=IP_MAP[src_host])
            self.add_flow(dp_first_hop, 9, match, []) # Empty actions = drop
            self.logger.info("ISOLATION rule on s%d: DROP all traffic from %s not matching slice flow.", path[0], src_host)

        # Install REVERSE PATH RULES for the slice.
        reverse_path = list(path)
        reverse_path.reverse()
        for i in range(len(reverse_path) - 1):
            hop_src, hop_dst = reverse_path[i], reverse_path[i+1]
            datapath = datapath_list.get(hop_src)
            if not datapath:
                continue
            out_port = self.net[hop_src][hop_dst]['port']
            parser = datapath.ofproto_parser
            match = parser.OFPMatch(eth_type=0x0800, ipv4_src=IP_MAP[dst_host], ipv4_dst=IP_MAP[src_host])
            actions = [parser.OFPActionOutput(out_port)]
            self.add_flow(datapath, 10, match, actions)
            self.logger.info("REVERSE rule on s%d: %s->%s via port %d", hop_src, dst_host, src_host, out_port)

        # Install REVERSE ISOLATION RULE (DROP) at the reverse first hop.
        dp_rev_first_hop = datapath_list.get(reverse_path[0])
        if dp_rev_first_hop:
            parser = dp_rev_first_hop.ofproto_parser
            match = parser.OFPMatch(eth_type=0x0800, ipv4_src=IP_MAP[dst_host])
            self.add_flow(dp_rev_first_hop, 9, match, []) # Empty actions = drop
            self.logger.info("ISOLATION rule on s%d: DROP all traffic from %s not matching slice flow.", reverse_path[0], dst_host)

        # Apply QoS using the queue_create.sh script on the first hop interface.
        first_hop_src, first_hop_dst = path[0], path[1]
        link_data = self.net.get_edge_data(first_hop_src, first_hop_dst)
        iface = f"s{first_hop_src}-eth{link_data['port']}"
        if iface not in self.active_slices[slice_name]['ifaces']:
            self.active_slices[slice_name]['ifaces'].add(iface)
            self.logger.info("Applying QoS for slice '%s' on %s", slice_name, iface)
            script_path = os.path.join(os.path.dirname(__file__), 'queue_create.sh')
            subprocess.Popen([script_path, slice_name, str(pct), IP_MAP[src_host], IP_MAP[dst_host], iface])

    def deactivate_slice(self, slice_name):
        # Deactivate a slice and remove all associated rules and QoS.
        if slice_name not in self.active_slices:
            msg = f"Slice '{slice_name}' is not active."
            self.logger.warning(msg)
            return False, msg

        self.logger.info("--- Deactivating slice '%s' ---", slice_name)
        
        slice_info = self.active_slices[slice_name]
        spec = self.slices[slice_name]
        bw_to_release = slice_info['bw']

        # Remove all flow rules for the slice.
        switches = get_switch(self, None)
        datapath_list = {sw.dp.id: sw.dp for sw in switches}
        if datapath_list:
            any_dp = next(iter(datapath_list.values()))
            parser = any_dp.ofproto_parser
            for flow in spec['flows']:
                src_host, dst_host = flow['src'], flow['dst']
                # Remove FORWARD and REVERSE rules (priority 10)
                match_fwd = parser.OFPMatch(eth_type=0x0800, ipv4_src=IP_MAP[src_host], ipv4_dst=IP_MAP[dst_host])
                match_rev = parser.OFPMatch(eth_type=0x0800, ipv4_src=IP_MAP[dst_host], ipv4_dst=IP_MAP[src_host])
                for dp in datapath_list.values():
                    self.remove_flow(dp, 10, match_fwd)
                    self.remove_flow(dp, 10, match_rev)
                
                # Remove ISOLATION rules (priority 9)
                src_dpid = self.get_host_location(src_host)
                dst_dpid = self.get_host_location(dst_host)
                if datapath_list.get(src_dpid):
                    self.remove_flow(datapath_list[src_dpid], 9, parser.OFPMatch(eth_type=0x0800, ipv4_src=IP_MAP[src_host]))
                if datapath_list.get(dst_dpid):
                    self.remove_flow(datapath_list[dst_dpid], 9, parser.OFPMatch(eth_type=0x0800, ipv4_src=IP_MAP[dst_host]))
            self.logger.info("Flow rules for slice '%s' removed.", slice_name)

        # Release bandwidth for all links used by the slice.
        for path in slice_info['paths']:
            for i in range(len(path) - 1):
                u, v = path[i], path[i+1]
                if self.net.has_edge(u, v):
                    self.net.edges[u, v]['used_bw'] -= bw_to_release
                    self.logger.info(f"Link s{u}-s{v} usage: {self.net.edges[u, v]['used_bw']}/{self.net.edges[u, v]['capacity']} Mbps")

        # Clean up QoS rules using queue_delete.sh for each interface.
        script_path = os.path.join(os.path.dirname(__file__), 'queue_delete.sh')
        for iface in slice_info['ifaces']:
            subprocess.Popen([script_path, slice_name, iface])
        
        del self.active_slices[slice_name]
        msg = f"Slice '{slice_name}' deactivated successfully."
        self.logger.info(msg)
        return True, msg