"""Configuratii centrale pentru sistemul de prognoza si raportare."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


class ConfigurationError(RuntimeError):
    """Ridicata atunci cand fisierul de configurare este invalid."""


@dataclass(slots=True)
class PREInfo:
    cod_pre: str
    cod_brp: str
    operator_name: str
    timezone: str = "Europe/Bucharest"


@dataclass(slots=True)
class ModbusDevice:
    ip: str
    port: int = 502
    unit_id: int = 1
    timeout_s: float = 5.0
    retry_attempts: int = 3
    protocol: str = "modbus"


@dataclass(slots=True)
class RouterConfig:
    host: str
    api_user: Optional[str] = None
    api_password: Optional[str] = None
    snmp_enabled: bool = True
    snmp_port: int = 161
    verify_tls: bool = True
    ca_bundle: Optional[Path] = None
    openvpn_profile: Optional[Path] = None
    openvpn_executable: Optional[Path] = None


@dataclass(slots=True)
class QualityThresholds:
    max_thd_voltage: float = 8.0
    max_thd_current: float = 5.0
    min_power_factor: float = 0.9
    voltage_min_percent: float = -10.0
    voltage_max_percent: float = 10.0


@dataclass(slots=True)
class DeadlineConfig:
    d_minus_1_notification: time = time(hour=15, minute=0)
    reminder_offset_minutes: int = 30
    monthly_anre_day: int = 10
    monthly_anre_hour: int = 10


@dataclass(slots=True)
class StorageConfig:
    database_url: str = "sqlite:///./prognoza.db"
    backup_dir: Path = Path("backups")
    export_dir: Path = Path("exports")
    keep_days: int = 365


@dataclass(slots=True)
class WeatherConfig:
    provider: str = "openweather"
    api_key: Optional[str] = None
    latitude: float = 44.4268
    longitude: float = 26.1025
    forecast_horizon_hours: int = 48
    timezone: str = "Europe/Bucharest"


@dataclass(slots=True)
class NotificationRecipients:
    legal_representatives: List[str] = field(default_factory=list)
    dispatch_contacts: List[str] = field(default_factory=list)
    it_on_call: List[str] = field(default_factory=list)


@dataclass(slots=True)
class HTTPFieldConfig:
    path: str
    value_key: Optional[str] = None


@dataclass(slots=True)
class UMGHTTPConfig:
    base_url: str
    timeout_s: float = 5.0
    verify_tls: bool = False
    endpoints: Dict[str, HTTPFieldConfig] = field(default_factory=dict)


@dataclass(slots=True)
class Settings:
    pre: PREInfo
    modbus: ModbusDevice
    router: RouterConfig
    quality: QualityThresholds = field(default_factory=QualityThresholds)
    deadlines: DeadlineConfig = field(default_factory=DeadlineConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    weather: WeatherConfig = field(default_factory=WeatherConfig)
    recipients: NotificationRecipients = field(default_factory=NotificationRecipients)
    extra: Dict[str, str] = field(default_factory=dict)
    umg_http: Optional[UMGHTTPConfig] = None


def _load_file(path: Path) -> Dict[str, object]:
    if not path.exists():
        raise ConfigurationError(f"Configuration file {path} does not exist")
    text = path.read_text(encoding="utf-8")
    try:
        suffix = path.suffix.lower()
        if suffix in {".yaml", ".yml"}:
            if yaml is None:
                raise ConfigurationError("PyYAML is required for YAML configuration files")
            return yaml.safe_load(text) or {}
        if suffix == ".json":
            return json.loads(text)
    except ConfigurationError:
        raise
    except Exception as exc:  # pragma: no cover
        raise ConfigurationError(f"Invalid configuration format: {exc}") from exc
    raise ConfigurationError("Unsupported configuration format; use YAML or JSON")


def _looks_like_windows_absolute(path: str) -> bool:
    return (
        len(path) > 1 and path[1] == ":"
        or path.startswith("\\\\")
        or path.startswith("//")
    )


def _coerce_config_path(value: Path | str, base_dir: Path) -> Path:
    if isinstance(value, Path):
        raw_str = str(value)
        candidate = value.expanduser()
    else:
        raw_str = str(value)
        candidate = Path(value).expanduser()
    if candidate.is_absolute() or _looks_like_windows_absolute(raw_str):
        return candidate
    base = base_dir
    if candidate.parts and candidate.parts[0] == base_dir.name:
        base = base_dir.parent
    return (base / candidate).resolve()


def _parse_http_config(raw: Dict[str, object]) -> UMGHTTPConfig:
    try:
        base_url = raw["base_url"]
    except KeyError as exc:
        raise ConfigurationError("`umg_http.base_url` is required when protocol is HTTP") from exc
    endpoints_raw = raw.get("endpoints", {})
    endpoints: Dict[str, HTTPFieldConfig] = {}
    for name, value in endpoints_raw.items():
        if isinstance(value, str):
            endpoints[name] = HTTPFieldConfig(path=value, value_key=None)
        elif isinstance(value, dict):
            path = value.get("path")
            if not path:
                raise ConfigurationError(f"HTTP endpoint `{name}` requires a `path`")
            endpoints[name] = HTTPFieldConfig(path=path, value_key=value.get("value_key"))
        else:
            raise ConfigurationError(f"Invalid endpoint definition for `{name}`")
    return UMGHTTPConfig(
        base_url=str(base_url),
        timeout_s=float(raw.get("timeout_s", 5.0)),
        verify_tls=bool(raw.get("verify_tls", False)),
        endpoints=endpoints,
    )


def load_settings(path: Optional[Path | str] = None) -> Settings:
    candidate_paths: List[Path] = []
    if path:
        candidate_paths.append(Path(path))
    env_path = os.getenv("PROGNOZA_CONFIG")
    if env_path:
        candidate_paths.append(Path(env_path))
    candidate_paths.append(Path("config/settings.yaml"))

    for candidate in candidate_paths:
        if candidate.exists():
            raw = _load_file(candidate)
            config_path = candidate
            break
    else:
        raise ConfigurationError("No configuration file found")

    config_dir = config_path.parent.resolve()
    try:
        pre = PREInfo(**raw["pre"])
        modbus = ModbusDevice(**raw["modbus"])
        router_data = raw.get("router", {})
        for key in ("openvpn_profile", "ca_bundle", "openvpn_executable"):
            if router_data.get(key):
                router_data[key] = _coerce_config_path(router_data[key], config_dir)
        router = RouterConfig(**router_data)
        quality = QualityThresholds(**raw.get("quality", {}))
        deadlines = DeadlineConfig(**raw.get("deadlines", {}))
        storage_data = raw.get("storage", {})
        for key in ("backup_dir", "export_dir"):
            if storage_data.get(key):
                storage_data[key] = Path(storage_data[key])
        storage = StorageConfig(**storage_data)
        weather = WeatherConfig(**raw.get("weather", {}))
        recipients = NotificationRecipients(**raw.get("recipients", {}))
        extra = raw.get("extra", {})
        umg_http = _parse_http_config(raw["umg_http"]) if raw.get("umg_http") else None
    except KeyError as exc:  # pragma: no cover
        raise ConfigurationError(f"Missing configuration key: {exc}") from exc

    if not pre.cod_pre or not pre.cod_brp:
        raise ConfigurationError("PRE and BRP codes are mandatory per PO TEL-133")
    if modbus.port <= 0:
        raise ConfigurationError("Modbus port must be positive")

    storage.export_dir.mkdir(parents=True, exist_ok=True)
    storage.backup_dir.mkdir(parents=True, exist_ok=True)

    return Settings(
        pre=pre,
        modbus=modbus,
        router=router,
        quality=quality,
        deadlines=deadlines,
        storage=storage,
        weather=weather,
        recipients=recipients,
        extra=extra,
        umg_http=umg_http,
    )
