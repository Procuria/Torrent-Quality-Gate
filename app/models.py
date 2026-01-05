from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from .db import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    analyses = relationship("Analysis", back_populates="created_by_user")

class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    category: Mapped[str] = mapped_column(String(16))   # "Movie" or "TV"
    input_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    input_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    torrent_info_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    info_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    announce: Mapped[str | None] = mapped_column(Text, nullable=True)       # json string
    files: Mapped[str | None] = mapped_column(Text, nullable=True)          # json string

    results: Mapped[str] = mapped_column(Text)                              # json string

    created_by_user = relationship("User", back_populates="analyses")
