"""Gestionare conexiuni OpenVPN pentru acces la UMG 509."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from prognoza.config.settings import RouterConfig


class OpenVPNError(RuntimeError):
    """Erori la pornirea sau gestionarea conexiunii OpenVPN."""


@dataclass
class OpenVPNManager:
    profile: Path
    executable: str = "openvpn"
    log_dir: Path = Path("logs")
    up_timeout_s: int = 120

    def __post_init__(self) -> None:
        self.profile = self.profile.expanduser().resolve()
        self.log_dir = self.log_dir.expanduser().resolve()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._process: Optional[subprocess.Popen[str]] = None
        self._log_file: Optional[Path] = None
        self._connected = False

    @property
    def log_file(self) -> Optional[Path]:
        return self._log_file

    @property
    def connected(self) -> bool:
        return self._connected and self._process is not None and self._process.poll() is None

    def start(self, timeout_s: Optional[int] = None) -> None:
        if self._process and self._process.poll() is None:
            return
        timeout = timeout_s or self.up_timeout_s
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        log_path = self.log_dir / f"openvpn_{self.profile.stem}_{timestamp}.log"
        executable_path = str(self.executable)
        if isinstance(self.executable, Path):
            executable_path = str(self.executable)
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        try:
            self._process = subprocess.Popen(
                [executable_path, "--config", str(self.profile)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=creationflags,
            )
        except FileNotFoundError as exc:
            raise OpenVPNError(f"OpenVPN executable not found: {executable_path}") from exc
        except PermissionError as exc:
            raise OpenVPNError("Insufficient privileges to launch OpenVPN (run as Administrator)") from exc
        assert self._process.stdout is not None
        start_time = time.monotonic()
        with log_path.open("w", encoding="utf-8") as log_handle:
            while True:
                if timeout and time.monotonic() - start_time > timeout:
                    self._terminate_process()
                    raise OpenVPNError("OpenVPN connection timed out")
                line = self._process.stdout.readline()
                if not line:
                    if self._process.poll() is not None:
                        code = self._process.returncode
                        raise OpenVPNError(f"OpenVPN exited unexpectedly with code {code}")
                    time.sleep(0.2)
                    continue
                log_handle.write(line)
                log_handle.flush()
                if "AUTH_FAILED" in line:
                    self._terminate_process()
                    raise OpenVPNError("OpenVPN authentication failed")
                if "TLS Error" in line or "Connection reset" in line or "Inactivity timeout" in line:
                    start_time = time.monotonic()
                if "Initialization Sequence Completed" in line:
                    self._connected = True
                    break
        self._log_file = log_path

    def stop(self, wait_s: float = 10.0) -> None:
        if not self._process or self._process.poll() is not None:
            self._process = None
            self._connected = False
            return
        if os.name == "nt":
            try:
                self._process.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
            except ValueError:
                self._process.terminate()
        else:
            self._process.terminate()
        try:
            self._process.wait(timeout=wait_s)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=wait_s)
        finally:
            self._process = None
            self._connected = False

    def _terminate_process(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
        self._process = None
        self._connected = False


def create_vpn_manager(router: RouterConfig, log_dir: Path = Path("logs"), timeout_s: int = 120) -> OpenVPNManager:
    if not router.openvpn_profile:
        raise OpenVPNError("Router configuration does not provide `openvpn_profile` path")
    executable: str | Path = "openvpn"
    if router.openvpn_executable:
        executable = router.openvpn_executable
    manager = OpenVPNManager(
        profile=router.openvpn_profile,
        executable=str(executable),
        log_dir=log_dir,
        up_timeout_s=timeout_s,
    )
    return manager
