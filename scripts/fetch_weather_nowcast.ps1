# ==============================================================================
# Script: Fetch Nowcast (2h @ 15min) pentru control intraday
# Frecvență: La fiecare 15 minute
# Scop: Ajustări rapide pentru piața intraday și rebalanțare
# ==============================================================================

$ErrorActionPreference = "Stop"
Set-Location "C:\Users\Opaop\Desktop\Prognoza\PROGNOZA"

# Creează director dacă nu există
New-Item -ItemType Directory -Force -Path "data\weather" | Out-Null

$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Write-Host "[$Timestamp] Fetching nowcast (2h @ 15min)..." -ForegroundColor Cyan

try {
    python -m weather.router --nowcast 2 --out data/weather/brezoaia_nowcast.csv

    if (Test-Path "data\weather\brezoaia_nowcast.csv") {
        $Lines = (Get-Content "data\weather\brezoaia_nowcast.csv" | Measure-Object -Line).Lines - 1
        Write-Host "✓ SUCCESS: Nowcast saved ($Lines data points)" -ForegroundColor Green

        # Backup cu timestamp pentru tracking
        $BackupFile = "data\weather\archive\nowcast_$(Get-Date -Format 'yyyyMMdd_HHmm').csv"
        New-Item -ItemType Directory -Force -Path "data\weather\archive" | Out-Null
        Copy-Item "data\weather\brezoaia_nowcast.csv" $BackupFile -Force
    } else {
        Write-Host "✗ ERROR: File not created" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "✗ EXCEPTION: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
