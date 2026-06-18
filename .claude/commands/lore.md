Query the Horus Rising entity store for canonical lore about a character, location, object, or faction.

The user will provide a name or concept as the argument (e.g. `/lore Loken` or `/lore Murder`).

Run this Python snippet to search the entity store:

```python
import sys
sys.path.insert(0, '.')
from rag.entity_extractor import get_all_entities

query = "$ARGUMENTS".lower()
entities = get_all_entities()

# Try exact id match first, then name match, then partial
matches = [e for e in entities if query == e['id'].lower()]
if not matches:
    matches = [e for e in entities if query == e['name'].lower()]
if not matches:
    matches = [e for e in entities if query in e['name'].lower() or query in e['id'].lower()]

for e in matches[:5]:
    print(f"NAME: {e['name']} ({e['type']})")
    print(f"DESCRIPTION: {e['canonical_description']}")
    if e.get('visual_notes'):
        print(f"VISUAL NOTES: {'; '.join(e['visual_notes'])}")
    if e.get('aliases'):
        print(f"ALIASES: {', '.join(e['aliases'])}")
    if e.get('faction'):
        print(f"FACTION: {e['faction']}")
    print(f"FIRST APPEARS: {e['first_appearance']}")
    print(f"APPEARANCES: {e['appearance_count']}")
    print()
```

Present the results clearly to the user. If nothing is found, say so and suggest trying a partial name. If the lore database isn't loaded yet, tell the user to run `/restore-lore` first.
