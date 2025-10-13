# ==============================================================================
# Script: Fetch Weather Data pentru Brezoaia PV Park
# Autor: PROGNOZA System
# Descriere: Descarca toate raportarile meteo necesare conform legislatiei RO
# ==============================================================================

$ErrorActionPreference = "Continue"
$StartTime = Get-Date

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "BREZOAIA PV PARK - Weather Data Fetch" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Start: $StartTime" -ForegroundColor Green
Write-Host ""

# Navighează la directorul proiectului
Set-Location "C:\Users\Opaop\Desktop\Prognoza\PROGNOZA"

# Creează directoare dacă nu există
New-Item -ItemType Directory -Force -Path "data\weather" | Out-Null
New-Item -ItemType Directory -Force -Path "logs" | Out-Null

# Creează log file
$LogDate = Get-Date -Format "yyyyMMdd_HHmm"
$LogFile = "logs\weather_fetch_$LogDate.log"

function Log-Message {
    param($Message, $Color = "White")
    Write-Host $Message -ForegroundColor $Color
    $Message | Out-File -FilePath $LogFile -Append
}

# ==============================================================================
# 1. NOWCAST (2 ore la 15 minute) - pentru control intraday
# ==============================================================================
Log-Message "[1/4] Fetching NOWCAST (2h @ 15min resolution)..." "Yellow"
try {
    python -m weather.router --nowcast 2 --out data/weather/brezoaia_nowcast.csv 2>&1 | Tee-Object -FilePath $LogFile -Append
    if ($LASTEXITCODE -eq 0) {
        Log-Message "✓ SUCCESS: Nowcast saved to brezoaia_nowcast.csv" "Green"
    } else {
        Log-Message "✗ ERROR: Nowcast fetch failed (exit code: $LASTEXITCODE)" "Red"
    }
} catch {
    Log-Message "✗ EXCEPTION: $($_.Exception.Message)" "Red"
}
Write-Host ""

# ==============================================================================
# 2. HOURLY 48H - pentru raportare day-ahead (D+1)
# ==============================================================================
Log-Message "[2/4] Fetching 48H HOURLY forecast (D+1 + D+2)..." "Yellow"
try {
    python -m weather.router --hourly 48 --out data/weather/brezoaia_48h.csv 2>&1 | Tee-Object -FilePath $LogFile -Append
    if ($LASTEXITCODE -eq 0) {
        Log-Message "✓ SUCCESS: 48h forecast saved to brezoaia_48h.csv" "Green"
    } else {
        Log-Message "✗ ERROR: 48h forecast fetch failed (exit code: $LASTEXITCODE)" "Red"
    }
} catch {
    Log-Message "✗ EXCEPTION: $($_.Exception.Message)" "Red"
}
Write-Host ""

# ==============================================================================
# 3. HOURLY 168H (7 zile) - pentru planificare săptămânală
# ==============================================================================
Log-Message "[3/4] Fetching 168H WEEKLY forecast (7 days)..." "Yellow"
try {
    python -m weather.router --hourly 168 --out data/weather/brezoaia_weekly.csv 2>&1 | Tee-Object -FilePath $LogFile -Append
    if ($LASTEXITCODE -eq 0) {
        Log-Message "SUCCESS: Weekly forecast saved to brezoaia_weekly.csv" "Green"
    } else {
        Log-Message "ERROR: Weekly forecast fetch failed (exit code: $LASTEXITCODE)" "Red"
    }
} catch {
    Log-Message "EXCEPTION: $($_.Exception.Message)" "Red"
}
Write-Host ""

# ==============================================================================
# 4. RAPORT SUMAR
# ==============================================================================
Log-Message "[4/4] Generating summary report..." "Yellow"

$Files = @(
    "data/weather/brezoaia_nowcast.csv",
    "data/weather/brezoaia_48h.csv",
    "data/weather/brezoaia_weekly.csv"
)

Write-Host ""
Write-Host "=== WEATHER DATA SUMMARY ===" -ForegroundColor Cyan
foreach ($file in $Files) {
    if (Test-Path $file) {
        $lines = (Get-Content $file | Measure-Object -Line).Lines - 1  # -1 pentru header
        $size = (Get-Item $file).Length / 1KB
        Log-Message "✓ $file : $lines rows, $($size.ToString('0.0')) KB" "Green"
    } else {
        Log-Message "✗ $file : MISSING" "Red"
    }
}

$EndTime = Get-Date
$Duration = $EndTime - $StartTime

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Fetch completed: $EndTime" -ForegroundColor Green
Write-Host "Total duration: $($Duration.TotalSeconds.ToString('0.0')) seconds" -ForegroundColor Green
Write-Host "Log saved to: $LogFile" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
