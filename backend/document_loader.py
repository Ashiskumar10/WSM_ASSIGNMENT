"""Load UTF-8 TXT files and split them into paragraph-sized search documents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass
class Document:
    doc_id: str
    title: str
    text: str
    source: str
    paragraph_number: int


def split_paragraphs(text: str) -> list[str]:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not cleaned:
        return []
    paragraphs = [re.sub(r"[ \t]+", " ", chunk).strip() for chunk in re.split(r"\n\s*\n+", cleaned)]
    return [paragraph for paragraph in paragraphs if paragraph]


def load_txt_file(path: str | Path) -> list[Document]:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8", errors="replace")
    paragraphs = split_paragraphs(text)
    documents: list[Document] = []
    for number, paragraph in enumerate(paragraphs, start=1):
        first_line = paragraph.splitlines()[0].strip()
        first_line = re.sub(r"^#{1,6}\s*", "", first_line)
        title = first_line[:88].rstrip(" .,:;—-") or f"{file_path.stem} · paragraph {number}"
        if len(first_line) > 88:
            title += "…"
        doc_id = f"{file_path.stem}::p{number:03d}"
        documents.append(Document(
            doc_id=doc_id,
            title=title,
            text=paragraph,
            source=file_path.name,
            paragraph_number=number,
        ))
    return documents


def load_corpus(directory: str | Path) -> list[Document]:
    corpus_dir = Path(directory)
    corpus_dir.mkdir(parents=True, exist_ok=True)
    documents: list[Document] = []
    for file_path in sorted(corpus_dir.rglob("*.txt")):
        documents.extend(load_txt_file(file_path))
    return documents
