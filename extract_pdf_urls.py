import argparse
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from pypdf import PdfReader


DOI_PREFIX_PATTERN = re.compile(r"https?://(?:dx\.)?doi\s*\.\s*org/", re.IGNORECASE)
HTTP_PREFIX_PATTERN = re.compile(r"https?://", re.IGNORECASE)


@dataclass
class UrlCheckResult:
    url: str
    is_valid: bool
    reason: str


def clean_url(raw_url: str) -> str:
    normalized = re.sub(r"\s+", "", raw_url)
    return normalized.rstrip(".,;:!?)\"]}'")


def should_continue_after_whitespace(previous_char: str, next_char: str) -> bool:
    if not previous_char or not next_char:
        return False

    if previous_char in {"/", "-"}:
        return next_char.isalnum()

    if previous_char == "_":
        return next_char.isalnum()

    if previous_char == ".":
        return next_char.islower() or next_char.isdigit()

    if previous_char.isdigit() and next_char.isdigit():
        return True

    if previous_char.islower() and next_char.islower():
        return True

    return False


def extract_doi_urls_from_text(text: str) -> list[str]:
    doi_urls: list[str] = []

    for prefix_match in DOI_PREFIX_PATTERN.finditer(text):
        start = prefix_match.start()
        index = prefix_match.end()
        collected: list[str] = [text[start:index]]

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

        candidate = clean_url("".join(collected))
        if candidate.lower().startswith(("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/")):
            doi_urls.append(candidate)

    return doi_urls


def extract_generic_urls_from_text(text: str) -> list[str]:
    generic_urls: list[str] = []

    for prefix_match in HTTP_PREFIX_PATTERN.finditer(text):
        start = prefix_match.start()
        index = prefix_match.end()
        collected: list[str] = [text[start:index]]

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

        candidate = clean_url("".join(collected))
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
        annotation_urls = extract_urls_from_page_annotations(page)
        urls.extend(annotation_urls)

        text = page.extract_text() or ""
        doi_urls = extract_doi_urls_from_text(text)
        urls.extend(doi_urls)

        generic_urls = extract_generic_urls_from_text(text)
        for url in generic_urls:
            parsed = urlparse(url)
            if parsed.netloc.lower() in {"doi.org", "dx.doi.org"}:
                continue
            urls.append(url)

    seen: set[str] = set()
    unique_urls: list[str] = []
    for url in urls:
        if url and url not in seen:
            seen.add(url)
            unique_urls.append(url)

    filtered_urls: list[str] = []
    for candidate in unique_urls:
        is_truncated_prefix = (
            candidate.endswith("-")
            and any(other != candidate and other.startswith(candidate) for other in unique_urls)
        )
        if not is_truncated_prefix:
            filtered_urls.append(candidate)

    return filtered_urls


