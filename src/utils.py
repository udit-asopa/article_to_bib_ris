import re
from urllib.parse import urlparse

DOI_IDENTIFIER_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", re.IGNORECASE)


def clean_url(raw_url: str) -> str:
    normalized = re.sub(r"\s+", "", raw_url)
    return normalized.rstrip(".,;:!?)\"]}'")


def should_continue_after_whitespace(previous_char: str, next_char: str) -> bool:
    if not previous_char or not next_char:
        return False

    if previous_char in {"/", "-", "_"}:
        return next_char.isalnum()

    if previous_char == ".":
        return next_char.islower() or next_char.isdigit()

    if previous_char.isdigit() and next_char.isdigit():
        return True

    if previous_char.islower() and next_char.islower():
        return True

    return False


def is_doi_url(url: str) -> bool:
    return urlparse(url).netloc.lower() in {"doi.org", "dx.doi.org"}


def doi_identifier_from_url(doi_url: str) -> str:
    return urlparse(doi_url).path.lstrip("/")


def extract_doi_identifier_from_text(text: str) -> str | None:
    match = DOI_IDENTIFIER_PATTERN.search(text)
    if not match:
        return None
    return match.group(0).rstrip(".,;:!?)\"]}'")


def sanitize_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "doi"


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_items: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            unique_items.append(item)
    return unique_items


def drop_truncated_prefix_urls(urls: list[str]) -> list[str]:
    filtered_urls: list[str] = []
    for candidate in urls:
        is_truncated_prefix = candidate.endswith("-") and any(
            other != candidate and other.startswith(candidate) for other in urls
        )
        if not is_truncated_prefix:
            filtered_urls.append(candidate)
    return filtered_urls
