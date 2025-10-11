"""Client utilities for checking and reading Janitza UMG values."""
from __future__ import annotations
import logging
import math
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
import yaml
from pymodbus.client import ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder

from app import settings

LOGGER = logging.getLogger(__name__)

try:
    BIG_ENDIAN = Endian.__members__["BIG"]
except KeyError as exc:
    raise RuntimeError("pymodbus Endian enum missing BIG entry") from exc

DEFAULT_REGISTERS: Dict[str, int] = {
    # Instantaneous power
    "power_active_l1": 19020,
    "power_active_l2": 19022,
    "power_active_l3": 19024,
    "power_active_total": 19026,
    "power_reactive_l1": 19036,
    "power_reactive_l2": 19038,
    "power_reactive_l3": 19040,
    "power_reactive_total": 19042,
    "power_apparent_l1": 19028,
    "power_apparent_l2": 19030,
    "power_apparent_l3": 19032,
    "power_apparent_total": 19034,
    # Energy
    "energy_active_import_l1": 13987,
    "energy_active_import_l2": 13989,
    "energy_active_import_l3": 13991,
    "energy_active_import_total": 13997,
    "energy_active_export_l1": 13999,
    "energy_active_export_l2": 14001,
    "energy_active_export_l3": 14003,
    "energy_active_export_total": 14009,
    "energy_export_global_l1": 19070,
    "energy_export_global_l2": 19072,
    "energy_export_global_l3": 19074,
    "energy_export_global_total": 19076,
    "energy_reactive_total_l1": 13975,
    "energy_reactive_total_l2": 13977,
    "energy_reactive_total_l3": 13979,
    "energy_reactive_total_sum": 13985,
    "energy_reactive_inductive_l1": 14059,
    "energy_reactive_inductive_l2": 14061,
    "energy_reactive_inductive_l3": 14063,
    "energy_reactive_inductive_sum": 14069,
    "energy_reactive_capacitive_l1": 14071,
    "energy_reactive_capacitive_l2": 14073,
    "energy_reactive_capacitive_l3": 14075,
    "energy_reactive_capacitive_sum": 14081,
    # Electrical values
    "cos_phi_l1": 19044,
    "cos_phi_l2": 19046,
    "cos_phi_l3": 19048,
    "frequency": 19050,
    "voltage_l1_n": 19000,
    "voltage_l2_n": 19002,
    "voltage_l3_n": 19004,
    "voltage_l1_l2": 19006,
    "voltage_l2_l3": 19008,
    "voltage_l3_l1": 19010,
    "current_l1": 19012,
    "current_l2": 19014,
    "current_l3": 19016,
    "current_sum": 19018,
    # Legacy compatibility metrics
    "energy_active_import": 19062,
    "energy_active_export": 19070,
    "energy_reactive_import": 19094,
    "energy_reactive_export": 19102,
    "voltage_l1": 19000,
    "voltage_l2": 19002,
    "voltage_l3": 19004,
    "current_l1_avg": 19012,
    "current_l2_avg": 19014,
    "current_l3_avg": 19016,
    "power_factor": 19636,
    "thd_voltage_l1": 19110,
    "thd_current_l1": 19116,
}


