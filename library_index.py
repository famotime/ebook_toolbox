from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import sqlite3


INDEX_DB_FILENAME = "_file_index.sqlite3"
SUPPORTED_EBOOK_EXTENSIONS = (".epub", ".pdf", ".txt", ".mobi", ".azw3")
EXTENSION_PRIORITY = {ext: index for index, ext in enumerate(SUPPORTED_EBOOK_EXTENSIONS)}
SKIP_DIRS = {
    "System Volume Information",
    "$Recycle.Bin",
    "$RECYCLE.BIN",
    "Config.Msi",
    "Recovery",
    "Documents and Settings",
    "PerfLogs",
    "Program Files",
    "Program Files (x86)",
    "Windows",
}
QUICK_HASH_CHUNK_SIZE = 64 * 1024


@dataclass(frozen=True)
class IndexedFileRecord:
    path: Path
    name: str
    stem: str
    stem_norm: str
    ext: str
    ext_priority: int
    book_key: str
    size: int
    mtime: float
    quick_hash: str | None = None
    full_hash: str | None = None


def normalize_text(text: str) -> str:
    cleaned = re.sub(r"[^\u4e00-\u9fff\w]", "", text or "")
    return cleaned.lower()


def normalize_extension(extension: str) -> str:
    if not extension:
        return ""
    return extension.lower() if extension.startswith(".") else f".{extension.lower()}"


def build_book_key(title: str, extension: str) -> str:
    return f"{normalize_text(title)}|{normalize_extension(extension)}"


def get_index_db_path(root_dir: Path | str) -> Path:
    return Path(root_dir) / INDEX_DB_FILENAME


def is_valid_index_target(path: Path, allowed_extensions: tuple[str, ...] | None = None) -> bool:
    if not path.is_file():
        return False
    if path.name == INDEX_DB_FILENAME:
        return False
    if any(part.startswith("$") or part in SKIP_DIRS for part in path.parts):
        return False
    if allowed_extensions is None:
        return True
    return path.suffix.lower() in allowed_extensions


