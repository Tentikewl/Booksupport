"""Universe glossary — expand 40K/Horus Heresy specific terms in image prompts."""
from __future__ import annotations
import re

# Core Warhammer 40K / Horus Heresy visual vocabulary.
# Keys are the in-universe term (lowercase). Values are visual descriptions
# suitable for an image generator unfamiliar with the lore.
_HARDCODED: dict[str, str] = {
    # Vehicles & craft
    "stormbird": "large angular military dropship spacecraft with swept wings and heavy armour plating",
    "thunderhawk": "large angular military gunship spacecraft with swept wings, nose-mounted cannons, heavy armour",
    "land raider": "massive heavily armoured tracked battle tank with twin sponson-mounted cannons",
    "rhino": "boxy armoured personnel carrier tracked vehicle",
    "drop pod": "cylindrical armoured re-entry pod with splayed legs, scorched metal hull",

    # Weapons
    "bolter": "large powerful automatic rifle with a drum magazine, fires explosive rounds",
    "bolt pistol": "large powerful semi-automatic pistol firing explosive rounds",
    "chainsword": "sword with a motorised chainsaw blade along its edge, roaring with teeth",
    "power sword": "sword with an energy field crackling along the blade",
    "power fist": "massive armoured gauntlet crackling with disruptive energy field",
    "plasma gun": "bulky rifle with glowing blue plasma coils and venting steam",
    "plasma pistol": "bulky pistol with glowing blue plasma coils",
    "melta gun": "short-range weapon that emits intense focused heat, industrial looking",
    "flamer": "weapon that projects a stream of burning promethium fuel",
    "lascannon": "large directed energy weapon emitting focused laser beams",
    "storm bolter": "oversized double-barrelled bolter rifle, firing two streams of explosive rounds",
    "narthecium": "medical gauntlet device worn on the forearm with blades and injectors",
    "reductor": "surgical tool used to extract gene-seed from fallen Space Marines",

    # Armour & equipment
    "power armour": "massive full-body ceramite armour suit with servo-assisted joints, aquila eagle emblem on chest",
    "terminator armour": "enormous bulky tactical dreadnought armour, far larger than standard power armour, thick ceramite plates",
    "mark iv armour": "sleek full-body ceramite power armour with distinctive helmet and aquila chest emblem, Horus Heresy era",
    "ceramite": "advanced ceramic composite armour material, smooth white or grey plating",
    "aquila": "double-headed eagle emblem emblazoned on Space Marine chest armour",
    "vox": "communication device, like a radio handset or helmet-mounted speaker grille",
    "auspex": "handheld scanning device, like a rugged military sensor paddle",

    # Units & roles
    "astartes": "towering superhuman Space Marine warrior in full ceramite power armour, seven feet tall",
    "space marine": "towering superhuman warrior in massive ceramite power armour, seven feet tall",
    "luna wolf": "Space Marine in white ceramite power armour with wolf iconography",
    "luna wolves": "Space Marines in white ceramite power armour with wolf iconography",
    "primarch": "godlike superhuman warrior, larger and more magnificent than even a Space Marine",
    "apothecary": "Space Marine medic in white power armour carrying medical equipment",
    "chaplain": "Space Marine priest in black power armour with skull-faced helmet",
    "terminator": "Space Marine in enormous bulky tactical dreadnought armour",
    "tactical squad": "squad of Space Marines in power armour carrying bolters",
    "remembrancer": "civilian artist or scholar in plain robes accompanying the military expedition",
    "iterator": "civilian orator and propagandist in plain robes",
    "tech-priest": "half-human half-machine servant of the Mechanicum with cybernetic augmentations and red robes",
    "mechanicum": "red-robed techno-priests with cybernetic augmentations and mechanical limbs",

    # Ships & locations
    "strike cruiser": "large grey angular military spacecraft with weapon batteries along its hull",
    "battle barge": "enormous heavily armed warship spacecraft bristling with weapons",
    "warp": "swirling chaotic otherworldly dimension of psychic energy, purple and violet colours",
    "strategium": "large military command room with holographic tactical displays and map tables",
    "apothecarion": "sterile medical bay with advanced surgical equipment",
    "arming chamber": "personal armour storage room lined with armour stands and weapon racks",
    "embarkation deck": "vast hangar deck inside a starship with rows of aircraft and troops",

    # Factions & organisations
    "mournival": "elite brotherhood of four Space Marine captains serving as the Warmaster's counsel",
    "legio custodes": "elite golden-armoured warriors who guard the Emperor, taller than Space Marines",
    "custodian": "elite golden-armoured warrior of the Legio Custodes, taller than a Space Marine",
    "imperial army": "regular human soldiers in standard military uniforms and light armour",
    "imperial fists": "Space Marines in bright yellow ceramite power armour",

    # Universe concepts
    "great crusade": "vast military campaign to reunite humanity across the galaxy",
    "horus heresy": "galaxy-spanning civil war among Space Marines",
    "gene-seed": "small biological implant, thumb-sized organic capsule",
    "hololithic": "holographic three-dimensional tactical display projection",
    "hololith": "holographic three-dimensional display projection",
}


def _build_entity_glossary() -> dict[str, str]:
    """Pull object and location entities from the store as additional glossary terms."""
    try:
        from rag.entity_extractor import get_all_entities
        entities = get_all_entities()
    except Exception:
        return {}

    glossary: dict[str, str] = {}
    for e in entities:
        if e["type"] not in ("object", "location"):
            continue
        name = e.get("name", "").strip()
        desc = e.get("canonical_description", "").strip()
        if name and desc:
            glossary[name.lower()] = desc
    return glossary


def expand_prompt(prompt: str) -> str:
    """Replace universe-specific terms in prompt with visual descriptions."""
    entity_glossary = _build_entity_glossary()
    glossary = {**_HARDCODED, **entity_glossary}

    # Sort by length descending so multi-word terms match before single words
    sorted_terms = sorted(glossary.keys(), key=len, reverse=True)

    for term in sorted_terms:
        pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
        if pattern.search(prompt):
            replacement = f"{term} ({glossary[term]})"
            prompt = pattern.sub(replacement, prompt, count=1)

    return prompt
