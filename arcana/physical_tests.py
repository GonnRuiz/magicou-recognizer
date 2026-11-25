"""Evaluate independent published camera photos, not crops of gallery references.

Photos are downloaded only into ignored local data. Their source is attributed
in the report; no third-party photos/model/code are redistributed in this repo.
"""
import argparse
import json
import sqlite3
from pathlib import Path

import httpx
import numpy as np

from .recognizer import Recognizer
from .scryfall import UA
from .vision.imaging import load_image

CASES = ["7286819f-6c57-4503-898c-528786ad86e9_sample.jpg",
         "d0def54b-9f0a-4ab1-9df9-25506a06350c_hidden_name.jpg",
         "f31a6dfd-93d2-49c8-a357-9a707b9c42bd_deep_skew.jpg"]
SOURCE = "https://github.com/HanClinto/CollectorVision/tree/main/examples/images"


def evaluate(root, photo_dir, output):
    root, photo_dir = Path(root), Path(photo_dir)
    photo_dir.mkdir(parents=True, exist_ok=True)
    recognizer = Recognizer(root)
    database = sqlite3.connect(recognizer.index.database)
    results = []
    try:
        for filename in CASES:
            path = photo_dir / filename
            if not path.exists():
                response = httpx.get("https://raw.githubusercontent.com/HanClinto/CollectorVision/main/examples/images/"
                                     + filename, headers={"User-Agent": UA}, timeout=30)
                response.raise_for_status()
                path.write_bytes(response.content)
            expected = database.execute("select oracle_id from faces where card_id=?", (filename[:36],)).fetchone()
            if expected is None:
                raise ValueError("Test printing missing from catalogue")
            result = recognizer.identify(load_image(path))
            winner = result["candidates"][0] if result["candidates"] else None
            passed = bool(winner and winner["oracle_id"] == expected[0]
                          and result["status"] in {"ambiguous", "confident"})
            results.append({"file": filename, "passed": passed, "status": result["status"],
                            "winner": winner, "duration_ms": result["duration_ms"]})
            print(json.dumps(results[-1]), flush=True)
        rng = np.random.default_rng(83)
        negatives = [np.zeros((700, 540, 3), np.uint8), rng.integers(0, 255, (700, 540, 3), dtype=np.uint8)]
        rejected = all(not recognizer.identify(image)["candidates"] for image in negatives)
        report = {"source": SOURCE, "coverage": recognizer.coverage(), "photos": results,
                  "full_catalog_snapshot": recognizer.index.manifest.get("metadata", {}).get("bulk_type")
                      in {"default_cards", "all_cards"} and len(recognizer.index.ids) > 10000,
                  "negative_controls_rejected": rejected,
                  "passed": all(row["passed"] for row in results) and rejected,
                  "limitations": ["Only three independent photos", "Not a physical iPhone camera permission test",
                                  "Exact edition/finish still needs confirmation"]}
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report
    finally:
        database.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data")
    parser.add_argument("--photos", default="data/physical-tests")
    parser.add_argument("--output", default="data/physical-report.json")
    args = parser.parse_args()
    if not evaluate(args.data, args.photos, args.output)["passed"]:
        raise SystemExit("Camera-photo regression gate FAILED; do not deploy")
