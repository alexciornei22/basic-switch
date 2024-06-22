# 1. Switching Table

When an Ethernet frame is received, the switch performs the algorithm explained below:

1. **Receive Frame on Port**: The frame  $F$ is received on port $P$.
2. **Source and Destination Addresses**: Extract the source (`src`) and destination (`dst`) MAC addresses from the frame $F$.
3. **Update MAC Table**: 
   - Add or update the entry in the MAC table associating the source MAC address (`src`) with the port $P$.
4. **Check Destination Address**:
   - **If the destination is unicast**:
     - If the destination address (`dst`) exists in the MAC table, forward the frame to the port mapped to this address.
     - If the destination address (`dst`) does not exist in the MAC table, forward the frame to all ports except the one it came from (port \( P \)).
   - **If the destination is not unicast**:
     - **Flood** - Forward the frame to all ports except the one it came from (port $P$).

When VLANs are involved, broadcasting is restricted to ports within the same VLAN or trunk ports, ensuring that frames are only sent where they are relevant within the VLAN structure.

# 2. VLAN

A significant advantage of Ethernet switches is their ability to create Virtual Local Area Networks (VLANs). A VLAN can be defined as a set of ports attached to one or more VLANs. A switch can support multiple VLANs. When a switch receives a frame with an unknown or broadcast destination, it transmits it over all ports that belong to the same VLAN (including trunks), but not over ports that belong to other VLANs.

Every time the switch receives a frame from an access interface (to a host), it will send the frame as follows:

- With an 802.1q header if it is sent to a trunk interface
- Without an 802.1q header if it is sent to an access interface and the VLAN ID matches the one of the interface from which it came

Every time the switch receives a frame from a trunk interface, it will remove the tag and send the frame as follows:

- With the 802.1q header (including the tag) if it is sent to a trunk interface
- Without the 802.1q header if it is sent to an access interface and the VLAN ID matches the one of the received frame

In this implementation, the switch will not retain VLAN tags when switching a frame to a host.

# 3. STP

In this implementation, there will be two states for a port on the switch: **Blocking** and **Listening** (open port).

- **Blocking Mode**: The port is inactive and does not forward frames.
- **Listening Mode**: The port is used normally.

### Initial State

We will start each port in **Blocking mode**. Initially, each switch will consider itself as the **Root Bridge**, which means it will set all ports to **Listening mode** because they are designated.

### Root Bridge Election

The next stage is to establish consensus among all switches on which one is the root. This is done by identifying the switch with the minimum ID. During this stage:

- Each switch that considers itself the root bridge will regularly send a BPDU frame (`send_bpdu_every_sec()`).
- Upon receiving a BPDU frame, each switch reacts based on the root bridge ID it knows.
- If the received BPDU has a smaller ID than the known root bridge ID, the switch updates the state of its ports and forwards the BPDU.

### Port States

- **Root Ports**: Ports that are the best path to the root bridge.
- **Designated Ports**: Ports that forward frames towards the root bridge.
- **Blocking Ports**: Ports that do not forward frames to prevent loops.

Only the **Root** and **Designated** ports are used to transmit data frames, and these ports are in **Listening mode**.
