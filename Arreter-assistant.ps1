# Arrête le bot et son gardien, sans toucher aux autres programmes Python.
$botPath = Split-Path $MyInvocation.MyCommand.Path
New-Item -ItemType File -Force (Join-Path $botPath "data\arret.flag") | Out-Null
Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like '*Garder-assistant-actif.ps1*' -or $_.CommandLine -like '*-m assistant*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
