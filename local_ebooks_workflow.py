from pathlib import Path


SINGLE_BOOK_DIRNAME = "单本好书"
FOUND_SECTION_HEADER = "已找到并复制的文件："


def resolve_output_dir(
    base_output_dir: Path | str,
    list_path: Path | str,
    book_names: list[str],
    from_clipboard: bool,
    clipboard_dir_name: str | None = None,
) -> Path:
    base_output_dir = Path(base_output_dir)
    list_path = Path(list_path)

    if len(book_names) <= 1:
        return base_output_dir / SINGLE_BOOK_DIRNAME

    if from_clipboard:
        if not clipboard_dir_name:
            raise ValueError("剪贴板模式缺少目录名")
        return list_path / clipboard_dir_name

    return base_output_dir / list_path.stem


def extract_previously_copied_books(result_content: str) -> set[str]:
    if FOUND_SECTION_HEADER not in result_content:
        return set()

    copied_section = result_content.split(FOUND_SECTION_HEADER, 1)[1].split("\n\n", 1)[0]
    books = set()
    for line in copied_section.strip().splitlines():
        if line.startswith("- 《") and "》" in line:
            book_name = line.split("《", 1)[1].split("》", 1)[0]
            books.add(book_name)
    return books


def extract_existing_copied_section(result_content: str) -> str:
    if FOUND_SECTION_HEADER not in result_content:
        return ""

    parts = result_content.split(FOUND_SECTION_HEADER, 1)
    if len(parts) < 2:
        return ""
    return parts[1].split("\n\n", 1)[0].strip()


def classify_list_file(file_path: Path | str, processed_files: set[str], existing_dirs: set[str]) -> str:
    file_path = Path(file_path)
    if str(file_path) in processed_files:
        return "processed"
    if file_path.stem.lower() in existing_dirs:
        return "existing_dir"
    return "pending"
