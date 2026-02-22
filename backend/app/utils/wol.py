"""Wake-on-LAN (WOL) implementation."""

import socket
import struct


def send_wol(mac_address: str, broadcast: str = "255.255.255.255", port: int = 9) -> None:
    """
    Send a Wake-on-LAN magic packet.

    Args:
        mac_address: MAC address in format "AA:BB:CC:DD:EE:FF" or "AA-BB-CC-DD-EE-FF"
        broadcast: Broadcast address (default: 255.255.255.255)
        port: UDP port (default: 9)
    """
    mac = mac_address.replace(":", "").replace("-", "")
    if len(mac) != 12:
        raise ValueError(f"Invalid MAC address: {mac_address}")

    mac_bytes = bytes.fromhex(mac)
    # Magic packet: 6x 0xFF + 16x MAC address
    packet = b"\xff" * 6 + mac_bytes * 16

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(packet, (broadcast, port))
