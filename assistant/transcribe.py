from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)


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
    def __init__(self, model: str, device: str, compute_type: str) -> None:
        _register_windows_cuda_dlls()
        from faster_whisper import WhisperModel

        log.info("Chargement de Whisper %s sur %s (%s)…", model, device, compute_type)
        try:
            self._model = WhisperModel(model, device=device, compute_type=compute_type)
        except Exception:
            if device == "cpu":
                raise
            log.exception("Whisper n'a pas pu utiliser le GPU, passage sur le processeur (plus lent).")
            self._model = WhisperModel(model, device="cpu", compute_type="int8")

    def transcribe(self, audio_path: Path) -> str:
        segments, _ = self._model.transcribe(
            str(audio_path),
            language="fr",
            beam_size=5,
            vad_filter=True,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()
