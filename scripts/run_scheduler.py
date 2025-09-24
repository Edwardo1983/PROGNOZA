"""Porneste schedulerul pentru notificari si rapoarte."""
from __future__ import annotations

import sys
import time

from prognoza.compliance.deadline_monitor import DeadlineMonitor
from prognoza.compliance.legal_validator import LegalValidator
from prognoza.config.settings import load_settings
from prognoza.infrastructure.vpn import OpenVPNError, create_vpn_manager
from prognoza.scheduling.tasks import TaskRegistry


def main() -> None:
    settings = load_settings()
    vpn_manager = None
    try:
        if settings.router.openvpn_profile:
            print("Pornire tunel OpenVPN pentru acces la UMG...")
            vpn_manager = create_vpn_manager(settings.router, timeout_s=120)
            vpn_manager.start(timeout_s=120)
            if vpn_manager.log_file:
                print(f"VPN activ (log: {vpn_manager.log_file})")
        monitor = DeadlineMonitor(settings.pre, settings.deadlines)
        validator = LegalValidator(settings.pre, settings.quality, settings.deadlines)
        registry = TaskRegistry(settings, monitor, validator)
        registry.register_all()
        registry.start()
        print("Scheduler started. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except OpenVPNError as exc:
        print(f"Nu s-a putut porni tunelul OpenVPN: {exc}")
        if vpn_manager and vpn_manager.log_file:
            print(f"Verifica logul: {vpn_manager.log_file}")
        sys.exit(2)
    except KeyboardInterrupt:
        print("Stopping scheduler...")
    finally:
        if 'monitor' in locals() and monitor:
            monitor.stop()
        if vpn_manager:
            vpn_manager.stop()
            print("Tunel OpenVPN oprit.")
        print("Scheduler stopped.")


if __name__ == "__main__":
    main()
