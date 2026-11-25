"""Export a COMPLETE index, model and metadata; never include reference JPEGs."""
import gzip
import hashlib
import json
import tarfile
from pathlib import Path

from .model import SHA256


def export(root="data", output="data/release", *, allow_partial=False):
    root, output = Path(root), Path(output)
    generation = root / "indexes" / (root / "current").read_text().strip()
    manifest = json.loads((generation / "manifest.json").read_text())
    permitted_partial = allow_partial and manifest.get("partial_snapshot") is True
    if ((not manifest["complete"] and not permitted_partial) or manifest["failed_faces"]
            or manifest.get("metadata", {}).get("bulk_type") not in {"default_cards", "all_cards"}):
        raise ValueError("Refusing to publish an incomplete visual index")
    output.mkdir(parents=True, exist_ok=True)
    packed = output / "bundle.tar.gz"
    files = [(root / "models/dinov2-small.onnx", "models/dinov2-small.onnx")]
    files.append((Path(__file__).parent / "assets/DINOV2_LICENSE.txt", "DINOV2_LICENSE.txt"))
    files += [(generation / name, "indexes/snapshot/" + name)
              for name in ("embeddings.npy", "hashes.npy", "catalog.sqlite", "manifest.json")]
    def normalized(info):
        info.mtime, info.uid, info.gid = 0, 0, 0
        info.uname, info.gname = "", ""
        return info
    with packed.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=5, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as archive:
            for source, name in files:
                archive.add(source, arcname=name, recursive=False, filter=normalized)
    parts = []
    digest = hashlib.sha256()
    with packed.open("rb") as source:
        while chunk := source.read(5_000_000):
            digest.update(chunk)
            name = f"part-{len(parts):03}.bin"
            (output / name).write_bytes(chunk)
            parts.append({"name": name, "size": len(chunk), "sha256": hashlib.sha256(chunk).hexdigest()})
    result = {"schema": 1, "id": digest.hexdigest(), "parts": parts, "size": packed.stat().st_size,
              "complete": manifest["complete"], "partial_snapshot": permitted_partial,
              "catalog_faces": manifest["catalog_faces"],
              "indexed_faces": manifest["indexed_faces"], "model_sha256": SHA256}
    if result["size"] > 450_000_000:
        raise ValueError("Export exceeds the free storage safety budget")
    (output / "manifest.json").write_text(json.dumps(result), encoding="utf-8")
    return result


def unpack_for_bundle(source, target):
    """Convert the transport tar into individually compressed, whitelisted files."""
    target = Path(target)
    allowed = {"DINOV2_LICENSE.txt", "models/dinov2-small.onnx", "indexes/snapshot/embeddings.npy", "indexes/snapshot/hashes.npy",
               "indexes/snapshot/catalog.sqlite", "indexes/snapshot/manifest.json"}
    with tarfile.open(source, "r:gz") as archive:
        names = set()
        for member in archive:
            if member.name not in allowed or not member.isfile() or member.size > 350_000_000:
                raise ValueError("Unexpected bundle member")
            path = target / (member.name + ".gz")
            path.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as data, gzip.open(path, "wb", compresslevel=5) as output:
                import shutil
                shutil.copyfileobj(data, output)
            names.add(member.name)
        if names != allowed:
            raise ValueError("Missing bundle members")
