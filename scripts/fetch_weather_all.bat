@echo off
REM ==============================================================================
REM Script: Fetch Weather Data pentru Brezoaia PV Park
REM Autor: PROGNOZA System
REM Descriere: Descarca toate raportarile meteo necesare conform legislatiei RO
REM ==============================================================================

echo ========================================
echo BREZOAIA PV PARK - Weather Data Fetch
echo ========================================
echo Start: %date% %time%
echo.

cd /d C:\Users\Opaop\Desktop\Prognoza\PROGNOZA

REM Asigura ca directoarele exista
if not exist data\weather mkdir data\weather
if not exist logs mkdir logs

set LOGFILE=logs\weather_fetch_%date:~-4,4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%.log

echo [1/4] Fetching nowcast (2h @ 15min)... | tee -a %LOGFILE%
python -m weather.router --nowcast 2 --out data/weather/brezoaia_nowcast.csv >> %LOGFILE% 2>&1
if errorlevel 1 (
    echo ERROR: Nowcast fetch failed! | tee -a %LOGFILE%
) else (
    echo SUCCESS: Nowcast saved to brezoaia_nowcast.csv | tee -a %LOGFILE%
)

echo [2/4] Fetching 48h hourly forecast... | tee -a %LOGFILE%
python -m weather.router --hourly 48 --out data/weather/brezoaia_48h.csv >> %LOGFILE% 2>&1
if errorlevel 1 (
    echo ERROR: 48h forecast fetch failed! | tee -a %LOGFILE%
) else (
    echo SUCCESS: 48h forecast saved to brezoaia_48h.csv | tee -a %LOGFILE%
)

echo [3/4] Fetching 168h (7-day) forecast... | tee -a %LOGFILE%
python -m weather.router --hourly 168 --out data/weather/brezoaia_weekly.csv >> %LOGFILE% 2>&1
if errorlevel 1 (
    echo ERROR: Weekly forecast fetch failed! | tee -a %LOGFILE%
) else (
    echo SUCCESS: Weekly forecast saved to brezoaia_weekly.csv | tee -a %LOGFILE%
)

echo [4/4] Generating summary report... | tee -a %LOGFILE%
python -c "import pandas as pd; from datetime import datetime; print('\n=== WEATHER DATA SUMMARY ==='); files = ['data/weather/brezoaia_nowcast.csv', 'data/weather/brezoaia_48h.csv', 'data/weather/brezoaia_weekly.csv']; [print(f'{f}: {len(pd.read_csv(f))} rows') if os.path.exists(f) else print(f'{f}: MISSING') for f in files]; print(f'Fetch completed: {datetime.now()}')" >> %LOGFILE% 2>&1

echo.
echo ========================================
echo Fetch completed: %date% %time%
echo Log saved to: %LOGFILE%
echo ========================================

pause
