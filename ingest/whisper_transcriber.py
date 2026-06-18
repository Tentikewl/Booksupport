from __future__ import annotations
from pathlib import Path


def transcribe(audio_path: Path, output_txt: Path | None = None) -> str:
    """Transcribe an audiobook file to text using local Whisper."""
    try:
        import whisper
    except ImportError as e:
        raise ImportError("pip install openai-whisper") from e

    print(f"Loading Whisper model (base)…")
    model = whisper.load_model("base")

    print(f"Transcribing {audio_path.name} — this may take a while…")
    result = model.transcribe(str(audio_path), verbose=False)
    text: str = result["text"]

    if output_txt is None:
        output_txt = audio_path.with_suffix(".txt")

    output_txt.write_text(text, encoding="utf-8")
    print(f"Transcript saved to {output_txt}")
    return text
