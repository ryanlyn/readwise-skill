"""Pydantic models for Readwise API request payloads and responses."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Request models (strict — no extra fields)
# ---------------------------------------------------------------------------


class HighlightCreatePayload(BaseModel):
    text: str
    title: str | None = None
    author: str | None = None
    source_url: str | None = None
    book_id: int | None = None
    category: Literal["articles", "books", "tweets", "podcasts", "supplementals"] | None = None
    note: str | None = None
    tags: list[str] = []
    location: str | None = None
    location_type: str | None = None


class HighlightUpdatePayload(BaseModel):
    text: str | None = None
    title: str | None = None
    author: str | None = None
    source_url: str | None = None
    note: str | None = None
    tags: list[str] | None = None
    location: str | None = None
    location_type: str | None = None
    color: str | None = None


class HighlightListParams(BaseModel):
    book_id: int | None = None
    tag: str | None = None
    updated_after: str | None = None
    updated_before: str | None = None
    category: Literal["articles", "books", "tweets", "podcasts", "supplementals"] | None = None


class DailyReviewParams(BaseModel):
    updated_after: str | None = None
    updated_before: str | None = None
    limit: int = 50


class BookListParams(BaseModel):
    author: str | None = None
    title: str | None = None


class DocumentCreatePayload(BaseModel):
    url: str | None = None
    html: str | None = None
    title: str | None = None
    summary: str | None = None
    category: str | None = None
    tags: list[str] = []
    labels: list[str] = []


class DocumentListParams(BaseModel):
    document_id: str | None = None
    category: str | None = None
    tag: str | None = None
    location: str | None = None
    updated_after: str | None = None


class DocumentUpdatePayload(BaseModel):
    title: str | None = None
    summary: str | None = None
    category: str | None = None
    labels: list[str] | None = None
    tags: list[str] | None = None
    location: str | None = None


class DocumentPullParams(BaseModel):
    location: str | None = None
    since: str | None = None


# ---------------------------------------------------------------------------
# Response models (extra="allow" — API may return additional fields)
# ---------------------------------------------------------------------------


class Highlight(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    text: str
    note: str | None = None
    location: int | str | None = None
    location_type: str | None = None
    book_id: int | None = None
    color: str | None = None
    tags: list[Any] | None = None
    highlighted_at: str | None = None


class Book(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    title: str
    author: str | None = None
    category: str | None = None
    source: str | None = None
    num_highlights: int | None = None


class DailyReviewResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    count: int | None = None
    results: list[Highlight] = []
    nextPageCursor: str | None = None


class Document(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    url: str | None = None
    source_url: str | None = None
    title: str | None = None
    author: str | None = None
    location: str | None = None
    category: str | None = None
    tags: dict[str, str] | list[str] | None = None


class DocumentSaveResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    url: str


class TokenValidationResult(BaseModel):
    valid: bool
    status: int | None = None
    message: str


class DryRunResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    dry_run: bool = True
    request_payload: dict[str, Any] | None = None
    highlight_id: int | None = None
    document_id: str | None = None
    action: str | None = None


class DeleteResult(BaseModel):
    deleted: bool
    highlight_id: int | None = None
    document_id: str | None = None
