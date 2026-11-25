import json
from io import BytesIO

import cv2
import numpy as np
import pytest
from PIL import Image

from arcana.api import decode
from arcana.index import Index, build
from arcana.model import descriptors, geometric_match
from arcana.recognizer import printing_line
from arcana.scryfall import connect, faces, prices, upsert
from arcana.vision.rectify import rectify

CARD = {
    "id": "6904ea20-e504-47da-95a0-08739fdde260", "name": "Delver of Secrets // Insectile Aberration",
    "oracle_id": "oracle", "set": "inr", "collector_number": "60", "lang": "en", "games": ["paper"],
    "finishes": ["nonfoil", "foil"], "prices": {"usd": "0.00", "usd_foil": None},
    "card_faces": [
        {"name": "Delver of Secrets", "image_uris": {"normal": "https://cards.scryfall.io/front.jpg"}},
        {"name": "Insectile Aberration", "image_uris": {"normal": "https://cards.scryfall.io/back.jpg"}},
    ],
}


def test_double_faces_share_printing_but_have_independent_references():
    result = list(faces(CARD))
    assert len(result) == 2
    assert result[0]["card_id"] == result[1]["card_id"]
    assert result[0]["face_id"] != result[1]["face_id"]
    assert result[1]["name"] == "Insectile Aberration"
    assert not list(faces({**CARD, "games": ["arena"]}))


def test_untrusted_image_and_missing_images_are_not_imported():
    assert not list(faces({**CARD, "card_faces": [{"name": "x", "image_uris": {
        "normal": "https://evil.example/front.jpg"}}]}))


def test_split_card_with_single_image_does_not_duplicate_faces():
    result = list(faces({**CARD, "image_uris": {"normal": "https://cards.scryfall.io/whole.jpg"}}))
    assert len(result) == 1


def test_footer_is_anchored_to_modern_language_and_set_line():
    assert printing_line("0060 U INR · EN NILS HAMM") == ("inr", "60")
    assert printing_line("1/1 deals 3 damage 2026 Wizards") is None
    assert printing_line("00060 INR • ES") == ("inr", "60")


def test_price_uses_exact_uuid_and_finish_and_preserves_missing_and_zero(monkeypatch):
    from arcana import scryfall
    class API:
        def get(self, path):
            assert path == "/cards/" + CARD["id"]
            return CARD

        def close(self):
            pass
    monkeypatch.setattr(scryfall, "Scryfall", API)
    assert prices(CARD["id"], "nonfoil")["value"] == 0
    assert prices(CARD["id"], "foil")["value"] is None
    with pytest.raises(ValueError):
        prices("../secret", "foil")


def test_decoder_rejects_nonimages_and_accepts_camera_jpeg():
    with pytest.raises(ValueError):
        decode(b"not an image")
    buffer = BytesIO()
    Image.new("RGB", (100, 140)).save(buffer, format="JPEG")
    assert decode(buffer.getvalue()).shape == (140, 100, 3)


def test_geometric_verification_handles_perspective_and_rejects_unrelated_image():
    rng = np.random.default_rng(32)
    image = rng.integers(0, 255, (546, 390, 3), dtype=np.uint8)
    image = cv2.GaussianBlur(image, (3, 3), 0)
    corners = np.array([[25, 30], [355, 9], [380, 520], [8, 535]], np.float32)
    original = np.array([[0, 0], [389, 0], [389, 545], [0, 545]], np.float32)
    warped = cv2.warpPerspective(image, cv2.getPerspectiveTransform(original, corners), (390, 546))
    corrected = rectify(warped, corners)
    assert geometric_match(descriptors(corrected), descriptors(image)) >= 20
    assert geometric_match(descriptors(np.zeros_like(image)), descriptors(image)) == 0


class FakeEncoder:
    fingerprint = "test-model-v1"

    def embed(self, image):
        # Deterministic test fixture, never a production fallback.
        return np.array([1, .1, .2], dtype=np.float32)


def test_index_records_real_coverage_survives_failed_update_and_rejects_model_swap(tmp_path):
    with connect(tmp_path) as db:
        upsert(db, CARD)
    (tmp_path / "images").mkdir()
    Image.new("RGB", (390, 546), "red").save(tmp_path / "images" / (CARD["id"] + "_0.jpg"))
    (tmp_path / "images" / (CARD["id"] + "_0.url")).write_text(CARD["card_faces"][0]["image_uris"]["normal"])
    report = build(tmp_path, FakeEncoder(), limit=1)
    assert report["indexed_faces"] == 1 and report["catalog_faces"] == 2
    assert not report["complete"]
    from arcana.export import export
    with pytest.raises(ValueError, match="incomplete"):
        export(tmp_path)
    index = Index(tmp_path, "test-model-v1")
    assert len(index.ids) == 1
    with pytest.raises(ValueError, match="mismatch"):
        Index(tmp_path, "different-model")
    before = (tmp_path / "current").read_text()
    # Corrupt local cache causes an extraction failure, never a successful empty release.
    for file in (tmp_path / "features").glob("*.npz"):
        file.write_bytes(b"invalid")
    with pytest.raises(RuntimeError, match="No references"):
        build(tmp_path, FakeEncoder(), limit=1)
    assert (tmp_path / "current").read_text() == before
    assert json.loads((tmp_path / "indexes" / before / "manifest.json").read_text())["indexed_faces"] == 1
