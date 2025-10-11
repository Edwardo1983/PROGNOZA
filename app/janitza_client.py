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
        """Read configured holding registers as IEEE-754 floats with batch optimization."""
        start_total = time.perf_counter()
        client = ModbusTcpClient(host=self.host, port=self.modbus_port, timeout=self.timeout_s)
        if not client.connect():
            raise ConnectionError(f"Unable to establish Modbus TCP session with {self.host}:{self.modbus_port}")

        results: Dict[str, Optional[float]] = {}
        timing_log = []

        try:
            # Grupeaza registrele consecutive pentru citiri batch
            batches = self._group_consecutive_registers(self.registers)
            LOGGER.debug(f"Grouped {len(self.registers)} registers into {len(batches)} batches")

            idx = 0
            for batch_start, batch_registers in batches:
                idx += 1
                batch_names = [name for name, _ in batch_registers]

                if len(batch_registers) == 1:
                    # Citire individuala (registru izolat)
                    name, address = batch_registers[0]
                    start_reg = time.perf_counter()
                    value = self._read_float(client, address)
                    elapsed_ms = (time.perf_counter() - start_reg) * 1000

                    results[name] = value
                    status = "OK" if value is not None else "FAILED"
                    timing_log.append(f"{idx:02d}. {name:40s} @ {address:5d} = {elapsed_ms:7.2f}ms [{status}] [SINGLE]")

                    if elapsed_ms > 1000:
                        LOGGER.warning("Slow register read: %s @ %s took %.2fms", name, address, elapsed_ms)
                else:
                    # Citire batch (multiple registre consecutive)
                    start_reg = time.perf_counter()
                    batch_values = self._read_batch(client, batch_start, len(batch_registers))
                    elapsed_ms = (time.perf_counter() - start_reg) * 1000

                    # Distribuie valorile citite
                    for (name, address), value in zip(batch_registers, batch_values):
                        results[name] = value
                        status = "OK" if value is not None else "FAILED"
                        timing_log.append(f"{idx:02d}. {name:40s} @ {address:5d} = {elapsed_ms/len(batch_registers):7.2f}ms [{status}] [BATCH:{len(batch_registers)}]")
                        idx += 1
                    idx -= 1  # Adjust pentru loop

                    if elapsed_ms > 1000:
                        LOGGER.warning("Slow batch read: %d registers starting @ %s took %.2fms",
                                     len(batch_registers), batch_start, elapsed_ms)
        finally:
            client.close()

        total_elapsed = time.perf_counter() - start_total

        # Scrie log detaliat in fisier separat
        log_file = settings.DATA_DIR / "modbus_timing.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n{'=' * 80}\n")
            f.write(f"Modbus Read Session (BATCH MODE): {datetime.now(timezone.utc).astimezone().isoformat()}\n")
            f.write(f"Host: {self.host}:{self.modbus_port} | Timeout: {self.timeout_s}s\n")
            f.write(f"Total: {total_elapsed:.2f}s | Registers: {len(self.registers)} | Success: {sum(1 for v in results.values() if v is not None)}\n")
            f.write(f"Batches: {len(batches)}\n")
            f.write(f"{'-' * 80}\n")
            for line in timing_log:
                f.write(f"{line}\n")
            f.write(f"{'=' * 80}\n")

        LOGGER.info("Modbus read completed (BATCH): %.2fs, %d/%d registers OK", total_elapsed, sum(1 for v in results.values() if v is not None), len(self.registers))

        return results

    def _group_consecutive_registers(self, registers: Dict[str, int]) -> list:
        """
        Grupeaza registrele consecutive pentru citiri batch.

        Returns:
            Lista de tupluri: [(adresa_start, [(nume, adresa), ...]), ...]
        """
        sorted_regs = sorted(registers.items(), key=lambda x: x[1])

        batches = []
        current_batch = []
        last_address = None

        for name, address in sorted_regs:
            # Fiecare registru IEEE float = 2 words (4 bytes)
            # Consecutive inseamna: address = last_address + 2
            if last_address is None or address == last_address + 2:
                current_batch.append((name, address))
                last_address = address
            else:
                # Incepe un batch nou
                if current_batch:
                    batches.append((current_batch[0][1], current_batch))
                current_batch = [(name, address)]
                last_address = address

        # Adauga ultimul batch
        if current_batch:
            batches.append((current_batch[0][1], current_batch))

        return batches

    def _read_batch(self, client: ModbusTcpClient, start_address: int, count: int) -> list:
        """
        Citeste multiple registre consecutive intr-o singura cerere.

        Args:
            client: Client Modbus
            start_address: Adresa de start
            count: Numar de registre IEEE float (fiecare = 2 words)

        Returns:
            Lista de valori float (None pentru erori)
        """
        try:
            # Citeste count * 2 words (fiecare float = 2 words)
            response = client.read_holding_registers(
                address=start_address,
                count=count * 2,
                slave=self.unit_id
            )

            if not response or getattr(response, "isError", lambda: True)():
                LOGGER.debug(f"Batch read error for address {start_address}, count={count}")
                return [None] * count

            registers_data = getattr(response, "registers", None)
            if not registers_data or len(registers_data) != count * 2:
                return [None] * count

            # Decode fiecare float (2 words)
            values = []
            for i in range(count):
                try:
                    word_pair = registers_data[i*2:(i*2)+2]
                    if len(word_pair) != 2:
                        values.append(None)
                        continue

                    decoder = BinaryPayloadDecoder.fromRegisters(
                        word_pair,
                        byteorder=BIG_ENDIAN,
                        wordorder=BIG_ENDIAN
                    )
                    value = decoder.decode_32bit_float()

                    if math.isnan(value) or math.isinf(value):
                        values.append(None)
                    else:
                        values.append(float(np.float32(value)))
                except Exception as e:
                    LOGGER.debug(f"Error decoding float at offset {i}: {e}")
                    values.append(None)

            return values

        except Exception as exc:
            LOGGER.debug(f"Batch read failed for {start_address}, count={count}: {exc}")
            return [None] * count

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

    def export_csv(
        self,
        values: Dict[str, Optional[float]],
        timestamp: Optional[float] = None,
        path: Optional[Path] = None,
    ) -> Tuple[Dict[str, object], Path]:
        """Append readings to a daily CSV and return the stored row."""
        if timestamp is not None:
            capture_time = datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone()
        else:
            capture_time = datetime.now(timezone.utc).astimezone()
        timestamp_str = capture_time.replace(microsecond=0).isoformat()

        exports_dir = Path(path) if path is not None else settings.EXPORTS_DIR
        exports_dir.mkdir(parents=True, exist_ok=True)
        csv_path = exports_dir / f"umg_readings_{capture_time.date().isoformat()}.csv"

        if csv_path.exists():
            try:
                head = pd.read_csv(csv_path, usecols=["timestamp"], nrows=1)
                first_ts = datetime.fromisoformat(str(head.iloc[0]["timestamp"]))
            except Exception:  # pragma: no cover
                first_ts = capture_time
        else:
            first_ts = capture_time

        elapsed_minutes = round((capture_time - first_ts).total_seconds() / 60.0, 2)
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
    polling_cfg = data.get("polling", {})
    export_dir_cfg = polling_cfg.get("export_dir")
    if export_dir_cfg:
        export_path = Path(export_dir_cfg)
        if not export_path.is_absolute():
            export_path = settings.BASE_DIR / export_dir_cfg
        resolved["export_dir"] = export_path
    resolved["polling"] = polling_cfg
    return resolved