@dataclass
class JanitzaUMG:
    """Minimal Janitza UMG helper supporting connectivity and Modbus reads."""

    host: str = settings.UMG_IP
    http_port: int = 80
    modbus_port: int = settings.UMG_TCP_PORT
    timeout_s: float = 3.0
    registers: Dict[str, int] | None = None
    unit_id: int = 1

    def __post_init__(self) -> None:
        if self.registers is None:
            self.registers = DEFAULT_REGISTERS.copy()

    @staticmethod
    def tcp_ping(host: str, port: int, timeout_s: float) -> Optional[float]:
        """Attempt a TCP connection and return latency in milliseconds."""
        start = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=timeout_s):
                end = time.perf_counter()
                return round((end - start) * 1000.0, 3)
        except (OSError, ValueError):
            return None

    def health(self) -> Dict[str, Optional[float] | bool]:
        """Probe HTTP and Modbus ports returning latency metrics."""
        http_ms = self.tcp_ping(self.host, 80, self.timeout_s)
        modbus_ms = self.tcp_ping(self.host, self.modbus_port, self.timeout_s)
        reachable = modbus_ms is not None and (http_ms is not None or modbus_ms is not None)
        return {
            "http_ms": http_ms,
            "modbus_ms": modbus_ms,
            "reachable": reachable,
        }

    def read_registers(self) -> Dict[str, Optional[float]]:
        """Read configured holding registers as IEEE-754 floats."""
        client = ModbusTcpClient(host=self.host, port=self.modbus_port, timeout=self.timeout_s)
        if not client.connect():
            raise ConnectionError(f"Unable to establish Modbus TCP session with {self.host}:{self.modbus_port}")

        results: Dict[str, Optional[float]] = {}
        try:
            for name, address in self.registers.items():
                value = self._read_float(client, address)
                results[name] = value
        finally:
            client.close()
        return results

    def _read_float(self, client: ModbusTcpClient, address: int) -> Optional[float]:
        try:
            response = client.read_holding_registers(address=address, count=2, slave=self.unit_id)
        except Exception as exc:  # pragma: no cover - network failure
            LOGGER.debug("Modbus read failed for %s @ %s: %s", self.host, address, exc)
            return None
        if not response or getattr(response, "isError", lambda: True)():
            LOGGER.debug("Modbus read error for address %s", address)
            return None
        registers = getattr(response, "registers", None)
        if not registers or len(registers) != 2:
            return None
        decoder = BinaryPayloadDecoder.fromRegisters(
            registers,
            byteorder=BIG_ENDIAN,
            wordorder=BIG_ENDIAN,
        )
        try:
            value = decoder.decode_32bit_float()
        except Exception:  # pragma: no cover - malformed payload
            return None
        if math.isnan(value) or math.isinf(value):
            return None
        return float(np.float32(value))

    def export_csv(self, values: Dict[str, Optional[float]], path: Optional[Path] = None) -> Tuple[Dict[str, object], Path]:
        """Append readings to a daily CSV and return the stored row."""
        timestamp = datetime.now(timezone.utc).astimezone()
        timestamp_str = timestamp.isoformat()

        exports_dir = Path(path) if path else settings.EXPORTS_DIR
        exports_dir.mkdir(parents=True, exist_ok=True)
        csv_path = exports_dir / f"umg_readings_{timestamp.date().isoformat()}.csv"

        if csv_path.exists():
            try:
                head = pd.read_csv(csv_path, usecols=["timestamp"], nrows=1)
                first_ts = datetime.fromisoformat(str(head.iloc[0]["timestamp"]))
            except Exception:  # pragma: no cover
                first_ts = timestamp
        else:
            first_ts = timestamp

        elapsed_minutes = round((timestamp - first_ts).total_seconds() / 60.0, 2)
        thresholds = [5, 10, 15, 30, 60]
        milestones = ";".join(str(t) for t in thresholds if elapsed_minutes >= t)

        row: Dict[str, object] = {
            "timestamp": timestamp_str,
            **values,
            "elapsed_minutes": elapsed_minutes,
            "milestones": milestones,
        }

        pd.DataFrame([row]).to_csv(
            csv_path,
            mode="a",
            header=not csv_path.exists(),
            index=False,
        )
        return row, csv_path


def load_umg_config() -> Dict[str, object]:
    """Load UMG settings from config.yaml, falling back to defaults."""
    if not settings.CONFIG_FILE.exists():
        return {"registers": DEFAULT_REGISTERS.copy()}
    with settings.CONFIG_FILE.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    umg_cfg = data.get("umg", {})
    registers = umg_cfg.get("registers") or data.get("registers") or DEFAULT_REGISTERS.copy()
    resolved: Dict[str, object] = {
        "host": umg_cfg.get("host", settings.UMG_IP),
        "http_port": umg_cfg.get("http_port", 80),
        "modbus_port": umg_cfg.get("modbus_port", settings.UMG_TCP_PORT),
        "timeout_s": umg_cfg.get("timeout_s", 3),
        "unit_id": umg_cfg.get("unit_id", 1),
        "registers": registers,
    }
    return resolved
