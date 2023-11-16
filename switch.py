#!/usr/bin/python3
import sys
import struct
import wrapper
import threading
import time
from wrapper import recv_from_any_link, send_to_link, get_switch_mac, get_interface_name

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

def create_vlan_tag(vlan_id):
    # 0x8100 for the Ethertype for 802.1Q
    # vlan_id & 0x0FFF ensures that only the last 12 bits are used
    return struct.pack('!H', 0x8200) + struct.pack('!H', vlan_id & 0x0FFF)

def send_bdpu_every_sec():
    while True:
        # TODO Send BDPU every second if necessary
        time.sleep(1)

def get_config_data(filename, interfaces_vlan):
    file = open(filename, "r")
    lines = file.readlines()

    for index, line in enumerate(lines[1:]):
        vlan_id = line.split()[1]
        if (vlan_id != "T"):
            interfaces_vlan[index] = int(vlan_id)
        else:
            interfaces_vlan[index] = vlan_id

    file.close()

def main():
    # init returns the max interface number. Our interfaces
    # are 0, 1, 2, ..., init_ret value + 1
    switch_id = sys.argv[1]
    interfaces_vlan = dict()
    get_config_data(f"configs/switch{switch_id}.cfg", interfaces_vlan)

    num_interfaces = wrapper.init(sys.argv[2:])
    interfaces = range(0, num_interfaces)
    mac_table = dict()

    print("# Starting switch with id {}".format(switch_id), flush=True)
    print("[INFO] Switch MAC", ':'.join(f'{b:02x}' for b in get_switch_mac()))

    # Create and start a new thread that deals with sending BDPU
    t = threading.Thread(target=send_bdpu_every_sec)
    t.start()

    # Printing interface names
    for i in interfaces:
        print(get_interface_name(i))

    while True:
        # Note that data is of type bytes([...]).
        # b1 = bytes([72, 101, 108, 108, 111])  # "Hello"
        # b2 = bytes([32, 87, 111, 114, 108, 100])  # " World"
        # b3 = b1[0:2] + b[3:4].
        interface, data, length = recv_from_any_link()

        dest_mac, src_mac, ethertype, vlan_id = parse_ethernet_header(data)

        # Print the MAC src and MAC dst in human readable format
        dest_mac = ':'.join(f'{b:02x}' for b in dest_mac)
        src_mac = ':'.join(f'{b:02x}' for b in src_mac)

        # Note. Adding a VLAN tag can be as easy as
        # tagged_frame = data[0:12] + create_vlan_tag(10) + data[12:]

        print(f'Destination MAC: {dest_mac}')
        print(f'Source MAC: {src_mac}')
        print(f'EtherType: {ethertype}')

        print("Received frame of size {} on interface {}".format(length, interface), flush=True)

        tagged_frame = bytes()
        tagged_length = 0
        if (vlan_id == -1): # came from access interface
            vlan_id = interfaces_vlan[interface]
            tagged_frame = data[0:12] + create_vlan_tag(vlan_id) + data[12:]
            tagged_length = length + 4
        else: # came from trunk interface
            tagged_frame = data
            tagged_length = length
            data = data[0:12] + data[16:]
            length = length - 4

        print(f"vlan: {vlan_id}")

        # forwarding with learning
        mac_table[src_mac] = interface
        if dest_mac in mac_table:
            dest_interface = mac_table[dest_mac]
            if interfaces_vlan[dest_interface] == "T":
                send_to_link(dest_interface, tagged_frame, tagged_length)
            if interfaces_vlan[dest_interface] == vlan_id:
                send_to_link(dest_interface, data, length)
        else:
            for i in interfaces:
                if i != interface:
                    print(f"{get_interface_name(i)}: {interfaces_vlan[i]}")
                    if (interfaces_vlan[i] == "T"):
                        send_to_link(i, tagged_frame, tagged_length)
                    if interfaces_vlan[i] == vlan_id:
                        send_to_link(i, data, length)

        # TODO: Implement STP support

        # data is of type bytes.
        # send_to_link(i, data, length)

        print()
if __name__ == "__main__":
    main()
