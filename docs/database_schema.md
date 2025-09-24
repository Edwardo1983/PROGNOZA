# Schema baza de date Prognoza PV

| Tabela | Scop legal | Campuri principale |
| --- | --- | --- |
| `measurements` | Trasabilitate masuratori PRE (Cod RET cap. 6.5) | `timestamp`, `active_power_kw`, `reactive_power_kvar`, `energy_export_kwh`, `metadata_json` |
| `quality_flags` | Evidenta neconformitatilor calitate energie (Ordin ANRE 51/2019) | `measurement_id`, `issue`, `severity` |
| `forecasts` | Arhivare prognoze D-1 si intrazilnice (Cod RET cap. 5.3) | `delivery_day`, `horizon`, `mae`, `payload` |
| `notifications` | Audit notificari fizice si confirmari MMS (PO TEL-133) | `delivery_day`, `submitted_at`, `transport_reference`, `file_hash` |

## Relatii
- `quality_flags.measurement_id` refera `measurements.id` pentru a marca intervalele cu abateri.
- `notifications.file_hash` trebuie sa fie hash SHA-256 calculat la transmiterea fisierului catre MMS Transelectrica.

## Indexare recomandata
- Index pe `measurements.timestamp` pentru interogari grafice.
- Index pe `notifications.delivery_day` pentru audit OTS.

## Retentie date
- Minim 24 luni pentru `measurements` si `notifications` conform cerintelor Transelectrica.
- Arhivare anuala in format Parquet pentru analize istorice.
