# 📊 RAPORTĂRI CONFORM LEGISLAȚIEI ROMÂNEȘTI - PARC FOTOVOLTAIC BREZOAIA

## 📋 **CERINȚE LEGISLATIVE ROMÂNIA:**

### **1. ANRE (Autoritatea Națională de Reglementare în Energie)**

#### **A. Raportare Zilnică (Day-Ahead) - OBLIGATORIE**
**Legislație:** Cod de Măsurare (Ordinul ANRE 11/2013, modificat)

**Cerințe:**
- 📅 **Deadline:** Zi D-1, ora 12:00 → prognoza pentru ziua D
- ⏱️ **Interval:** Valorile orar pentru toate cele 24 de ore
- 📊 **Date necesare:** Producție estimată (MWh) pentru fiecare oră
- 🎯 **Precizie:** Prag de toleranță ±10% (depășire = penalizare)

**Fișier generat:**
```
data/weather/brezoaia_48h.csv → folosit pentru prognoza D+1
```

---

#### **B. Raportare Intraday - RECOMANDATĂ**
**Legislație:** Cod de Măsurare + Regulament piața intraday

**Cerințe:**
- 📅 **Frecvență:** La fiecare 15 minute (ziua curentă)
- ⏱️ **Interval:** Nowcast pentru următoarele 2 ore
- 📊 **Date necesare:** Ajustări producție pentru rebalanțare
- 🎯 **Scop:** Reducere dezechilibre → evitare penalizări

**Fișier generat:**
```
data/weather/brezoaia_nowcast.csv → rezoluție 15 minute
```

---

#### **C. Raportare Anuală - OBLIGATORIE**
**Legislație:** Ordinul ANRE 11/2013, Anexa 6

**Cerințe:**
- 📅 **Deadline:** 31 martie anul N+1 (pentru anul N)
- 📊 **Date necesare:**
  - Producție totală anuală (MWh)
  - Disponibilitate parc (%)
  - Incidente și întreruperi
  - Factorii de capacitate
- 📁 **Format:** Raport standardizat ANRE

---

### **2. TRANSELECTRICA (Operatorul de Transport și Sistem)**

#### **A. Programare Zilnică (Day-Ahead Schedule)**
**Legislație:** Cod de Rețea Transport

**Cerințe:**
- 📅 **Deadline:** Zi D-1, ora 10:00
- ⏱️ **Interval:** Prognoza oră cu oră pentru D
- 📊 **Date necesare:** Producție planificată (MW) pentru fiecare interval orar
- 🔌 **Modalitate:** Portal TRANSELECTRICA sau API

**Fișier generat:**
```
data/weather/brezoaia_48h.csv → input pentru algoritm de programare
```

---

#### **B. Reprogramare Intraday**
**Legislație:** Regulament Piața Intraday

**Cerințe:**
- 📅 **Frecvență:** Sesiuni continue până cu 5 minute înainte de livrare
- ⏱️ **Interval:** Ajustări pentru fiecare interval de 15 minute
- 📊 **Date necesare:** Deviații de la programarea inițială

**Fișier generat:**
```
data/weather/brezoaia_nowcast.csv → pentru ajustări rapide
```

---

### **3. OPCOM (Operatorul Pieței de Energie Electrică)**

#### **A. Piața Centralizată pentru Contracte Bilaterale (PCCB)**
**Legislație:** Regulament PCCB

**Cerințe:**
- 📅 **Deadline:** Zi D-1, ora 12:00
- ⏱️ **Interval:** Valori orar pentru ziua D
- 📊 **Date necesare:** Cantități offerate (MWh)
- 💰 **Scop:** Vânzare energie produsă

**Fișier generat:**
```
data/weather/brezoaia_48h.csv → pentru ofertare PCCB
```

---

#### **B. Piața Intraday (PI)**
**Legislație:** Regulament PI

**Cerințe:**
- 📅 **Frecvență:** Continuu (sesiuni 15 minute)
- ⏱️ **Interval:** Ajustări pentru intervale de 15 minute
- 📊 **Date necesare:** Oferte/cereri ajustare
- ⚡ **Scop:** Rebalanțare portofoliu

**Fișier generat:**
```
data/weather/brezoaia_nowcast.csv → pentru tranzacții rapide
```

---

## 🕐 **CRONOLOGIE RAPORTĂRI (EXEMPLU ZIUA D):**

```
D-1, ora 10:00  → Programare TRANSELECTRICA (folosind brezoaia_48h.csv)
D-1, ora 12:00  → Raportare ANRE Day-Ahead (folosind brezoaia_48h.csv)
D-1, ora 12:00  → Ofertare OPCOM PCCB (folosind brezoaia_48h.csv)
D-1, ora 14:00  → Rezultate PCCB primite

ZIUA D:
00:00 - 24:00   → Nowcast continuu la 15 min (brezoaia_nowcast.csv)
00:00 - 24:00   → Ajustări Intraday pe baza nowcast
23:59           → Măsurare producție reală vs prognoza
```

---

## 📁 **STRUCTURĂ FIȘIERE PENTRU RAPORTĂRI:**

