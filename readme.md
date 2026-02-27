# EPUB Reader for Windows (Python)

A lightweight desktop EPUB reader built with `PySide6`.

## Features

- Open `.epub` files from a native file picker
- Chapter list on the left
- Reading pane on the right
- Previous/Next chapter navigation

## Setup

1. Create/activate a Python environment (recommended Python 3.10+).
2. Install dependencies:

	```powershell
	pip install -r requirements.txt
	```

## Run

```powershell
python epub_reader.py
```

## Extract URLs from a PDF

```powershell
python extract_pdf_urls.py path\to\your_file.pdf
```

Save to a text file (one URL per line):

```powershell
python extract_pdf_urls.py path\to\your_file.pdf -o urls.txt
```

Validate extracted URLs (format + reachability):

```powershell
python extract_pdf_urls.py path\to\your_file.pdf --check
```

Set custom timeout per URL check:

```powershell
python extract_pdf_urls.py path\to\your_file.pdf --check --timeout 12
```

Speed up checks with parallel workers:

```powershell
python extract_pdf_urls.py path\to\your_file.pdf --check --workers 40
```

Show only valid URLs:

```powershell
python extract_pdf_urls.py path\to\your_file.pdf --check --status ok
```

Show only failed URLs:

```powershell
python extract_pdf_urls.py path\to\your_file.pdf --check --status bad
```

Save a text report with 3 sections: Retrieved URLs, Valid URLs, Invalid URLs:

```powershell
python extract_pdf_urls.py path\to\your_file.pdf --report-output url_report.txt
```

Note: DOI links split across line breaks in PDFs (for example `.../0034` on one line and `4257...` on the next) are automatically reconstructed.

Use **File → Open EPUB** or `Ctrl+O` to load a book.

## Build as Windows .exe (optional)

```powershell
pip install pyinstaller
pyinstaller --noconfirm --windowed --name EPUBReader epub_reader.py
```

The executable will be generated under `dist/EPUBReader/`.