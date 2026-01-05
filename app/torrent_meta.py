from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import json
import hashlib

try:
    from torf import Torrent
except Exception:
    Torrent = None

@dataclass
class TorrentMeta:
    info_name: str | None
    info_hash: str | None
    announce: list[str]
    files: list[str]

def read_torrent_bytes(data: bytes) -> TorrentMeta:
    if Torrent is None:
        # Minimal fallback: we can't parse without torf
        return TorrentMeta(info_name=None, info_hash=None, announce=[], files=[])

    t = Torrent.read_stream(data)
    # torf gives values as native types
    info_name = getattr(t, "name", None)
    # infohash: torf exposes t.infohash (bytes) or t.infohash_hex depending on version
    info_hash = None
    if hasattr(t, "infohash"):
        ih = t.infohash
        if isinstance(ih, (bytes, bytearray)):
            info_hash = ih.hex()
        else:
            info_hash = str(ih)
    elif hasattr(t, "infohash_hex"):
        info_hash = str(t.infohash_hex)

    announce = []
    if getattr(t, "trackers", None):
        # trackers can be list-of-lists or flat depending on torf version
        tr = t.trackers
        if isinstance(tr, list):
            for item in tr:
                if isinstance(item, list):
                    announce.extend([str(x) for x in item])
                else:
                    announce.append(str(item))

    files = []
    if getattr(t, "files", None):
        # t.files is list of (path, size) in newer versions
        for f in t.files:
            try:
                path = f[0]
                files.append(str(path))
            except Exception:
                # fallback
                files.append(str(f))

    return TorrentMeta(info_name=info_name, info_hash=info_hash, announce=announce, files=files)
