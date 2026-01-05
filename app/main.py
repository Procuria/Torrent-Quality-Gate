from fastapi import FastAPI, Request, Form, UploadFile, File, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from datetime import datetime
import json

from .db import engine
from .models import User, Analysis
from .auth import get_db, verify_password, hash_password, create_token, set_auth_cookie, clear_auth_cookie, get_current_user, require_admin
from .settings import settings
from .torrent_meta import read_torrent_bytes
from .checks import analyze_title, analyze_files
from .guessit_wrap import guess

app = FastAPI(title="Quality Gateway")
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

def ensure_schema_and_admin(db: Session):
    from .db import Base
    Base.metadata.create_all(bind=engine)

    # If no users exist, create initial admin from env vars (if provided)
    if db.query(User).count() == 0:
        if not (settings.secret_key and getattr(settings, "secret_key", None)):
            # Settings already enforces secret_key, so this is mainly conceptual
            pass
        admin_user = getattr(settings, "admin_user", None)
        admin_pass = getattr(settings, "admin_pass", None)

        # pydantic-settings won't load unknown fields, so read raw env:
        import os
        admin_user = os.environ.get("QG_ADMIN_USER")
        admin_pass = os.environ.get("QG_ADMIN_PASS")
        if admin_user and admin_pass:
            u = User(username=admin_user, password_hash=hash_password(admin_pass), is_admin=True)
            db.add(u)
            db.commit()

@app.on_event("startup")
def _startup():
    from .db import SessionLocal
    db = SessionLocal()
    try:
        ensure_schema_and_admin(db)
    finally:
        db.close()

def _analysis_to_dict(a: Analysis) -> dict:
    return {
        "id": a.id,
        "created_by_username": (a.created_by_user.username if getattr(a, "created_by_user", None) else None),
        "created_at": a.created_at.isoformat() + "Z",
        "created_by": a.created_by,
        "category": a.category,
        "input_title": a.input_title,
        "input_description": a.input_description,
        "torrent_info_name": a.torrent_info_name,
        "info_hash": a.info_hash,
        "announce": json.loads(a.announce) if a.announce else [],
        "files": json.loads(a.files) if a.files else [],
        "results": json.loads(a.results),
    }

def _pick_reason_from_checks(title_res: dict) -> tuple[str | None, str | None]:
    """
    Returns (reason_string, reason_code) for moderation.
    reason_string is a short staff-facing string; reason_code helps debugging.
    """
    checks = title_res.get("checks") or []
    failed = [c for c in checks if not c.get("ok")]

    if not failed:
        return (None, None)

    # Prefer porn_block if it failed
    porn = next((c for c in failed if c.get("code") == "porn_block"), None)
    if porn:
        return ("No Porn here", "porn_block")

    first = failed[0]
    code = first.get("code")

    mapping = {
        "dot_style": "Naming wrong - use dots, no spaces/parentheses",
        "group_suffix": "Naming wrong - missing -GROUP suffix",
        "pattern_movie": "Naming wrong - Movie pattern required (Title.Year.Res.Source-Group)",
        "pattern_tv": "Naming wrong - TV pattern required (Show.SxxEyy...-Group or Show.Sxx...-Group)",
        "pattern_tv_ep": "Naming wrong - TV episode pattern required (Show.SxxEyy...-Group)",
        "pattern_tv_season": "Naming wrong - TV season pattern required (Show.Sxx...-Group)",
        "banned_quality": "Banned quality - no TS/SCREEN/CAM etc",
        "min_resolution": "Resolution too low (min 760p)",
    }

    return (mapping.get(code, "Naming wrong - check your naming"), code)


def _make_results(category: str, title: str, torrent_meta, description: str | None):
    title_res = analyze_title(category, title, settings.min_res_p, settings.enable_porn_block)
    files_res = analyze_files(torrent_meta.files if torrent_meta else [])
    gi_title = guess(title)
    gi_info = guess(torrent_meta.info_name or "") if torrent_meta and torrent_meta.info_name else {}
    gi_files = []
    for f in (torrent_meta.files[:10] if torrent_meta else []):  # cap for UI
        # f can be a legacy string path OR a dict {"path": "...", "size": ...}
        if isinstance(f, dict):
            p = str(f.get("path", ""))
            size = f.get("size")
        else:
            p = str(f)
            size = None
        basename = p.split("/")[-1].split("\\")[-1]
        gi_files.append({"path": p, "size": size, "guessit": guess(basename)})


    
    # Decide overall verdict and reason:
    # - If title checks fail: FAIL with reason (porn or naming)
    # - Else if file checks warn: WARN (no reason)
    # - Else: PASS (no reason)
    reason = None
    reason_code = None

    if title_res.get("verdict") == "fail":
        reason, reason_code = _pick_reason_from_checks(title_res)
        verdict = "fail"
    elif files_res.get("verdict") == "fail":
        verdict = "fail"
    elif files_res.get("verdict") == "warn":
        verdict = "warn"
    else:
        verdict = "pass"


    return {
        "verdict": verdict,
        "reason": reason,
        "reason_code": reason_code,
        "policy": {
            "min_res_p": settings.min_res_p,
            "enable_porn_block": settings.enable_porn_block,
        },
        "title_checks": title_res,
        "file_checks": files_res,
        "guessit": {
            "title": gi_title,
            "torrent_info_name": gi_info,
            "sample_files": gi_files,
        }
    }


