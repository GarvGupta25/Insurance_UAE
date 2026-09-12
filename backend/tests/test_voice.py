import io
import wave
from types import SimpleNamespace
from unittest.mock import MagicMock


def test_short_voice_upload_returns_editable_transcript_without_storing_audio(fixture_client, monkeypatch):
    from app import main

    client, _, _ = fixture_client
    audio = io.BytesIO()
    with wave.open(audio, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(8000)
        recording.writeframes(b"\x00\x00" * 8000)

    groq = MagicMock()
    groq.return_value.audio.transcriptions.create.return_value = SimpleNamespace(
        text="I prefer a lower premium.", duration=1
    )
    monkeypatch.setattr(main, "Groq", groq)
    monkeypatch.setattr(
        main, "settings", lambda: SimpleNamespace(groq_api_key="test-only", groq_stt_model="whisper-large-v3")
    )
    result = client.post(
        "/api/voice/transcriptions",
        files={"file": ("sample.wav", audio.getvalue(), "audio/wav")},
    )
    assert result.status_code == 200, result.text
    assert result.json() == {
        "transcript": "I prefer a lower premium.",
        "duration": 1,
        "persisted_audio": False,
    }
