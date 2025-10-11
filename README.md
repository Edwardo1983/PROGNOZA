# PROGNOZA - Industrial Energy Monitoring System

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Automated monitoring system for Janitza UMG 509 PRO energy analyzers via OpenVPN connection. Collects Modbus data at synchronized intervals and exports to CSV for time-series analysis and energy forecasting.

---

## Features

- **Automated VPN Management**: Connects to remote devices via OpenVPN GUI
- **Modbus TCP Polling**: Reads 50+ registers from Janitza UMG 509 PRO
- **Time-Synchronized Sampling**: Collects data at exact minute intervals (±3s accuracy)
- **CSV Export**: Daily files with ISO timestamps and temporal markers
- **Health Monitoring**: HTTP and Modbus connectivity checks
- **Configurable Registers**: YAML-based register mapping
- **Windows Task Scheduler Ready**: Run as scheduled background task

---

## System Architecture

```
┌─────────────────┐      ┌──────────────┐      ┌─────────────────┐
│   Python App    │─────▶│  OpenVPN GUI │─────▶│  VPN Gateway    │
│   (This Repo)   │      │   (Windows)  │      │   (RUT240/etc)  │
└─────────────────┘      └──────────────┘      └─────────────────┘
                                                         │
                                                         ▼
                                                ┌─────────────────┐
                                                │  Janitza UMG    │
                                                │  509 PRO        │
                                                │  192.168.x.x    │
                                                └─────────────────┘
```

---

## Quick Start

### Prerequisites

