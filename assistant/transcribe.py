from __future__ import annotations

import logging
from pathlib import Path

from faster_whisper import WhisperModel

log = logging.getLogger(__name__)


class Transcriber:
    def __init__(self, model: str, device: str, compute_type: str) -> None:
        log.info("Chargement de Whisper %s sur %s (%s)…", model, device, compute_type)
        self._model = WhisperModel(model, device=device, compute_type=compute_type)

    def transcribe(self, audio_path: Path) -> str:
        segments, _ = self._model.transcribe(
            str(audio_path),
            language="fr",
            beam_size=5,
            vad_filter=True,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()
