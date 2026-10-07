# Démarre le bot en arrière-plan, sauf s'il tourne déjà.
$botPath = Split-Path $MyInvocation.MyCommand.Path
$keeper = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
    Where-Object { $_.CommandLine -like '*Garder-assistant-actif.ps1*' }
if ($keeper) { exit }
Start-Process -FilePath "powershell.exe" -WindowStyle Hidden `
    -ArgumentList "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$botPath\Garder-assistant-actif.ps1`""
