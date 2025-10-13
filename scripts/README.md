# 📋 SCRIPTS - WEATHER & REPORTING AUTOMATION

## 🎯 **RĂSPUNS LA ÎNTREBĂRILE TALE:**

### **1. Le pot da una după alta?**
✅ **DA! Rulează-le SECVENȚIAL (recomandat)**

```powershell
# Metoda simplă - un singur script care face totul
.\scripts\fetch_weather_all_simple.ps1
```

**Ce face:**
- ✅ Rulează comenzile **UNA DUPĂ ALTA** (secvențial)
- ✅ Așteaptă să termine fiecare comandă înainte de următoarea
- ✅ Durată totală: **~5-10 secunde**
- ✅ **SIGUR** - fără conflicte de cache

---

### **2. Sistemul le va rula simultan?**
❌ **NU, comenzile rulează SECVENȚIAL (una după alta)**

**De ce secvențial:**
- ✅ Cache SQLite nu e thread-safe 100%
- ✅ API rate limits - unii provideri limitează requests/secundă
- ✅ Logging clar - vezi exact unde e problema
- ✅ Timpul nu e critic - 10 secunde e acceptabil

**Dacă vrei paralel (NERECOMANDAT):**
```powershell
Start-Job { python -m weather.router --nowcast 2 --out data/weather/brezoaia_nowcast.csv }
Start-Job { python -m weather.router --hourly 48 --out data/weather/brezoaia_48h.csv }
Get-Job | Wait-Job | Receive-Job
```

---

### **3. Trebuie să le dau pe rând, aștept să termine?**
✅ **DA, execuție secvențială e RECOMANDATĂ**

**Soluția optimă:**
```powershell
# Un singur script care face totul automat
cd C:\Users\Opaop\Desktop\Prognoza\PROGNOZA
.\scripts\fetch_weather_all_simple.ps1
```

**Output așteptat:**
```
========================================
BREZOAIA PV PARK - Weather Data Fetch
========================================

[1/4] Fetching NOWCAST (2h @ 15min)...
SUCCESS: Nowcast saved

[2/4] Fetching 48H HOURLY forecast...
SUCCESS: 48h forecast saved

[3/4] Fetching 168H WEEKLY forecast...
SUCCESS: Weekly forecast saved

[4/4] Generating summary...
+ data/weather/brezoaia_nowcast.csv : 12 rows, 1.0 KB
+ data/weather/brezoaia_48h.csv : 48 rows, 3.4 KB
+ data/weather/brezoaia_weekly.csv : 168 rows, 11.2 KB

Duration: 5.1 seconds
========================================
```

---

## 📁 **SCRIPTURI DISPONIBILE:**

### **1. fetch_weather_all_simple.ps1** ⭐ RECOMANDAT
**Descriere:** Fetch toate raportările meteo (nowcast + 48h + weekly)
**Frecvență:** Rulează manual sau automat (Task Scheduler)
**Durată:** ~5-10 secunde

**Utilizare:**
```powershell
.\scripts\fetch_weather_all_simple.ps1
```

---

### **2. fetch_weather_nowcast.ps1**
**Descriere:** Fetch DOAR nowcast (2h @ 15min)
**Frecvență:** La fiecare 15 minute (intraday trading)
**Durată:** ~2 secunde

**Utilizare:**
```powershell
.\scripts\fetch_weather_nowcast.ps1
```

**Task Scheduler:** Automat la fiecare 15 minute

---

### **3. fetch_weather_daily.ps1**
**Descriere:** Fetch DOAR day-ahead (48h orar)
**Frecvență:** Zilnic la 08:00 (pregătire raportare ANRE 12:00)
**Durată:** ~3 secunde

**Utilizare:**
```powershell
.\scripts\fetch_weather_daily.ps1
```

**Task Scheduler:** Automat zilnic la 08:00

---

### **4. setup_task_scheduler.ps1**
**Descriere:** Configurează automat Task Scheduler (o singură dată)
**Frecvență:** Rulează o singură dată la setup

**Utilizare:**
```powershell
# Rulează cu drepturi Administrator
.\scripts\setup_task_scheduler.ps1
```

**Ce face:**
- ✅ Creează task "Brezoaia_Weather_Nowcast" → La 15 minute
- ✅ Creează task "Brezoaia_Weather_DayAhead" → Zilnic 08:00
- ✅ Creează task "Brezoaia_Weather_Weekly" → Duminică 18:00

---

## 📊 **RAPORTĂRI CONFORM LEGISLAȚIEI ROMÂNE:**

### **Cerințe ANRE + TRANSELECTRICA + OPCOM:**

