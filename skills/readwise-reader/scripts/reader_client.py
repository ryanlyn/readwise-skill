"""CLI for interacting with the Readwise Reader API."""

from __future__ import annotations

import os
from collections.abc import Iterable
from typing import Annotated, Any

import requests
import typer

from readwise_common import (
    DeleteResult,
    Document,
    DocumentCreatePayload,
    DocumentListParams,
    DocumentSaveResponse,
    DocumentUpdatePayload,
    DryRunResult,
    TokenValidationResult,
    build_tags,
    get_reader_token,
    parse_iso_datetime,
    parse_tags,
    print_result,
    request_with_backoff,
)
from readwise_common.http import APIRequestError

DEFAULT_BASE_URL = "https://readwise.io/api/v3"
AUTH_URL = "https://readwise.io/api/v2/auth/"
USER_AGENT = "readwise-reader-skill/0.1"


class ReaderClient:
    def __init__(self, token: str, *, base_url: str | None = None, auth_url: str | None = None, dry_run: bool = False):
        resolved = base_url or os.getenv("READWISE_READER_API_BASE_URL") or DEFAULT_BASE_URL
        self.base_url = resolved.rstrip("/")
        self.auth_url = auth_url or os.getenv("READWISE_READER_AUTH_URL") or AUTH_URL
        self.dry_run = dry_run
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Token {token}",
                "User-Agent": USER_AGENT,
            }
        )

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{path}"
        return request_with_backoff(self.session, method, url, **kwargs)

    def create_document(self, payload: DocumentCreatePayload) -> DocumentSaveResponse | DryRunResult:
        data = payload.model_dump(exclude_none=True)
        if self.dry_run:
            return DryRunResult(request_payload=data)
        response = self._request("post", "/save/", json=data)
        return DocumentSaveResponse.model_validate(response.json())

    def list_documents(self, params: DocumentListParams) -> Iterable[Document]:
        query: dict[str, Any] = {}
        if params.document_id is not None:
            query["id"] = params.document_id
        if params.category is not None:
            query["category"] = params.category
        if params.tag is not None:
            query["tag"] = params.tag
        if params.location is not None:
            query["location"] = params.location
        if params.updated_after is not None:
            query["updatedAfter"] = params.updated_after
        cursor: str | None = None
        while True:
            scoped = dict(query)
            if cursor:
                scoped["pageCursor"] = cursor
            response = self._request("get", "/list/", params=scoped)
            resp_data = response.json()
            for doc in resp_data.get("results", []):
                yield Document.model_validate(doc)
            cursor = resp_data.get("nextPageCursor")
            if not cursor:
                break

    def update_document(self, document_id: str, payload: DocumentUpdatePayload) -> DocumentSaveResponse | DryRunResult:
        data = payload.model_dump(exclude_none=True)
        if self.dry_run:
            return DryRunResult(document_id=document_id, request_payload=data)
        response = self._request("patch", f"/update/{document_id}/", json=data)
        return DocumentSaveResponse.model_validate(response.json())

    def delete_document(self, document_id: str) -> DeleteResult | DryRunResult:
        if self.dry_run:
            return DryRunResult(document_id=document_id, action="delete")
        self._request("delete", f"/delete/{document_id}/")
        return DeleteResult(deleted=True, document_id=document_id)

    def validate_token(self) -> None:
        response = request_with_backoff(self.session, "get", self.auth_url)
        if response.status_code != 204:
            error = requests.HTTPError("Unexpected auth response", response=response)
            raise error


# ---------------------------------------------------------------------------
# Typer CLI
# ---------------------------------------------------------------------------

app = typer.Typer(help="Interact with Readwise Reader API")
docs_app = typer.Typer(help="Document operations")
auth_app = typer.Typer(help="Authentication helpers")

app.add_typer(docs_app, name="docs")
app.add_typer(auth_app, name="auth")


