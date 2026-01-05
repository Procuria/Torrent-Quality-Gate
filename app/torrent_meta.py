from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import hashlib
import io

try:
    from torf import Torrent
except Exception:
    Torrent = None


@dataclass
class TorrentMeta:
    info_name: str | None
    info_hash: str | None
    announce: list[str]
    files: list[dict[str, Any]]  # [{"path": "...", "size": 123}, ...]


def read_torrent_bytes(data: bytes) -> TorrentMeta:
    """
    Parse a .torrent file (bytes) and extract metadata only.
    We do NOT download any payload content.
    """
    if Torrent is None:
        return TorrentMeta(info_name=None, info_hash=None, announce=[], files=[])

    # torf expects a binary stream; BytesIO is the safest cross-version option
    t = Torrent.read_stream(io.BytesIO(data))

    info_name = getattr(t, "name", None)

    # infohash: torf exposes different attributes depending on version
    info_hash = None
    if hasattr(t, "infohash_hex"):
        try:
            info_hash = str(t.infohash_hex)
        except Exception:
            info_hash = None
    elif hasattr(t, "infohash"):
        try:
            ih = t.infohash
            if isinstance(ih, (bytes, bytearray)):
                info_hash = ih.hex()
            else:
                info_hash = str(ih)
        except Exception:
            info_hash = None

    # Announce / announce-list
    announce: list[str] = []
    try:
        a = getattr(t, "announce", None)
        if a:
            announce.append(str(a))
    except Exception:
        pass

    try:
        al = getattr(t, "announce_list", None)
        if al:
            # announce_list can be nested list
            for item in al:
                if isinstance(item, (list, tuple)):
                    for sub in item:
                        announce.append(str(sub))
                else:
                    announce.append(str(item))
    except Exception:
        pass

    # Files (path + size if available)
    files: list[dict[str, Any]] = []
    if getattr(t, "files", None):
        for f in t.files:
            try:
                path = str(f[0])
                size = int(f[1]) if len(f) > 1 else None
                files.append({"path": path, "size": size})
            except Exception:
                files.append({"path": str(f), "size": None})

    return TorrentMeta(info_name=info_name, info_hash=info_hash, announce=announce, files=files)
