# ==============================================================================
# Script: Setup Task Scheduler pentru raportări automate
# Descriere: Configurează automat toate task-urile necesare
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "SETUP TASK SCHEDULER - BREZOAIA PV PARK" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$ProjectPath = "C:\Users\Opaop\Desktop\Prognoza\PROGNOZA"

# Verifică dacă scripturile există
$Scripts = @(
    "$ProjectPath\scripts\fetch_weather_nowcast.ps1",
    "$ProjectPath\scripts\fetch_weather_daily.ps1",
    "$ProjectPath\scripts\fetch_weather_all.ps1"
)

foreach ($Script in $Scripts) {
    if (!(Test-Path $Script)) {
        Write-Host "✗ ERROR: Script missing: $Script" -ForegroundColor Red
        exit 1
    }
}
Write-Host "✓ All scripts found" -ForegroundColor Green
Write-Host ""

# ==============================================================================
# TASK 1: Nowcast la fiecare 15 minute (intraday)
# ==============================================================================
Write-Host "[1/3] Creating task: Weather Nowcast (every 15 min)..." -ForegroundColor Yellow

$TaskName = "Brezoaia_Weather_Nowcast"
$Action = New-ScheduledTaskAction -Execute "PowerShell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ProjectPath\scripts\fetch_weather_nowcast.ps1`""

$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration ([TimeSpan]::MaxValue)

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U

try {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal | Out-Null
    Write-Host "✓ Task created: $TaskName" -ForegroundColor Green
} catch {
    Write-Host "✗ Failed to create task: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

# ==============================================================================
# TASK 2: Day-Ahead zilnic la 08:00 (pregătire raportare ANRE)
# ==============================================================================
Write-Host "[2/3] Creating task: Weather Day-Ahead (daily 08:00)..." -ForegroundColor Yellow

$TaskName = "Brezoaia_Weather_DayAhead"
$Action = New-ScheduledTaskAction -Execute "PowerShell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ProjectPath\scripts\fetch_weather_daily.ps1`""

$Trigger = New-ScheduledTaskTrigger -Daily -At "08:00"

try {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal | Out-Null
    Write-Host "✓ Task created: $TaskName" -ForegroundColor Green
} catch {
    Write-Host "✗ Failed to create task: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

# ==============================================================================
# TASK 3: Weekly forecast duminică la 18:00 (planificare săptămână)
# ==============================================================================
Write-Host "[3/3] Creating task: Weather Weekly (Sunday 18:00)..." -ForegroundColor Yellow

$TaskName = "Brezoaia_Weather_Weekly"
$Action = New-ScheduledTaskAction -Execute "PowerShell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -Command `"cd '$ProjectPath'; python -m weather.router --hourly 168 --out data/weather/brezoaia_weekly.csv`""

$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At "18:00"

try {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal | Out-Null
    Write-Host "✓ Task created: $TaskName" -ForegroundColor Green
} catch {
    Write-Host "✗ Failed to create task: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

# ==============================================================================
# SUMMARY
# ==============================================================================
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "TASK SCHEDULER SETUP COMPLETED" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Configured tasks:" -ForegroundColor Cyan
Write-Host "  1. Brezoaia_Weather_Nowcast   → Every 15 minutes" -ForegroundColor White
Write-Host "  2. Brezoaia_Weather_DayAhead  → Daily at 08:00" -ForegroundColor White
Write-Host "  3. Brezoaia_Weather_Weekly    → Sunday at 18:00" -ForegroundColor White
Write-Host ""
Write-Host "To verify:" -ForegroundColor Yellow
Write-Host "  Get-ScheduledTask | Where-Object {`$_.TaskName -like 'Brezoaia*'}" -ForegroundColor Gray
Write-Host ""
Write-Host "To run manually:" -ForegroundColor Yellow
Write-Host "  Start-ScheduledTask -TaskName 'Brezoaia_Weather_DayAhead'" -ForegroundColor Gray
Write-Host ""
Write-Host "Logs location: $ProjectPath\logs\" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