# ---------- Web UI ----------
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"}, status_code=401)

    token = create_token(user)
    resp = RedirectResponse(url="/", status_code=302)
    set_auth_cookie(resp, token)
    return resp

@app.get("/logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=302)
    clear_auth_cookie(resp)
    return resp

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    analyses = db.query(Analysis).order_by(Analysis.id.desc()).limit(50).all()
    # Precompute verdict for quick UI badges
    items = []
    for a in analyses:
        try:
            r = json.loads(a.results) if a.results else {}
            v = r.get("verdict")
        except Exception:
            v = None
        by = a.created_by_user.username if getattr(a, "created_by_user", None) else None
        items.append({"a": a, "verdict": v, "by": by})
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user, "items": items})

@app.get("/analyses/new", response_class=HTMLResponse)
def new_analysis_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("new_analysis.html", {"request": request, "user": user})

@app.post("/analyses/new")
async def new_analysis(
    request: Request,
    category: str = Form(...),
    title: str | None = Form(None),
    description: str | None = Form(None),
    torrent_file: UploadFile | None = File(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if category not in ("Movie", "TV"):
        raise HTTPException(400, "Category must be Movie or TV")
    
    if not torrent_file:
        return templates.TemplateResponse(
            "new_analysis.html",
            {
                "request": request,
                "user": user,
                "error": "Please upload a .torrent file to run an analysis.",
            },
            status_code=400,
        )

    raw = None
    meta = None
    if torrent_file:
        raw = await torrent_file.read()
        meta = read_torrent_bytes(raw)

    effective_title = (title or (meta.info_name if meta else "") or "").strip()
    import re

    # If title was not pasted, we typically use the torrent's info name.
    # That can include a container extension (e.g. "...-GROUP.mkv") which breaks pattern/group checks.
    if meta and (not title):
        effective_title = re.sub(r"\.(mkv|mp4|avi|m2ts|ts|mov|wmv)$", "", effective_title, flags=re.IGNORECASE)

    # Also strip accidental ".torrent" if someone pastes/uses a filename
    effective_title = re.sub(r"\.torrent$", "", effective_title, flags=re.IGNORECASE)
    if not effective_title:
        raise HTTPException(400, "Provide a title or upload a torrent with an info name")

    results = _make_results(category, effective_title, meta, description)

    a = Analysis(
        created_by=user.id,
        category=category,
        input_title=title,
        input_description=description,
        torrent_info_name=(meta.info_name if meta else None),
        info_hash=(meta.info_hash if meta else None),
        announce=json.dumps(meta.announce if meta else []),
        files=json.dumps(meta.files if meta else []),
        results=json.dumps(results),
    )
    db.add(a)
    db.commit()
    db.refresh(a)

    return RedirectResponse(url=f"/analyses/{a.id}", status_code=302)

@app.get("/analyses/{analysis_id}", response_class=HTMLResponse)
def analysis_detail(analysis_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.get(Analysis, analysis_id)
    if not a:
        raise HTTPException(404, "Not found")
    results = json.loads(a.results)
    return templates.TemplateResponse("analysis_detail.html", {"request": request, "user": user, "a": a, "results": results})

# ---------- Admin: user management ----------
@app.get("/admin/users", response_class=HTMLResponse)
def users_page(request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.id.asc()).all()
    return templates.TemplateResponse("users.html", {"request": request, "user": admin, "users": users})

@app.post("/admin/users")
def create_user(
    username: str = Form(...),
    password: str = Form(...),
    is_admin: str | None = Form(None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(400, "Username already exists")
    u = User(username=username, password_hash=hash_password(password), is_admin=bool(is_admin))
    db.add(u)
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=302)

# ---------- JSON API ----------
@app.post("/api/analyses")
async def api_create_analysis(
    category: str = Form(...),
    title: str | None = Form(None),
    description: str | None = Form(None),
    torrent_file: UploadFile | None = File(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if category not in ("Movie", "TV"):
        raise HTTPException(400, "Category must be Movie or TV")
    
    if not torrent_file:
        raise HTTPException(400, "torrent_file is required")

    raw = None
    meta = None
    if torrent_file:
        raw = await torrent_file.read()
        meta = read_torrent_bytes(raw)

    effective_title = (title or (meta.info_name if meta else "") or "").strip()
    if not effective_title:
        raise HTTPException(400, "Provide a title or upload a torrent with an info name")

    results = _make_results(category, effective_title, meta, description)

    a = Analysis(
        created_by=user.id,
        category=category,
        input_title=title,
        input_description=description,
        torrent_info_name=(meta.info_name if meta else None),
        info_hash=(meta.info_hash if meta else None),
        announce=json.dumps(meta.announce if meta else []),
        files=json.dumps(meta.files if meta else []),
        results=json.dumps(results),
    )
    db.add(a)
    db.commit()
    db.refresh(a)

    return JSONResponse(_analysis_to_dict(a))

@app.get("/api/analyses")
def api_list_analyses(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    analyses = db.query(Analysis).order_by(Analysis.id.desc()).limit(200).all()
    return [_analysis_to_dict(a) for a in analyses]

@app.get("/api/analyses/{analysis_id}")
def api_get_analysis(analysis_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.get(Analysis, analysis_id)
    if not a:
        raise HTTPException(404, "Not found")
    return _analysis_to_dict(a)
