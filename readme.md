# PDF URL Parser

Extract URLs from PDF files, validate them, and export references (`.ris` / `.bib`) from DOI-linked sources.

## What it does

- Extracts URLs from PDF text content.
- Extracts embedded PDF hyperlink annotations.
- Reconstructs wrapped/broken links (including split DOI links).
- Validates links with status output and optional redirect display.
- Exports references into a PDF-stem folder (`.ris` first, `.bib` fallback).

## Setup

### Preferred (pixi)

```bash
pixi install
```

### Optional (plain pip)

```bash
pip install -r requirements.txt
```

## Basic usage

```bash
pixi run python main.py path/to/file.pdf
```

## Development checks

Format code:

```bash
pixi run format
```

Run lint/type checks:

```bash
pixi run lint
```

Without pixi:

```bash
python main.py path/to/file.pdf
```

## Common flags

- `-o, --output <file>`: save extracted URLs (one per line)
- `--check`: validate extracted URLs
- `--timeout <seconds>`: per-request timeout (default: `8.0`)
- `--workers <n>`: parallel workers for validation (default: `20`)
- `--status ok|bad`: show only OK or BAD validation lines
- `--report-output [file]`: save report (`Retrieved/Valid/Invalid` sections)
- `--export`: export references to `<pdf_stem>/`

## Examples

Extract + print:

```bash
pixi run python main.py REVIEW.pdf
```

Extract + save URLs:

```bash
pixi run python main.py REVIEW.pdf -o urls.txt
```

Validate with filtering:

```bash
pixi run python main.py REVIEW.pdf --check --status bad
```

Save report with custom filename:

```bash
pixi run python main.py REVIEW.pdf --check --report-output review_report.txt
```

Save report with default filename (`<pdf_stem>.txt`):

```bash
pixi run python main.py REVIEW.pdf --check --report-output
```

Export references:

```bash
pixi run python main.py REVIEW.pdf --check --export
```

Full flow:

```bash
pixi run python main.py REVIEW.pdf --check --report-output --export
```

## Export behavior

When `--export` is used, a folder named after the PDF stem is created (example: `REVIEW.pdf` -> `REVIEW/`).

Inside that folder:

- `.ris` files for DOI references where RIS is available
- `.bib` files for remaining DOI references (fallback)
- `link_status_log.txt` with validation summary/details
- report file (if `--report-output` is used)

## Notes

- Some URLs may return `403` to scripts but still be valid in browsers; those are treated as likely valid for known access-restricted patterns.
- Redirected links are shown in console output when detected.
- DOI links split across line breaks are reconstructed automatically.
