# Torrent-Quality-Gate (TQG) — Release Notes

## Overview
This release is a **first usable public draft** of Torrent-Quality-Gate (TQG): a lightweight moderation pre-check service with a modern web UI and a JSON API.  
Goal: reduce manual triage time by turning common “does this look valid?” checks into a clear **PASS / WARN / FAIL** report.

> Note: This is still an early release. Expect sharp edges and please report false positives / missing rules.

---

## Key Features

### Web UI (Staff-friendly)
- Dark UI (teal/blue accents) with a clear result report
- “Explain failures” summary (shows which checks failed and why)
- “Copy moderation note” button to quickly paste a structured note into tracker moderation actions
- Multi-user support with admin-managed users

### API (Automation-ready)
- Create analyses and fetch results via JSON API
- Results include verdict, reason string (when applicable), and per-check breakdown

### Metadata extraction
- Extracts metadata from uploaded `.torrent` files using **torrentcheck**:
  - info name
  - file list (and sizes if present)
  - info hash
  - announce list (if present)

### Title parsing & debugging
- Uses **GuessIt** to parse the effective title and help understand:
  - year, resolution, source, codecs, group, etc.

---

## Implemented Checkers (Current Set)

### Title checks
- **Dot-style naming** (no spaces / parentheses)
- **Must end with `-GROUP`**
- **Movie pattern** validation (Title.Year.Res.Source-Group)
- **TV pattern** validation (Show.SxxEyy…-Group and Show.Sxx…-Group)
- **Banned quality tokens** (TS/SCREEN/CAM/etc)  
  - Segment-based matching to avoid false positives (e.g. does **not** flag `DTS`)
- **No porn** keyword blocklist
- **Minimum resolution** (rejects below configured threshold, default 760p)

### Torrent/file checks
- Video file presence
- Suspicious junk filetypes (e.g. `.exe`, `.bat`, `.lnk`, `.url`, etc.)
- Sample detection
- Large file-count warnings (pack/collection indicator)
- “Tiny largest video” heuristic (when file sizes exist)

---

## Configuration
All important parameters are configurable via environment variables (no code edits needed), including:
- secret key / admin bootstrap user + password
- minimum resolution threshold
- porn block enable/disable
- reason strings (and other policy knobs)

---

## Known Limitations / Notes
- Early release: ruleset will evolve based on feedback.
- Some torrents don’t provide file sizes — size-based heuristics may be skipped.
- Naming standards vary between trackers; adapt config/rules as needed.

---

## Feedback Wanted
Please report:
- false positives (valid uploads rejected)
- false negatives (bad uploads passing)
- missing tokens/patterns relevant for your tracker
- UI/UX friction points for staff moderation flow
