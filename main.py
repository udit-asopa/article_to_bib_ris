from pathlib import Path
from typing import cast

import typer

from src.models import PipelineConfig, StatusFilter
from src.workflow import run_pipeline

app = typer.Typer(add_completion=False)
AUTO_REPORT_SENTINEL = "__AUTO_REPORT__"


@app.command()
def main(
    pdf: Path = typer.Argument(..., help="Path to input PDF"),
    output: Path | None = typer.Option(
        None,
        "-o",
        "--output",
        help="Optional output file path (one URL per line)",
    ),
    check: bool = typer.Option(
        False,
        "-c",
        "--check",
        help="Validate extracted URLs (format + reachability)",
    ),
    timeout: float = typer.Option(
        8.0,
        "-t",
        "--timeout",
        help="Timeout in seconds for each URL check",
    ),
    workers: int = typer.Option(
        20,
        "-w",
        "--workers",
        help="Number of parallel workers for URL checks",
    ),
    status: str | None = typer.Option(
        None,
        "-s",
        "--status",
        help="Show only URL checks with this status (ok or bad)",
    ),
    report_output: str | None = typer.Option(
        None,
        "-r",
        "--report-output",
        flag_value=AUTO_REPORT_SENTINEL,
        help="Save a text report with retrieved URLs plus valid/invalid sections",
    ),
    export: bool = typer.Option(
        False,
        "-e",
        "--export",
        help="Export references for valid URLs (RIS first, then BibTeX fallback)",
    ),
) -> None:
    if not pdf.exists():
        raise typer.BadParameter(f"PDF not found: {pdf}")

    if status not in {None, "ok", "bad"}:
        raise typer.BadParameter("--status must be 'ok' or 'bad'")

    resolved_report_output: Path | None
    resolved_check = check
    resolved_export = export
    if report_output is None:
        resolved_report_output = None
    elif report_output == AUTO_REPORT_SENTINEL:
        resolved_report_output = Path(f"{pdf.stem}.txt")
    elif report_output.startswith("-"):
        if report_output in {"--export", "-e"}:
            resolved_export = True
        if report_output in {"--check", "-c"}:
            resolved_check = True
        resolved_report_output = Path(f"{pdf.stem}.txt")
    else:
        resolved_report_output = Path(report_output)

    config = PipelineConfig(
        pdf=pdf,
        output=output,
        check=resolved_check,
        timeout=timeout,
        workers=workers,
        status=cast(StatusFilter | None, status),
        report_output=resolved_report_output,
        export=resolved_export,
    )
    run_pipeline(config)


if __name__ == "__main__":
    app()
