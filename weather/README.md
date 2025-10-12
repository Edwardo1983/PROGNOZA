# Weather Package

The `weather` package consolidates multiple external forecast feeds into a single, cache-aware pipeline that returns normalized data aligned in UTC.

## Modules

- `core.py` – shared schema, provider base class, resampling helpers, and `ForecastFrame` wrapper.  
- `cache.py` – lightweight SQLite cache that stores provider responses as pandas frames with per-scope TTLs.  
- `normalize.py` – unit conversion and parsing helpers for OpenWeather, Open-Meteo, and Rainviewer payloads.  
- `providers/` – concrete adapters:
  - `openweather.py` (One Call 3.0 hourly/current)
  - `openmeteo_ecmwf.py` (ECMWF/ICON hourly via Open-Meteo)
  - `rainviewer_nowcast.py` (radar nowcast proxy; falls back to stub when no API key)
- `router.py` – `WeatherRouter` coordinator, config loader, and CLI entry point.  
- `config_example.yaml` – starter configuration describing location, provider priorities, and TTLs.

## Quick Start

1. Copy the example config and fill in API keys:
   ```powershell
   Copy-Item weather\config_example.yaml config\weather.yaml
   ```
2. Define credentials in `.env` or environment variables:
   ```env
   OPENWEATHER_API_KEY=your-one-call-key
   RAINVIEWER_API_KEY=optional-radar-token
   WEATHER_ROUTER_TZ=Europe/Bucharest
   ```
3. Fetch an aligned hourly forecast:
   ```bash
   python -m weather.router --hourly 48 --out data/weather/hourly.parquet
   ```
4. Fetch a 2-hour nowcast resampled to 15-minute steps:
   ```bash
   python -m weather.router --nowcast 2 --out data/weather/nowcast.parquet
   ```

Outputs are indexed in UTC and expose the unified columns:
`[temp_C, wind_ms, wind_deg, clouds_pct, humidity, uvi, ghi_Wm2, source]`.

## Using the Router Programmatically

```python
from weather.router import WeatherRouter, build_providers, load_weather_config

cfg = load_weather_config("config/weather.yaml")
providers = build_providers(cfg)
router = WeatherRouter(providers, tz=cfg.get("timezone", "UTC"))

hourly = router.get_hourly(start, end)          # pandas.DataFrame
nowcast = router.get_nowcast(next_hours=2)
```

The router merges providers by ascending `priority`, filling gaps with lower-tier feeds while preserving `source` provenance.

## Tests

Unit tests live under `tests/`:

- `tests/test_providers_smoke.py` – normalization + caching behaviour for OpenWeather and Open-Meteo providers.  
- `tests/test_router_merge.py` – verifies merge priority, nowcast resampling, and source attribution.

Run the full suite with:

```bash
.\.venv\Scripts\python.exe -m pytest
```

## Configuration Notes

- `location.lat`/`location.lon` drive geographical queries; override per-provider if needed.  
- `providers[].priority` controls merge order (lower value = higher priority).  
- `providers[].ttl` sets cache expiry per provider/scope; defaults are chosen to respect upstream rate limits.  
- Rainviewer nowcast gracefully returns an empty frame when no API key is available, enabling offline operation.
