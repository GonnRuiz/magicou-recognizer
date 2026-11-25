"""Command-line setup, incremental indexing, recognition and API server."""
import argparse
import json
import logging
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(prog="magicou-recognizer", description="Self-hosted Magic card recognition")
    parser.add_argument("--version", action="version", version="%(prog)s 0.3.0")
    parser.add_argument("--data", default="data")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("model", help="Download and SHA-256 verify the pinned generic DINOv2 ONNX model")
    sync = commands.add_parser("sync", help="Import all paper printings from Scryfall's bulk export")
    sync.add_argument("--all-languages", action="store_true")
    build = commands.add_parser("build", help="Incrementally build visual references")
    build.add_argument("--limit", type=int, help="Explicit partial index for evaluation; omitted indexes all faces")
    build.add_argument("--workers", type=int, default=1, choices=range(1, 9))
    identify = commands.add_parser("identify")
    identify.add_argument("image")
    identify.add_argument("--cropped", action="store_true")
    identify.add_argument("--guided", action="store_true")
    identify.add_argument("--ocr", action="store_true")
    serve = commands.add_parser("serve")
    serve.add_argument("--port", default=8015, type=int)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--ocr", action="store_true")
    commands.add_parser("coverage")
    export = commands.add_parser("export", help="Export a portable checksummed index without reference JPEGs")
    export.add_argument("--output", default="data/release")
    export.add_argument("--allow-partial", action="store_true", help="Explicitly label and export a partial snapshot")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.command == "model":
        from .model import download_model
        print(download_model(args.data))
    elif args.command == "sync":
        from .scryfall import sync
        print(json.dumps(sync(args.data, args.all_languages), indent=2))
    elif args.command == "build":
        from .index import build
        from .model import Encoder
        if args.limit is not None and args.limit < 1:
            parser.error("--limit must be positive")
        encoder = Encoder(Path(args.data) / "models/dinov2-small.onnx", threads=1 if args.workers > 1 else 2)
        print(json.dumps(build(args.data, encoder, args.limit, args.workers), indent=2))
    elif args.command == "identify":
        from .recognizer import FooterOCR, Recognizer
        from .vision.imaging import load_image
        recognizer = Recognizer(args.data, ocr=FooterOCR() if args.ocr else None)
        print(json.dumps(recognizer.identify(load_image(args.image), cropped=args.cropped,
                                           guided=args.guided), indent=2))
    elif args.command == "coverage":
        root = Path(args.data)
        manifest = json.loads((root / "indexes" / (root / "current").read_text().strip()
                               / "manifest.json").read_text())
        manifest.pop("ids")
        print(json.dumps(manifest, indent=2))
    elif args.command == "export":
        from .export import export
        print(json.dumps(export(args.data, args.output, allow_partial=args.allow_partial), indent=2))
    elif args.command == "serve":
        import os
        import uvicorn
        from .config import setting
        os.environ["MAGICOU_RECOGNIZER_DATA"] = str(Path(args.data).resolve())
        os.environ["MAGICOU_RECOGNIZER_OCR"] = "1" if args.ocr else "0"
        if args.host not in {"127.0.0.1", "localhost"} and not setting("API_KEY"):
            parser.error("Set MAGICOU_RECOGNIZER_API_KEY before exposing the service outside localhost")
        uvicorn.run("arcana.api:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
