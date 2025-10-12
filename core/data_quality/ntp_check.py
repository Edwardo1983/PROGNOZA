"""Simple NTP drift check against pool.ntp.org."""
from __future__ import annotations

import socket
import struct
import time
from typing import Dict

NTP_DELTA = 2208988800  # seconds between 1900-01-01 and 1970-01-01


def ntp_check(host: str = "pool.ntp.org", timeout: float = 2.0) -> Dict[str, object]:
    """Return offset between system clock and remote NTP pool in milliseconds."""
    packet = b"\x1b" + 47 * b"\0"

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        t1 = time.time()
        sock.sendto(packet, (host, 123))
        data, _ = sock.recvfrom(48)
        t4 = time.time()

    if len(data) < 48:
        raise RuntimeError("Incomplete NTP response")

    unpacked = struct.unpack("!12I", data[0:48])
    transmit = unpacked[10] + float(unpacked[11]) / (1 << 32)
    server_time = transmit - NTP_DELTA

    offset = ((server_time - t1) + (server_time - t4)) / 2.0
    offset_ms = offset * 1000.0
    return {
        "offset_ms": offset_ms,
        "ok": abs(offset_ms) <= 1000.0,
        "host": host,
        "measured_at": time.time(),
    }
