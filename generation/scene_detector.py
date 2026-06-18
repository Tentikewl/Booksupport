"""Detect visually strong scene beats per chapter using Claude Sonnet."""
from __future__ import annotations
import json
import re

import anthropic

import config

_DETECTION_PROMPT = """\
You are a visual scene selector for a book illustration project.

Read the chapter text below and identify {min_beats}–{max_beats} scene beats that are strong candidates for illustration.

Good beats have:
- A clear visual anchor (physical action, new location, character appearance, dramatic moment)
- Atmospheric or cinematic quality
- Named characters present

Avoid:
- Pure dialogue with no visual setting
- Beats that are nearly identical to another beat you've selected
- Internal monologue with no external action

Return a JSON array. Each beat must have:
  "position"           — float 0.0–1.0, approximate position through chapter
  "visual_description" — one vivid sentence describing the scene visually
  "mood"               — one or two words (e.g. "tense", "ethereal", "grim")
  "location"           — location name or id (snake_case)
  "entities_present"   — list of entity id strings (snake_case) for characters/objects present
  "visual_strength"    — float 0.0–1.0, how visually strong/illustratable this beat is

Return ONLY valid JSON, no prose, no markdown fences.

CHAPTER ID: {chapter_id}
KNOWN ENTITY IDS: {known_ids}

CHAPTER TEXT:
{text}
"""


def detect_beats(
    chapter_id: str,
    chapter_text: str,
    known_entity_ids: list[str],
    min_beats: int = config.MIN_BEATS_PER_CHAPTER,
    max_beats: int = config.MAX_BEATS_PER_CHAPTER,
    visual_strength_threshold: float = config.VISUAL_STRENGTH_THRESHOLD,
) -> list[dict]:
    """Return filtered list of scene beat dicts for a chapter."""
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    prompt = _DETECTION_PROMPT.format(
        min_beats=min_beats,
        max_beats=max_beats,
        chapter_id=chapter_id,
        known_ids=", ".join(known_entity_ids) if known_entity_ids else "none",
        text=chapter_text[:8000],  # cap to avoid oversized prompts
    )

    msg = client.messages.create(
        model=config.SCENE_MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = msg.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        beats = json.loads(raw)
        if not isinstance(beats, list):
            beats = []
    except json.JSONDecodeError:
        beats = []

    # Filter by visual strength
    beats = [b for b in beats if float(b.get("visual_strength", 0)) >= visual_strength_threshold]

    # Attach chapter id
    for beat in beats:
        beat["chapter"] = chapter_id

    return beats