def ensure_index_schema(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            stem TEXT NOT NULL,
            stem_norm TEXT NOT NULL,
            ext TEXT NOT NULL,
            ext_priority INTEGER NOT NULL,
            book_key TEXT NOT NULL,
            size INTEGER NOT NULL,
            mtime REAL NOT NULL,
            quick_hash TEXT,
            full_hash TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_files_stem_lookup
        ON files(stem_norm, ext_priority, size DESC, mtime DESC)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_files_book_key
        ON files(book_key)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_files_size_hash
        ON files(size, quick_hash, full_hash)
        """
    )


def collect_index_rows(
    root_dir: Path | str,
    folders_to_update: list[str] | None = None,
    allowed_extensions: tuple[str, ...] | None = SUPPORTED_EBOOK_EXTENSIONS,
    recursive: bool = True,
) -> list[tuple[str, str, str, str, str, int, str, int, float]]:
    root_path = Path(root_dir)
    candidate_roots = [root_path]
    if folders_to_update:
        candidate_roots = [root_path / folder for folder in folders_to_update]

    rows = []
    for candidate_root in candidate_roots:
        if not candidate_root.exists():
            continue
        iterator = candidate_root.rglob("*") if recursive else candidate_root.glob("*")
        try:
            for path in iterator:
                try:
                    if not is_valid_index_target(path, allowed_extensions):
                        continue
                    resolved_path = path.resolve()
                    stat = resolved_path.stat()
                    extension = resolved_path.suffix.lower()
                    rows.append(
                        (
                            str(resolved_path),
                            resolved_path.name,
                            resolved_path.stem,
                            normalize_text(resolved_path.stem),
                            extension,
                            EXTENSION_PRIORITY.get(extension, len(EXTENSION_PRIORITY)),
                            build_book_key(resolved_path.stem, extension),
                            stat.st_size,
                            stat.st_mtime,
                        )
                    )
                except (PermissionError, OSError):
                    continue
        except Exception:
            continue
    return rows


def generate_file_index(
    root_dir: Path | str,
    folders_to_update: list[str] | None = None,
    allowed_extensions: tuple[str, ...] | None = SUPPORTED_EBOOK_EXTENSIONS,
    recursive: bool = True,
) -> Path:
    root_path = Path(root_dir)
    index_db_path = get_index_db_path(root_path)
    rows = collect_index_rows(root_path, folders_to_update, allowed_extensions, recursive)

    with closing(sqlite3.connect(index_db_path)) as conn:
        ensure_index_schema(conn)
        if folders_to_update:
            for folder in folders_to_update:
                folder_prefix = str((root_path / folder).resolve())
                conn.execute(
                    "DELETE FROM files WHERE path = ? OR path LIKE ?",
                    (folder_prefix, folder_prefix + "\\%"),
                )
        else:
            conn.execute("DELETE FROM files")

        conn.executemany(
            """
            INSERT INTO files(path, name, stem, stem_norm, ext, ext_priority, book_key, size, mtime)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()

    return index_db_path


def _record_from_row(row) -> IndexedFileRecord:
    return IndexedFileRecord(
        path=Path(row[0]),
        name=row[1],
        stem=row[2],
        stem_norm=row[3],
        ext=row[4],
        ext_priority=int(row[5]),
        book_key=row[6],
        size=int(row[7]),
        mtime=float(row[8]),
        quick_hash=row[9],
        full_hash=row[10],
    )


def load_index_records(
    root_dir: Path | str,
    allowed_extensions: tuple[str, ...] | None = None,
) -> list[IndexedFileRecord]:
    index_db_path = get_index_db_path(root_dir)
    if not index_db_path.exists() or index_db_path.stat().st_size == 0:
        return []

    query = (
        "SELECT path, name, stem, stem_norm, ext, ext_priority, book_key, size, mtime, quick_hash, full_hash "
        "FROM files"
    )
    params: tuple = ()
    if allowed_extensions:
        placeholders = ",".join("?" for _ in allowed_extensions)
        query += f" WHERE ext IN ({placeholders})"
        params = tuple(allowed_extensions)
    query += " ORDER BY path"

    with closing(sqlite3.connect(index_db_path)) as conn:
        ensure_index_schema(conn)
        rows = conn.execute(query, params).fetchall()

    return [_record_from_row(row) for row in rows]


def query_best_prefix_match(
    root_dir: Path | str,
    title: str,
    allowed_extensions: tuple[str, ...] | None = SUPPORTED_EBOOK_EXTENSIONS,
) -> Path | None:
    index_db_path = get_index_db_path(root_dir)
    if not index_db_path.exists() or index_db_path.stat().st_size == 0:
        return None

    title_norm = normalize_text(title)
    if not title_norm:
        return None

    query = (
        "SELECT path FROM files WHERE stem_norm LIKE ?"
    )
    params: list[str] = [f"{title_norm}%"]
    if allowed_extensions:
        placeholders = ",".join("?" for _ in allowed_extensions)
        query += f" AND ext IN ({placeholders})"
        params.extend(allowed_extensions)
    query += " ORDER BY ext_priority ASC, size DESC, mtime DESC LIMIT 1"

    with closing(sqlite3.connect(index_db_path)) as conn:
        ensure_index_schema(conn)
        row = conn.execute(query, tuple(params)).fetchone()
    return Path(row[0]) if row else None


def query_best_exact_book_match(
    root_dir: Path | str,
    title: str,
    extension: str,
) -> Path | None:
    index_db_path = get_index_db_path(root_dir)
    if not index_db_path.exists() or index_db_path.stat().st_size == 0:
        return None

    with closing(sqlite3.connect(index_db_path)) as conn:
        ensure_index_schema(conn)
        row = conn.execute(
            """
            SELECT path
            FROM files
            WHERE book_key = ?
            ORDER BY size DESC, mtime DESC
            LIMIT 1
            """,
            (build_book_key(title, extension),),
        ).fetchone()
    return Path(row[0]) if row else None


def calculate_quick_hash(file_path: Path | str, chunk_size: int = QUICK_HASH_CHUNK_SIZE) -> str:
    path = Path(file_path)
    file_size = path.stat().st_size
    hasher = hashlib.blake2b(digest_size=16)
    hasher.update(str(file_size).encode("utf-8"))
    with path.open("rb") as file_handle:
        head = file_handle.read(chunk_size)
        hasher.update(head)
        if file_size > chunk_size:
            seek_offset = max(file_size - chunk_size, 0)
            file_handle.seek(seek_offset)
            hasher.update(file_handle.read(chunk_size))
    return hasher.hexdigest()


def calculate_full_hash(file_path: Path | str, chunk_size: int = QUICK_HASH_CHUNK_SIZE) -> str:
    path = Path(file_path)
    hasher = hashlib.blake2b(digest_size=16)
    with path.open("rb") as file_handle:
        while chunk := file_handle.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def ensure_hashes_for_paths(
    root_dir: Path | str,
    paths: list[Path],
    include_full_hash: bool,
) -> dict[Path, tuple[str, str | None]]:
    index_db_path = get_index_db_path(root_dir)
    path_map = {path.resolve(): None for path in paths}
    if not path_map:
        return {}

    with closing(sqlite3.connect(index_db_path)) as conn:
        ensure_index_schema(conn)
        result: dict[Path, tuple[str, str | None]] = {}
        for path in path_map:
            row = conn.execute(
                "SELECT quick_hash, full_hash FROM files WHERE path = ?",
                (str(path),),
            ).fetchone()
            quick_hash = row[0] if row else None
            full_hash = row[1] if row else None
            if not quick_hash:
                quick_hash = calculate_quick_hash(path)
            if include_full_hash and not full_hash:
                full_hash = calculate_full_hash(path)
            if row:
                conn.execute(
                    "UPDATE files SET quick_hash = ?, full_hash = COALESCE(?, full_hash) WHERE path = ?",
                    (quick_hash, full_hash if include_full_hash else None, str(path)),
                )
            result[path] = (quick_hash, full_hash if include_full_hash else full_hash)
        conn.commit()
    return result


def files_share_content(first_path: Path | str, second_path: Path | str) -> bool:
    first = Path(first_path)
    second = Path(second_path)
    if not first.exists() or not second.exists():
        return False
    if first.stat().st_size != second.stat().st_size:
        return False
    first_quick = calculate_quick_hash(first)
    second_quick = calculate_quick_hash(second)
    if first_quick != second_quick:
        return False
    return calculate_full_hash(first) == calculate_full_hash(second)
