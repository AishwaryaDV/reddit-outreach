from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.message import Message


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    reddit_post_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    subreddit: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), index=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'new'"))
    score: Mapped[int | None] = mapped_column(Integer)
    score_reason: Mapped[str | None] = mapped_column(Text)
    num_comments: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    reddit_upvotes: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    messages: Mapped[list[Message]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )
