"""PDF -> clean markdown for the judges.

``pymupdf4llm`` markdown carries extraction noise that misleads the rubric judges
(especially the redaction/format criterion): running headers/footers, page
numbers, hyphenation line-breaks, image placeholders, ligatures and stray
control characters. This module extracts per page, drops repeated
headers/footers, and normalizes the text before it reaches the model.
"""

import logging
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pymupdf4llm

log = logging.getLogger(__name__)

# A top/bottom line is treated as a running header/footer when it repeats on at
# least this fraction of pages (only applied when the document has >= 3 pages).
_HEADER_FOOTER_FREQ = 0.6
# How many lines from the top and bottom of each page are header/footer candidates.
_EDGE_LINES = 2

_IMAGE_MD = re.compile(r"!\[[^\]]*\]\([^)]*\)")
# pymupdf4llm placeholder for omitted images/graphics, e.g.
# "**==> picture [88 x 87] intentionally omitted <==**".
_OMITTED_PLACEHOLDER = re.compile(r"\*{0,2}\s*==>.*?<==\s*\*{0,2}")
_HYPHEN_BREAK = re.compile(r"(\w)[-‐­]\n\s*(\w)")
_PAGE_NUMBER_LINE = re.compile(
    r"^\s*(p[áa]g(?:ina)?\.?\s*)?\d+\s*(/\s*\d+)?\s*$", re.IGNORECASE
)
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_BLANK_LINES = re.compile(r"\n{3,}")


@dataclass
class ExtractionStats:
    pages: int
    raw_chars: int
    clean_chars: int
    removed_header_footer_lines: int


def _normalize_for_match(line: str) -> str:
    """Strip + lowercase + drop digits, so 'Página 1' / 'Página 2' collapse."""
    return re.sub(r"\d+", "#", line.strip().lower())


def _strip_running_headers_footers(pages: list[str]) -> tuple[list[str], int]:
    """Remove top/bottom lines that repeat across most pages."""
    if len(pages) < 3:
        return pages, 0

    counts: Counter[str] = Counter()
    for page in pages:
        lines = [ln for ln in page.splitlines() if ln.strip()]
        edges = lines[:_EDGE_LINES] + lines[-_EDGE_LINES:]
        for ln in set(_normalize_for_match(e) for e in edges):
            counts[ln] += 1

    threshold = max(3, int(_HEADER_FOOTER_FREQ * len(pages)))
    repeated = {key for key, n in counts.items() if n >= threshold and key}

    if not repeated:
        return pages, 0

    removed = 0
    cleaned: list[str] = []
    for page in pages:
        lines = page.splitlines()
        # Only inspect the edge lines so a body line that happens to match a
        # header isn't deleted from the middle of the page.
        non_empty_idx = [i for i, ln in enumerate(lines) if ln.strip()]
        edge_idx = set(non_empty_idx[:_EDGE_LINES] + non_empty_idx[-_EDGE_LINES:])
        kept: list[str] = []
        for i, ln in enumerate(lines):
            if i in edge_idx and _normalize_for_match(ln) in repeated:
                removed += 1
                continue
            kept.append(ln)
        cleaned.append("\n".join(kept))
    return cleaned, removed


def clean_markdown(text: str) -> str:
    """Normalize a single markdown string extracted from a PDF."""
    # NFKC fixes ligatures (ﬁ -> fi) and full-width forms while keeping accents.
    text = unicodedata.normalize("NFKC", text)
    text = _CONTROL_CHARS.sub("", text)
    text = _IMAGE_MD.sub("", text)
    text = _OMITTED_PLACEHOLDER.sub("", text)
    text = _HYPHEN_BREAK.sub(r"\1\2", text)

    lines = [
        ln.rstrip()
        for ln in text.splitlines()
        if not _PAGE_NUMBER_LINE.match(ln)
    ]
    text = "\n".join(lines)
    text = _BLANK_LINES.sub("\n\n", text)
    return text.strip()


def extract_clean_text(
    pdf_path: Path, show_progress: bool = True
) -> tuple[str, ExtractionStats]:
    """Extract a PDF to cleaned markdown plus extraction stats."""
    chunks = pymupdf4llm.to_markdown(
        pdf_path,
        page_chunks=True,
        ignore_images=True,
        ignore_graphics=True,
        show_progress=show_progress,
    )
    pages = [chunk["text"] for chunk in chunks]
    raw_chars = sum(len(p) for p in pages)

    pages, removed = _strip_running_headers_footers(pages)
    text = clean_markdown("\n\n".join(pages))

    stats = ExtractionStats(
        pages=len(pages),
        raw_chars=raw_chars,
        clean_chars=len(text),
        removed_header_footer_lines=removed,
    )
    return text, stats
