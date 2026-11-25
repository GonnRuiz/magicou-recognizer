![Magicou Recognizer — a visual recognition toolkit](docs/assets/banner.svg)

[![Tests](https://github.com/GonnRuiz/magicou-recognizer/actions/workflows/check.yml/badge.svg)](https://github.com/GonnRuiz/magicou-recognizer/actions/workflows/check.yml)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-8470b5)
[![License: MIT](https://img.shields.io/badge/license-MIT-72aa98)](LICENSE)
![Status: experimental](https://img.shields.io/badge/status-experimental-cd9a73)

**Identify physical Magic: The Gathering cards from photos and camera frames.**

Run it as a Python library, a command-line tool, or an HTTP service on your own infrastructure. No hosted recognition account or paid AI API is required.

[Quick start](#quick-start) · [Python](#use-it-in-python) · [HTTP API](docs/api.md) · [Architecture](docs/architecture.md) · [Español](README.es.md)

## What it does

- **Visual retrieval:** DINOv2 embeddings compare the full card and its artwork.
- **Multiple signals:** perceptual hashes and RootSIFT/RANSAC verify the shortlist.
- **Printing-aware results:** Scryfall IDs, editions, collector numbers, languages, and alternative printings.
- **Optional OCR:** a modern printing line can distinguish compatible editions.
- **USD reference prices:** query the exact printing and nonfoil, foil, or etched finish.
- **An index you control:** bulk ingestion, incremental caching, bounded concurrency, and explicit coverage.

This repository contains the engine and its developer tooling. Camera interfaces, accounts, collection management, and hosted applications belong in the consuming project.

### AI model and network access

The encoder is **DINOv2-small in ONNX format**, executed on your CPU through ONNX Runtime. `magicou-recognizer model` downloads a fixed revision and verifies its SHA-256. Visual recognition uses these generic weights plus your reference index; no custom Magic training checkpoint is required.

Photos are processed by the Python process you run. HTTP clients send their photo to the service they configure. Model setup, catalogue updates, uncached public reference images, and USD quotes make network requests to the documented sources. Credentials and service configuration are supplied by each integrator; generated data stays outside Git.

## Quick start

You need **Python 3.11+**, Git, Internet access for setup, and local space for reference images. Start with a small index before a full build.

```sh
git clone https://github.com/GonnRuiz/magicou-recognizer.git
cd magicou-recognizer
python -m venv .venv
```

Activate your environment:

```sh
# Linux / macOS
source .venv/bin/activate
```

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install and prepare the engine:

```sh
python -m pip install -e .
magicou-recognizer model
magicou-recognizer sync
magicou-recognizer build --limit 100
magicou-recognizer coverage
magicou-recognizer identify card.jpg --cropped
```

Use `--cropped` for an image already tightly framing a card. For a photo with background, use `magicou-recognizer identify photo.jpg`.

> **A catalogue is not a visual index.** `sync` imports metadata; `build` creates scannable references. A 100-reference trial can only visually retrieve those references. `coverage` reports actual counts and completeness.

### Build the selected full catalogue

```sh
magicou-recognizer build --workers 4
```

Omit `--limit` to process all eligible faces. The first build can take hours and consume many GB of disk space. Later builds reuse compatible features. Workers share a conservative download-start limiter.

`sync` defaults to Scryfall's **`default_cards`** dataset: English printings, or the available printed language for objects without an English version. To import the other language records:

```sh
magicou-recognizer sync --all-languages
magicou-recognizer build --workers 4
```

This is a larger dataset and requires building its corresponding index. Paper records with usable reference images are included; digital-only records are excluded. Independently illustrated double faces get separate references.

## Use it in Python

```python
import numpy as np
from PIL import Image, ImageOps
from magicou_recognizer import Recognizer

recognizer = Recognizer("./data")  # Load once; reuse between requests.
with Image.open("photo.jpg") as source:
    image = np.asarray(ImageOps.exif_transpose(source).convert("RGB"))

result = recognizer.identify(image)
for candidate in result["candidates"]:
    print(candidate["name"], candidate["set"], candidate["number"])
```

Fetch a selected printing's quote separately:

```python
from magicou_recognizer import get_price

quote = get_price("6904ea20-e504-47da-95a0-08739fdde260", finish="foil")
print(quote["value"], quote["currency"])  # value may be None.
```

`magicou-recognizer` and `python -m magicou_recognizer` expose the same CLI. The previous `magic-recognizer` command, `magic_recognizer` imports and internal `arcana` modules remain available for existing integrations.

## Run the HTTP service

```sh
magicou-recognizer serve --port 8015
```

```sh
curl http://127.0.0.1:8015/health
curl -X POST -F "file=@card.jpg" "http://127.0.0.1:8015/identify?cropped=true"
curl "http://127.0.0.1:8015/cards/6904ea20-e504-47da-95a0-08739fdde260/price?finish=foil"
```

Interactive documentation: **`http://127.0.0.1:8015/docs`**. The [API guide](docs/api.md) covers capture modes, authentication, limits, and response handling.

For optional OCR, use an isolated environment:

```sh
python -m pip install -e '.[ocr]'
magicou-recognizer serve --ocr
```

## How recognition works

```mermaid
flowchart LR
    A[Photo or camera frame] --> B[Card crop proposals]
    B --> C[DINOv2 + pHash retrieval]
    C --> D[RootSIFT + RANSAC verification]
    D --> E[Printing candidates]
    E --> F[Optional OCR confirmation]
    F --> G[Select printing and finish]
    G --> H[Scryfall USD quote]
```

Recognition is retrieval, rather than classification against a fixed list of names. New references can be embedded without retraining. The encoder is **generic DINOv2-small**, not a model fine-tuned specifically for Magic. [Architecture notes →](docs/architecture.md)

## Coverage and honest results

A reference build on **2026-11-25** indexed **115,084 paper-card faces** from the selected default-language export. This is a dated snapshot, not a claim that every language, future printing, or photograph is supported.

Three independent published camera photographs passed identity checks against that gallery, including an occluded title and perspective distortion. Shared-art editions remain ambiguous without printing evidence. **Three photographs are a smoke test, not an accuracy benchmark.**

- [Physical-photo report](docs/benchmarks/physical-photos-2026-11-25.json)
- [Evaluation method and limitations](docs/evaluation.md)
- [Data, index updates, and exports](docs/data-and-indexes.md)

Similarity is not a calibrated probability. Finish, condition, authenticity, and grading need separate confirmation. Missing prices remain missing; no price is invented or borrowed from another edition.

## Development

```sh
python -m pip install -e '.[dev]'
ruff check .
pytest -q
python -m compileall -q arcana magicou_recognizer
python -m pip wheel --no-deps --wheel-dir dist .
```

Unit tests run without downloading models or card images. Optional image evaluations require a separately built index and public fixtures. See [CONTRIBUTING.md](CONTRIBUTING.md) for changes and reproducible bug reports.

## License and attribution

Code is **MIT-licensed**. Generic geometry helpers are adapted from [Pokeum](https://github.com/TBLgGamin/pokeum), with its original attribution preserved. Models, OCR libraries, card data, and artwork retain their own rights. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Magic: The Gathering belongs to Wizards of the Coast. This is an independent, unofficial project without affiliation or endorsement.
