# Architecture

## A standalone retrieval engine

Local Python inference and a Scryfall reference catalogue are the core dependencies. The engine does not require a particular application, account system, database provider, hosting platform, or managed deployment.

```text
arcana/                 Recognition implementation and compatibility CLI
  vision/               Crop proposals, geometry and rectification
  model.py              Pinned DINOv2, pHash and local descriptors
  index.py              Incremental features and atomic generations
  recognizer.py         Retrieval and printing candidates
  scryfall.py           Catalogue ingestion and exact-printing quotes
  api.py                Optional FastAPI service
magicou_recognizer/       Public Python import and module entry point
tests/                  Offline unit tests
docs/                   Integration, data and evaluation guides
```

The internal `arcana` namespace is retained for compatibility. New consumers can import `Recognizer`, `FooterOCR`, and `get_price` from `magicou_recognizer`.

## Recognition pipeline

1. Limit image dimensions and generate bounded card-crop proposals. Guided frames prioritize their known capture margin.
2. Encode the whole card and artwork using the same frozen DINOv2-small encoder as the references.
3. Rank references with normalized embeddings and perceptual hashes.
4. Verify candidates with RootSIFT/RANSAC. Generic border matches alone are insufficient; artwork evidence is required.
5. Use optional OCR of a modern printing line to confirm a compatible edition and collector number. Otherwise return alternatives.
6. Query the selected printing and finish's price separately.

Reference descriptors have a bounded LRU cache. Missing local verification images can be fetched from trusted Scryfall image URLs. A complete image cache supports local visual matching; uncached references require Internet access.

## Model and index compatibility

The generic DINOv2-small ONNX graph has a pinned revision and SHA-256. It is not trained specifically for Magic. The fingerprint also identifies preprocessing and hash settings.

Reference vectors are stored as float16 and normalized as float32 during retrieval. Changing the model or preprocessing requires compatible rebuilt features. A mismatched index is rejected. New references can be added without training a new classifier.

## Storage and consistency

SQLite stores catalogue metadata. Features are cached by face, image URL and encoder fingerprint. Double-faced cards can have several references sharing a printing UUID; a split card with one reference image has one visual object.

Builds use bounded workers and a shared download-start limiter. Completed compatible features survive interruption. A process lock prevents simultaneous builds of one data root; low disk space stops construction.

Each generation contains vectors, hashes, a manifest and consistent metadata. A pointer selects it atomically. Catalogue, selected and indexed counts are distinct. Failed references are reported, not silently counted as scannable. Complete and explicitly partial exports remain distinguishable.

## Scope

Thresholds are heuristic, not calibrated probabilities. Shared artwork can identify a card family while leaving its printing ambiguous. Finish, condition, authenticity and grading require separate confirmation. A host application should display alternatives when details remain unresolved.

Geometry helpers preserve the MIT attribution of [Pokeum](https://github.com/TBLgGamin/pokeum). References: [Scryfall](https://scryfall.com/docs/api), [DINOv2](https://huggingface.co/facebook/dinov2-small) and its [ONNX export](https://huggingface.co/Xenova/dinov2-small).
