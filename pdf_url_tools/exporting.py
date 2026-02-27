from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .utils import (
    dedupe_preserve_order,
    doi_identifier_from_url,
    extract_doi_identifier_from_text,
    is_doi_url,
    sanitize_filename,
)


def _extract_doi_from_error(error: HTTPError) -> str | None:
    location_header = error.headers.get("Location") if error.headers else None
    if location_header:
        location_doi = extract_doi_identifier_from_text(location_header)
        if location_doi:
            return location_doi

    try:
        error_body = error.read().decode("utf-8", errors="replace")
    except Exception:
        return None

    return extract_doi_identifier_from_text(error_body)


def fetch_bibtex_for_doi_url(doi_url: str, timeout_seconds: float) -> tuple[bool, str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (BibTeX-Exporter)",
        "Accept": "application/x-bibtex; charset=utf-8",
    }

    try:
        request = Request(doi_url, headers=headers, method="GET")
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read().decode("utf-8", errors="replace").strip()
            if not payload:
                return False, "empty bibtex response"
            return True, payload
    except HTTPError as error:
        return False, f"http {error.code}"
    except URLError as error:
        return False, f"network error: {error.reason}"
    except Exception as error:
        return False, f"error: {error}"


def fetch_ris_for_doi_identifier(doi_identifier: str, timeout_seconds: float) -> tuple[bool, str]:
    encoded_doi = quote(doi_identifier, safe="/")
    ris_url = (
        f"https://citation-needed.springer.com/v2/references/{encoded_doi}"
        "?format=refman&flavour=citation"
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (RIS-Exporter)",
        "Accept": "application/x-research-info-systems, text/plain, */*",
    }

    try:
        request = Request(ris_url, headers=headers, method="GET")
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read().decode("utf-8", errors="replace").strip()
            if not payload:
                return False, "empty ris response"
            if "TY  -" not in payload:
                return False, "unexpected ris payload"
            return True, payload
    except HTTPError as error:
        return False, f"http {error.code}"
    except URLError as error:
        return False, f"network error: {error.reason}"
    except Exception as error:
        return False, f"error: {error}"


def resolve_doi_identifier(source_url: str, timeout_seconds: float) -> tuple[bool, str]:
    if is_doi_url(source_url):
        doi_identifier = doi_identifier_from_url(source_url)
        if doi_identifier:
            return True, doi_identifier

    embedded_doi = extract_doi_identifier_from_text(source_url)
    if embedded_doi:
        return True, embedded_doi

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        request = Request(source_url, headers=headers, method="GET")
        with urlopen(request, timeout=timeout_seconds) as response:
            final_url = response.geturl() or source_url
            final_doi = extract_doi_identifier_from_text(final_url)
            if final_doi:
                return True, final_doi

            try:
                page_text = response.read().decode("utf-8", errors="replace")
                body_doi = extract_doi_identifier_from_text(page_text)
                if body_doi:
                    return True, body_doi
            except Exception:
                pass

            return False, "could not resolve DOI from redirect"
    except HTTPError as error:
        error_doi = _extract_doi_from_error(error)
        if error_doi:
            return True, error_doi
        return False, f"http {error.code}"
    except URLError as error:
        return False, f"network error: {error.reason}"
    except Exception as error:
        return False, f"error: {error}"


def collect_resolved_doi_identifiers(source_urls: list[str], timeout_seconds: float) -> tuple[list[str], int]:
    resolved_identifiers: list[str] = []
    failed_resolution_count = 0

    for source_url in source_urls:
        success, payload = resolve_doi_identifier(source_url=source_url, timeout_seconds=timeout_seconds)
        if success:
            resolved_identifiers.append(payload)
            continue

        failed_resolution_count += 1
        print(f"[DOI RESOLVE FAIL] {payload} -> {source_url}")

    return dedupe_preserve_order(resolved_identifiers), failed_resolution_count


def export_reference_files(pdf_path: Path, source_urls: list[str], timeout_seconds: float) -> tuple[int, int, int, int, Path]:
    output_folder = pdf_path.parent / pdf_path.stem
    output_folder.mkdir(parents=True, exist_ok=True)

    doi_identifiers, failed_resolution_count = collect_resolved_doi_identifiers(
        source_urls=source_urls,
        timeout_seconds=timeout_seconds,
    )

    ris_exported_count = 0
    bib_exported_count = 0
    failed_count = 0

    for index, doi_identifier in enumerate(doi_identifiers, start=1):
        doi_url = f"https://doi.org/{doi_identifier}"
        base_name = f"{index:03d}_{sanitize_filename(doi_identifier)}"

        ris_success, ris_payload = fetch_ris_for_doi_identifier(doi_identifier, timeout_seconds=timeout_seconds)
        if ris_success:
            (output_folder / f"{base_name}.ris").write_text(ris_payload + "\n", encoding="utf-8")
            ris_exported_count += 1
            continue

        bib_success, bib_payload = fetch_bibtex_for_doi_url(doi_url, timeout_seconds=timeout_seconds)
        if bib_success:
            (output_folder / f"{base_name}.bib").write_text(bib_payload + "\n", encoding="utf-8")
            bib_exported_count += 1
            continue

        failed_count += 1
        print(f"[RIS FAIL] {ris_payload} -> {doi_url}")
        print(f"[BIB FAIL] {bib_payload} -> {doi_url}")

    return ris_exported_count, bib_exported_count, failed_count, failed_resolution_count, output_folder
