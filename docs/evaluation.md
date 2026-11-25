# Evaluation

## Current evidence

The **2026-11-25** full-gallery report has **115,084 indexed faces**, three independent camera photos, and two negative controls. All three identity checks passed; both controls were rejected.

Fixtures show Scrying Glass, Rush of Adrenaline with a partly hidden title, and Chromatic Sphere at an angle. They are published by [CollectorVision](https://github.com/HanClinto/CollectorVision/tree/main/examples/images). Photos are downloaded only to ignored local data and are not redistributed here. Its recognition models/code are not incorporated.

A correct identity can have a different top printing when artwork is shared. The test compares oracle identity and requires a verified result. It does not claim that every photograph establishes foil finish or exact edition.

**Three photos do not estimate general accuracy.** This check does not validate every set, frame, language, phone, sleeve, glare level or lighting condition.

## Independent-photo check

After building the intended index:

```sh
python -m arcana.physical_tests --data ./data --output ./data/physical-report.json
```

The command exits nonzero on failure. Its report identifies full selected-catalogue snapshots versus evaluation subsets.

## Synthetic smoke test

```sh
python -m arcana.evaluate --data ./data --count 10 --output ./data/synthetic-report.json
```

This applies perspective, blur and JPEG compression to gallery scans. Since images derive from the same references, do not present this as independent-camera accuracy. The archived 100-reference report is historical, not the complete-gallery benchmark.

## Further validation

Useful tests include independent photos from different devices/sets, duplicate-art printings, double/split faces, localized cards, sleeves, reflections, small/off-center subjects and non-card negatives. Separate identity recall, printing accuracy, false positives, first-request latency and warm latency. Record gallery/model versions and conditions.

- [Full-gallery physical report](benchmarks/physical-photos-2026-11-25.json)
- [Historical synthetic report](benchmarks/synthetic-smoke-2026-11-25.json)
