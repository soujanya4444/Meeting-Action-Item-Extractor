"""
transcribe.py
--------------
Optional standalone helper to turn a meeting AUDIO recording into a text
transcript, which you then paste into the web UI (or pipe straight into
extractor.py).

This is a separate, optional step from the main app because:
  - Local Whisper needs to download model weights (requires internet on
    first run) and benefits a lot from a GPU
  - The OpenAI Whisper API needs an API key and network access
  - The main app (app.py) is designed to run with ZERO external
    dependencies/API keys, using pasted-in transcript text

Two supported modes:

1. Local Whisper (openai-whisper pip package, runs on your own machine):
     pip install openai-whisper
     python transcribe.py meeting_audio.mp3 --mode local

2. OpenAI Whisper API (needs OPENAI_API_KEY):
     pip install openai
     python transcribe.py meeting_audio.mp3 --mode api
"""

import argparse
import os


def transcribe_local(audio_path: str, model_size: str = "base") -> str:
    """Runs Whisper locally on your machine. Downloads model weights on
    first run (requires internet once), then works fully offline."""
    import whisper
    model = whisper.load_model(model_size)
    result = model.transcribe(audio_path)
    return result["text"]


def transcribe_api(audio_path: str) -> str:
    """Uses OpenAI's hosted Whisper API - no local model download needed,
    but requires network access and an API key."""
    from openai import OpenAI
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    with open(audio_path, "rb") as f:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
        )
    return transcript.text


def main():
    parser = argparse.ArgumentParser(description="Transcribe meeting audio to text.")
    parser.add_argument("audio_path", help="Path to the audio file (mp3, wav, m4a, ...)")
    parser.add_argument("--mode", choices=["local", "api"], default="local",
                         help="'local' runs Whisper on your machine, 'api' uses OpenAI's hosted API")
    parser.add_argument("--model-size", default="base",
                         help="Whisper model size for local mode: tiny, base, small, medium, large")
    parser.add_argument("--output", default=None, help="Optional path to save the transcript .txt file")
    args = parser.parse_args()

    if args.mode == "local":
        text = transcribe_local(args.audio_path, args.model_size)
    else:
        text = transcribe_api(args.audio_path)

    print(text)

    if args.output:
        with open(args.output, "w") as f:
            f.write(text)
        print(f"\nSaved transcript -> {args.output}")


if __name__ == "__main__":
    main()
