from pathlib import Path

from .exporting import export_reference_files
from .extraction import extract_urls_from_pdf
from .models import PipelineConfig, UrlCheckResult
from .reporting import (
    filter_check_results,
    format_validation_line,
    validation_counts,
    write_url_report,
    write_validation_log,
)
from .validation import validate_urls


def _print_retrieved_urls(urls: list[str], output_path) -> None:
    if output_path:
        output_path.write_text("\n".join(urls), encoding="utf-8")
        print(f"Saved {len(urls)} URLs to {output_path}")
        return

    for url in urls:
        print(url)
    print(f"\nTotal URLs found: {len(urls)}")


def _should_validate(config: PipelineConfig) -> bool:
    return config.check or config.report_output is not None or config.export


def _print_validation_results(results: list[UrlCheckResult], status_filter) -> None:
    filtered_results = filter_check_results(results, status_filter)
    for result in filtered_results:
        print(format_validation_line(result))

    valid_count, invalid_count = validation_counts(results)
    print(f"\nValidation summary: {valid_count} valid, {invalid_count} invalid, {len(results)} total")
    if status_filter:
        print(f"Displayed {len(filtered_results)} result(s) after --status {status_filter} filter")


def _run_reference_export(config: PipelineConfig, check_results: list[UrlCheckResult]) -> None:
    if not config.export:
        return

    valid_urls = [result.url for result in check_results if result.is_valid]
    if not valid_urls:
        print("No valid URLs found to export references.")
        return

    ris_count, bib_count, failed_count, resolve_failed_count, output_folder = export_reference_files(
        pdf_path=config.pdf,
        source_urls=valid_urls,
        timeout_seconds=config.timeout,
    )
    details: list[str] = []
    if failed_count:
        details.append(f"{failed_count} export failed")
    if resolve_failed_count:
        details.append(f"{resolve_failed_count} DOI unresolved")
    suffix = f" ({', '.join(details)})" if details else ""
    print(f"Exported {ris_count} RIS and {bib_count} BibTeX file(s) to {output_folder}{suffix}")


def _export_folder_path(pdf_path: Path) -> Path:
    folder_path = pdf_path.parent / pdf_path.stem
    folder_path.mkdir(parents=True, exist_ok=True)
    return folder_path


def _resolve_report_path(config: PipelineConfig, export_folder: Path | None) -> Path | None:
    if not config.report_output:
        return None
    if export_folder is None:
        return config.report_output
    return export_folder / config.report_output.name


def run_pipeline(config: PipelineConfig) -> None:
    export_folder = _export_folder_path(config.pdf) if config.export else None
    urls = extract_urls_from_pdf(config.pdf)
    _print_retrieved_urls(urls, config.output)

    check_results: list[UrlCheckResult] = []
    if _should_validate(config):
        print("\nChecking extracted URLs...")
        check_results = validate_urls(urls, timeout_seconds=config.timeout, workers=config.workers)
        _print_validation_results(check_results, config.status)

    if export_folder is not None and check_results:
        log_path = export_folder / "link_status_log.txt"
        write_validation_log(log_path, check_results)
        print(f"Saved status log to {log_path}")

    report_path = _resolve_report_path(config, export_folder)
    if report_path:
        write_url_report(report_path, urls, check_results)
        print(f"Saved URL report to {report_path}")

    _run_reference_export(config, check_results)
