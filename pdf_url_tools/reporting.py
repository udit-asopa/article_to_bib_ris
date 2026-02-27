from pathlib import Path

from .models import StatusFilter, UrlCheckResult


def filter_check_results(results: list[UrlCheckResult], status: StatusFilter | None) -> list[UrlCheckResult]:
    if status == "ok":
        return [result for result in results if result.is_valid]
    if status == "bad":
        return [result for result in results if not result.is_valid]
    return results


def validation_counts(results: list[UrlCheckResult]) -> tuple[int, int]:
    valid_count = sum(1 for result in results if result.is_valid)
    invalid_count = len(results) - valid_count
    return valid_count, invalid_count


def format_validation_line(result: UrlCheckResult) -> str:
    status = "OK" if result.is_valid else "BAD"
    line = f"[{status}] {result.reason} -> {result.url}"
    if result.redirected_links:
        redirected_text = " | ".join(result.redirected_links)
        line += f" --> {redirected_text}"
    return line


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


def write_validation_log(log_path: Path, results: list[UrlCheckResult]) -> None:
    valid_count, invalid_count = validation_counts(results)
    lines: list[str] = [
        f"# Link Status Log -- {len(results)}",
        f"# OK -- {valid_count}",
        f"# BAD -- {invalid_count}",
        "",
    ]
    lines.extend(format_validation_line(result) for result in results)
    lines.append("")
    log_path.write_text("\n".join(lines), encoding="utf-8")
