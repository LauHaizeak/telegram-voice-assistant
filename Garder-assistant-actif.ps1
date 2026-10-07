# Fait tourner une seule instance du bot et la relance si elle plante.
$botPath = Split-Path $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $botPath ".venv\Scripts\python.exe"
$stopFlag = Join-Path $botPath "data\arret.flag"
$env:PYTHONIOENCODING = "utf-8"
Remove-Item $stopFlag -ErrorAction SilentlyContinue

while (-not (Test-Path $stopFlag)) {
    $process = Start-Process -FilePath $pythonPath -ArgumentList "-m", "assistant" -WindowStyle Hidden `
        -WorkingDirectory $botPath -PassThru `
        -RedirectStandardError (Join-Path $botPath "data\bot.log") `
        -RedirectStandardOutput (Join-Path $botPath "data\bot.out.log")
    Wait-Process -InputObject $process
    if (-not (Test-Path $stopFlag)) { Start-Sleep -Seconds 5 }
}
