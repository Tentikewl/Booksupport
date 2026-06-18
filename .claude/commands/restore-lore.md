Restore the Horus Rising lore database from the committed JSON exports.

Run the following command from the project root:

```bash
python restore_entities.py
```

This rebuilds both ChromaDB collections (entities + passages) from `horus_rising_entities.json` and `horus_rising_passages.json`. No API calls are made — everything is embedded locally. Takes about 30 seconds.

When complete, confirm how many entities and passages were restored and tell the user the lore database is ready.
