from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Generator, List, TypedDict


class PageRow(TypedDict, total=False):
    page_id: str
    url: str
    title: str
    parent_url: str
    breadcrumbs_json: str
    toc_json: str
    fetched_at: str
    http_status: str
    content_hash: str


class Block(TypedDict):
    kind: str
    source_order: int
    section_path: List[str]


class TextBlock(Block):
    chunk_id: str
    text: str


class TableBlock(Block):
    table_id: str
    caption: str
    columns: List[str]
    rows: List[List[str]]


@dataclass
class PageIndex:
    page_id: str
    url: str
    title: str
    text_chars_total: int
    chunks_count: int
    tables_count: int


def read_jsonl(path: Path) -> Generator[dict, None, None]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def load_pages(pages_path: Path) -> Dict[str, PageRow]:
    pages: Dict[str, PageRow] = {}
    with pages_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not row.get("page_id"):
                continue
            pages[str(row["page_id"])] = row
    return pages


def main() -> None:
    data_dir = Path("data/raw")
    derived_dir = Path("data/derived")
    pages_path = data_dir / "pages.csv"
    chunks_path = data_dir / "text_chunks.jsonl"
    tables_path = data_dir / "tables.jsonl"

    if not pages_path.exists():
        raise FileNotFoundError(pages_path)

    pages = load_pages(pages_path)
    bundles: Dict[str, List[Block]] = {page_id: [] for page_id in pages.keys()}
    text_chars_total: Dict[str, int] = {page_id: 0 for page_id in pages.keys()}
    chunks_count: Dict[str, int] = {page_id: 0 for page_id in pages.keys()}
    tables_count: Dict[str, int] = {page_id: 0 for page_id in pages.keys()}

    if chunks_path.exists():
        for item in read_jsonl(chunks_path):
            page_id = str(item["page_id"])
            if page_id not in bundles:
                continue
            text = item.get("text", "")
            block: TextBlock = {
                "kind": "text",
                "chunk_id": str(item["chunk_id"]),
                "source_order": int(item.get("source_order", 0)),
                "section_path": item.get("section_path") or [],
                "text": text,
            }
            bundles[page_id].append(block)
            chunks_count[page_id] += 1
            text_chars_total[page_id] += len(text)

    if tables_path.exists():
        for item in read_jsonl(tables_path):
            page_id = str(item["page_id"])
            if page_id not in bundles:
                continue
            block: TableBlock = {
                "kind": "table",
                "table_id": str(item["table_id"]),
                "source_order": int(item.get("source_order", 0)),
                "section_path": item.get("section_path") or [],
                "caption": item.get("caption") or "",
                "columns": item.get("columns") or [],
                "rows": item.get("rows") or [],
            }
            bundles[page_id].append(block)
            tables_count[page_id] += 1

    output_dir = derived_dir / "page_bundles"
    output_dir.mkdir(parents=True, exist_ok=True)

    page_index: List[PageIndex] = []
    for page_id, blocks in bundles.items():
        blocks.sort(key=lambda item: item["source_order"])
        page = pages[page_id]
        payload = {
            "page": {
                "page_id": page_id,
                "url": page.get("url"),
                "title": page.get("title"),
                "parent_url": page.get("parent_url"),
                "breadcrumbs": json.loads(page.get("breadcrumbs_json") or "null"),
                "toc": json.loads(page.get("toc_json") or "null"),
            },
            "blocks": blocks,
        }
        with (output_dir / f"{page_id}.json").open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)

        page_index.append(
            PageIndex(
                page_id=page_id,
                url=page.get("url", ""),
                title=page.get("title", ""),
                text_chars_total=text_chars_total[page_id],
                chunks_count=chunks_count[page_id],
                tables_count=tables_count[page_id],
            )
        )

    index_path = derived_dir / "pages_index.json"
    with index_path.open("w", encoding="utf-8") as handle:
        json.dump([item.__dict__ for item in page_index], handle, ensure_ascii=False)


if __name__ == "__main__":
    main()
