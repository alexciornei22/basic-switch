#!/usr/bin/python3
import sys
import struct
import wrapper
import threading
import time
from wrapper import recv_from_any_link, send_to_link, get_switch_mac, get_interface_name

class Interface(object):
    def __init__(self, vlan_id, state):
        self.vlan_id = vlan_id
        self.state = state

class Config(object):
    def __init__(self, own_ID, root_ID, root_path_cost):
        self.own_ID = own_ID
        self.root_ID = root_ID
        self.root_path_cost = root_path_cost
        self.root_port = -1

def parse_ethernet_header(data):
    # Unpack the header fields from the byte array
    #dest_mac, src_mac, ethertype = struct.unpack('!6s6sH', data[:14])
    dest_mac = data[0:6]
    src_mac = data[6:12]
    
    # Extract ethertype. Under 802.1Q, this may be the bytes from the VLAN TAG
    ether_type = (data[12] << 8) + data[13]

    vlan_id = -1
    # Check for VLAN tag (0x8100 in network byte order is b'\x81\x00')
    if ether_type == 0x8200:
        vlan_tci = int.from_bytes(data[14:16], byteorder='big')
        vlan_id = vlan_tci & 0x0FFF  # extract the 12-bit VLAN ID
        ether_type = (data[16] << 8) + data[17]

    return dest_mac, src_mac, ether_type, vlan_id

def parse_bdpu_header(data):
    bdpu_header = data[21:]
    root_ID = int.from_bytes(bdpu_header[1:2], "big")
    root_path_cost = int.from_bytes(bdpu_header[9:13], "big")
    sender_ID = int.from_bytes(bdpu_header[13:14], "big")
    return root_ID, root_path_cost, sender_ID

def create_vlan_tag(vlan_id):
    # 0x8100 for the Ethertype for 802.1Q
    # vlan_id & 0x0FFF ensures that only the last 12 bits are used
    return struct.pack('!H', 0x8200) + struct.pack('!H', vlan_id & 0x0FFF)

def is_unicast(mac_addr):
    return mac_addr != bytes([0x01, 0x80, 0xc2, 0, 0, 0])

def make_bdpu_packet(config):
    dst_mac = bytes([0x01, 0x80, 0xc2, 0, 0, 0])
    src_mac = get_switch_mac()
    ether_len = int(38).to_bytes(2, byteorder='big')
    llc = bytes([0x42, 0x42, 0x03])

    root_ID = config.root_ID.to_bytes(1, byteorder='big')
    root_path_cost = config.root_path_cost.to_bytes(4, byteorder='big')
    own_ID = config.own_ID.to_bytes(1, byteorder='big')
    return dst_mac + src_mac + ether_len + llc + bytes(5) + root_ID + bytes(1) + src_mac + root_path_cost + own_ID + bytes(1) + src_mac + bytes(10) , 38 + 14

def send_bdpu_every_sec(config, interfaces):
    while True:
        if (config.own_ID == config.root_ID):
            bdpu_packet, length = make_bdpu_packet(config)
            for i in interfaces:
                if interfaces[i].vlan_id == "T":
                    send_to_link(i, bdpu_packet, length)
        time.sleep(1)

def get_config_data(filename, interfaces):
    file = open(filename, "r")
    lines = file.readlines()

    priority = int(lines[0].split()[0])

    for index, line in enumerate(lines[1:]):
        vlan_id = line.split()[1]
        if (vlan_id != "T"):
            interfaces[index] = Interface(int(vlan_id), 1)
        else:
            interfaces[index] = Interface(vlan_id, 1)

    file.close()
    return priority

def main():
    # init returns the max interface number. Our interfaces
    # are 0, 1, 2, ..., init_ret value + 1
    switch_id = sys.argv[1]
    interfaces = dict()
    mac_table = dict()
    num_interfaces = wrapper.init(sys.argv[2:])

    priority = get_config_data(f"configs/switch{switch_id}.cfg", interfaces)
    config = Config(priority, priority, 0)

    # Create and start a new thread that deals with sending BDPU
    t = threading.Thread(target=send_bdpu_every_sec, args=(config, interfaces))
    t.start()

    while True:
        # Note that data is of type bytes([...]).
        # b1 = bytes([72, 101, 108, 108, 111])  # "Hello"
        # b2 = bytes([32, 87, 111, 114, 108, 100])  # " World"
        # b3 = b1[0:2] + b[3:4].
        interface, data, length = recv_from_any_link()

        dest_mac, src_mac, ethertype, vlan_id = parse_ethernet_header(data)
        
        # forwarding with learning
        mac_table[src_mac] = interface
        if is_unicast(dest_mac):
            tagged_frame = bytes()
            tagged_length = 0
            if (vlan_id == -1): # came from access interface
                vlan_id = interfaces[interface].vlan_id
                tagged_frame = data[0:12] + create_vlan_tag(vlan_id) + data[12:]
                tagged_length = length + 4
            else: # came from trunk interface
                tagged_frame = data
                tagged_length = length
                data = data[0:12] + data[16:]
                length = length - 4

            if dest_mac in mac_table:
                dest_interface = mac_table[dest_mac]
                if interfaces[dest_interface].vlan_id == "T" and interfaces[dest_interface].state == 1:
                    send_to_link(dest_interface, tagged_frame, tagged_length)
                else:
                    send_to_link(dest_interface, data, length)

            else:
                for i in interfaces:
                    if i != interface:
                        if (interfaces[i].vlan_id == "T" and interfaces[i].state == 1):
                            send_to_link(i, tagged_frame, tagged_length)
                        if interfaces[i].vlan_id == vlan_id:
                            send_to_link(i, data, length)

        else:
            root_ID, root_path_cost, sender_ID = parse_bdpu_header(data)
            if root_ID < config.root_ID:
                config.root_ID = root_ID
                config.root_path_cost = root_path_cost + 10
                config.root_port = interface

                for i in interfaces:
                    if interfaces[i].vlan_id == "T" and i != config.root_port:
                        interfaces[i].state = 0
                
                for i in interfaces:
                    if interfaces[i].vlan_id == "T" and i != interface:
                        bdpu, bdpu_length = make_bdpu_packet(config)
                        send_to_link(i, bdpu, bdpu_length)
            elif root_ID == config.root_ID:
                if interface == config.root_port and root_path_cost + 10 < config.root_path_cost:
                    config.root_path_cost = root_path_cost + 10
                elif interface != config.root_port:
                    if root_path_cost > config.root_path_cost:
                        interfaces[interface].state = 1
            elif sender_ID == config.own_ID:
                interfaces[interface].state = 0

            if config.own_ID == config.root_ID:
                config.root_port = -1
                for i in interfaces:
                    interfaces[i].state = 1
if __name__ == "__main__":
    main()