1. **Python 3.10+** installed
2. **OpenVPN GUI** for Windows ([Download](https://openvpn.net/community-downloads/))
   - Install to `C:\Program Files\OpenVPN\`
3. **OpenVPN configuration file** (`.ovpn`) with credentials
4. Network access to VPN gateway

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/prognoza.git
cd prognoza

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -m app --help
```

### Configuration

1. **Place your OpenVPN file** in `secrets/` directory:
   ```
   secrets/user@example-site.ovpn
   ```

2. **Edit settings** in [app/settings.py](app/settings.py):
   ```python
   # Your OpenVPN file name
   OVPN_INPUT = SECRETS_DIR / "user@example-site.ovpn"

   # Your UMG IP address
   UMG_IP = "192.168.1.30"
   ```

3. **Configure registers** in [config.yaml](config.yaml):
   ```yaml
   umg:
     host: "192.168.1.30"
     modbus_port: 502

   registers:
     power_active_total: 19026
     voltage_l1_n: 19000
     # ... add your registers
   ```

---

## Usage

### One-Shot Data Collection

Connects VPN, reads data once, disconnects:

```bash
python -m app poll-once
```

### Continuous Monitoring

Polls data every minute, synchronized to clock (13:00, 13:01, 13:02...):

```bash
# Run indefinitely
python -m app poll-loop --minutes 1

# Run for specific number of cycles
python -m app poll-loop --minutes 1 --cycles 10
```

### VPN Management

```bash
# Start VPN connection
python -m app vpn-start

# Check VPN status
python -m app vpn-status

# Stop VPN
python -m app vpn-stop
```

### Device Health Check

```bash
python -m app umg-health
```

Output example:
```
============================================================
UMG HEALTH CHECK
============================================================

Device: 192.168.1.30
Status: ✓ REACHABLE

  HTTP  (port 80):   ✓ 45.23ms
  Modbus (port 502): ✓ 12.34ms

✓ Device is reachable via Modbus
============================================================
```

### JSON Output

For automation and integration:

```bash
python -m app vpn-status --json
python -m app umg-health --json
python -m app poll-once --json
```

---

## Data Export

CSV files are saved in `data/exports/`:

```
data/exports/umg_readings_2025-01-15.csv
data/exports/umg_readings_2025-01-16.csv
```

### CSV Format

```csv
timestamp,minutes_elapsed,marker_5min,marker_10min,power_active_total,voltage_l1_n,...
2025-01-15T13:00:02.123,0,False,False,12345.67,230.12,...
2025-01-15T13:01:01.987,1,False,False,12400.23,229.98,...
2025-01-15T13:05:02.111,5,True,False,12412.89,230.21,...
```

**Columns:**
- `timestamp`: ISO 8601 timestamp
- `minutes_elapsed`: Minutes since first reading of the day
- `marker_5min`, `marker_10min`, etc.: Boolean markers for temporal aggregation
- All Modbus registers defined in `config.yaml`

---

## Automation (Windows Task Scheduler)

Create a scheduled task to run every minute:

### Step 1: Create batch script

`run_poll.bat`:
```batch
@echo off
cd /d C:\path\to\prognoza
python -m app poll-once >> logs\scheduled_runs.log 2>&1
```

### Step 2: Add to Task Scheduler

1. Open **Task Scheduler** (taskschd.msc)
2. **Create Basic Task** → "Energy Monitor"
3. **Trigger**: Daily → **Repeat every 1 minute**
4. **Action**: Start program → Select `run_poll.bat`
5. **Settings**:
   - ✓ Run whether user is logged on or not
   - ✓ Run with highest privileges

The task will run at exact minute intervals (synchronized with system clock).

---

## Configuration

### Register Mapping (config.yaml)

Define Modbus registers to read:

```yaml
registers:
  # Active Power (W)
  power_active_l1: 19020
  power_active_l2: 19022
  power_active_l3: 19024
  power_active_total: 19026

  # Reactive Power (var)
  power_reactive_total: 19042

  # Voltages (V)
  voltage_l1_n: 19000
  voltage_l2_n: 19002
  voltage_l3_n: 19004

  # Currents (A)
  current_l1: 19012
  current_l2: 19014
  current_l3: 19016

  # Energy (Wh)
  energy_active_import_total: 13997
  energy_active_export_total: 14009

  # Power Quality
  frequency: 19050
  cos_phi_l1: 19044
```

See [config.yaml](config.yaml) for full register list.

### Polling Settings

```yaml
polling:
  interval_minutes: 1           # Polling interval
  cycles_default: 1             # Default cycles for poll-once
  export_dir: "data/exports"    # CSV output directory

  time_markers:                 # Temporal markers (minutes)
    - 5
    - 10
    - 15
    - 30
    - 60
```

### VPN Auto-Management

```yaml
vpn:
  auto_start: true              # Auto-start VPN if not connected
  auto_stop: true               # Auto-stop VPN after polling
  max_retries: 3                # Connection retry attempts
```

---

## Project Structure

```
prognoza/
├── app/
│   ├── __main__.py              # CLI entry point
│   ├── settings.py              # Central configuration
│   ├── vpn_connection.py        # VPN orchestration
│   ├── openvpn_manager.py       # OpenVPN GUI control
│   ├── ovpn_config.py           # OVPN profile preparation
│   ├── janitza_client.py        # Modbus client for UMG 509
│   ├── poll.py                  # Polling engine
│   └── data/raw/                # Log files
├── secrets/                      # OpenVPN files (gitignored)
│   └── user@example-site.ovpn
├── data/exports/                 # CSV output (gitignored)
├── config.yaml                   # Register mapping
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

---

## CLI Reference

### Commands

| Command | Description |
|---------|-------------|
| `vpn-start` | Start VPN connection |
| `vpn-stop` | Stop VPN connection |
| `vpn-status` | Check VPN status |
| `umg-health` | Health check for UMG device |
| `poll-once` | Single data collection cycle |
| `poll-loop` | Continuous polling with interval |

### Options

| Option | Description |
|--------|-------------|
| `--json` | JSON output format |
| `--verbose`, `-v` | Debug logging |
| `--config PATH` | Custom config file (default: config.yaml) |
| `--minutes N` | Polling interval for poll-loop (default: 1) |
| `--cycles N` | Number of cycles for poll-loop (default: infinite) |

### Examples

```bash
# One-shot with JSON output
python -m app poll-once --json

# Poll every 5 minutes, 12 times (1 hour total)
python -m app poll-loop --minutes 5 --cycles 12

# Custom config file
python -m app poll-once --config custom_registers.yaml

# Verbose debugging
python -m app vpn-start --verbose
```

---

## Troubleshooting

### VPN Connection Fails

**Check:**
1. OpenVPN GUI installed at `C:\Program Files\OpenVPN\`
2. `.ovpn` file exists in `secrets/` directory
3. VPN credentials are correct
4. Network connectivity to VPN gateway

**View logs:**
```bash
type app\data\raw\vpn.log
```

### UMG Not Reachable

**Check:**
1. VPN is connected:
   ```bash
   python -m app vpn-status
   ```

2. Device is powered on and network cable connected

3. IP address in `config.yaml` is correct

4. Firewall allows Modbus TCP (port 502)

### Modbus Read Errors

**Check:**
1. Unit ID in `config.yaml` matches device (usually 1)
2. Register addresses are correct for your UMG model
3. Timeout is sufficient (increase in `config.yaml` if slow network)

**Consult device manual:**
- [Janitza UMG 509 PRO Modbus Manual](https://www.janitza.com/support.html)

### CSV Files Not Created

**Check:**
1. `data/exports/` directory exists and is writable
2. No disk space errors
3. Check logs for permission errors

---

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Code Style

```bash
# Format code
black app/

# Lint
flake8 app/
```

### Adding New Registers

1. Add to `config.yaml`:
   ```yaml
   registers:
     my_new_register: 19999
   ```

2. Restart polling - register will appear in CSV automatically

---

## Security Notes

- **OpenVPN files contain credentials** - keep in `secrets/` (gitignored)
- **CSV files may contain sensitive data** - restrict access
- **Logs may contain IP addresses** - review before sharing
- Use strong VPN passwords and certificate-based auth

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- [pymodbus](https://github.com/pymodbus-dev/pymodbus) - Modbus TCP/IP library
- [Janitza UMG 509 PRO](https://www.janitza.com/) - Energy analyzer hardware
- [OpenVPN](https://openvpn.net/) - VPN connectivity

---

## Support

For issues and feature requests, please use [GitHub Issues](https://github.com/yourusername/prognoza/issues).

For device-specific questions, consult:
- **Janitza Support**: https://www.janitza.com/support.html
- **UMG 509 PRO Manual**: Available from manufacturer

---

**Version:** 1.0
**Python:** 3.10+
**Platform:** Windows 10/11
**Status:** Production Ready
