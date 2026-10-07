@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
title Installation de l'assistant vocal

where ollama >nul 2>nul
if errorlevel 1 (
    echo Ollama n'est pas installe, installation automatique...
    winget install -e --id Ollama.Ollama --accept-package-agreements --accept-source-agreements
)

where py >nul 2>nul
if errorlevel 1 (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python n'est pas installe, installation automatique...
        winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        echo.
        echo Python installe. Ferme cette fenetre et relance Lancer-assistant.bat.
        pause
        exit /b
    )
)

if not exist .venv\Scripts\python.exe (
    echo Creation de l'environnement Python...
    py -3 -m venv .venv 2>nul || python -m venv .venv
)

echo Installation / mise a jour des dependances (la premiere fois peut prendre quelques minutes)...
.venv\Scripts\python.exe -m pip install -q --upgrade pip
.venv\Scripts\python.exe -m pip install -q -r requirements.txt nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
if errorlevel 1 (
    echo L'installation des dependances a echoue.
    pause
    exit /b 1
)

.venv\Scripts\python.exe scripts\setup_wizard.py
if errorlevel 1 (
    pause
    exit /b 1
)

powershell -ExecutionPolicy Bypass -File "%~dp0Demarrer-assistant.ps1"
echo.
echo L'assistant tourne en arriere-plan. Tu peux fermer cette fenetre.
echo Pour l'arreter : Arreter-assistant.ps1 (ou le raccourci du Bureau).
pause
