"""Citire date din Janitza UMG 509 PRO prin Modbus TCP sau HTTP."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import struct
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd
import requests
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusIOException
from requests import Response
from tenacity import RetryError, retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from prognoza.config.settings import ModbusDevice, UMGHTTPConfig

# Toate registrele sunt float 32-bit (IEEE 754) si ocupa doua registre consecutive.
REGISTER_MAP: Dict[str, int] = {
    # Puteri instantanee (kW/kvar/kVA) - suma pe 3 faze
    "power_active_total": 19026,
    "power_reactive_total": 19042,
    "power_apparent_total": 19034,
    # Energii cumulative (kWh/kvarh)
    "energy_active_import": 19062,
    "energy_active_export": 19070,
    "energy_reactive_import": 19094,
    "energy_reactive_export": 19102,
    # Parametri calitate
    "voltage_l1": 19000,
    "voltage_l2": 19002,
    "voltage_l3": 19004,
    "current_l1": 19012,
    "current_l2": 19014,
    "current_l3": 19016,
    "frequency": 19050,
    "power_factor": 19636,
    "thd_voltage_l1": 19110,
    "thd_current_l1": 19116,
}

QUALITY_LIMITS: Dict[str, float] = {
    "voltage_thd_max": 8.0,
    "current_thd_max": 5.0,
    "power_factor_min": 0.9,
    "frequency_min": 49.5,
    "frequency_max": 50.5,
    "voltage_variation": 10.0,
}

# Alias-uri pentru compatibilitate cu restul pipeline-ului (denumiri istorice).
FIELD_ALIASES: Dict[str, str] = {
    "active_power_kw": "power_active_total",
    "reactive_power_kvar": "power_reactive_total",
    "apparent_power_kva": "power_apparent_total",
    "energy_import_kwh": "energy_active_import",
    "energy_export_kwh": "energy_active_export",
    "frequency_hz": "frequency",
    "thd_voltage": "thd_voltage_l1",
    "thd_current": "thd_current_l1",
}


@dataclass(slots=True)
class Measurement:
    timestamp: datetime
    values: Dict[str, float]


class UMG509Reader:
    """Client pentru preluarea datelor din UMG 509 PRO."""

    def __init__(
        self,
        config: ModbusDevice,
        profile_export_dir: Optional[Path] = None,
        http_config: Optional[UMGHTTPConfig] = None,
    ) -> None:
        self._config = config
        self._profile_export_dir = profile_export_dir
        self._http_config = http_config
        self._use_http = config.protocol.lower() == "http"
        if self._use_http:
            if not http_config:
                raise ValueError("HTTP protocol selected but `umg_http` configuration missing")
            self._session: Optional[requests.Session] = None
            self._client = None
        else:
            self._client = ModbusTcpClient(
                host=config.ip,
                port=config.port,
                timeout=config.timeout_s,
            )
            self._session = None

    def __enter__(self) -> "UMG509Reader":
        if self._use_http:
            return self
        if not self._client.connect():
            raise ConnectionError(f"Cannot connect to UMG at {self._config.ip}:{self._config.port}")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._client:
            self._client.close()
        if self._session:
            self._session.close()

    def _ensure_session(self) -> requests.Session:
        if not self._session:
            self._session = requests.Session()
        return self._session

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_fixed(1), retry=retry_if_exception_type(ConnectionError))
    def read_realtime_measurements(self, fields: Optional[Iterable[str]] = None) -> Measurement:
        """Citeste valori instantanee necesare raportarii."""
        requested_fields = list(fields) if fields else list(REGISTER_MAP.keys())
        canonical_order: List[str] = []

        for field in requested_fields:
            if field in REGISTER_MAP:
                canonical = field
            elif field in FIELD_ALIASES:
                canonical = FIELD_ALIASES[field]
            else:
                raise KeyError(f"Unknown measurement field requested: {field}")
            if canonical not in canonical_order:
                canonical_order.append(canonical)

        if self._use_http:
            base_values = self._read_http(canonical_order)
        else:
            base_values = self._read_modbus(canonical_order)

        values: Dict[str, float] = dict(base_values)
        for alias, canonical in FIELD_ALIASES.items():
            if canonical in base_values and alias not in values:
                values[alias] = base_values[canonical]

        return Measurement(timestamp=datetime.now(timezone.utc), values=values)

    def _read_modbus(self, canonical_order: List[str]) -> Dict[str, float]:
        if not self._client:
            raise ConnectionError("Modbus client not initialized")
        if not self._client.connect():  # reconectare automata pentru robustete
            raise ConnectionError("Failed to establish Modbus connection")
        base_values: Dict[str, float] = {}
        for canonical in canonical_order:
            register = REGISTER_MAP[canonical]
            try:
                response = self._client.read_holding_registers(address=register, count=2, unit=self._config.unit_id)
            except ModbusIOException as exc:  # pragma: no cover - hardware specific
                raise ConnectionError(f"Modbus IO error: {exc}") from exc
            if not response or response.isError():
                raise ConnectionError(f"Failed to read register {register} for field {canonical}")
            base_values[canonical] = self._to_float(response.registers)
        return base_values

    def _read_http(self, canonical_order: List[str]) -> Dict[str, float]:
        if not self._http_config:
            raise ConnectionError("HTTP configuration missing")
        session = self._ensure_session()
        base_values: Dict[str, float] = {}
        base_url = self._http_config.base_url.rstrip("/")
        for canonical in canonical_order:
            endpoint = self._http_config.endpoints.get(canonical)
            if not endpoint:
                raise KeyError(f"No HTTP endpoint configured for field `{canonical}`")
            url = base_url + endpoint.path
            try:
                response: Response = session.get(
                    url,
                    timeout=self._http_config.timeout_s,
                    verify=self._http_config.verify_tls,
                )
            except requests.RequestException as exc:
                raise ConnectionError(f"HTTP request failed for {url}: {exc}") from exc
            if response.status_code >= 400:
                raise ConnectionError(f"HTTP {response.status_code} received for {url}")
            try:
                payload = response.json()
            except ValueError as exc:
                raise ConnectionError(f"Invalid JSON payload for {url}: {exc}") from exc
            value = self._extract_value(payload, endpoint.value_key, canonical)
            base_values[canonical] = float(value)
        return base_values

    @staticmethod
    def _extract_value(payload: object, value_key: Optional[str], field: str) -> float:
        data = payload
        if value_key:
            keys = value_key.split(".")
            for key in keys:
                if isinstance(data, dict) and key in data:
                    data = data[key]
                else:
                    raise ConnectionError(f"Key `{value_key}` not found in response for `{field}`")
        if isinstance(data, (int, float)):
            return float(data)
        raise ConnectionError(f"Unexpected payload format for `{field}`: {data}")

    def read_profile_csv(self, date: datetime) -> pd.DataFrame:
        """Incarca profilul de 15 minute exportat de UMG in CSV."""
        if not self._profile_export_dir:
            raise FileNotFoundError("Profile export directory not configured")
        date_str = date.strftime("%Y%m%d")
        pattern = f"profile_{date_str}.csv"
        candidate = next((p for p in self._profile_export_dir.glob(pattern)), None)
        if candidate is None:
            raise FileNotFoundError(f"Profile file not found: {pattern}")
        df = pd.read_csv(candidate, sep=";", decimal=",", parse_dates=["timestamp"], dayfirst=True)
        df = df.set_index("timestamp").sort_index()
        return df

    @staticmethod
    def _to_float(registers: List[int]) -> float:
        """Converteste doua registre Modbus (big-endian) in float IEEE-754."""
        if len(registers) != 2:
            raise ValueError("Expected two registers for float conversion")
        packed = struct.pack(">HH", registers[0], registers[1])
        return struct.unpack(">f", packed)[0]


def fetch_measurements(
    config: ModbusDevice,
    fields: Optional[Iterable[str]] = None,
    http_config: Optional[UMGHTTPConfig] = None,
) -> Measurement:
    """Helper procedural pentru citire rapida."""
    reader = UMG509Reader(config, http_config=http_config)
    try:
        with reader:
            return reader.read_realtime_measurements(fields)
    except RetryError as exc:  # pragma: no cover
        raise ConnectionError("Repeated read failure") from exc
    except AttributeError:
        # HTTP mode does not need context manager connection
        return reader.read_realtime_measurements(fields)
