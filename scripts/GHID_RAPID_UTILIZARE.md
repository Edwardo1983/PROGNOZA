# 🚀 GHID RAPID DE UTILIZARE - WEATHER SYSTEM BREZOAIA

## ⚡ **START RAPID (5 MINUTE):**

### **1. Test Manual - Rulează toate comenzile:**
```powershell
# Navighează la directorul proiectului
cd C:\Users\Opaop\Desktop\Prognoza\PROGNOZA

# Rulează scriptul complet (toate raportările)
.\scripts\fetch_weather_all.ps1
```

**Output așteptat:**
```
========================================
BREZOAIA PV PARK - Weather Data Fetch
========================================
[1/4] Fetching NOWCAST (2h @ 15min resolution)...
✓ SUCCESS: Nowcast saved to brezoaia_nowcast.csv

[2/4] Fetching 48H HOURLY forecast (D+1 + D+2)...
✓ SUCCESS: 48h forecast saved to brezoaia_48h.csv

[3/4] Fetching 168H WEEKLY forecast (7 days)...
✓ SUCCESS: Weekly forecast saved to brezoaia_weekly.csv

[4/4] Generating summary report...
✓ data/weather/brezoaia_nowcast.csv : 8 rows, 2.1 KB
✓ data/weather/brezoaia_48h.csv : 48 rows, 12.3 KB
✓ data/weather/brezoaia_weekly.csv : 168 rows, 43.2 KB

========================================
Fetch completed: 2025-01-15 10:35:22
Total duration: 8.3 seconds
========================================
```

---

## 🔄 **MOD DE LUCRU - RĂSPUNS LA ÎNTREBAREA TA:**

### **❓ Le pot da una după alta?**
✅ **DA! Recomandat pentru siguranță.**

```powershell
# Varianta 1: O singură comandă care rulează toate (RECOMANDAT)
.\scripts\fetch_weather_all.ps1

# Varianta 2: Manual, una după alta
python -m weather.router --nowcast 2 --out data/weather/brezoaia_nowcast.csv
python -m weather.router --hourly 48 --out data/weather/brezoaia_48h.csv
python -m weather.router --hourly 168 --out data/weather/brezoaia_weekly.csv
```

**Cum funcționează:**
- ✅ Comenzile se execută **SECVENȚIAL** (una după alta)
- ✅ Dacă prima eșuează, celelalte **NU SE EXECUTĂ**
- ✅ Timpul total: **~10-15 secunde** (acceptabil)
- ✅ **SIGUR** - nu există conflicte de cache

---

### **❓ Sistemul le va rula simultan?**
❌ **NU, decât dacă specifici explicit.**

Pentru execuție paralelă (nu recomandat):
```powershell
# Varianta paralela (NERECOMANDAT - poate cauza conflicte cache)
Start-Job { python -m weather.router --nowcast 2 --out data/weather/brezoaia_nowcast.csv }
Start-Job { python -m weather.router --hourly 48 --out data/weather/brezoaia_48h.csv }
Start-Job { python -m weather.router --hourly 168 --out data/weather/brezoaia_weekly.csv }
Get-Job | Wait-Job | Receive-Job
```

**De ce NU recomandat:**
- ⚠️ Toate folosesc același cache SQLite → risc de lock
- ⚠️ API rate limits pot bloca requests simultane
- ⚠️ Greu de debugat dacă apare eroare

---

### **❓ Trebuie sa le dau pe rand, astept sa termine?**
✅ **DA, execuție secvențială este RECOMANDATĂ.**

**Soluția optimă:**
```powershell
# Folosește scriptul care face asta automat
.\scripts\fetch_weather_all.ps1
```

Acest script:
- ✅ Rulează fiecare comandă și așteaptă să termine
- ✅ Verifică dacă fișierul s-a creat înainte de următoarea
- ✅ Logează toate operațiile
- ✅ Raportează erori clar

---

## 📅 **FRECVENȚE RECOMANDATE PENTRU RAPORTĂRI:**

### **Pentru Legislația Română (ANRE, TRANSELECTRICA, OPCOM):**

