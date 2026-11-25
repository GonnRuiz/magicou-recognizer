"""Magic-specific multi-signal recognition; similarities are not probabilities."""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from .index import Index
from .model import Encoder, artwork, descriptors, geometric_match, hashes
from .vision.imaging import cap_long_side
from .vision.rectify import rectify_or_whole
from .vision.proposals import card_views


def printing_line(text):
    """Only parse a modern collector line anchored to a set/language suffix."""
    match = re.search(r"\b([A-Z0-9]{3,6})[\s•·.\-\ufffd]+(?:EN|ES|FR|DE|IT|PT|JA|JP|KO|RU|ZHS|ZHT)\b",
                      text.upper())
    if not match:
        return None
    numbers = re.findall(r"\b(\d{1,5}[A-Z]?)(?:\s*/\s*\d+)?\b", text[:match.start()].upper())
    if not numbers:
        return None
    number = numbers[-1]
    return match[1].lower(), str(int(number)) if number.isdigit() else number.lstrip("0")


class FooterOCR:
    """Optional OCR; the visual engine remains usable without this dependency."""

    def __init__(self):
        from rapidocr import RapidOCR
        self.engine = RapidOCR()
        self.lock = threading.Lock()

    def read(self, card):
        import cv2
        h, w = card.shape[:2]
        region = card[int(h * .875):, :int(w * .72)]
        with self.lock:
            output = self.engine(cv2.cvtColor(region, cv2.COLOR_RGB2BGR))
        return " ".join(text for text, confidence in zip(output.txts or [], output.scores or [])
                        if confidence >= .6)


