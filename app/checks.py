import re
from dataclasses import dataclass
from typing import Any

# Tunables (kept here so policy is easy to edit)
BANNED_QUALITY_TOKENS = [
    "TS", "SCREEN",
    "TELESYNC", "CAM", "HDCAM", "TC", "TELECINE", "SCREENER", "DVDSCR", "SCR",
]

PORN_TOKENS = [
    "XXX", "PORN", "HENTAI", "ONLYFANS",
    "BRAZZERS", "BANGBROS", "VIXEN", "TUSHY", "REALITYKINGS", "NAUGHTYAMERICA",
    "DIGITALPLAYGROUND", "TEAMSKEET",
]

MOVIE_REGEX = re.compile(
    r"^(?!.*[()\s])"                                  # no spaces/parentheses
    r"(?P<title>[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)*)\."    # dot title
    r"(?P<year>(?:19|20)\d{2})\."                      # .YEAR.
    r"(?P<res>\d{3,4})p\."                             # .1080p.
    r"(?:(?P<service>[A-Z0-9]{2,6})\.)?"               # optional NF/ATVP/AMZN...
    r"(?P<source>WEB-DL|WEBRip|WEB|BluRay|BDRip|REMUX|HDTV)\."
    r".+-"                                             # rest
    r"(?P<group>[A-Za-z0-9]{2,})$",
    re.IGNORECASE,
)

TV_EP_REGEX = re.compile(
    r"^(?!.*[()\s])"
    r"(?P<show>[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)*)\."
    r"S(?P<season>\d{2})E(?P<episode>\d{2})\."
    r"(?P<res>\d{3,4})p\."
    r"(?:(?P<service>[A-Z0-9]{2,6})\.)?"
    r"(?P<source>WEB-DL|WEBRip|WEB|BluRay|BDRip|REMUX|HDTV)\."
    r".+-"
    r"(?P<group>[A-Za-z0-9]{2,})$",
    re.IGNORECASE,
)

TV_SEASON_REGEX = re.compile(
    r"^(?!.*[()\s])"
    r"(?P<show>[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)*)\."
    r"S(?P<season>\d{2})\."
    r"(?P<res>\d{3,4})p\."
    r"(?:(?P<service>[A-Z0-9]{2,6})\.)?"
    r"(?P<source>WEB-DL|WEBRip|WEB|BluRay|BDRip|REMUX|HDTV)\."
    r".+-"
    r"(?P<group>[A-Za-z0-9]{2,})$",
    re.IGNORECASE,
)


RES_FALLBACK = re.compile(r"(\d{3,4})p", re.IGNORECASE)
YEAR_FALLBACK = re.compile(r"(?:19|20)\d{2}")

VIDEO_EXTS = (".mkv", ".mp4", ".avi", ".m2ts", ".ts", ".mov", ".wmv")

def _contains_any_token_ci(text: str, tokens: list[str]) -> str | None:
    t = text.upper()
    for tok in tokens:
        if tok in t:
            return tok
    return None

def _has_spaces_or_parens(text: str) -> bool:
    return bool(re.search(r"\s|\(|\)", text))

def _has_group_suffix(text: str) -> bool:
    return bool(re.search(r"-[A-Za-z0-9]{2,}$", text))

def _best_resolution_token(text: str) -> int | None:
    # Prefer dotted "xxxp." patterns are already enforced by regex, but fallback for warnings
    m = RES_FALLBACK.search(text)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None

@dataclass
class CheckResult:
    ok: bool
    code: str
    message: str
    meta: dict[str, Any] | None = None

