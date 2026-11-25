# Contributing

Contributions should improve the reusable Magic recognition engine, data tooling, API, tests or documentation. Application-specific accounts, collection management, hosting credentials and deployment automation belong in the consuming project.

## Local checks

```sh
python -m venv .venv
# Activate your environment.
python -m pip install -e '.[dev]'
ruff check .
pytest -q
python -m compileall -q arcana magicou_recognizer
python -m pip wheel --no-deps --wheel-dir dist .
```

Unit tests use local fixtures and do not require model downloads or API keys. Optional image evaluations need a separately built index.

## Recognition bug reports

Include engine version, model/index fingerprint, capture mode, expected Scryfall UUID, actual response, image dimensions and relevant glare/occlusion/rotation. A permitted minimal photo or reproducible test is more useful than a host application's screenshot.

Share only images you have permission to share. Remove location metadata and unrelated personal content. Exclude API keys, tokens, emails, account configuration and production collection data.

## Changes

Keep model/preprocessing changes explicit: embeddings from different fingerprints are not interchangeable. Add meaningful regressions for recognition, printing mix-ups, price nullability, limits and index consistency. Preserve attribution and explain evaluation limits.

Do not commit generated reference images, model weights, full indexes, databases or personal configuration. Performance claims need gallery size, method and independent test conditions.
