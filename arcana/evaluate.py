"""Reproducible synthetic smoke benchmark, deliberately not a physical-photo accuracy claim."""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .recognizer import Recognizer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--output", default="docs/evaluation.json")
    args = parser.parse_args()
    recognizer = Recognizer(args.data)
    result = []
    for face_id in recognizer.index.ids[:args.count]:
        path = Path(args.data) / "images" / (face_id.replace(":", "_") + ".jpg")
        image = np.asarray(Image.open(path).convert("RGB").resize((390, 546)))
        # Artificial handheld-like perspective, downsampling, JPEG and blur.
        # References and test images derive from the SAME scan: smoke test only.
        source = np.array([[0, 0], [389, 0], [389, 545], [0, 545]], np.float32)
        target = np.array([[90, 60], [439, 90], [465, 600], [65, 620]], np.float32)
        matrix = cv2.getPerspectiveTransform(source, target)
        photo = cv2.warpPerspective(image, matrix, (540, 700), borderValue=(65, 115, 80))
        photo = cv2.GaussianBlur(photo, (3, 3), .6)
        _, encoded = cv2.imencode(".jpg", cv2.cvtColor(photo, cv2.COLOR_RGB2BGR),
                                  [cv2.IMWRITE_JPEG_QUALITY, 78])
        photo = cv2.cvtColor(cv2.imdecode(encoded, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
        response = recognizer.identify(photo)
        predicted = response["candidates"][0]["scryfall_id"] if response["candidates"] else None
        result.append({"expected_id": face_id.split(":")[0], "predicted_id": predicted,
                       "correct_top1_printing": predicted == face_id.split(":")[0],
                       "status": response["status"], "duration_ms": response["duration_ms"]})
        print(json.dumps(result[-1]), flush=True)
    negatives = [recognizer.identify(np.zeros((700, 540, 3), dtype=np.uint8))]
    durations = [row["duration_ms"] for row in result]
    report = {"benchmark": "synthetic reference-derived smoke test; not independent physical photos",
              "coverage": recognizer.coverage(), "samples": len(result), "results": result,
              "correct_top1": sum(row["correct_top1_printing"] for row in result),
              "latency_ms": {"median": float(np.median(durations)), "p95": float(np.percentile(durations, 95))},
              "blank_negative_rejected": not negatives[0]["candidates"],
              "limitations": ["Small partial gallery", "Reference-derived inputs", "No physical iPhone camera test",
                              "No finish/condition inference", "Default language export; not every language"]}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
