"""Generate images via Replicate FLUX API."""
from __future__ import annotations
import time
import urllib.request
from pathlib import Path

import config


def generate_image(prompt: str, output_path: Path) -> Path:
    """Generate one image and save it to output_path. Returns the path."""
    try:
        import replicate
    except ImportError as e:
        raise ImportError("pip install replicate") from e

    output_path.parent.mkdir(parents=True, exist_ok=True)

    client = replicate.Client(api_token=config.REPLICATE_API_TOKEN)

    delay = 10
    for attempt in range(5):
        try:
            output = client.run(
                config.IMAGE_MODEL,
                input={
                    "prompt": prompt,
                    "width": config.IMAGE_WIDTH,
                    "height": config.IMAGE_HEIGHT,
                    "num_inference_steps": 4,  # flux-schnell uses 1-4 steps
                    "output_format": "jpg",
                    "output_quality": 85,
                },
            )
            break
        except Exception as e:
            if "429" in str(e) or "throttled" in str(e).lower() or "rate limit" in str(e).lower():
                if attempt == 4:
                    raise
                print(f"\n  Rate limited — waiting {delay}s…")
                time.sleep(delay)
                delay *= 2
            else:
                raise

    # Replicate returns a list of URLs or file-like objects
    if isinstance(output, list):
        url_or_file = output[0]
    else:
        url_or_file = output

    if hasattr(url_or_file, "read"):
        image_data = url_or_file.read()
        output_path.write_bytes(image_data)
    else:
        url = str(url_or_file)
        _download(url, output_path)

    return output_path


def _download(url: str, dest: Path, retries: int = 4) -> None:
    delay = 2
    for attempt in range(retries):
        try:
            urllib.request.urlretrieve(url, str(dest))
            return
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(delay)
            delay *= 2


def generate_chapter_images(
    beats: list[dict],
    prompts: list[str],
    chapter_id: str,
    output_dir: Path,
) -> list[dict]:
    """Generate all images for a chapter. Returns list of {beat, image_path} dicts."""
    results = []
    for i, (beat, prompt) in enumerate(zip(beats, prompts)):
        filename = f"{chapter_id}_beat_{i + 1:02d}.jpg"
        dest = output_dir / chapter_id / filename
        print(f"  Generating image {i + 1}/{len(beats)}: {beat.get('visual_description', '')[:60]}…")
        image_path = generate_image(prompt, dest)
        results.append({
            "beat": beat,
            "prompt": prompt,
            "image_path": str(image_path),
            "filename": filename,
        })
    return results