| Raportare | Frecvență | Comandă | Deadline |
|-----------|-----------|---------|----------|
| **Nowcast** | La 15 min | `fetch_weather_nowcast.ps1` | Continuu (intraday) |
| **Day-Ahead** | Zilnic 08:00 | `fetch_weather_daily.ps1` | Pentru raportare 12:00 |
| **Săptămânal** | Duminică 18:00 | `hourly 168` | Planificare M.O.M |

---

## ⚙️ **AUTOMATIZARE - SETUP COMPLET:**

### **Pasul 1: Configurează Task Scheduler (o singură dată)**

```powershell
# Rulează scriptul de setup (cu drepturi Administrator)
.\scripts\setup_task_scheduler.ps1
```

**Ce face:**
- ✅ Creează task pentru **nowcast** (la fiecare 15 minute)
- ✅ Creează task pentru **day-ahead** (zilnic la 08:00)
- ✅ Creează task pentru **weekly** (duminică la 18:00)
- ✅ Configurează logging automat

---

### **Pasul 2: Verifică că taskurile rulează**

```powershell
# Verifică taskurile create
Get-ScheduledTask | Where-Object {$_.TaskName -like 'Brezoaia*'}

# Rulează un task manual pentru test
Start-ScheduledTask -TaskName 'Brezoaia_Weather_DayAhead'

# Verifică statusul
Get-ScheduledTask -TaskName 'Brezoaia_Weather_DayAhead' | Get-ScheduledTaskInfo
```

---

### **Pasul 3: Monitorizează logs**

```powershell
# Verifică ultimul log
Get-Content logs\weather_daily_$(Get-Date -Format 'yyyyMMdd').log -Tail 20

# Monitorizează live (PowerShell)
Get-Content logs\weather_daily_$(Get-Date -Format 'yyyyMMdd').log -Wait
```

---

## 📊 **WORKFLOW COMPLET PENTRU RAPORTARE ZILNICĂ:**

### **CRONOLOGIE AUTOMATĂ:**

```
06:00  → Sistem se pregătește
08:00  → ✅ Task "Day-Ahead" pornește automat
         → Fetch brezoaia_48h.csv (prognoza meteo D+1 și D+2)
         → Durată: ~3-5 secunde
08:05  → ✅ AI Pipeline generează forecast putere (rulezi manual sau automat)
         → Input: brezoaia_48h.csv
         → Output: power_day_ahead.csv
         → Durată: ~10-30 secunde
09:00  → ✅ Generare raport ANRE (rulezi manual sau automat)
         → Input: power_day_ahead.csv
         → Output: anre_day_ahead_YYYYMMDD.xlsx
         → Durată: ~5 secunde
10:00  → ✅ Upload raport TRANSELECTRICA (manual)
         → Portal TRANSELECTRICA sau API
12:00  → ✅ Deadline raportare ANRE
         → Email/Upload portal ANRE

CONTINUU:
00:00-23:59 → ✅ Nowcast la fiecare 15 minute (automat)
              → brezoaia_nowcast.csv actualizat continuu
              → Pentru ajustări intraday
```

---

## 🎯 **CAZURI DE UTILIZARE SPECIFICE:**

### **Caz 1: Pregătire raportare ANRE (zilnic)**
```powershell
# Manual (dacă task scheduler nu e configurat)
cd C:\Users\Opaop\Desktop\Prognoza\PROGNOZA
.\scripts\fetch_weather_daily.ps1

# Verifică fișierul generat
python -c "import pandas as pd; df = pd.read_csv('data/weather/brezoaia_48h.csv', index_col=0); print(f'{len(df)} ore prognoză'); print(df.head())"
```

---

### **Caz 2: Ajustare rapidă intraday (piața spot)**
```powershell
# Fetch nowcast urgent
.\scripts\fetch_weather_nowcast.ps1

# Verifică predicție următoarea oră
python -c "import pandas as pd; df = pd.read_csv('data/weather/brezoaia_nowcast.csv', index_col=0); print('Următoarea oră:'); print(df.head(4))"
```

