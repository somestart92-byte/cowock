"""Voiceover providers.

Three modes, chosen by ``social.video.voiceover`` in config.yaml:

* ``none``       — silent video (default; nothing to install, nothing to pay for)
* ``espeak``     — offline synthesis via the espeak-ng binary if present
* ``elevenlabs`` — ElevenLabs API when ``ELEVENLABS_API_KEY`` is set

Each provider returns a WAV/MP3 path or ``None``; callers must handle ``None``
so a missing voice never breaks a render.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


class VoiceoverError(RuntimeError):
    pass


def available(provider: str) -> bool:
    if provider == "none":
        return True
    if provider == "espeak":
        return bool(shutil.which("espeak-ng") or shutil.which("espeak"))
    if provider == "elevenlabs":
        return bool(os.environ.get("ELEVENLABS_API_KEY"))
    return False


def synthesize(
    text: str,
    out_path: str | Path,
    provider: str = "none",
    voice: str = "",
    words_per_minute: int = 165,
) -> Path | None:
    """Render ``text`` to an audio file. Returns ``None`` when unavailable."""
    text = " ".join(text.split())
    if not text or provider == "none":
        return None
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if provider == "espeak":
        return _espeak(text, out, voice, words_per_minute)
    if provider == "elevenlabs":
        return _elevenlabs(text, out, voice)
    raise VoiceoverError(f"unknown voiceover provider: {provider!r}")


def _espeak(text: str, out: Path, voice: str, wpm: int) -> Path | None:
    binary = shutil.which("espeak-ng") or shutil.which("espeak")
    if not binary:
        return None
    cmd = [binary, "-s", str(wpm), "-w", str(out), text]
    if voice:
        cmd[1:1] = ["-v", voice]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists():
        raise VoiceoverError(f"espeak failed: {proc.stderr.strip()[:300]}")
    return out


def _elevenlabs(text: str, out: Path, voice: str) -> Path | None:
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        return None
    import requests

    voice_id = voice or os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
    resp = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={"xi-api-key": api_key, "accept": "audio/mpeg"},
        json={
            "text": text,
            "model_id": os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2"),
            "voice_settings": {"stability": 0.45, "similarity_boost": 0.75},
        },
        timeout=120,
    )
    if resp.status_code >= 400:
        raise VoiceoverError(f"ElevenLabs {resp.status_code}: {resp.text[:300]}")
    out = out.with_suffix(".mp3")
    out.write_bytes(resp.content)
    return out
