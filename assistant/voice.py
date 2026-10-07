"""Réponses vocales : synthèse Piper sur le processeur (aucune mémoire graphique), envoyée en vocal Telegram."""

from __future__ import annotations

import io
import logging
import re
import subprocess
import sys
import threading
import wave
from pathlib import Path

import av

log = logging.getLogger(__name__)

UNLOAD_AFTER_SECONDS = 300
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")


def speakable(text: str) -> str:
    """Retire ce qui ne se dit pas : émojis, mise en forme, liens."""
    text = _EMOJI.sub("", text)
    text = re.sub(r"https?://\S+", "le lien", text)
    text = re.sub(r"[*_#`>]+", "", text)
    text = re.sub(r"^\s*[-•]\s*", "", text, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", text).strip()


class Speaker:
    def __init__(self, voice_dir: Path, voice_name: str) -> None:
        self._model_path = voice_dir / f"{voice_name}.onnx"
        self._voice = None
        self._lock = threading.Lock()
        self._unload_timer: threading.Timer | None = None

    def _load(self):
        from piper import PiperVoice

        if not self._model_path.exists():
            log.info("Téléchargement de la voix %s…", self._model_path.stem)
            self._model_path.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run([sys.executable, "-m", "piper.download_voices", "--download-dir",
                            str(self._model_path.parent), self._model_path.stem], check=True)
        self._voice = PiperVoice.load(str(self._model_path))

    def _unload(self) -> None:
        with self._lock:
            self._voice = None

    def speak(self, text: str) -> bytes:
        """Renvoie un vocal Telegram (OGG/Opus)."""
        with self._lock:
            if self._unload_timer:
                self._unload_timer.cancel()
            if self._voice is None:
                self._load()
            wav = io.BytesIO()
            with wave.open(wav, "wb") as w:
                self._voice.synthesize_wav(speakable(text), w)
            self._unload_timer = threading.Timer(UNLOAD_AFTER_SECONDS, self._unload)
            self._unload_timer.daemon = True
            self._unload_timer.start()
        wav.seek(0)
        return _to_ogg_opus(wav)


def _to_ogg_opus(wav: io.BytesIO) -> bytes:
    out = io.BytesIO()
    with av.open(wav) as src, av.open(out, "w", format="ogg") as dst:
        stream = dst.add_stream("libopus", rate=48000, layout="mono")
        resampler = av.AudioResampler(format="s16", layout="mono", rate=48000)
        for frame in src.decode(audio=0):
            for f in resampler.resample(frame):
                dst.mux(stream.encode(f))
        for f in resampler.resample(None):
            dst.mux(stream.encode(f))
        dst.mux(stream.encode(None))
    return out.getvalue()
