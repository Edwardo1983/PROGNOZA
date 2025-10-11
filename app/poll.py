"""Polling helpers for Janitza UMG via VPN with minute-level synchronisation."""
from __future__ import annotations

import json
import logging
import math
import time
from datetime import datetime, timezone
from typing import Dict, Optional

from app.janitza_client import JanitzaUMG, load_umg_config
from app.vpn_connection import VPNConnection

LOGGER = logging.getLogger(__name__)


def _ceil_to_interval(timestamp: float, interval_seconds: int) -> float:
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be greater than zero")
    return math.ceil(timestamp / interval_seconds) * interval_seconds


def _sleep_until(target_wall_time: float) -> None:
    remaining = target_wall_time - time.time()
    if remaining <= 0:
        return

    target_monotonic = time.monotonic() + remaining
    while True:
        remaining = target_monotonic - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(remaining, 0.5))


def _format_wall_time(timestamp: Optional[float]) -> str:
    if timestamp is None:
        return "-"
    return time.strftime("%H:%M:%S", time.localtime(timestamp))


def _to_iso(timestamp: Optional[float]) -> Optional[str]:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone().isoformat()


def poll_once(scheduled_wall_time: Optional[float] = None) -> Dict[str, object]:
    """Ensure VPN connectivity, read registers once, and append the CSV row."""
    actual_start = time.time()
    vpn = VPNConnection()
    status_before = vpn.status()
    vpn_already_connected = bool(status_before.get("is_connected"))
    started_vpn = False

    start_delay = None
    if scheduled_wall_time is not None:
        start_delay = actual_start - scheduled_wall_time

    if not vpn_already_connected:
        connect_result = vpn.connect()
        if not connect_result.get("is_connected"):
            raise RuntimeError("Unable to establish VPN tunnel before polling")
        started_vpn = True

    try:
        umg_cfg = load_umg_config()
        client = JanitzaUMG(
            host=umg_cfg.get("host"),
            http_port=umg_cfg.get("http_port"),
            modbus_port=umg_cfg.get("modbus_port"),
            timeout_s=umg_cfg.get("timeout_s"),
            registers=umg_cfg.get("registers"),
            unit_id=umg_cfg.get("unit_id", 1),
        )

        health = client.health()
        if not health.get("reachable"):
            raise RuntimeError(f"UMG device unreachable: {json.dumps(health, sort_keys=True)}")

        readings = client.read_registers()
        capture_timestamp = scheduled_wall_time or actual_start
        export_dir = umg_cfg.get("export_dir")
        row, csv_path = client.export_csv(readings, timestamp=capture_timestamp, path=export_dir)

        payload: Dict[str, object] = {
            "health": health,
            "data": row,
            "csv_path": str(csv_path),
            "started_at": actual_start,
            "started_at_iso": _to_iso(actual_start),
            "scheduled_start": scheduled_wall_time,
            "scheduled_start_iso": _to_iso(scheduled_wall_time),
            "start_delay_s": start_delay,
            "vpn_started": started_vpn,
        }
        return payload
    finally:
        if started_vpn:
            vpn.disconnect()


def poll_loop(
    interval_s: int = 60,
    cycles: Optional[int] = 1,
    *,
    sync: bool = True,
    sync_tolerance_s: float = 0.5,
    max_drift_s: float = 3.0,
) -> None:
    """Run ``poll_once`` repeatedly, aligned to the wall clock if requested."""
    interval_s = max(1, int(interval_s))
    executed = 0

    next_run = time.time()
    if sync:
        next_run = _ceil_to_interval(next_run, interval_s)
        LOGGER.info("First poll scheduled for %s (interval %ds)", _format_wall_time(next_run), interval_s)

    while cycles is None or executed < cycles:
        scheduled = next_run if sync else None

        if scheduled is not None:
            wait_time = scheduled - time.time()
            if wait_time > sync_tolerance_s:
                LOGGER.info(
                    "Sleeping %.2fs to align with %s", wait_time, _format_wall_time(scheduled)
                )
                _sleep_until(scheduled)

        payload = poll_once(scheduled_wall_time=scheduled)

        start_delay = payload.get("start_delay_s")
        if scheduled is not None and start_delay is not None:
            LOGGER.debug(
                "Poll started at %s (scheduled %s, drift %+0.3fs)",
                _format_wall_time(payload.get("started_at")),
                _format_wall_time(scheduled),
                start_delay,
            )
            if abs(start_delay) > max_drift_s:
                LOGGER.warning(
                    "Start drift %.3fs exceeds configured max %.3fs (scheduled %s)",
                    start_delay,
                    max_drift_s,
                    _format_wall_time(scheduled),
                )

        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        executed += 1
        if cycles is not None and executed >= cycles:
            break

        if sync and scheduled is not None:
            next_run += interval_s
            while next_run <= time.time():
                next_run += interval_s
        else:
            next_run = time.time() + interval_s