### **Layout recomandat:**
```
PROGNOZA/
├── data/
│   ├── weather/              # Weather forecasts
│   │   ├── brezoaia_nowcast.csv      # Nowcast 15min (2h)
│   │   ├── brezoaia_48h.csv          # Day-ahead + D+2
│   │   ├── brezoaia_weekly.csv       # Planificare 7 zile
│   │   └── archive/                  # Istoric prognoze
│   │
│   ├── forecasts/            # Power forecasts (AI generated)
│   │   ├── power_nowcast.csv         # Putere estimată 15min
│   │   ├── power_day_ahead.csv       # Putere D+1 (pentru ANRE)
│   │   └── power_weekly.csv          # Planificare săptămână
│   │
│   ├── actuals/              # Măsurători reale (Janitza)
│   │   ├── umg509_YYYYMMDD.csv       # Date zilnice
│   │   └── umg509_real_time.csv      # Date live
│   │
│   └── reports/              # Rapoarte generate
│       ├── anre_day_ahead_YYYYMMDD.xlsx    # Raport ANRE
│       ├── transelectrica_schedule.xml      # Programare TSO
│       └── opcom_bids.csv                   # Oferte PCCB
│
└── scripts/
    ├── fetch_weather_all.ps1           # Fetch weather data
    ├── generate_forecasts.ps1          # Generate power forecasts
    └── generate_reports_anre.ps1       # Generate ANRE reports
```

---

## ⚙️ **AUTOMATIZARE RAPORTĂRI - TASK SCHEDULER:**

### **Task 1: Weather Fetch Nowcast (la fiecare 15 minute)**
```powershell
# Trigger: La fiecare 15 minute (00, 15, 30, 45)
# Script: scripts\fetch_weather_nowcast.ps1
python -m weather.router --nowcast 2 --out data/weather/brezoaia_nowcast.csv
```

**Task Scheduler Settings:**
- Trigger: Daily, repeat every 15 minutes, duration: 1 day
- Start time: 00:00
- Action: PowerShell script

---

### **Task 2: Weather Fetch Day-Ahead (zilnic la 08:00)**
```powershell
# Trigger: Zilnic la 08:00 (pregătire pentru raportare 10:00)
# Script: scripts\fetch_weather_daily.ps1
python -m weather.router --hourly 48 --out data/weather/brezoaia_48h.csv
```

**Task Scheduler Settings:**
- Trigger: Daily at 08:00
- Action: PowerShell script

---

### **Task 3: Generate Day-Ahead Forecast (zilnic la 09:00)**
```powershell
# Trigger: Zilnic la 09:00 (după fetch weather)
# Script: scripts\generate_power_forecast.ps1
python -m ai_hibrid.pipeline.predict \
    --weather data/weather/brezoaia_48h.csv \
    --horizon 48 \
    --out data/forecasts/power_day_ahead.csv
```

**Task Scheduler Settings:**
- Trigger: Daily at 09:00 (după Task 2)
- Action: PowerShell script

---

### **Task 4: Generate ANRE Report (zilnic la 09:30)**
```powershell
# Trigger: Zilnic la 09:30 (pregătire pentru deadline 12:00)
# Script: scripts\generate_anre_report.ps1
python scripts/generate_anre_report.py \
    --forecast data/forecasts/power_day_ahead.csv \
    --out data/reports/anre_day_ahead_$(date +%Y%m%d).xlsx
```

**Task Scheduler Settings:**
- Trigger: Daily at 09:30
- Action: PowerShell script
- Alert: Email dacă raportul eșuează

---

## 📊 **PRECIZIE RAPORTĂRI (TOLERANȚE ANRE):**

### **Penalizări pentru deviații:**

| Deviație față de prognoza | Penalizare |
|---------------------------|------------|
| **< ±10%** | ✅ Fără penalizare |
| **±10-15%** | ⚠️ Penalizare 50% din dezechilibru |
| **±15-20%** | ⚠️ Penalizare 75% din dezechilibru |
| **> ±20%** | ❌ Penalizare 100% din dezechilibru |

**Exemplu:**
```
Prognoză D-1: 500 MWh pentru ziua D
Producție reală: 450 MWh
Deviație: -50 MWh (-10%)
Status: ✅ Sub pragul de toleranță → fără penalizare
```

---

## 🎯 **RECOMANDĂRI OPERAȚIONALE:**

### **1. Pentru maximizare profit:**
- ✅ Folosește prognoza **brezoaia_48h.csv** pentru licitații day-ahead
- ✅ Actualizează cu **brezoaia_nowcast.csv** pentru ajustări intraday
- ✅ Monitorizează continuu deviațiile față de prognoză
- ✅ Ajustează ofertele pe piața intraday când deviația depășește 5%

### **2. Pentru minimizare penalizări:**
- ✅ Calibrează modelul AI cu date istorice Brezoaia
- ✅ Include safety margin de 5-10% în prognoze conservatoare
- ✅ Monitorizează acuratețea prognozei meteo vs realitate
- ✅ Ajustează parametrii modelului lunar pe baza performanței

### **3. Pentru conformitate legislativă:**
- ✅ Păstrează istoric complet prognoze + măsurători (min 5 ani)
- ✅ Documentează metodologia de forecasting pentru ANRE
- ✅ Implementează alerting pentru deadline-uri raportări
- ✅ Backup automat pentru toate datele critice

---

## 📞 **CONTACTE UTILE:**

- **ANRE:** +40-21-327-8600, office@anre.ro
- **TRANSELECTRICA:** +40-21-303-5400, dispecerat@transelectrica.ro
- **OPCOM:** +40-21-307-5700, office@opcom.ro

---

## 📚 **LEGISLAȚIE RELEVANTĂ:**

1. **Ordinul ANRE 11/2013** - Cod de Măsurare
2. **Ordinul ANRE 114/2018** - Regulament organizare piață
3. **Cod de Rețea Transport** - Transelectrica
4. **Regulament PCCB** - OPCOM
5. **Regulament Piața Intraday** - OPCOM

---

**📅 Ultima actualizare:** Ianuarie 2025
**✅ Status:** Production Ready pentru Brezoaia PV Park
