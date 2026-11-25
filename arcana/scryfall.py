"""Scryfall HTTP policy and streaming, resumable bulk ingestion.

Card images/data retain their owners' rights; they are not covered by our MIT license.
"""
from __future__ import annotations

import gzip
import json
import sqlite3
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

UA = "MagicouRecognizer/0.3 (+https://github.com/GonnRuiz/magicou-recognizer)"
_api_lock = threading.Lock()
_last_api_request = 0.0


def now():
    return datetime.now(timezone.utc).isoformat()


class Scryfall:
    """One client per process; API calls are spaced by at least 110 ms."""

    def __init__(self):
        self.client = httpx.Client(headers={"User-Agent": UA, "Accept": "application/json"},
                                   timeout=60, follow_redirects=True)

    def close(self):
        self.client.close()

    def get(self, path):
        global _last_api_request
        with _api_lock:
            time.sleep(max(0, .11 - (time.monotonic() - _last_api_request)))
            _last_api_request = time.monotonic()
            response = self.client.get("https://api.scryfall.com" + path)
        if response.status_code == 429:
            raise RuntimeError("Scryfall rate limit; wait before retrying")
        response.raise_for_status()
        return response.json()

    def download(self, url, target, *, host):
        if urlparse(url).scheme != "https" or urlparse(url).hostname != host:
            raise ValueError("Untrusted asset URL")
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".part")
        with self.client.stream("GET", url) as response:
            response.raise_for_status()
            if urlparse(str(response.url)).hostname != host:
                raise ValueError("Untrusted asset redirect")
            with temporary.open("wb") as output:
                for chunk in response.iter_bytes():
                    output.write(chunk)
        temporary.replace(target)


def connect(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(root / "catalog.sqlite")
    db.row_factory = sqlite3.Row
    db.executescript("""
      create table if not exists faces (
        face_id text primary key, card_id text not null, face_index integer not null,
        oracle_id text, illustration_id text, name text not null, printed_name text,
        set_code text not null, collector_number text not null, lang text not null,
        image_url text not null, finishes text not null, prices text not null, checked_at text not null
      );
      create index if not exists by_oracle on faces(oracle_id);
      create table if not exists metadata (key text primary key, value text not null);
    """)
    return db


def faces(card):
    """Include every paper printing and every independently illustrated card face."""
    if "paper" not in card.get("games", []):
        return
    parts = [card] if card.get("image_uris") else card.get("card_faces", [])
    for index, face in enumerate(parts):
        image = face.get("image_uris", {}).get("normal")
        if not image or urlparse(image).hostname != "cards.scryfall.io":
            continue
        yield {
            "face_id": f"{card['id']}:{index}", "card_id": card["id"], "face_index": index,
            "oracle_id": card.get("oracle_id"), "illustration_id": face.get("illustration_id"),
            "name": face["name"], "printed_name": face.get("printed_name"),
            "set_code": card["set"], "collector_number": card["collector_number"],
            "lang": card.get("lang", "en"), "image_url": image,
            "finishes": json.dumps(card.get("finishes", [])), "prices": json.dumps(card.get("prices", {})),
            "checked_at": now(),
        }


def upsert(db, card):
    count = 0
    for row in faces(card):
        columns = ",".join(row)
        db.execute(f"insert or replace into faces ({columns}) values ({','.join('?' for _ in row)})",
                   tuple(row.values()))
        count += 1
    return count


def sync(root, all_languages=False):
    """Bulk mode covers the selected complete dataset, never just API page one.

    Current Scryfall exports are gzip JSONL. Legacy JSON is supported as well.
    Updating a snapshot is transactional: interruptions leave the prior catalogue intact.
    """
    root = Path(root)
    api = Scryfall()
    kind = "all_cards" if all_languages else "default_cards"
    try:
        descriptor = next(x for x in api.get("/bulk-data")["data"] if x["type"] == kind)
        url = descriptor.get("jsonl_download_uri") or descriptor["download_uri"]
        is_jsonl = ".jsonl" in url
        target = root / "bulk" / (kind + (".jsonl.gz" if is_jsonl else ".json"))
        stamp = target.with_suffix(target.suffix + ".version")
        if not target.exists() or not stamp.exists() or stamp.read_text() != descriptor["updated_at"]:
            api.download(url, target, host="data.scryfall.io")
            stamp.write_text(descriptor["updated_at"])
        db = connect(root)
        try:
            with db:
                db.execute("delete from faces")
                stream = gzip.open(target, "rt", encoding="utf-8") if is_jsonl else target.open(encoding="utf-8")
                with stream:
                    cards = (json.loads(line) for line in stream if line.strip()) if is_jsonl else json.load(stream)
                    count = 0
                    for card in cards:
                        count += upsert(db, card)
                db.executemany("insert or replace into metadata values (?,?)", [
                    ("bulk_type", kind), ("bulk_updated_at", descriptor["updated_at"]),
                    ("synced_at", now()), ("faces", str(count)),
                ])
            return {"faces": count, "bulk_type": kind, "updated_at": descriptor["updated_at"]}
        finally:
            db.close()
    finally:
        api.close()


def prices(card, finish):
    """Refresh the exact Scryfall UUID; never substitute another printing or currency."""
    import uuid
    card = str(uuid.UUID(card.removeprefix("mtg-")))
    key = {"nonfoil": "usd", "foil": "usd_foil", "etched": "usd_etched"}[finish]
    api = Scryfall()
    try:
        result = api.get("/cards/" + card)
        quote = result.get("prices", {}).get(key)
        return {"card_id": card, "finish": finish, "currency": "USD", "source": "Scryfall",
                "value": float(quote) if quote is not None else None, "checked_at": now()}
    finally:
        api.close()
