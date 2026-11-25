# Data and indexes

## Catalogue selection

Scryfall's `default_cards` is the default: English printings, or the available printed language for objects without an English version. `all_cards` includes other language records and is larger.

```sh
magicou-recognizer sync
# Or:
magicou-recognizer sync --all-languages
```

Paper records with usable trusted reference URLs are imported. Independently illustrated back faces get their own face IDs; printing identity stays the Scryfall UUID. The importer supports gzip JSONL and legacy JSON exports.

Requests use a descriptive User-Agent. API calls are serialized and conservatively spaced within the process. Image downloads share a limiter during indexing.

## Build and inspect

```sh
magicou-recognizer build --limit 100
magicou-recognizer coverage
magicou-recognizer build --workers 4
```

`--limit` caps the total faces selected for that snapshot, not an additional batch. Omit it to process all references. A small trial index is a subset, not a universal recognizer.

`data/progress.json` reports build progress. The completed generation's manifest is authoritative: catalogue/selected/indexed counts, failures, fingerprint, source metadata and creation date. Zero-failure completeness and explicitly partial snapshots are distinct.

Initial indexing can take hours and many GB of disk. Hardware, network, storage and source-service limits still apply even though inference has no paid API dependency. Rebuilding reuses compatible cached features. Keep `data/` outside Git.

## Update

```sh
magicou-recognizer sync
magicou-recognizer build --workers 4
magicou-recognizer coverage
```

Price refreshes are separate from visual index updates. Query a selected UUID/finish without rebuilding the neural index.

## Portable export

```sh
magicou-recognizer export --output ./data/release
```

Exports include the pinned model/license, matrices, hashes, metadata and manifest. They exclude reference JPEGs, credentials, account configuration and application code. SHA-256 values cover the bundle and its transport parts.

Completeness is required by default. An intentionally partial generation must carry `partial_snapshot: true` and be exported explicitly with `--allow-partial`. Keep its coverage visible to consumers. No cloud uploader, account, storage endpoint or automatic application deployment is bundled.

Only use artifacts from trusted sources. Code licensing does not grant ownership of card artwork or unrestricted redistribution of source data. Read [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) before redistributing artifacts.
