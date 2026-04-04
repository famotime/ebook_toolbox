from pathlib import Path

from lxml import html


def safe_filename(filename: str) -> str:
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, "_")
    if len(filename.encode("utf-8")) > 240:
        filename = filename[:200] + "..." + filename[-10:]
    return filename


def build_target_file_path(save_dir: Path | str, file_stem: str, extension: str) -> Path:
    save_dir = Path(save_dir)
    normalized_extension = extension if extension.startswith(".") else f".{extension}"
    return save_dir / f"{file_stem}{normalized_extension}"


def parse_booklist_html(page_content: str, base_url: str = "https://1lib.sk") -> tuple[str, list[dict[str, str]]]:
    tree = html.fromstring(page_content)

    title_nodes = tree.xpath("/html/head/title/text()")
    booklist_title = title_nodes[0].strip() if title_nodes else "未命名书单"

    books = []
    for element in tree.xpath("//z-bookcard"):
        title = _get_text(element, './/div[@slot="title"]/text()')
        author = _get_text(element, './/div[@slot="author"]/text()')
        book_id = element.get("id", "")

        if not title or not author or not book_id:
            continue

        download_path = element.get("download", "")
        download_url = f"{base_url}{download_path}" if download_path else ""

        books.append(
            {
                "title": title,
                "author": author,
                "book_id": book_id,
                "language": element.get("language", ""),
                "year": element.get("year", ""),
                "format": element.get("extension", ""),
                "download_url": download_url,
            }
        )

    return booklist_title, books


def find_local_library_match(book: dict[str, str], local_files_index: dict[tuple[str, str], Path]) -> Path | None:
    extension = book["format"].lower()
    normalized_extension = extension if extension.startswith(".") else f".{extension}"

    exact_key = (book["title"], normalized_extension)
    if exact_key in local_files_index:
        return local_files_index[exact_key]

    fallback_key = (safe_filename(book["title"]), normalized_extension)
    return local_files_index.get(fallback_key)


def _get_text(element, xpath: str) -> str:
    try:
        result = element.xpath(xpath)
        return result[0].strip() if result else ""
    except Exception:
        return ""
