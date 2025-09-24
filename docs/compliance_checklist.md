# Checklist conformitate legislativa

1. **Notificare fizica PRE** (Cod Tehnic RET cap. 6.5.2)
   - Transmitere D-1 pana la ora 15:00 prin MMS Transelectrica.
   - Fisiere XML/CSV validate cu schema PO TEL-133.
   - Confirmare primire OTS arhivata 24 luni.

2. **Raportare calitate energie** (Ordin ANRE 51/2019, SR EN 50160)
   - Monitorizare THD, tensiuni, factor de putere.
   - Incident de calitate raportat in 24h prin formular ANRE.

3. **Rapoarte ANRE periodice** (Ordin ANRE 177/2015)
   - Lunar: energie produsa/livrata, indisponibilitati.
   - Trimestrial: evenimente, lucrari mentenanta.

4. **Audit si retentie**
   - Log complet in `logs/audit.log` cu hash-uri fisiere transmise.
   - Backup zilnic in directorul `backups/` cu retentie 12 luni.

5. **Sincronizare timp**
   - RUT240 si server sincronizate NTP; abateri >2s declanseaza alerta.

6. **Securitate comunicatii**
   - Tunel VPN OpenVPN activ si monitorizat.
   - Certificatelor TLS verificate periodic.
