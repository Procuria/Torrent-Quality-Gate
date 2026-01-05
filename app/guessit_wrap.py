from __future__ import annotations
from typing import Any
import json
import urllib.request
import urllib.parse

from .settings import settings

def guessit_local(text: str) -> dict[str, Any]:
    from guessit import guessit
    try:
        return guessit(text)
    except Exception as e:
        return {"_error": str(e)}

def guessit_rest(text: str) -> dict[str, Any]:
    # expects guessit-rest style: ?filename=
    url = settings.guessit_rest_url.rstrip("/") + "/?filename=" + urllib.parse.quote(text)
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            raw = r.read().decode("utf-8", errors="replace")
            return json.loads(raw)
    except Exception as e:
        return {"_error": str(e), "_url": url}

def guess(text: str) -> dict[str, Any]:
    if not text:
        return {}
    if settings.guessit_rest_url:
        return guessit_rest(text)
    return guessit_local(text)
