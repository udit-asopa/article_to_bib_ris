import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

from bs4 import BeautifulSoup
from ebooklib import epub, ITEM_DOCUMENT
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
)


@dataclass
class Chapter:
    title: str
    html: str


class EpubBook:
    def __init__(self, path: Path):
        self.path = path
        self.chapters: List[Chapter] = []
        self._load()

    def _load(self) -> None:
        book = epub.read_epub(str(self.path))

        seen_names: set[str] = set()
        for spine_entry in book.spine:
            if not spine_entry:
                continue

            item_id = spine_entry[0]
            item = book.get_item_with_id(item_id)
            if not item or item.get_type() != ITEM_DOCUMENT:
                continue

            name = Path(item.get_name()).name
            if name in seen_names:
                continue

            html = item.get_body_content().decode("utf-8", errors="ignore")
            chapter_title = self._extract_title(html) or Path(name).stem or "Untitled"
            self.chapters.append(Chapter(title=chapter_title, html=html))
            seen_names.add(name)

        if self.chapters:
            return

        for item in book.get_items_of_type(ITEM_DOCUMENT):
            html = item.get_body_content().decode("utf-8", errors="ignore")
            fallback_name = Path(item.get_name()).name
            chapter_title = self._extract_title(html) or Path(fallback_name).stem or "Untitled"
            self.chapters.append(Chapter(title=chapter_title, html=html))

    @staticmethod
    def _extract_title(html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        heading = soup.find(["h1", "h2", "title"])
        if heading:
            text = heading.get_text(strip=True)
            if text:
                return text
        return ""


class EpubReaderWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EPUB Reader")
        self.resize(1100, 720)

        self.current_book: EpubBook | None = None
        self.current_index = -1

        self.chapter_list = QListWidget()
        self.chapter_list.itemSelectionChanged.connect(self._on_chapter_selection_changed)

        self.reader = QTextBrowser()
        self.reader.setOpenExternalLinks(True)
        self.reader.setReadOnly(True)

        self.book_label = QLabel("Open an EPUB file to start reading")
        self.book_label.setWordWrap(True)

        self.prev_button = QPushButton("Previous")
        self.prev_button.clicked.connect(self._prev_chapter)
        self.prev_button.setEnabled(False)

        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self._next_chapter)
        self.next_button.setEnabled(False)

        nav_layout = QHBoxLayout()
        nav_layout.addWidget(self.prev_button)
        nav_layout.addWidget(self.next_button)

        right_layout = QVBoxLayout()
        right_layout.addWidget(self.book_label)
        right_layout.addWidget(self.reader, stretch=1)
        right_layout.addLayout(nav_layout)

        content_layout = QHBoxLayout()
        content_layout.addWidget(self.chapter_list, stretch=1)

        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        content_layout.addWidget(right_widget, stretch=3)

        container = QWidget()
        container.setLayout(content_layout)
        self.setCentralWidget(container)

        self._create_menu()

    def _create_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")

        open_action = QAction("Open EPUB", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_epub)
        file_menu.addAction(open_action)

        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def _open_epub(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open EPUB File",
            "",
            "EPUB Files (*.epub)",
        )
        if not file_path:
            return

        try:
            self.current_book = EpubBook(Path(file_path))
        except Exception as error:
            QMessageBox.critical(self, "Error", f"Failed to open EPUB file:\n{error}")
            return

        if not self.current_book.chapters:
            QMessageBox.warning(self, "No Content", "No readable chapters found in this EPUB.")
            return

        self.chapter_list.clear()
        for chapter in self.current_book.chapters:
            self.chapter_list.addItem(QListWidgetItem(chapter.title))

        self.book_label.setText(f"Reading: {Path(file_path).name}")
        self.current_index = 0
        self.chapter_list.setCurrentRow(0)
        self._update_nav_buttons()

    def _on_chapter_selection_changed(self) -> None:
        row = self.chapter_list.currentRow()
        if row < 0 or not self.current_book:
            return

        self.current_index = row
        chapter = self.current_book.chapters[row]
        self.reader.setHtml(chapter.html)
        self._update_nav_buttons()

    def _prev_chapter(self) -> None:
        if not self.current_book:
            return
        new_index = self.current_index - 1
        if new_index >= 0:
            self.chapter_list.setCurrentRow(new_index)

    def _next_chapter(self) -> None:
        if not self.current_book:
            return
        new_index = self.current_index + 1
        if new_index < len(self.current_book.chapters):
            self.chapter_list.setCurrentRow(new_index)

    def _update_nav_buttons(self) -> None:
        if not self.current_book or self.current_index < 0:
            self.prev_button.setEnabled(False)
            self.next_button.setEnabled(False)
            return

        total = len(self.current_book.chapters)
        self.prev_button.setEnabled(self.current_index > 0)
        self.next_button.setEnabled(self.current_index < total - 1)


def main() -> None:
    app = QApplication(sys.argv)
    window = EpubReaderWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
