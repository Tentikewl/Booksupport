"""Hierarchical retrieval + image prompt assembly."""
from __future__ import annotations

from rag.passage_indexer import query_passages
from rag.entity_extractor import get_entity


_PROMPT_TEMPLATE = """\
{style}

[SCENE] {scene_description} — {location_description}

[CHARACTERS PRESENT]
{character_block}

[MOOD] {mood}

[EXCLUDE] Do not show characters not listed above. Do not add background figures.\
"""

_STYLE = (
    "Detailed fantasy illustration, painterly, dramatic lighting, "
    "cinematic composition, high detail, digital art"
)


def compose_prompt(beat: dict) -> str:
    """Compose a FLUX image prompt for a scene beat.

    beat keys: chapter, visual_description, mood, location, entities_present,
               position (optional)
    """
    chapter = beat.get("chapter", "")
    visual_description = beat.get("visual_description", "")
    mood = beat.get("mood", "")
    location_id = beat.get("location", "")
    beat_entities: list[str] = beat.get("entities_present", [])

    # Retrieve nearby passages to discover additional entities
    nearby = query_passages(
        query_text=visual_description,
        chapter=chapter,
        n_results=5,
    )

    discovered_ids: set[str] = set(beat_entities)
    for passage in nearby:
        discovered_ids.update(passage.get("entity_ids", []))

    # Fetch canonical records
    entity_records: list[dict] = []
    for eid in discovered_ids:
        record = get_entity(eid)
        if record:
            entity_records.append(record)

    # Separate characters from locations
    characters = [e for e in entity_records if e["type"] == "character"]
    locations = [e for e in entity_records if e["type"] == "location"]

    # Prefer the beat's declared location entity if available
    location_desc = ""
    if location_id:
        loc = get_entity(location_id)
        if loc:
            location_desc = loc["canonical_description"]
    if not location_desc and locations:
        location_desc = locations[0]["canonical_description"]
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

    character_block = "\n".join(char_lines) if char_lines else "- No named characters described"

    return _PROMPT_TEMPLATE.format(
        style=_STYLE,
        scene_description=visual_description,
        location_description=location_desc,
        character_block=character_block,
        mood=mood or "atmospheric",
    )
