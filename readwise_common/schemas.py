"""Entity display field definitions for human-readable output."""

HIGHLIGHT_DISPLAY_FIELDS = ["id", "text", "note", "tags"]
BOOK_DISPLAY_FIELDS = ["id", "title", "author", "category", "source", "num_highlights"]
DOCUMENT_DISPLAY_FIELDS = ["id", "url", "title", "category", "location", "tags"]

DISPLAY_FIELDS: dict[str, list[str]] = {
    "highlight": HIGHLIGHT_DISPLAY_FIELDS,
    "book": BOOK_DISPLAY_FIELDS,
    "document": DOCUMENT_DISPLAY_FIELDS,
}
