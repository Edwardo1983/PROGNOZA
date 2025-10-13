# ==============================================================================
# Script: Fetch Weather Data pentru Brezoaia PV Park - SIMPLIFIED
# ==============================================================================

$ErrorActionPreference = "Continue"
$StartTime = Get-Date

Write-Host "========================================"
Write-Host "BREZOAIA PV PARK - Weather Data Fetch"
Write-Host "========================================"
Write-Host "Start: $StartTime"
Write-Host ""

Set-Location "C:\Users\Opaop\Desktop\Prognoza\PROGNOZA"

New-Item -ItemType Directory -Force -Path "data\weather" | Out-Null
New-Item -ItemType Directory -Force -Path "logs" | Out-Null

$LogDate = Get-Date -Format "yyyyMMdd_HHmm"
$LogFile = "logs\weather_fetch_$LogDate.log"

# ==============================================================================
# 1. NOWCAST (2h @ 15min)
# ==============================================================================
Write-Host "[1/4] Fetching NOWCAST (2h @ 15min)..."
python -m weather.router --nowcast 2 --out data/weather/brezoaia_nowcast.csv 2>&1 | Tee-Object -FilePath $LogFile -Append
if ($LASTEXITCODE -eq 0) {
    Write-Host "SUCCESS: Nowcast saved" -ForegroundColor Green
} else {
    Write-Host "ERROR: Nowcast failed" -ForegroundColor Red
}
Write-Host ""

# ==============================================================================
# 2. HOURLY 48H
# ==============================================================================
Write-Host "[2/4] Fetching 48H HOURLY forecast..."
python -m weather.router --hourly 48 --out data/weather/brezoaia_48h.csv 2>&1 | Tee-Object -FilePath $LogFile -Append
if ($LASTEXITCODE -eq 0) {
    Write-Host "SUCCESS: 48h forecast saved" -ForegroundColor Green
} else {
    Write-Host "ERROR: 48h forecast failed" -ForegroundColor Red
}
Write-Host ""

# ==============================================================================
# 3. HOURLY 168H
# ==============================================================================
Write-Host "[3/4] Fetching 168H WEEKLY forecast..."
python -m weather.router --hourly 168 --out data/weather/brezoaia_weekly.csv 2>&1 | Tee-Object -FilePath $LogFile -Append
if ($LASTEXITCODE -eq 0) {
    Write-Host "SUCCESS: Weekly forecast saved" -ForegroundColor Green
} else {
    Write-Host "ERROR: Weekly forecast failed" -ForegroundColor Red
}
Write-Host ""

# ==============================================================================
# 4. SUMMARY
# ==============================================================================
Write-Host "[4/4] Generating summary..."
Write-Host ""
Write-Host "=== WEATHER DATA SUMMARY ==="

$Files = @(
    "data/weather/brezoaia_nowcast.csv",
    "data/weather/brezoaia_48h.csv",
    "data/weather/brezoaia_weekly.csv"
)

foreach ($file in $Files) {
    if (Test-Path $file) {
        $lines = (Get-Content $file | Measure-Object -Line).Lines - 1
        $size = (Get-Item $file).Length / 1KB
        Write-Host "+ $file : $lines rows, $($size.ToString('0.0')) KB" -ForegroundColor Green
    } else {
        Write-Host "- $file : MISSING" -ForegroundColor Red
    }
}

$EndTime = Get-Date
$Duration = $EndTime - $StartTime

Write-Host ""
Write-Host "========================================"
Write-Host "Fetch completed: $EndTime"
Write-Host "Duration: $($Duration.TotalSeconds.ToString('0.0')) seconds"
Write-Host "Log: $LogFile"
Write-Host "========================================"
