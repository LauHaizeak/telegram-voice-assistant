from __future__ import annotations

import gc
import logging
import os
import sys
import threading
from pathlib import Path

log = logging.getLogger(__name__)

UNLOAD_AFTER_SECONDS = 300


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
