"""Voice input via Muse Voice Transcribe (muse-voice-transcribe-1.0).

Protocol (official docs: https://dev.meta.ai/docs/speech-to-text):
file endpoint POST https://api.meta.ai/v1/asr/transcribe takes multipart
with a `request` JSON part (model, audioEncoding WAV, mode PUSH_TO_TALK)
plus an `audio` WAV part, Bearer auth, and returns buffered JSON with a
top-level `transcript`. The realtime WebSocket path was probed and works,
but a complete recording fits the simpler file endpoint.
"""
import json
import os
import subprocess
import uuid
import wave

import httpx

from app.core.config import UPLOAD_DIR, require_api_key
from app.services.catalog import detect_user_lang

VOICE_MODEL = "muse-voice-transcribe-1.0"
TRANSCRIBE_URL = "https://api.meta.ai/v1/asr/transcribe"
TARGET_RATE = 16000
MAX_SECONDS = 600
AUDIO_EXT = {".webm", ".ogg", ".oga", ".opus", ".m4a", ".mp3", ".wav",
             ".mp4", ".aac", ".aif", ".aiff", ".flac"}


class VoiceError(RuntimeError):
    """Transcription failed (bad audio, missing ffmpeg, or API error)."""


def wav_duration(path):
    with wave.open(path, "rb") as w:
        return w.getnframes() / float(w.getframerate() or 1)


def convert_to_wav(src, dest):
    """Convert any audio to mono 16-bit PCM WAV at 16 kHz. Returns seconds.

    Raises VoiceError when ffmpeg is missing, the file is unreadable,
    or the audio is longer than MAX_SECONDS.
    """
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", src,
             "-ac", "1", "-ar", str(TARGET_RATE), "-sample_fmt", "s16",
             dest],
            check=True, capture_output=True)
    except FileNotFoundError:
        raise VoiceError("ffmpeg is not installed")
    except subprocess.CalledProcessError:
        raise VoiceError("could not read audio file")
    seconds = wav_duration(dest)
    if seconds > MAX_SECONDS:
        raise VoiceError("audio is longer than 10 minutes")
    if seconds <= 0:
        raise VoiceError("audio is empty")
    return seconds


def transcribe_wav(path, api_key=None):
    """Send a WAV file to the transcribe endpoint. Returns plain text."""
    key = api_key or require_api_key()
    payload = {"model": VOICE_MODEL, "audioEncoding": "WAV",
               "mode": "PUSH_TO_TALK"}
    try:
        with open(path, "rb") as audio:
            resp = httpx.post(
                TRANSCRIBE_URL,
                headers={"Authorization": "Bearer " + key,
                         "Accept": "application/json"},
                files={"request": (None, json.dumps(payload),
                                    "application/json"),
                       "audio": (os.path.basename(path), audio,
                                 "audio/wav")},
                timeout=180.0)
    except httpx.HTTPError as exc:
        raise VoiceError("transcription request failed: %s" % exc)
    if resp.status_code != 200:
        raise VoiceError("transcription failed (HTTP %d)"
                         % resp.status_code)
    try:
        data = resp.json()
    except ValueError:
        raise VoiceError("transcription returned invalid JSON")
    text = (data.get("transcript") or "").strip()
    if not text:
        turns = data.get("turns") or []
        text = " ".join(t.get("transcript", "") for t in turns).strip()
    return text


def transcribe(audio_path):
    """Transcribe any audio file. Returns {"text", "language"}."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    wav = os.path.join(UPLOAD_DIR, "voice-%s.wav" % uuid.uuid4().hex)
    try:
        convert_to_wav(audio_path, wav)
        text = transcribe_wav(wav)
    finally:
        if os.path.exists(wav):
            os.remove(wav)
    return {"text": text, "language": detect_user_lang(text)}
