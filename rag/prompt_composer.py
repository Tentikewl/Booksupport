"""Hierarchical retrieval + image prompt assembly."""
from __future__ import annotations

from rag.passage_indexer import query_passages
from rag.entity_extractor import get_entity
from rag.glossary import expand_prompt


_PROMPT_TEMPLATE = """\
{style}

[COMPOSITION] {composition}

[SCENE] {scene_description} — {location_description}

[CHARACTERS PRESENT]
{character_block}

[MOOD] {mood}

[EXCLUDE] Do not show characters not listed above. Do not add background figures.\
"""

_STYLE = (
    "Grimdark sci-fi illustration, Warhammer 40K Horus Heresy aesthetic, "
    "hyper-detailed power armour, cinematic dramatic lighting, digital art, highly detailed. "
    "Characters are Space Marines — towering superhuman warriors in full ceramite power armour "
    "with aquila emblems, sealed helmets, and bolter weapons unless otherwise described."
)

# Composition direction keyed by mood keywords
_COMPOSITION_MAP = [
    ({"chaotic", "violent", "brutal", "frantic", "desperate"},
     "Dynamic angled composition, figures in motion, no central hero pose, sense of confusion and danger"),
    ({"tragic", "doomed", "mournful", "grief", "loss"},
     "Still, weight-bearing composition, subject off-centre, heavy negative space, downward gaze"),
    ({"tense", "foreboding", "ominous", "dread"},
     "Low angle, long shadows, subject silhouetted or partially obscured, oppressive atmosphere"),
    ({"awe", "magnificent", "triumphant", "epic", "glorious"},
     "Wide establishing shot, dramatic upward angle, subject commanding the frame"),
    ({"intimate", "quiet", "introspective", "solemn"},
     "Close framing, shallow depth, single subject, muted background"),
    ({"surreal", "ethereal", "uncanny"},
     "Unusual perspective, distorted scale, dreamlike lighting"),
]

_DEFAULT_COMPOSITION = "Cinematic wide shot, dramatic lighting, scene accurately depicted as described"


def _composition_for_mood(mood: str) -> str:
    mood_lower = mood.lower()
    for keywords, direction in _COMPOSITION_MAP:
        if any(kw in mood_lower for kw in keywords):
            return direction
    return _DEFAULT_COMPOSITION


def compose_prompt(beat: dict) -> str:
    """Compose a FLUX image prompt for a scene beat."""
    chapter = beat.get("chapter", "")
    visual_description = beat.get("visual_description", "")
    mood = beat.get("mood", "")
    location_id = beat.get("location", "")

    # Only use characters explicitly listed in the beat — no RAG bleed
    beat_entity_ids: list[str] = beat.get("entities_present", [])
    characters: list[dict] = []
    for eid in beat_entity_ids:
        record = get_entity(eid)
        if record and record["type"] == "character":
            characters.append(record)

    # Use passage query only to find location context, not characters
    location_desc = ""
    if location_id:
        loc = get_entity(location_id)
        if loc:
            location_desc = loc["canonical_description"]

    if not location_desc:
        nearby = query_passages(query_text=visual_description, chapter=chapter, n_results=3)
        for passage in nearby:
            for eid in passage.get("entity_ids", []):
                record = get_entity(eid)
                if record and record["type"] == "location":
                    location_desc = record["canonical_description"]
                    break
            if location_desc:
                break

    if not location_desc:
        location_desc = location_id or "an unspecified location"

    # Build character block
    char_lines: list[str] = []
    for char in characters:
        notes = "; ".join(char.get("visual_notes", []))
        desc = char["canonical_description"]
        if notes:
            desc = f"{desc}. {notes}"
        char_lines.append(f"- {char['name']}: {desc}")

    character_block = "\n".join(char_lines) if char_lines else "- No named characters — focus on the scene and atmosphere"

    return _PROMPT_TEMPLATE.format(
        style=_STYLE,
        composition=_composition_for_mood(mood),
        scene_description=expand_prompt(visual_description),
        location_description=expand_prompt(location_desc),
        character_block=expand_prompt(character_block),
        mood=mood or "atmospheric",
    )
