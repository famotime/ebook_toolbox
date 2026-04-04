import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import collect_local_ebooks
from download_from_zlibrary_booklist import BooklistDownloader, build_local_files_index
from zlibrary_booklist_workflow import (
    build_target_file_path,
    find_local_library_match,
    parse_booklist_html,
)


FIXTURE_PATH = Path(__file__).resolve().parent.parent / "temp" / "译文经典 Booklist _ Z-Library.html"


class ZlibraryBooklistWorkflowTests(unittest.TestCase):
    class _LoggerStub:
        def info(self, *args, **kwargs):
            return None

        def warning(self, *args, **kwargs):
            return None

        def error(self, *args, **kwargs):
            return None

    def test_parse_booklist_html_extracts_title_and_books_from_fixture(self):
        html_content = FIXTURE_PATH.read_text(encoding="utf-8")

        booklist_title, books = parse_booklist_html(html_content)

        self.assertEqual(booklist_title, "译文经典 — Booklist | Z-Library")
        self.assertGreater(len(books), 5)
        self.assertEqual(books[0]["title"], "局外人")
        self.assertEqual(books[0]["author"], "加缪")
        self.assertEqual(books[0]["book_id"], "5900906")
        self.assertEqual(books[0]["format"], "pdf")
        self.assertEqual(books[0]["download_url"], "https://1lib.sk/dl/5900906/f42476")

    def test_parse_booklist_html_skips_books_missing_required_fields(self):
        html_content = """
        <html>
          <head><title>测试书单</title></head>
          <body>
            <z-bookcard id="1" extension="epub" download="/dl/1/a">
              <div slot="title">有效书籍</div>
              <div slot="author">作者甲</div>
            </z-bookcard>
            <z-bookcard id="2" extension="pdf" download="/dl/2/b">
              <div slot="title">缺作者</div>
            </z-bookcard>
            <z-bookcard extension="mobi" download="/dl/3/c">
              <div slot="title">缺ID</div>
              <div slot="author">作者乙</div>
            </z-bookcard>
          </body>
        </html>
        """

        booklist_title, books = parse_booklist_html(html_content)

        self.assertEqual(booklist_title, "测试书单")
        self.assertEqual(
            books,
            [{
                "title": "有效书籍",
                "author": "作者甲",
                "book_id": "1",
                "language": "",
                "year": "",
                "format": "epub",
                "download_url": "https://1lib.sk/dl/1/a",
            }],
        )

    def test_find_local_library_match_prefers_exact_title_then_safe_filename(self):
        exact_match = find_local_library_match(
            book={"title": "局外人", "format": "pdf"},
            local_files_index={
                ("局外人", ".pdf"): Path("D:/books/局外人.pdf"),
                ("局外人_译文经典_", ".pdf"): Path("D:/books/fallback.pdf"),
            },
        )
        fallback_match = find_local_library_match(
            book={"title": "局外人/译文经典?", "format": "pdf"},
            local_files_index={
                ("局外人_译文经典_", ".pdf"): Path("D:/books/fallback.pdf"),
            },
        )

        self.assertEqual(exact_match, Path("D:/books/局外人.pdf"))
        self.assertEqual(fallback_match, Path("D:/books/fallback.pdf"))

    def test_build_target_file_path_avoids_double_dot_extensions(self):
        file_path = build_target_file_path(
            save_dir=Path("D:/downloads"),
            file_stem="局外人",
            extension=".pdf",
        )

        self.assertEqual(file_path, Path("D:/downloads/局外人.pdf"))

    def test_download_book_skips_books_already_marked_downloaded(self):
        with TemporaryDirectory() as temp_dir:
            downloader = BooklistDownloader.__new__(BooklistDownloader)
            downloader.downloaded_books = {"局外人"}
            downloader.total_books = 3
            downloader.logger = self._LoggerStub()
            downloader.save_dir = Path(temp_dir)
            downloader.use_local_index = False
            downloader.local_files_index = {}

            result = downloader.download_book({"title": "局外人", "format": "pdf", "book_id": "1"})

        self.assertTrue(result)

    def test_build_local_files_index_reads_sqlite_index(self):
        with TemporaryDirectory() as temp_dir:
            library_dir = Path(temp_dir)
            epub_file = library_dir / "局外人.epub"
            pdf_file = library_dir / "局外人.pdf"
            epub_file.write_bytes(b"epub content")
            pdf_file.write_bytes(b"pdf content")

            collect_local_ebooks.generate_file_list(library_dir)

            local_files_index = build_local_files_index(library_dir)

            self.assertEqual(local_files_index[("局外人", ".epub")].resolve(), epub_file.resolve())
            self.assertEqual(local_files_index[("局外人", ".pdf")].resolve(), pdf_file.resolve())
            self.assertFalse((library_dir / "_file_list.txt").exists())

    def test_build_local_files_index_and_match_use_normalized_book_key(self):
        with TemporaryDirectory() as temp_dir:
            library_dir = Path(temp_dir)
            epub_file = library_dir / "Clean-Code（第二版）.epub"
            epub_file.write_bytes(b"epub content")

            collect_local_ebooks.generate_file_list(library_dir)
            local_files_index = build_local_files_index(library_dir)

            matched = find_local_library_match(
                {"title": "Clean Code", "format": "epub"},
                local_files_index,
            )

            self.assertEqual(matched.resolve(), epub_file.resolve())


if __name__ == "__main__":
    unittest.main()
