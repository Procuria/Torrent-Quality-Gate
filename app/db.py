from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .settings import settings
import os

def _sqlite_url(path: str) -> str:
    # Ensure parent directory exists for file-based sqlite
    if path != ":memory:":
        parent = os.path.dirname(path) or "."
        os.makedirs(parent, exist_ok=True)
    return f"sqlite:///{path}"

engine = create_engine(_sqlite_url(settings.db_path), connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass
