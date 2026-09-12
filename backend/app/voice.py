from io import BytesIO

import av
from fastapi import HTTPException


def validate_audio(content: bytes):
    """Decode bounded media before submitting anything to the transcription provider."""
    if not content or len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "Use a recording below 10 MB and 60 seconds.")
    try:
        duration = 0.0
        with av.open(BytesIO(content)) as container:
            if not container.streams.audio or container.streams.video:
                raise HTTPException(422, "Upload a microphone audio recording, not a video.")
            for frame in container.decode(audio=0):
                duration += frame.samples / frame.sample_rate
                if duration > 60.5:
                    raise HTTPException(422, "Keep each voice answer to 60 seconds.")
        if duration < 0.2:
            raise HTTPException(422, "The recording is too short. Speak a short answer or use the keyboard.")
        return duration
    except HTTPException:
        raise
    except (av.FFmpegError, ValueError, ZeroDivisionError):
        raise HTTPException(
            422, "This recording could not be decoded. Try another browser or type your answer."
        ) from None