@app.callback()
def app_callback(
    ctx: typer.Context,
    token: Annotated[str | None, typer.Option(help="Override READWISE_TOKEN")] = None,
    raw: Annotated[bool, typer.Option("--raw", help="Output full JSON (all fields)")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    resolved = get_reader_token(token)
    ctx.ensure_object(dict)
    ctx.obj["client"] = ReaderClient(resolved.value, dry_run=dry_run)
    ctx.obj["raw"] = raw
    ctx.obj["dry_run"] = dry_run


@docs_app.command("create")
def docs_create(
    ctx: typer.Context,
    url: Annotated[str | None, typer.Option()] = None,
    content: Annotated[str | None, typer.Option()] = None,
    file: Annotated[str | None, typer.Option()] = None,
    title: Annotated[str | None, typer.Option()] = None,
    summary: Annotated[str | None, typer.Option()] = None,
    category: Annotated[str | None, typer.Option()] = None,
    tags: Annotated[str | None, typer.Option(help="Comma-separated tags")] = None,
    labels: Annotated[str | None, typer.Option(help="Comma-separated labels")] = None,
    generated: Annotated[bool, typer.Option("--generated")] = False,
) -> None:
    client: ReaderClient = ctx.obj["client"]
    if file:
        raise typer.BadParameter("--file uploads are not supported by Reader API v3")
    tag_list = build_tags(parse_tags(tags), generated)
    label_list = parse_tags(labels) if labels else []
    payload = DocumentCreatePayload(
        url=url,
        html=content,
        title=title,
        summary=summary,
        category=category,
        tags=tag_list,
        labels=label_list,
    )
    data = payload.model_dump(exclude_none=True)
    if not data.get("url") and not data.get("html"):
        raise typer.BadParameter("Provide --url or --content")
    result = client.create_document(payload)
    print_result(result, entity="document", raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])


@docs_app.command("list")
def docs_list(
    ctx: typer.Context,
    id: Annotated[str | None, typer.Option("--id")] = None,
    category: Annotated[str | None, typer.Option()] = None,
    tag: Annotated[str | None, typer.Option()] = None,
    location: Annotated[str | None, typer.Option()] = None,
    updated_after: Annotated[str | None, typer.Option("--updated-after")] = None,
    limit: Annotated[int, typer.Option()] = 50,
) -> None:
    client: ReaderClient = ctx.obj["client"]
    params = DocumentListParams(
        document_id=id,
        category=category,
        tag=tag,
        location=location,
        updated_after=parse_iso_datetime(updated_after) if updated_after else None,
    )
    docs = []
    for idx, doc in enumerate(client.list_documents(params), start=1):
        docs.append(doc)
        if limit and idx >= limit:
            break
    print_result(docs, entity="document", raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])


@docs_app.command("update")
def docs_update(
    ctx: typer.Context,
    document_id: Annotated[str, typer.Argument()],
    title: Annotated[str | None, typer.Option()] = None,
    summary: Annotated[str | None, typer.Option()] = None,
    category: Annotated[str | None, typer.Option()] = None,
    labels: Annotated[str | None, typer.Option()] = None,
    tags: Annotated[str | None, typer.Option()] = None,
    state: Annotated[str | None, typer.Option()] = None,
) -> None:
    client: ReaderClient = ctx.obj["client"]
    payload = DocumentUpdatePayload(
        title=title,
        summary=summary,
        category=category,
        labels=parse_tags(labels) if labels else None,
        tags=parse_tags(tags) if tags else None,
        location=state,
    )
    if not payload.model_dump(exclude_none=True):
        raise typer.BadParameter("No fields to update")
    result = client.update_document(document_id, payload)
    print_result(result, entity="document", raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])


@docs_app.command("pull")
def docs_pull(
    ctx: typer.Context,
    location: Annotated[str | None, typer.Option()] = None,
    since: Annotated[str | None, typer.Option()] = None,
    limit: Annotated[int, typer.Option()] = 50,
) -> None:
    client: ReaderClient = ctx.obj["client"]
    params = DocumentListParams(
        location=location,
        updated_after=parse_iso_datetime(since) if since else None,
    )
    docs = []
    for idx, doc in enumerate(client.list_documents(params), start=1):
        docs.append(doc)
        if limit and idx >= limit:
            break
    print_result(docs, entity="document", raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])


@auth_app.command("validate")
def auth_validate(ctx: typer.Context) -> None:
    client: ReaderClient = ctx.obj["client"]
    try:
        client.validate_token()
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code == 401:
            message = "Token is invalid. Generate one at https://readwise.io/access_token"
        elif status_code == 403:
            message = "Token is unauthorized. Generate one at https://readwise.io/access_token"
        else:
            status = status_code if status_code is not None else "unknown"
            message = f"Token validation failed with status {status}."
        result = TokenValidationResult(valid=False, status=status_code, message=message)
        print_result(result, entity="", raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])
        return
    except APIRequestError as exc:
        result = TokenValidationResult(valid=False, message=f"Token validation failed: {exc}")
        print_result(result, entity="", raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])
        return
    result = TokenValidationResult(valid=True, message="Token is valid for Readwise Reader API.")
    print_result(result, entity="", raw=ctx.obj["raw"], dry_run=ctx.obj["dry_run"])


def main(argv: Iterable[str] | None = None) -> int:
    """Entry point preserving the existing main(argv) interface for tests."""
    try:
        app(list(argv) if argv is not None else None, standalone_mode=False)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
