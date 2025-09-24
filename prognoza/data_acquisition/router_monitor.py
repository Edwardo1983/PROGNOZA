"""Monitorizare Teltonika RUT240 pentru disponibilitatea tunelului VPN."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import requests

try:
    from pysnmp.hlapi import (  # type: ignore
        CommunityData,
        ContextData,
        ObjectIdentity,
        ObjectType,
        SnmpEngine,
        UdpTransportTarget,
        getCmd,
    )
except ImportError:  # pragma: no cover
    CommunityData = None  # type: ignore
    ContextData = None  # type: ignore
    ObjectIdentity = None  # type: ignore
    ObjectType = None  # type: ignore
    SnmpEngine = None  # type: ignore
    UdpTransportTarget = None  # type: ignore
    getCmd = None  # type: ignore

from prognoza.config.settings import RouterConfig

VPN_STATUS_ENDPOINT = "/cgi-bin/api-get"
NTP_STATUS_ENDPOINT = "/cgi-bin/api-get"


@dataclass(slots=True)
class RouterStatus:
    timestamp: datetime
    vpn_active: bool
    signal_strength: Optional[int] = None
    uptime_seconds: Optional[int] = None
    ntp_synced: Optional[bool] = None


class RouterMonitor:
    """Verifica starea routerului Teltonika RUT240."""

    def __init__(self, config: RouterConfig, timeout: float = 5.0) -> None:
        self._config = config
        self._timeout = timeout

    def check_http_status(self) -> RouterStatus:
        if not self._config.api_user or not self._config.api_password:
            raise RuntimeError("Router API credentials are not configured")
        verify_param = self._resolve_verify()
        url = f"https://{self._config.host}{VPN_STATUS_ENDPOINT}"
        payload = {
            "cmd": "get_status",
            "group": "vpn",
        }
        response = requests.get(
            url,
            params=payload,
            auth=(self._config.api_user, self._config.api_password),
            timeout=self._timeout,
            verify=verify_param,
        )
        response.raise_for_status()
        data = response.json()
        vpn_info = data.get("data", {}).get("openvpn", {})
        vpn_active = bool(vpn_info.get("status") == "connected")
        signal = data.get("data", {}).get("mobile", {}).get("rsrp")
        ntp_synced = self._check_ntp_status(verify_param)
        uptime = self._fetch_uptime_snmp()
        return RouterStatus(
            timestamp=datetime.now(timezone.utc),
            vpn_active=vpn_active,
            signal_strength=int(signal) if signal else None,
            uptime_seconds=uptime,
            ntp_synced=ntp_synced,
        )

    def _check_ntp_status(self, verify_param) -> Optional[bool]:
        if not self._config.api_user or not self._config.api_password:
            return None
        url = f"https://{self._config.host}{NTP_STATUS_ENDPOINT}"
        payload = {
            "cmd": "get_status",
            "group": "system",
        }
        try:
            response = requests.get(
                url,
                params=payload,
                auth=(self._config.api_user, self._config.api_password),
                timeout=self._timeout,
                verify=verify_param,
            )
            response.raise_for_status()
            data = response.json().get("data", {})
            return bool(data.get("system", {}).get("ntp_synced"))
        except requests.RequestException:  # pragma: no cover
            return None

    def _fetch_uptime_snmp(self) -> Optional[int]:
        if not self._config.snmp_enabled or getCmd is None or ObjectIdentity is None:
            return None
        iterator = getCmd(
            SnmpEngine(),
            CommunityData("public", mpModel=1),
            UdpTransportTarget((self._config.host, self._config.snmp_port), timeout=self._timeout),
            ContextData(),
            ObjectType(ObjectIdentity("1.3.6.1.2.1.1.3.0")),
        )
        error_indication, error_status, error_index, var_binds = next(iterator)
        if error_indication or error_status:  # pragma: no cover
            return None
        for name, val in var_binds:
            if str(name) == "1.3.6.1.2.1.1.3.0":
                return int(val) // 100
        return None

    def _resolve_verify(self):
        if self._config.ca_bundle:
            return str(self._config.ca_bundle)
        return self._config.verify_tls


__all__ = ["RouterMonitor", "RouterStatus"]
