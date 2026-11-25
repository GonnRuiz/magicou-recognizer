"""Generic DINOv2 retrieval for Magic card references.

Both reference and query use the same versioned square-resize preprocessing.
The exported graph and upstream DINOv2 retain their upstream licenses.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
from PIL import Image

REVISION = "c2bb04a51fab207c420665f1946016107bffc701"
SHA256 = "83141175ec78b4ff9a2bb58a4c7c264ba0054d1c2e122e5a8114b79a8d4179ea"
MODEL_URL = f"https://huggingface.co/Xenova/dinov2-small/resolve/{REVISION}/onnx/model.onnx"
PREPROCESS = "rgb-bicubic-square224-imagenet-cls-opencv-phash-v1"


def download_model(root):
    import httpx
    from .scryfall import UA
    target = Path(root) / "models/dinov2-small.onnx"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == SHA256:
        return target
    temporary = target.with_suffix(".part")
    digest = hashlib.sha256()
    with httpx.stream("GET", MODEL_URL, headers={"User-Agent": UA}, follow_redirects=True, timeout=120) as r:
        r.raise_for_status()
        with temporary.open("wb") as f:
            for chunk in r.iter_bytes():
                digest.update(chunk)
                f.write(chunk)
    if digest.hexdigest() != SHA256:
        temporary.unlink()
        raise RuntimeError("Model checksum mismatch")
    temporary.replace(target)
    return target


def normalize(array):
    array = np.asarray(array, dtype=np.float32)
    return array / np.maximum(np.linalg.norm(array, axis=-1, keepdims=True), 1e-8)


class Encoder:
    fingerprint = SHA256 + ":" + PREPROCESS

    def __init__(self, path, threads=2):
        import onnxruntime as ort
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != SHA256:
            raise ValueError("Unrecognized model: rebuild/pin explicitly rather than mixing embeddings")
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])
        self.input = self.session.get_inputs()[0].name

    def embed(self, image):
        image = Image.fromarray(image).resize((224, 224), Image.Resampling.BICUBIC)
        values = np.asarray(image, dtype=np.float32) / 255
        values = (values - np.array([.485, .456, .406], dtype=np.float32)) / np.array(
            [.229, .224, .225], dtype=np.float32)
        output = self.session.run(None, {self.input: values.transpose(2, 0, 1)[None]})[0]
        # Base DINO exports token embeddings, not the flattened token matrix.
        vector = output[0, 0] if output.ndim == 3 else output[0]
        return normalize(vector)


def artwork(image):
    h, w = image.shape[:2]
    # Conventional Magic layout; full-card signal remains available for borderless,
    # split, showcase and textless cards, which need separate benchmark coverage.
    return image[int(h * .13):int(h * .54), int(w * .07):int(w * .93)]


def hashes(image):
    import cv2
    values = []
    for view in (image, artwork(image)):
        gray = cv2.cvtColor(view, cv2.COLOR_RGB2GRAY)
        small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
        coefficients = cv2.dct(small)[:8, :8]
        values.append(np.packbits((coefficients > np.median(coefficients)).ravel()))
    return np.stack(values)


def descriptors(image):
    import cv2
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    keypoints, raw = cv2.SIFT_create(nfeatures=800).detectAndCompute(gray, None)
    if raw is None:
        return np.empty((0, 2), np.float32), np.empty((0, 128), np.float32)
    root = np.sqrt(raw / np.maximum(raw.sum(axis=1, keepdims=True), 1e-8))
    return np.array([point.pt for point in keypoints], np.float32), root.astype(np.float32)


def geometric_match(query, reference):
    """Reject accidental appearance similarity using consistent local geometry."""
    import cv2
    qpoints, qdesc = query
    rpoints, rdesc = reference
    if len(qdesc) < 8 or len(rdesc) < 8:
        return 0
    pairs = cv2.BFMatcher().knnMatch(qdesc, rdesc, k=2)
    good = [pair[0] for pair in pairs if len(pair) == 2 and pair[0].distance < .72 * pair[1].distance]
    if len(good) < 8:
        return 0
    _, mask = cv2.findHomography(np.float32([qpoints[m.queryIdx] for m in good]),
                               np.float32([rpoints[m.trainIdx] for m in good]), cv2.RANSAC, 4)
    if mask is None:
        return 0
    inliers = [match for match, keep in zip(good, mask.ravel()) if keep]
    # Matching a generic Magic border/rules frame alone is not identity evidence.
    art_points = [rpoints[match.trainIdx] for match in inliers
                  if 390*.07 < rpoints[match.trainIdx][0] < 390*.93
                  and 546*.13 < rpoints[match.trainIdx][1] < 546*.54]
    if len(art_points) < 4:
        return 0
    return len(inliers)