def analyze_title(category: str, title: str, min_res_p: int, enable_porn_block: bool) -> dict[str, Any]:
    checks: list[CheckResult] = []

    if enable_porn_block:
        porn_hit = _contains_any_token_ci(title, PORN_TOKENS)
        checks.append(CheckResult(
            ok=(porn_hit is None),
            code="porn_block",
            message="No porn keywords detected" if porn_hit is None else f"Porn keyword detected: {porn_hit}",
            meta={"hit": porn_hit} if porn_hit else None
        ))
        if porn_hit is not None:
            return {"verdict": "fail", "checks": [c.__dict__ for c in checks], "reason_key": "porn"}

    checks.append(CheckResult(
        ok=not _has_spaces_or_parens(title),
        code="dot_style",
        message="No spaces or parentheses" if not _has_spaces_or_parens(title) else "Contains spaces/parentheses (not scene-dot style)"
    ))

    banned_hit = _contains_any_token_ci(title, BANNED_QUALITY_TOKENS)
    checks.append(CheckResult(
        ok=(banned_hit is None),
        code="banned_quality",
        message="No banned quality tokens" if banned_hit is None else f"Banned token detected: {banned_hit}",
        meta={"hit": banned_hit} if banned_hit else None
    ))

    checks.append(CheckResult(
        ok=_has_group_suffix(title),
        code="group_suffix",
        message="Ends with -GROUP" if _has_group_suffix(title) else "Missing -GROUP suffix"
    ))

    # Category pattern
    if category == "Movie":
        m = MOVIE_REGEX.match(title)
        checks.append(CheckResult(
            ok=bool(m),
            code="pattern_movie",
            message="Matches Movie pattern" if m else "Does not match Movie pattern (needs .YEAR., .RES., source, -GROUP)"
        ))
        res = None
        if m:
            # capture group (both are res)
            try:
                res = int(m.group(1))
            except Exception:
                res = _best_resolution_token(title)
        else:
            res = _best_resolution_token(title)

        if res is not None:
            checks.append(CheckResult(
                ok=(res >= min_res_p),
                code="min_resolution",
                message=f"Resolution token {res}p >= {min_res_p}p" if res >= min_res_p else f"Resolution token {res}p is below {min_res_p}p",
                meta={"res_p": res, "min_res_p": min_res_p}
            ))
        else:
            checks.append(CheckResult(
                ok=False,
                code="min_resolution",
                message="No resolution token found (e.g. 1080p)",
            ))

    elif category == "TV":
        m1 = TV_EP_REGEX.match(title)
        m2 = TV_SEASON_REGEX.match(title)
        checks.append(CheckResult(
            ok=bool(m1 or m2),
            code="pattern_tv",
            message="Matches TV Episode/Season pattern" if (m1 or m2) else "Does not match TV patterns (needs SxxEyy or Sxx, res, source, -GROUP)"
        ))
        m = m1 or m2
        res = None
        if m:
            try:
                res = int(m.group(1))
            except Exception:
                res = _best_resolution_token(title)
        else:
            res = _best_resolution_token(title)

        if res is not None:
            checks.append(CheckResult(
                ok=(res >= min_res_p),
                code="min_resolution",
                message=f"Resolution token {res}p >= {min_res_p}p" if res >= min_res_p else f"Resolution token {res}p is below {min_res_p}p",
                meta={"res_p": res, "min_res_p": min_res_p}
            ))
        else:
            checks.append(CheckResult(
                ok=False,
                code="min_resolution",
                message="No resolution token found (e.g. 1080p)",
            ))
    else:
        checks.append(CheckResult(
            ok=False,
            code="category",
            message=f"Unknown category: {category}"
        ))

    verdict = "pass" if all(c.ok for c in checks) else "fail"
    return {"verdict": verdict, "checks": [c.__dict__ for c in checks], "reason_key": "naming" if verdict == "fail" else None}

def analyze_files(file_paths: list[str]) -> dict[str, Any]:
    checks: list[CheckResult] = []
    total = len(file_paths)

    video_files = [p for p in file_paths if p.lower().endswith(VIDEO_EXTS)]
    checks.append(CheckResult(
        ok=(len(video_files) > 0),
        code="has_video",
        message=f"Video files detected: {len(video_files)} / {total}" if len(video_files) else "No common video extensions found in torrent file list",
        meta={"video_count": len(video_files), "total": total}
    ))

    # Warn-style checks could be added later (e.g. sample files, subtitles-only, etc.)
    verdict = "pass" if all(c.ok for c in checks) else "warn"
    return {"verdict": verdict, "checks": [c.__dict__ for c in checks]}
