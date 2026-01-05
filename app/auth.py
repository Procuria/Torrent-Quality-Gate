from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from .db import SessionLocal
from .settings import settings
from .models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGO = "HS256"
COOKIE_NAME = "qg_token"
TOKEN_TTL_HOURS = 24

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)

def create_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "usr": user.username,
        "adm": bool(user.is_admin),
        "iat": int(datetime.utcnow().timestamp()),
        "exp": int((datetime.utcnow() + timedelta(hours=TOKEN_TTL_HOURS)).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGO)

def set_auth_cookie(resp: Response, token: str):
    resp.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=False,  # set true behind https
        max_age=TOKEN_TTL_HOURS * 3600,
        path="/",
    )

def clear_auth_cookie(resp: Response):
    resp.delete_cookie(COOKIE_NAME, path="/")

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGO])
        uid = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.get(User, uid)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    return user
