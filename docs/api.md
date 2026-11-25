# HTTP integration

Start with a built index:

```sh
magicou-recognizer --data ./data serve --port 8015
```

The service binds to `127.0.0.1` by default. Interactive OpenAPI documentation is at `/docs`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Readiness, catalogue/indexed counts, completeness and build date |
| `POST` | `/identify` | Recognize an image and return printing candidates |
| `GET` | `/cards/{card_id}/price` | Fetch a selected printing's USD quote |

## Recognize an image

Send multipart form data with a `file` field. JPEG, PNG and WebP are supported. The limit is 3 MB per upload and 20 million decoded pixels.

```sh
curl -X POST -F "file=@photo.jpg" http://127.0.0.1:8015/identify
```

Choose one capture mode:

| Input | Query |
| --- | --- |
| Photo including background | No mode flag |
| Already tightly cropped card | `?cropped=true` |
| Camera-guide capture with 12% margin on every side | `?guided=true` |

For live scanning, crop a frame from your preview guide and wait for its response before sending another. Camera permissions, capture, UI feedback and selection belong to the host application. Inference concurrency is bounded; retry a `503` later rather than flooding the service.

Candidate-search responses include `status`, `candidates`, `exact_printing` and `finish_requires_confirmation`. A no-card result may contain only status, empty candidates and duration. Candidates provide a namespaced `id` (`mtg-<UUID>`), raw `scryfall_id`, face index, oracle/illustration IDs, set/number/language, finishes and image URL. Similarity and geometric inliers are diagnostics, not accuracy percentages.

| Status | Suggested handling |
| --- | --- |
| `confident` | Compatible visual evidence and printing OCR established an edition; confirm finish |
| `ambiguous` | Ask the user to select a printing |
| `uncertain` | Ask for another frame or manual confirmation |
| `no_match` | Adjust capture or offer a separate search flow |
| `no_card_detected` | Ask the user to place the card in view |

## Prices

```sh
curl "http://127.0.0.1:8015/cards/6904ea20-e504-47da-95a0-08739fdde260/price?finish=foil"
```

`finish` accepts `nonfoil` (default), `foil` or `etched`. Raw UUIDs and `mtg-` IDs are supported. Responses include printing ID, finish, `currency: "USD"`, `source: "Scryfall"`, nullable `value`, and `checked_at`.

Missing quotes stay `null`; a real zero remains zero. `checked_at` is retrieval time, not the source's quote-publication date. No currency conversion or cross-edition substitution occurs. Query after selection rather than on every camera frame.

## Configuration and authentication

| Variable | Default | Meaning |
| --- | --- | --- |
| `MAGICOU_RECOGNIZER_DATA` | `data` | Data root for the ASGI app |
| `MAGICOU_RECOGNIZER_OCR` | disabled | `1` enables optional OCR |
| `MAGICOU_RECOGNIZER_API_KEY` | unset | Bearer token protecting all endpoints |

CLI `--data` and `serve --ocr` configure the child service. Legacy `MAGIC_RECOGNIZER_*` and `ARCANA_*` variables remain supported, in that order; `MAGICOU_RECOGNIZER_*` names take precedence. `.env.example` is a reference, not an automatically loaded configuration file.

When a key is configured, send `Authorization: Bearer <your-token>`. The CLI requires a key when binding outside localhost. Use HTTPS and your own reverse proxy or platform controls for network-facing services. No provider account/project ID is embedded in the engine.

Errors include `400` for invalid input, `401` for authentication failure, `413` for oversized images, `503` for busy inference, and `502` for an unavailable price provider.

The engine does not archive uploaded photos. Multipart handling can spool temporary files. Reference images and index artifacts are a separate persistent local cache.