| Raportare | Frecvență | Script | Deadline | Scop |
|-----------|-----------|--------|----------|------|
| **Nowcast** | La 15 min | `fetch_weather_nowcast.ps1` | Continuu | Intraday trading |
| **Day-Ahead** | Zilnic 08:00 | `fetch_weather_daily.ps1` | 12:00 | Raportare ANRE D+1 |
| **Săptămânal** | Duminică | `fetch_weather_all_simple.ps1` | - | Planificare O&M |

**Documentație completă:** [README_RAPORTARI_RO.md](README_RAPORTARI_RO.md)

---

## ⚙️ **SETUP RAPID (5 MINUTE):**

### **Pasul 1: Test Manual**
```powershell
cd C:\Users\Opaop\Desktop\Prognoza\PROGNOZA
.\scripts\fetch_weather_all_simple.ps1
```

### **Pasul 2: Verifică Datele**
```powershell
python -c "
import pandas as pd
df = pd.read_csv('data/weather/brezoaia_48h.csv', index_col=0)
print(f'Rows: {len(df)}')
print(f'Valid: {df[\"temp_C\"].notna().sum()}/{len(df)}')
print(df.head())
"
```

### **Pasul 3: Automatizare (Optional)**
```powershell
# Configurează Task Scheduler (cu drepturi Administrator)
.\scripts\setup_task_scheduler.ps1
```

---

## 🕐 **CRONOLOGIE RAPORTĂRI ZILNICE:**

```
D-1, 08:00  → Fetch day-ahead (automat Task Scheduler)
            → Generează brezoaia_48h.csv

D-1, 09:00  → AI generează forecast putere (manual/automat)
            → Input: brezoaia_48h.csv
            → Output: power_day_ahead.csv

D-1, 10:00  → Upload TRANSELECTRICA (manual)
D-1, 12:00  → Deadline raportare ANRE

ZIUA D:
00:00-23:59 → Nowcast la 15 min (automat)
            → brezoaia_nowcast.csv actualizat continuu
```

---

## 📂 **STRUCTURĂ FIȘIERE GENERATE:**

```
data/
├── weather/
│   ├── brezoaia_nowcast.csv      # Nowcast 2h @ 15min
│   ├── brezoaia_48h.csv           # Day-ahead D+1 + D+2
│   ├── brezoaia_weekly.csv        # Planificare 7 zile
│   └── archive/                   # Istoric (backup automat)
│       ├── nowcast_20250115_0800.csv
│       ├── 48h_20250115.csv
│       └── ...
│
└── logs/
    ├── weather_fetch_20250115_0800.log
    ├── weather_daily_20250115.log
    └── ...
```

---

## 🐛 **TROUBLESHOOTING:**

### **Problemă: Date NaN**
```powershell
# Șterge cache și reîncearcă
Remove-Item .cache\weather_cache.sqlite
.\scripts\fetch_weather_all_simple.ps1
```

### **Problemă: Task Scheduler nu rulează**
```powershell
# Verifică task
Get-ScheduledTask | Where-Object {$_.TaskName -like 'Brezoaia*'}

# Rulează manual pentru test
Start-ScheduledTask -TaskName 'Brezoaia_Weather_DayAhead'

# Verifică log
Get-Content logs\weather_daily_$(Get-Date -Format 'yyyyMMdd').log
```

### **Problemă: Durează mult**
```powershell
# Verifică cache size
python -c "
import os
cache = '.cache/weather_cache.sqlite'
if os.path.exists(cache):
    print(f'Cache: {os.path.getsize(cache)/1024:.0f} KB')
"
```

---

## 📖 **DOCUMENTAȚIE DETALIATĂ:**

- 📘 [GHID_RAPID_UTILIZARE.md](GHID_RAPID_UTILIZARE.md) - Ghid pas cu pas
- 📗 [README_RAPORTARI_RO.md](README_RAPORTARI_RO.md) - Legislație și cerințe ANRE
- 📙 [../weather/README.md](../weather/README.md) - Documentație tehnică weather module

---

## ✅ **STATUS:**

```
✅ Weather system FUNCȚIONAL pentru Brezoaia (lat: 44.538476, lon: 25.795695, alt: 118m)
✅ Provider: Open-Meteo ECMWF + ICON (100% GRATUIT)
✅ Toate raportările testate și functionale
✅ Scripts pentru automatizare gata de folosit
✅ Conform cerințe ANRE, TRANSELECTRICA, OPCOM
✅ Production-ready pentru parc fotovoltaic

TIMP EXECUȚIE: ~5-10 secunde pentru toate raportările
FRECVENȚĂ RECOMANDATĂ:
  - Nowcast: La 15 minute (intraday)
  - Day-ahead: Zilnic la 08:00 (pregătire ANRE 12:00)
  - Weekly: Duminică seară (planificare săptămână)
```

---

**📅 Ultima actualizare:** Ianuarie 2025
**🏭 Site:** Brezoaia PV Park, Dâmbovița, România
**✅ Status:** PRODUCTION READY