def is_well_formed_url(url: str) -> tuple[bool, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False, "unsupported scheme"
    if not parsed.netloc:
        return False, "missing domain"
    return True, "format ok"


def check_url_reachable(url: str, timeout_seconds: float) -> tuple[bool, str]:
    headers = {"User-Agent": "Mozilla/5.0 (URL-Checker)"}

    try:
        head_request = Request(url, headers=headers, method="HEAD")
        with urlopen(head_request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", None)
            if status is None or status < 400:
                return True, f"reachable ({status})" if status is not None else "reachable"
            return False, f"http {status}"
    except HTTPError as error:
        if error.code in {405, 501}:
            pass
        elif urlparse(url).netloc.lower() in {"doi.org", "dx.doi.org"} and error.code in {
            401,
            403,
            406,
            429,
        }:
            return True, f"likely valid DOI (http {error.code}, access restricted)"
        else:
            return False, f"http {error.code}"
    except URLError as error:
        return False, f"network error: {error.reason}"
    except Exception as error:
        return False, f"error: {error}"

    try:
        get_request = Request(url, headers=headers, method="GET")
        with urlopen(get_request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", None)
            if status is None or status < 400:
                return True, f"reachable ({status})" if status is not None else "reachable"
            return False, f"http {status}"
    except HTTPError as error:
        if urlparse(url).netloc.lower() in {"doi.org", "dx.doi.org"} and error.code in {
            401,
            403,
            406,
            429,
        }:
            return True, f"likely valid DOI (http {error.code}, access restricted)"
        return False, f"http {error.code}"
    except URLError as error:
        return False, f"network error: {error.reason}"
    except Exception as error:
        return False, f"error: {error}"


def validate_single_url(url: str, timeout_seconds: float) -> UrlCheckResult:
    is_well_formed, format_reason = is_well_formed_url(url)
    if not is_well_formed:
        return UrlCheckResult(url=url, is_valid=False, reason=format_reason)

    is_reachable, reachability_reason = check_url_reachable(url, timeout_seconds)
    return UrlCheckResult(
        url=url,
        is_valid=is_reachable,
        reason=reachability_reason,
    )


def validate_urls(urls: list[str], timeout_seconds: float, workers: int) -> list[UrlCheckResult]:
    if not urls:
        return []

    max_workers = max(1, min(workers, len(urls)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(lambda current_url: validate_single_url(current_url, timeout_seconds), urls))


def write_url_report(report_path: Path, urls: list[str], check_results: list[UrlCheckResult]) -> None:
    valid_urls = [result.url for result in check_results if result.is_valid]
    invalid_urls = [result.url for result in check_results if not result.is_valid]

    lines: list[str] = []
    lines.append(f"# Retrieved URLs -- {len(urls)}")
    lines.extend(urls)
    lines.append("")
    lines.append(f"# Valid URLs -- {len(valid_urls)}")
    lines.extend(valid_urls)
    lines.append("")
    lines.append(f"# Invalid URLs -- {len(invalid_urls)}")
    lines.extend(invalid_urls)
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")


def is_doi_url(url: str) -> bool:
    return urlparse(url).netloc.lower() in {"doi.org", "dx.doi.org"}


def sanitize_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "doi"


def fetch_bibtex_for_doi_url(doi_url: str, timeout_seconds: float) -> tuple[bool, str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (BibTeX-Exporter)",
        "Accept": "application/x-bibtex; charset=utf-8",
    }

    try:
        request = Request(doi_url, headers=headers, method="GET")
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = response.read()
            bibtex_text = payload.decode("utf-8", errors="replace").strip()
            if not bibtex_text:
                return False, "empty bibtex response"
            return True, bibtex_text
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


def export_reference_files(pdf_path: Path, doi_urls: list[str], timeout_seconds: float) -> tuple[int, int, int, Path]:
    output_folder = pdf_path.parent / pdf_path.stem
    output_folder.mkdir(parents=True, exist_ok=True)

    ris_exported_count = 0
    bib_exported_count = 0
    failed_count = 0

    for index, doi_url in enumerate(doi_urls, start=1):
        doi_suffix = urlparse(doi_url).path.lstrip("/") or f"doi_{index}"
        base_name = f"{index:03d}_{sanitize_filename(doi_suffix)}"

        ris_success, ris_payload = fetch_ris_for_doi_identifier(doi_suffix, timeout_seconds=timeout_seconds)
        if ris_success:
            ris_path = output_folder / f"{base_name}.ris"
            ris_path.write_text(ris_payload + "\n", encoding="utf-8")
            ris_exported_count += 1
            continue

        bib_success, bib_payload = fetch_bibtex_for_doi_url(doi_url, timeout_seconds=timeout_seconds)
        if bib_success:
            bib_path = output_folder / f"{base_name}.bib"
            bib_path.write_text(bib_payload + "\n", encoding="utf-8")
            bib_exported_count += 1
        else:
            failed_count += 1
            print(f"[RIS FAIL] {ris_payload} -> {doi_url}")
            print(f"[BIB FAIL] {bib_payload} -> {doi_url}")

    return ris_exported_count, bib_exported_count, failed_count, output_folder


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract URLs from a PDF file")
    parser.add_argument("pdf", type=Path, help="Path to input PDF")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Optional output file path (one URL per line)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate extracted URLs (format + reachability)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=8.0,
        help="Timeout in seconds for each URL check (default: 8.0)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=20,
        help="Number of parallel workers for URL checks (default: 20)",
    )
    parser.add_argument(
        "--status",
        choices=["ok", "bad"],
        help="Show only URL checks with this status (requires --check)",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        help="Save a text report with retrieved URLs plus valid/invalid sections",
    )
    parser.add_argument(
        "--export",
        choices=["bib"],
        help="Export references for valid DOI URLs (RIS when available, else BibTeX)",
    )
    args = parser.parse_args()

    if not args.pdf.exists():
        raise FileNotFoundError(f"PDF not found: {args.pdf}")

    urls = extract_urls_from_pdf(args.pdf)

    if args.output:
        args.output.write_text("\n".join(urls), encoding="utf-8")
        print(f"Saved {len(urls)} URLs to {args.output}")
    else:
        for url in urls:
            print(url)
        print(f"\nTotal URLs found: {len(urls)}")

    should_check = args.check or args.report_output is not None or args.export == "bib"
    check_results: list[UrlCheckResult] = []

    if should_check:
        print("\nChecking extracted URLs...")
        check_results = validate_urls(urls, timeout_seconds=args.timeout, workers=args.workers)
        valid_count = sum(1 for result in check_results if result.is_valid)
        invalid_count = len(check_results) - valid_count

        if args.status == "ok":
            filtered_results = [result for result in check_results if result.is_valid]
        elif args.status == "bad":
            filtered_results = [result for result in check_results if not result.is_valid]
        else:
            filtered_results = check_results

        for result in filtered_results:
            status = "OK" if result.is_valid else "BAD"
            print(f"[{status}] {result.reason} -> {result.url}")

        print(
            f"\nValidation summary: {valid_count} valid, {invalid_count} invalid, {len(check_results)} total"
        )
        if args.status:
            print(f"Displayed {len(filtered_results)} result(s) after --status {args.status} filter")

    if args.report_output:
        write_url_report(args.report_output, urls, check_results)
        print(f"Saved URL report to {args.report_output}")

    if args.export == "bib":
        valid_doi_urls = [result.url for result in check_results if result.is_valid and is_doi_url(result.url)]
        if not valid_doi_urls:
            print("No valid DOI URLs found to export.")
        else:
            ris_count, bib_count, failed_count, output_folder = export_reference_files(
                pdf_path=args.pdf,
                doi_urls=valid_doi_urls,
                timeout_seconds=args.timeout,
            )
            print(
                f"Exported {ris_count} RIS and {bib_count} BibTeX file(s) to {output_folder}"
                + (f" ({failed_count} failed)" if failed_count else "")
            )


if __name__ == "__main__":
    main()
