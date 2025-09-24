# Sistem Prognoza Fotovoltaic - Arhitectura si Conformitate

## Context legal esential
- **Codul Tehnic al RET** (cap. 6, cap. 8) pentru cerinte PRE/OTS: termene D-1 15:00, format standard notificari fizice, necesitati agregare 15 min.
- **Procedura PO TEL-133**: structura XML/CSV pentru notificari fizice transmise prin MMS Transelectrica.
- **Regulamente ANRE** (Ord. 177/2015, Ord. 51/2019, Ord. 183/2020): raportari lunare/trimestriale, cerinte energie activa/reactiva, disponibilitate.
- **Norme de racordare** (Normativ PE 132/2014 si avize tehnice de racordare): factor de putere minim 0.9, monitorizare calitate energie (SR EN 50160).

## Arhitectura modulara
```
prognoza/
  data_acquisition/
    umg_reader.py        # citire Modbus TCP si export CSV din Janitza UMG 509 PRO
    router_monitor.py    # monitorizare tunel VPN Teltonika RUT240, SNMP/HTTP keepalive
    data_validator.py    # validari calitate date vs SR EN 50160 si praguri RET
  processing/
    aggregator.py        # agregare 1min -> 15min -> 1h, reconstructie load profile
    forecast_engine.py   # modele ML + forecast meteo conform cerintelor D+1
    notification_builder.py # generare structura notificari fizice PO TEL-133
  reporting/
    transelectrica_export.py # export XML/CSV pentru MMS
    anre_reports.py          # rapoarte Excel pentru ANRE (lunar/trimestrial)
    brp_export.py            # profile comerciale 15 min pentru BRP
  compliance/
    legal_validator.py   # verificare cerinte legale (termene, format, calitate energie)
    deadline_monitor.py  # scheduler APScheduler pentru termene D-1, lunar etc
    audit_trail.py       # logging, hash fisiere, jurnalizare acces
  config/
    settings.py          # configuratii PRE, cod BRP, praguri calitate, cai fisiere
  infrastructure/
    database.py          # conexiune SQLAlchemy (SQLite/PostgreSQL)
    backup.py            # rutine backup si restore CSV/XML/DB
  interfaces/
    api_server.py        # API REST pentru integrare dispecerat/BRP
    cli.py               # CLI operare manuala, regenerare rapoarte
```

## Flux principal de date
1. **Acquisitie**: UMG 509 PRO expune registre Modbus TCP (IP 192.168.1.30 via RUT240 VPN).
   - Citire la fiecare minut (energie activa/reactiva, putere, tensiuni, THD).
   - Validari imediate: valori nule, salturi, timp sincronizat (NTP).
2. **Persistenta**: scriere in baza de date (SQLite pe edge, PostgreSQL in centrala) cu tabela `measurements` si `quality_flags`.
   - Hash semnatura conform audit OTS.
3. **Procesare**:
   - Agregare 15 min pentru notificari PRE/BRP.
   - Calcule energie activa/reactiva, disponibilitate, calitate energie.
   - Forecast D+1 folosind date meteo (OpenWeather/Meteomatics) + istoric.
4. **Conformitate**:
   - Deadline monitor: la 14:30 ruleaza generare notificare + trimitere MMS.
   - Validari legale: format XML conform PO TEL-133, verificare toate intervalele (96/24).
5. **Raportare**:
   - Export XML/CSV catre Transelectrica (upload manual pe MMS sau API).
   - Raport ANRE Excel cu pivot 15 min -> lunar, includere indisponibilitati.
   - Export BRP (CSV) cu profil 15 min.
6. **Audit si backup**:
   - Log rotativ (retentie 24 luni), backup incremental zilnic, test restore lunar.

## Corelare module - cerinte legale
- `umg_reader.py`: garanteaza trasabilitate date masurare, conform art. 8 Cod Tehnic RET (obligatia PRE de a furniza date exacte din instalatii).
- `data_validator.py`: ruleaza verificari SR EN 50160 si Normativ ANRE 4/2019 pentru calitate energie; marcheaza deviatii pentru raportare incident.
- `aggregator.py`: produce profil 15 minute conform PO TEL-133 sectiunea 5 (Rezolutie minima 15 min).
- `forecast_engine.py`: asigura plan prognoza D+1, corelat cu art. 5.3 Cod RET (responsabilitatea PRE pentru notificari fizice).
- `notification_builder.py` + `transelectrica_export.py`: formeaza notificarea fizica standard (XML, CSV) si valideaza schema PO TEL-133.
- `deadline_monitor.py`: trimite alerte daca notificarea nu este transmisa pana la D-1 15:00 (Cod RET, cap. 6.5.2).
- `legal_validator.py`: verifica existenta confirmarii MMS, retine semnatura digitala, raporteaza catre audit trail.
- `anre_reports.py`: corespunde Ordin ANRE 177/2015 privind raportarea energiei produse si indisponibilitatilor.
- `backup.py`: respecta cerintele art. 46 din Codul Comercial cu privire la pastrarea datelor si posibilitatea auditului OTS.

## Comunicatii si securitate
- Conexiune VPN OpenVPN (fisier `config/Prognoza-umg509_stable.ovpn`) pentru acces sigur la UMG 509 PRO.
- Modbus TCP peste tunel; fallback FTP/SFTP pentru CSV daca Modbus indisponibil.
- Monitorizare router RUT240 (SNMP OID uptime, HTTP heartbeat). Alerte email/SMS prin APScheduler + SMTP.
- Sincronizare timp NTP pe RUT240 si server (obligatoriu pentru timestamp conform art. 8.10 Cod RET).

## Gestionare exceptii
- Pierdere VPN: router monitor lanseaza reconectare si comuta pe cache local (buffer CSV din UMG).
- Date invalide (NaN, valori negative inopinate): aggregator marcheaza `quality_flag`, exclude din forecast si anunta operatorul.
- Depasiri calitate energie (THD, PF < 0.9): generare raport incident pentru ANRE in 24h conform Regulament ANRE 51/2019.
- Eroare la trimitere MMS: retry cu exponential backoff, log complet, alerta catre PRE manager.

## Optimizari propuse
- Folosirea `asyncio` + `aiohttp` pentru colectare date si apeluri API meteo (reduce latenta, creste fiabilitate).
- Cache redis optional pentru forecast engine (scade timp recalcul D+1).
- Compresie Parquet pentru arhivare istorica (reduce spatiu, creste viteza agregare).
- Implementare semnatura digitala XAdES pentru fisierele transmisa catre Transelectrica (aliniere la cerinte viitoare ANRE privind semnaturi electronice).

## Dependinte cheie
- `pymodbus==3.x` pentru conectare Modbus TCP.
- `pandas`, `numpy` pentru procesare seriile de timp.
- `apscheduler` pentru scheduler termene legale.
- `lxml`, `xmlschema` pentru validare XML.
- `openpyxl`, `xlsxwriter` pentru rapoarte Excel ANRE.
- `sqlalchemy` pentru abstractizare DB.
- `requests` pentru API meteo, `tenacity` pentru retry.
- `prometheus_client` + `uvicorn`/`fastapi` pentru expunere metrici monitorizare.

## Cerinte N+1 disponbilitate
- Deploy in doua zone: server local la parc (edge) si server central (cloud). Replicare DB (asynchronous) pentru continuitate.
- Backup incremental zilnic, retentie 12 luni pentru conformitate ANRE.
- Test proceduri disaster recovery trimestrial, raport salvat in `audit_trail`.