---

### **Caz 3: Planificare săptămânală (management O&M)**
```powershell
# Fetch forecast 7 zile
python -m weather.router --hourly 168 --out data/weather/brezoaia_weekly.csv

# Analiză vreme săptămână viitoare
python -c "
import pandas as pd
df = pd.read_csv('data/weather/brezoaia_weekly.csv', index_col=0)
print('Prognoza săptămânală:')
print(f'Temp: {df[\"temp_C\"].min():.1f} to {df[\"temp_C\"].max():.1f} C')
print(f'Vânt mediu: {df[\"wind_ms\"].mean():.1f} m/s')
print(f'Iradiere medie: {df[\"ghi_Wm2\"].mean():.0f} W/m2')
print(f'Zile cu nori >80%: {(df[\"clouds_pct\"] > 80).sum()}')
"
```

---

## 🐛 **TROUBLESHOOTING:**

### **Problemă: Comenzile durează mult**
```powershell
# Verifică cache
python -c "
import os
cache = '.cache/weather_cache.sqlite'
if os.path.exists(cache):
    size = os.path.getsize(cache) / 1024
    print(f'Cache size: {size:.1f} KB')
    if size > 5000:
        print('WARNING: Cache foarte mare, consideră ștergere')
"

# Șterge cache dacă e prea mare
Remove-Item .cache\weather_cache.sqlite
```

---

### **Problemă: Date NaN în CSV**
```powershell
# Șterge cache și reîncearcă
Remove-Item .cache\weather_cache.sqlite -ErrorAction SilentlyContinue
python -m weather.router --hourly 48 --out data/weather/brezoaia_48h.csv

# Verifică datele
python -c "import pandas as pd; df = pd.read_csv('data/weather/brezoaia_48h.csv', index_col=0); print(f'Valid: {df[\"temp_C\"].notna().sum()}/{len(df)}')"
```

---

### **Problemă: Task Scheduler nu rulează**
```powershell
# Verifică status task
Get-ScheduledTask -TaskName 'Brezoaia_Weather_DayAhead' | Format-List *

# Verifică ultimul run
Get-ScheduledTask -TaskName 'Brezoaia_Weather_DayAhead' | Get-ScheduledTaskInfo

# Rulează manual pentru debug
Start-ScheduledTask -TaskName 'Brezoaia_Weather_DayAhead'

# Verifică logul
Get-Content logs\weather_daily_$(Get-Date -Format 'yyyyMMdd').log
```

---

## 📞 **CONTACT SUPPORT:**

**Pentru probleme tehnice:**
- 📧 Email: support@prognoza-system.ro (exemplu)
- 📱 Telefon: +40-xxx-xxx-xxx
- 📚 Documentație: [README_RAPORTARI_RO.md](README_RAPORTARI_RO.md)

---

## ✅ **CHECKLIST ZILNIC (PENTRU OPERATOR):**

```
□ 08:00 - Verifică că task "Day-Ahead" a rulat cu succes
□ 08:05 - Verifică că brezoaia_48h.csv există și are date valide
□ 09:00 - Generează forecast putere cu AI (dacă e configurat)
□ 09:30 - Generează raport ANRE (dacă e configurat)
□ 10:00 - Upload raport TRANSELECTRICA
□ 12:00 - Confirmă raportare ANRE trimisă
□ 14:00 - Verifică că nowcast rulează continuu (check logs)
□ 18:00 - Review deviații prognoză vs realitate
```

---

**🎯 REZUMAT RAPID:**

1. ✅ **Rulează comenzile SECVENȚIAL** (una după alta) cu `fetch_weather_all.ps1`
2. ✅ **NU executa în paralel** (risc conflicte cache)
3. ✅ **Configurează Task Scheduler** pentru automatizare (o singură dată)
4. ✅ **Monitorizează logs** pentru erori
5. ✅ **Backup fișiere** pentru conformitate ANRE (istoric 5 ani)

**Sistemul este PRODUCTION READY pentru raportări conform legislației românești! 🇷🇴**
