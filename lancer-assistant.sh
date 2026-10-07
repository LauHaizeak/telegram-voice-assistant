#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
    echo "Création de l'environnement Python..."
    python3 -m venv .venv
fi

echo "Installation / mise à jour des dépendances..."
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -r requirements.txt nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"

NVIDIA_LIBS=$(.venv/bin/python -c 'import os, nvidia.cublas.lib, nvidia.cudnn.lib; print(os.path.dirname(nvidia.cublas.lib.__file__) + ":" + os.path.dirname(nvidia.cudnn.lib.__file__))' 2>/dev/null || true)
export LD_LIBRARY_PATH="${NVIDIA_LIBS}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

.venv/bin/python scripts/setup_wizard.py
exec .venv/bin/python -m assistant
