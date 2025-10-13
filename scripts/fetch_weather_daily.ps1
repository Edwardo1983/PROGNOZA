# ==============================================================================
# Script: Fetch Day-Ahead Forecast (48h hourly)
# Frecvență: Zilnic la 08:00 (pregătire pentru raportare ANRE 12:00)
# Scop: Prognoza pentru ziua D+1 (day-ahead) și D+2
# ==============================================================================

$ErrorActionPreference = "Stop"
Set-Location "C:\Users\Opaop\Desktop\Prognoza\PROGNOZA"

# Creează directoare dacă nu există
New-Item -ItemType Directory -Force -Path "data\weather" | Out-Null
New-Item -ItemType Directory -Force -Path "logs" | Out-Null

$Date = Get-Date
$LogFile = "logs\weather_daily_$($Date.ToString('yyyyMMdd')).log"

function Log-Message {
    param($Message, $Color = "White")
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogLine = "[$Timestamp] $Message"
    Write-Host $LogLine -ForegroundColor $Color
    $LogLine | Out-File -FilePath $LogFile -Append
}

Log-Message "=== WEATHER FETCH DAY-AHEAD ===" "Cyan"
Log-Message "Date: $($Date.ToString('yyyy-MM-dd'))" "Cyan"

# Fetch 48h hourly
Log-Message "Fetching 48h hourly forecast..." "Yellow"
try {
    python -m weather.router --hourly 48 --out data/weather/brezoaia_48h.csv 2>&1 | Tee-Object -FilePath $LogFile -Append

    if ($LASTEXITCODE -eq 0 -and (Test-Path "data\weather\brezoaia_48h.csv")) {
        $Lines = (Get-Content "data\weather\brezoaia_48h.csv" | Measure-Object -Line).Lines - 1
        Log-Message "✓ SUCCESS: 48h forecast saved ($Lines hours)" "Green"

        # Arhivează pentru tracking istoric
        $ArchiveFile = "data\weather\archive\48h_$($Date.ToString('yyyyMMdd')).csv"
        New-Item -ItemType Directory -Force -Path "data\weather\archive" | Out-Null
        Copy-Item "data\weather\brezoaia_48h.csv" $ArchiveFile -Force
        Log-Message "✓ Archived to: $ArchiveFile" "Green"

        # Verifică calitatea datelor
        $Script = @"
import pandas as pd
df = pd.read_csv('data/weather/brezoaia_48h.csv', index_col=0)
valid = df['temp_C'].notna().sum()
total = len(df)
pct = (valid / total) * 100 if total > 0 else 0
print(f'Data quality: {valid}/{total} valid ({pct:.1f}%)')
if pct < 90:
    print('WARNING: Data quality below 90%')
    exit(1)
"@
        $Script | python

        if ($LASTEXITCODE -eq 0) {
            Log-Message "✓ Data quality check: PASSED" "Green"
        } else {
            Log-Message "⚠ Data quality check: WARNING" "Yellow"
        }
    } else {
        Log-Message "✗ ERROR: 48h forecast fetch failed" "Red"
        exit 1
    }
} catch {
    Log-Message "✗ EXCEPTION: $($_.Exception.Message)" "Red"
    exit 1
}

Log-Message "=== FETCH COMPLETED ===" "Cyan"
