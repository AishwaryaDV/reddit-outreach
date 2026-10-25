"""Pydantic request/response models for the API boundary.

These replace the shapes the frontend used to read straight from Supabase, so
the browser now talks only to the backend.
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reddit_post_id: str
    subreddit: str | None
    title: str | None
    body: str | None
    author: str | None
    posted_at: datetime | None
    detected_at: datetime
    status: str
    score: int | None
    score_reason: str | None
    num_comments: int
    reddit_upvotes: int


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    post_id: UUID
    draft: str | None
    final_message: str | None
    send_after: datetime | None
    sent_at: datetime | None
    status: str
    created_at: datetime
    reply_received: bool
    replied_at: datetime | None
    outcome: str | None


class MessageWithPost(MessageOut):
    # named `posts` to match what the frontend reads (item.posts)
    posts: PostOut | None = None


class PostsPage(BaseModel):
    posts: list[PostOut]
    total: int


class SearchTermOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    term: str
    active: bool
    created_at: datetime


# --- request bodies ---

class ApproveIn(BaseModel):
    final_message: str | None = None


class OutcomeIn(BaseModel):
    outcome: str | None = None


class SearchTermIn(BaseModel):
    term: str


class SearchTermPatch(BaseModel):
    active: bool


# --- Scorer structured output (LLM must return exactly this shape) ---

class ScoreResult(BaseModel):
    score: int = Field(ge=1, le=10)
    label: Literal["opportunity", "not_opportunity"]
    reasons: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    budget_mentioned: bool = False
    draft: str = ""


class TriageResult(BaseModel):
    """Cheap first-pass classify — is this plausibly a real paid dev-hire?"""
    decision: Literal["hire", "not_hire"]
    confidence: float = Field(ge=0.0, le=1.0)


class JudgeResult(BaseModel):
    """Draft quality gate — does the DM follow the rules well enough to send?"""
    passed: bool
    reasons: list[str] = Field(default_factory=list)
