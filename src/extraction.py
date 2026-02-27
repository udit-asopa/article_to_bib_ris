import re
from pathlib import Path

from pypdf import PdfReader

from .utils import (
    clean_url,
    dedupe_preserve_order,
    drop_truncated_prefix_urls,
    is_doi_url,
    should_continue_after_whitespace,
)

DOI_PREFIX_PATTERN = re.compile(r"https?://(?:dx\.)?doi\s*\.\s*org/", re.IGNORECASE)
HTTP_PREFIX_PATTERN = re.compile(r"https?://", re.IGNORECASE)


def _scan_url_from_prefix(text: str, start: int, end: int) -> str:
    index = end
    collected: list[str] = [text[start:end]]

    while index < len(text):
        current_char = text[index]

        if current_char in {'"', "'", "<", ">", "[", "]", "{", "}"}:
            break

        if current_char.isspace():
            look_ahead = index
            while look_ahead < len(text) and text[look_ahead].isspace():
                look_ahead += 1

            if look_ahead >= len(text):
                break

            previous_char = collected[-1][-1] if collected and collected[-1] else ""
            next_char = text[look_ahead]
            if should_continue_after_whitespace(previous_char, next_char):
                index = look_ahead
                continue

            break

        collected.append(current_char)
        index += 1

    return clean_url("".join(collected))


def extract_doi_urls_from_text(text: str) -> list[str]:
    doi_urls: list[str] = []
    for prefix_match in DOI_PREFIX_PATTERN.finditer(text):
        candidate = _scan_url_from_prefix(
            text, prefix_match.start(), prefix_match.end()
        )
        if is_doi_url(candidate):
            doi_urls.append(candidate)
    return doi_urls


def extract_generic_urls_from_text(text: str) -> list[str]:
    generic_urls: list[str] = []
    for prefix_match in HTTP_PREFIX_PATTERN.finditer(text):
        candidate = _scan_url_from_prefix(
            text, prefix_match.start(), prefix_match.end()
        )
        if candidate.lower().startswith(("http://", "https://")):
            generic_urls.append(candidate)
    return generic_urls


def extract_urls_from_page_annotations(page) -> list[str]:
    annotation_urls: list[str] = []
    annotations = page.get("/Annots")
    if not annotations:
        return annotation_urls

    for annotation_ref in annotations:
        try:
            annotation = annotation_ref.get_object()
        except Exception:
            continue

        if annotation.get("/Subtype") != "/Link":
            continue

        action = annotation.get("/A")
        if not action:
            continue

        uri_value = action.get("/URI")
        if not uri_value:
            continue

        candidate = clean_url(str(uri_value))
        if candidate.lower().startswith(("http://", "https://")):
            annotation_urls.append(candidate)

    return annotation_urls


def extract_urls_from_pdf(pdf_path: Path) -> list[str]:
    reader = PdfReader(str(pdf_path))
    urls: list[str] = []

    for page in reader.pages:
        urls.extend(extract_urls_from_page_annotations(page))

        text = page.extract_text() or ""
        urls.extend(extract_doi_urls_from_text(text))

        for generic_url in extract_generic_urls_from_text(text):
            if not is_doi_url(generic_url):
                urls.append(generic_url)

    deduped = dedupe_preserve_order(urls)
    return drop_truncated_prefix_urls(deduped)
