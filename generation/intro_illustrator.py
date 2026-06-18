"""Generate introduction illustrations for new entities (characters, objects, locations)."""
from __future__ import annotations
from pathlib import Path

from rag.glossary import expand_prompt

_CHARACTER_PORTRAIT_TEMPLATE = """\
Grimdark sci-fi character portrait, Warhammer 40K Horus Heresy aesthetic, \
hyper-detailed, dramatic lighting, digital art. \
This is a character introduction portrait — focus entirely on this individual.

[CHARACTER] {name}
{description}

[VISUAL NOTES] {notes}

[STYLE] Three-quarter view portrait, head and shoulders or full body depending on armour. \
Render every detail of their appearance faithfully. Dramatic chiaroscuro lighting. \
No background figures. No text or labels.\
"""

_CONCEPT_TEMPLATE = """\
Grimdark sci-fi concept illustration, Warhammer 40K Horus Heresy aesthetic, \
hyper-detailed, cinematic lighting, digital art. \
This is an establishing concept illustration — render this subject definitively.

[SUBJECT] {name} ({entity_type})
{description}

[VISUAL NOTES] {notes}

[STYLE] Clear establishing view that communicates exactly what this {entity_type} looks like. \
Accurate detail, dramatic atmosphere. No unrelated figures or elements.\
"""


def _significance_score(entity: dict) -> int:
    """Score an entity by visual richness. Higher = more worth illustrating."""
    desc = entity.get("canonical_description", "")
    notes = entity.get("visual_notes", [])
    score = 0
    visual_keywords = [
        "armour", "armor", "wear", "clad", "tall", "short", "hair", "eye",
        "face", "skin", "built", "figure", "spacecraft", "vehicle", "ship",
        "weapon", "sword", "gun", "blade", "tower", "palace", "structure",
        "robe", "cloth", "uniform", "plate", "helm", "helmet",
    ]
    combined = (desc + " ".join(notes)).lower()
    score += sum(1 for kw in visual_keywords if kw in combined)
    score += len(notes) * 2       # visual notes are high signal
    score += min(len(desc) // 50, 5)  # description length, capped
    return score


def _is_significant(entity: dict) -> bool:
    desc = entity.get("canonical_description", "")
    notes = entity.get("visual_notes", [])
    if len(desc) < 40 and not notes:
        return False
    return _significance_score(entity) >= 3


import config as _config
MAX_INTROS_PER_CHAPTER = _config.MAX_INTROS_PER_CHAPTER


def build_intro_prompts(chapter_id: str, entities: list[dict]) -> list[dict]:
    """
    Given entities first appearing in this chapter, return intro illustration specs.
    Each spec: {entity, prompt, filename, kind}
    """
    # Filter to significant entities and rank by visual richness
    significant = [e for e in entities if _is_significant(e)]
    # Characters first, then others, both sorted by score descending
    characters = sorted([e for e in significant if e["type"] == "character"],
                        key=_significance_score, reverse=True)
    others = sorted([e for e in significant if e["type"] != "character"],
                    key=_significance_score, reverse=True)
    ranked = (characters + others)[:MAX_INTROS_PER_CHAPTER]

    specs = []
    for entity in ranked:

        name = entity.get("name", entity["id"])
        desc = entity.get("canonical_description", "")
        notes = "; ".join(entity.get("visual_notes", []))
        kind = entity["type"]

        if kind == "character":
            prompt = expand_prompt(_CHARACTER_PORTRAIT_TEMPLATE.format(
                name=name,
                description=desc,
                notes=notes or "No additional notes.",
            ))
            filename = f"{chapter_id}_intro_{entity['id']}_portrait.jpg"
        else:
            prompt = expand_prompt(_CONCEPT_TEMPLATE.format(
                name=name,
                entity_type=kind,
                description=desc,
                notes=notes or "No additional notes.",
            ))
            filename = f"{chapter_id}_intro_{entity['id']}_concept.jpg"

        specs.append({
            "entity": entity,
            "prompt": prompt,
            "filename": filename,
            "kind": kind,
        })

    return specs


def generate_intro_images(
    chapter_id: str,
    new_entities: list[dict],
    output_dir: Path,
) -> list[dict]:
    """Generate portrait/concept images for newly introduced entities."""
    from generation.image_generator import generate_image

    specs = build_intro_prompts(chapter_id, new_entities)
    if not specs:
        return []

    results = []
    intro_dir = output_dir / chapter_id / "introductions"
    intro_dir.mkdir(parents=True, exist_ok=True)

    for spec in specs:
        dest = intro_dir / spec["filename"]
        name = spec["entity"].get("name", spec["entity"]["id"])
        kind = spec["kind"]
        print(f"  Illustrating new {kind}: {name}…")
        try:
            image_path = generate_image(spec["prompt"], dest)
            results.append({
                "entity": spec["entity"],
                "kind": spec["kind"],
                "filename": spec["filename"],
                "image_path": str(image_path),
                "prompt": spec["prompt"],
            })
        except Exception as e:
            print(f"  Warning: failed to generate intro for {name}: {e}")

    return results
