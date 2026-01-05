# Quality Gateway (torrent metadata analyzer)

A small, self-hosted, multi-user web app to **analyze .torrent files and release names**
against your moderation rules (naming policy, banned tokens, minimum resolution token, etc.).
It **does not** download content and only inspects metadata and filenames.

## Features
- Multi-user login (admin can create users in the UI)
- Upload `.torrent` + optional pasted title/description
- Runs checks:
  - dot-style naming (no spaces/parentheses)
  - must end with `-GROUP`
  - Movie: `.YEAR.` required
  - TV: `SxxEyy` or `Sxx` season-pack
  - banned tokens (TS/SCREEN etc.)
  - minimum resolution token (default: 760p; rejects 720p)
  - optional porn keyword block
- GuessIt parsing of title + torrent "info name" and file names
- JSON API for listing and retrieving analyses
- Verdict states: `pass`, `warn`, `fail` (reasons only shown on `fail`)

## Quick start (local)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export QG_SECRET_KEY="change-me"
export QG_ADMIN_USER="admin"
export QG_ADMIN_PASS="change-me-now"
uvicorn app.main:app --reload --port 8088
```

Open: http://localhost:8088

## Docker (optional)
A basic Dockerfile and docker-compose are included.
```bash
docker compose up --build
```

## Config
Environment variables:
- `QG_SECRET_KEY` (required)
- `QG_ADMIN_USER`, `QG_ADMIN_PASS` (used to create the first admin **if no users exist yet**)
- `QG_DB_PATH` (default: `./data/qg.sqlite`)
- `QG_MIN_RES_P` (default: `760`)
- `QG_ENABLE_PORN_BLOCK` (default: `true`)
- `QG_REASON_NAMING` (default: `Naming wrong - check you naming`)
- `QG_REASON_PORN` (default: `No Porn here`)
- `QG_GUESSIT_REST_URL` (optional): If set, GuessIt parsing will be done via REST.
  Otherwise it uses the local `guessit` Python package.

## API
- `POST /api/analyses` (multipart): `category`, optional `title`, optional `description`, optional `torrent_file`
- `GET /api/analyses`
- `GET /api/analyses/{id}`

Auth: JWT in httpOnly cookie from the web login.
