from __future__ import annotations

import gc
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

import requests

log = logging.getLogger(__name__)

UNLOAD_AFTER_SECONDS = 300
WHISPER_NEEDS_MB = 5000
OLLAMA_URL = "http://localhost:11434"


def gpu_free_mb() -> int | None:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5).stdout
        return int(out.split()[0])
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        return None


def unload_ollama_models() -> None:
    """Libère la carte graphique : Ollama rechargera le modèle à la prochaine demande."""
    try:
        for model in requests.get(f"{OLLAMA_URL}/api/ps", timeout=5).json().get("models", []):
            requests.post(f"{OLLAMA_URL}/api/generate", json={"model": model["name"], "keep_alive": 0}, timeout=30)
    except requests.RequestException as e:
        log.warning("Impossible de décharger Ollama : %s", e)


def _register_windows_cuda_dlls() -> None:
    """Rend visibles les DLL CUDA installées par pip (nvidia-cublas-cu12, nvidia-cudnn-cu12)."""
    if sys.platform != "win32":
        return
    try:
        import nvidia
    except ImportError:
        return
    for base in nvidia.__path__:
        for bin_dir in Path(base).glob("*/bin"):
            os.add_dll_directory(str(bin_dir))
            os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"


class Transcriber:
    """Whisper chargé au premier vocal et déchargé de la carte graphique après 5 min sans vocal."""

    def __init__(self, model: str, device: str, compute_type: str) -> None:
        _register_windows_cuda_dlls()
        self._model_name = model
        self._device = device
        self._compute_type = compute_type
        self._model = None
        self._lock = threading.Lock()
        self._unload_timer: threading.Timer | None = None

    def _load(self) -> None:
        from faster_whisper import WhisperModel

        if self._device == "cuda":
            free = gpu_free_mb()
            if free is not None and free < WHISPER_NEEDS_MB:
                log.warning("Carte graphique presque pleine (%s Mo libres) : je décharge l'IA d'Ollama", free)
                unload_ollama_models()

        log.info("Chargement de Whisper %s sur %s (%s)…", self._model_name, self._device, self._compute_type)
        try:
            self._model = WhisperModel(self._model_name, device=self._device, compute_type=self._compute_type)
        except Exception:
            if self._device == "cpu":
                raise
            log.exception("Whisper n'a pas pu utiliser le GPU, passage sur le processeur (plus lent).")
            self._model = WhisperModel(self._model_name, device="cpu", compute_type="int8")

    def _unload(self) -> None:
        with self._lock:
            if self._model is not None:
                log.info("Déchargement de Whisper (5 min sans vocal)")
                self._model = None
                gc.collect()

    def transcribe(self, audio_path: Path) -> str:
        with self._lock:
            if self._unload_timer:
                self._unload_timer.cancel()
            if self._model is None:
                self._load()
            segments, _ = self._model.transcribe(str(audio_path), language="fr", beam_size=5, vad_filter=True)
            text = " ".join(segment.text.strip() for segment in segments).strip()
            self._unload_timer = threading.Timer(UNLOAD_AFTER_SECONDS, self._unload)
            self._unload_timer.daemon = True
            self._unload_timer.start()
        return text
