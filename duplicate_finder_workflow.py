from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
from typing import Dict, List, Union


@dataclass
class FileInfoRecord:
    path: Path
    size: int
    name: str


def generate_index_name(path: Path) -> str:
    full_path = str(path.resolve())
    illegal_chars = '<>:"/\\|?*'
    for char in illegal_chars:
        full_path = full_path.replace(char, "_")

    if len(full_path) > 100:
        return hashlib.md5(str(path.resolve()).encode("utf-8")).hexdigest()

    return full_path


def select_preferred_file(
    files: List[FileInfoRecord],
    include_path: Union[str, List[str]] = None,
    exclude_path: Union[str, List[str]] = None,
    shortest_path: bool = True,
) -> Path:
    candidates = files.copy()

    exclude_paths = [exclude_path] if isinstance(exclude_path, str) else exclude_path
    include_paths = [include_path] if isinstance(include_path, str) else include_path

    if exclude_paths:
        candidates = [
            file_info
            for file_info in candidates
            if not any(excluded in str(file_info.path) for excluded in exclude_paths if excluded)
        ]
        if candidates:
            files = candidates

    if include_paths:
        included = [
            file_info
            for file_info in files
            if any(included_path in str(file_info.path) for included_path in include_paths if included_path)
        ]
        if included:
            files = included

    paths = [file_info.path for file_info in files]
    selector = min if shortest_path else max
    return selector(paths, key=lambda path: len(str(path)))


def format_duplicate_report(
    root_dir: Path,
    duplicates: Dict[str, List[Path]],
    generated_at: str | None = None,
) -> str:
    generated_at = generated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# 重复文件报告",
        "",
        f"搜索目录: {root_dir}",
        f"生成时间: {generated_at}",
        "",
    ]

    for kept_file, duplicate_files in duplicates.items():
        lines.append(f"- [ ] {kept_file}")
        for duplicate_file in duplicate_files:
            lines.append(f"- [x] {duplicate_file}")
        lines.extend(["", "---", ""])

    return "\n".join(lines).rstrip() + "\n"


def parse_checked_paths_from_report(report_content: str) -> list[str]:
    checked_paths = []
    for line in report_content.splitlines():
        if line.startswith("- [x]"):
            checked_paths.append(line.split("] ", 1)[1].strip())
    return checked_paths
