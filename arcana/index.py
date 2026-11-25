"""Incremental visual index with atomic generation publishing and explicit coverage."""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
import uuid
import time
import threading
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path

import numpy as np
from PIL import Image

from .model import artwork, hashes, normalize
from .scryfall import Scryfall, connect, now

logger = logging.getLogger(__name__)
_download_lock = threading.Lock()
_last_download = 0.0


def feature_key(row, fingerprint):
    return hashlib.sha256((row["face_id"] + row["image_url"] + fingerprint).encode()).hexdigest()


def build(root, encoder, limit=None, workers=1):
    """Resume cached feature extraction; --limit caps THIS snapshot's total rows.

    Failed downloads are recorded, never counted as indexed. Daily catalogue changes
    reuse compatible vectors. A nonblocking process lock prevents simultaneous builders.
    """
    root = Path(root)
    lock = root / "build.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    # OS-backed file lock is released even if the process crashes.
    with lock.open("a+b") as handle:
        handle.seek(0)
        if handle.read(1) == b"":
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        import os
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _build(root, encoder, limit, workers)


def extract(root, row, encoder, api):
    global _last_download
    key = feature_key(row, encoder.fingerprint)
    cached = root / "features" / (key + ".npz")
    cached.parent.mkdir(parents=True, exist_ok=True)
    if cached.exists():
        with np.load(cached, allow_pickle=False) as data:
            return data["emb"], data["hashes"]
    image_path = root / "images" / (row["face_id"].replace(":", "_") + ".jpg")
    version = image_path.with_suffix(".url")
    if (not image_path.exists() or not version.exists()
            or version.read_text(encoding="utf-8") != row["image_url"]):
        with _download_lock:
            time.sleep(max(0, .11 - (time.monotonic() - _last_download)))
            _last_download = time.monotonic()
        api.download(row["image_url"], image_path, host="cards.scryfall.io")
        version.write_text(row["image_url"], encoding="utf-8")
    with Image.open(image_path) as source:
        image = np.asarray(source.convert("RGB").resize((390, 546)))
    emb = np.stack([encoder.embed(image), encoder.embed(artwork(image))])
    hs = hashes(image)
    part = cached.with_suffix(".part")
    with part.open("wb") as output:
        np.savez_compressed(output, emb=emb.astype(np.float16), hashes=hs)
    part.replace(cached)
    return emb, hs


def extracted_rows(rows, root, encoder, api, workers):
    """Bound memory and network concurrency, retaining cached work on interruption."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {}
        rows = iter(rows)
        exhausted = False
        while pending or not exhausted:
            while not exhausted and len(pending) < workers * 2:
                row = next(rows, None)
                if row is None:
                    exhausted = True
                    break
                if shutil.disk_usage(root).free < 3_000_000_000:
                    raise RuntimeError("Less than 3 GB free disk; stopped safely, cached features retained")
                row = dict(row)
                pending[pool.submit(extract, root, row, encoder, api)] = row
            if not pending:
                break
            completed, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in completed:
                row = pending.pop(future)
                yield row, future


def _build(root, encoder, limit, workers):
    db = connect(root)
    api = Scryfall()
    generation = root / "indexes" / uuid.uuid4().hex
    generation.mkdir(parents=True)
    failures, ids = [], []
    embeddings, phashes = None, None
    try:
        total = db.execute("select count(*) from faces").fetchone()[0]
        selected = min(total, limit) if limit is not None else total
        if selected < 1:
            raise ValueError("Empty catalogue: run arcana sync first")
        phashes = np.lib.format.open_memmap(generation / "hashes.npy", mode="w+", dtype="uint8",
                                           shape=(selected, 2, 8))
        query = "select * from faces order by card_id,face_index limit ?"
        processed = 0
        started = time.monotonic()
        for row, future in extracted_rows(db.execute(query, (selected,)), root, encoder, api, workers):
            try:
                emb, hs = future.result()
                if embeddings is None:
                    embeddings = np.lib.format.open_memmap(generation / "embeddings.npy", mode="w+",
                                      dtype="float16", shape=(selected, 2, emb.shape[-1]))
                if emb.shape != embeddings.shape[1:]:
                    raise ValueError("Incompatible feature dimensions")
                embeddings[len(ids)] = emb
                phashes[len(ids)] = hs
                ids.append(row["face_id"])
                if len(ids) % 100 == 0:
                    logger.info("Indexed %s/%s faces", len(ids), selected)
            except Exception as error:
                failures.append({"face_id": row["face_id"], "error": str(error)[:250]})
                logger.warning("Skipped %s: %s", row["face_id"], error)
            processed += 1
            if processed % 100 == 0:
                progress = {"processed": processed, "selected": selected, "indexed": len(ids),
                            "failed": len(failures), "elapsed_seconds": round(time.monotonic() - started),
                            "complete": False}
                progress_part = root / "progress.part"
                progress_part.write_text(json.dumps(progress))
                progress_part.replace(root / "progress.json")
        if embeddings is None or not ids:
            raise RuntimeError("No references indexed; previous snapshot retained")
        embeddings.flush()
        phashes.flush()
        embeddings._mmap.close()
        phashes._mmap.close()
        embeddings, phashes = None, None
        manifest = {"schema": 1, "model": encoder.fingerprint, "created_at": now(),
                    "catalog_faces": total, "selected_faces": selected, "indexed_faces": len(ids),
                    "complete": len(ids) == total, "failed_faces": failures,
                    "metadata": dict(db.execute("select key,value from metadata")), "ids": ids}
        (generation / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        # Copy the exact metadata generation: later syncs cannot mismatch loaded vectors.
        snapshot = connect(generation)
        try:
            db.backup(snapshot)
        finally:
            snapshot.close()
        pointer = root / "current.part"
        pointer.write_text(generation.name)
        pointer.replace(root / "current")
        return {key: value for key, value in manifest.items() if key != "ids"}
    except Exception:
        for array in (embeddings, phashes):
            if array is not None:
                array._mmap.close()
        if not generation.resolve().is_relative_to((root / "indexes").resolve()):
            raise RuntimeError("Refusing to clean a directory outside the index workspace")
        shutil.rmtree(generation)
        raise
    finally:
        api.close()
        db.close()


class Index:
    def __init__(self, root, fingerprint):
        root = Path(root)
        generation = root / "indexes" / (root / "current").read_text().strip()
        self.manifest = json.loads((generation / "manifest.json").read_text(encoding="utf-8"))
        if self.manifest["model"] != fingerprint:
            raise ValueError("Index/model mismatch; rebuild references")
        self.ids = self.manifest["ids"]
        n = len(self.ids)
        self.emb = normalize(np.load(generation / "embeddings.npy", allow_pickle=False)[:n])
        self.hashes = np.load(generation / "hashes.npy", allow_pickle=False)[:n]
        self.database = generation / "catalog.sqlite"
        self.root = root

    def search(self, emb, hs, k=16):
        scores = np.einsum("nvd,vd->nv", self.emb, emb)
        similarity = .65 * scores[:, 0] + .35 * scores[:, 1]
        xor = np.bitwise_xor(self.hashes, hs)
        distance = np.unpackbits(xor, axis=-1).sum(axis=-1)
        hash_score = 1 - (.65 * distance[:, 0] + .35 * distance[:, 1]) / 64
        combined = .85 * similarity + .15 * hash_score
        order = np.argsort(combined)[::-1][:k]
        return [(self.ids[i], float(combined[i]), float(similarity[i])) for i in order]