class Recognizer:
    def __init__(self, root="data", *, ocr=None):
        self.root = Path(root)
        self.encoder = Encoder(self.root / "models/dinov2-small.onnx")
        self.index = Index(self.root, self.encoder.fingerprint)
        self.ocr = ocr

    @lru_cache(maxsize=64)
    def reference_descriptors(self, path):
        if path.startswith("https://cards.scryfall.io/"):
            from io import BytesIO
            import httpx
            from .scryfall import UA
            response = httpx.get(path, headers={"User-Agent": UA}, timeout=4)
            response.raise_for_status()
            source = BytesIO(response.content)
        else:
            source = path
        with Image.open(source) as reference:
            ref = np.asarray(reference.convert("RGB").resize((390, 546)))
        return descriptors(ref)

    def score_view(self, ranked, view, db, downloaded):
        query_desc = descriptors(np.asarray(Image.fromarray(view).resize((390, 546))))
        candidates = []
        verified_shortlist = False
        for rank, (face_id, score, visual) in enumerate(ranked):
            row = dict(db.execute("select * from faces where face_id=?", (face_id,)).fetchone())
            path = self.root / "images" / (face_id.replace(":", "_") + ".jpg")
            inliers = None
            if not verified_shortlist and (path.exists() or rank < 4) and visual >= .6:
                reference = str(path) if path.exists() else row["image_url"]
                if not path.exists() and reference not in downloaded:
                    if len(downloaded) >= 8:
                        continue
                    downloaded.add(reference)
                try:
                    inliers = geometric_match(query_desc, self.reference_descriptors(reference))
                except Exception:
                    inliers = None
                if visual >= .8 and (inliers or 0) >= 25:
                    verified_shortlist = True
            candidates.append({"row": row, "similarity": visual, "score": score,
                               "inliers": inliers})
        # Geometry validates the shortlist but does not claim identical-art
        # reprints are distinguished. A lack of local descriptors stays uncertain.
        candidates.sort(key=lambda c: (.8 * c["score"] + .2 * min((c["inliers"] or 0) / 35, 1)),
                        reverse=True)
        return candidates

    def identify(self, image, *, guided=False, cropped=False):
        started = time.perf_counter()
        image = cap_long_side(image, 1200)
        if float(np.std(image)) < 3:
            return {"status": "no_card_detected", "candidates": [], "duration_ms": self._elapsed(started)}
        views = [rectify_or_whole(image, None)] if cropped else card_views(image, guided)
        hypotheses = []
        # Score the ordinary orientation first. Strong visual agreement skips
        # redundant inverted encodings; weaker frames still try 180 degrees.
        for view in views:
            emb = np.stack([self.encoder.embed(view), self.encoder.embed(artwork(view))])
            ranked = self.index.search(emb, hashes(view))
            hypotheses.append((ranked, view))
            # Live captures already follow the on-screen guide. Verify that
            # crop immediately instead of spending seconds trying photo crops.
            # A failed frame is retried as the user aligns the physical card.
            if guided or ranked[0][1] >= .9:
                break
        if hypotheses and max(item[0][0][1] for item in hypotheses) < .75:
            card = max(hypotheses, key=lambda item: item[0][0][1])[1]
            inverted = np.ascontiguousarray(card[::-1, ::-1])
            emb = np.stack([self.encoder.embed(inverted), self.encoder.embed(artwork(inverted))])
            hypotheses.append((self.index.search(emb, hashes(inverted)), inverted))
        ranked, view = max(hypotheses, key=lambda item: item[0][0][1])
        db = sqlite3.connect(self.index.database)
        db.row_factory = sqlite3.Row
        try:
            downloaded = set()
            choices = sorted(hypotheses, key=lambda item: item[0][0][1], reverse=True)
            # Always retain the ordinary central crop as a geometric fallback.
            choices = choices[:5] + choices[-1:]
            selected = None
            for ranked_view, candidate_view in choices:
                scored = self.score_view(ranked_view, candidate_view, db, downloaded)
                if not scored:
                    continue
                lead = scored[0]
                consistent = ((lead["similarity"] >= .70 and (lead["inliers"] or 0) >= 12)
                              or (lead["similarity"] >= .60 and (lead["inliers"] or 0) >= 25))
                if selected is None or consistent:
                    selected = scored, candidate_view, consistent
                if consistent:
                    break
            candidates, view, verified = selected
            best = candidates[0]
            status = "ambiguous" if verified else "uncertain"
            if best["similarity"] < .55 or (best["inliers"] is not None and best["inliers"] < 8):
                status = "no_match"
            exact = False
            if verified and self.ocr:
                printing = printing_line(self.ocr.read(view))
                if printing:
                    rows = db.execute("select * from faces where set_code=? and oracle_id=?",
                                      (printing[0], best["row"]["oracle_id"])).fetchall()
                    found = [dict(row) for row in rows if row["collector_number"].lstrip("0") == printing[1]
                             and row["face_index"] == best["row"]["face_index"]]
                    if len(found) == 1:
                        best = {**best, "row": found[0]}
                        exact, status = True, "confident"
            if status == "no_match":
                output = []
            else:
                output = [self._candidate(best)]
                # Include all printings of the visual family, even when they were
                # outside the retrieval top 16; cap payload, report remaining count.
                family = db.execute("select * from faces where oracle_id=? order by set_code,collector_number",
                                    (best["row"]["oracle_id"],)).fetchall()
                seen = {best["row"]["card_id"]}
                for row in family:
                    if row["card_id"] not in seen and len(output) < 12:
                        output.append(self._candidate({"row": dict(row), "similarity": None, "inliers": None}))
                        seen.add(row["card_id"])
                for candidate in candidates:
                    plausible = (candidate["similarity"] >= best["similarity"] - .07
                                 and (candidate["inliers"] or 0) >= 12)
                    if plausible and candidate["row"]["card_id"] not in seen and len(output) < 12:
                        output.append(self._candidate(candidate))
                        seen.add(candidate["row"]["card_id"])
            return {"status": status, "exact_printing": exact, "finish_requires_confirmation": True,
                    "candidates": output, "coverage": self.coverage(),
                    "duration_ms": self._elapsed(started)}
        finally:
            db.close()

    @staticmethod
    def _elapsed(started):
        return round((time.perf_counter() - started) * 1000)

    @staticmethod
    def _candidate(candidate):
        row = candidate["row"]
        return {"id": "mtg-" + row["card_id"], "scryfall_id": row["card_id"],
                "oracle_id": row["oracle_id"],
                "illustration_id": row["illustration_id"],
                "face_index": row["face_index"], "name": row["name"], "set": row["set_code"],
                "number": row["collector_number"], "lang": row["lang"], "image_url": row["image_url"],
                "finishes": json.loads(row["finishes"]), "similarity": candidate["similarity"],
                "geometric_inliers": candidate["inliers"]}

    def coverage(self):
        return {key: self.index.manifest[key] for key in
                ("catalog_faces", "indexed_faces", "complete", "created_at")}
