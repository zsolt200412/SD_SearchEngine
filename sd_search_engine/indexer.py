from pathlib import Path
import os
import time
from datetime import datetime

from .config import ignored_extensions, ignored_folders, text_extensions


def _path_contains_ignored_folder(path: Path) -> bool:
    return any(part in ignored_folders for part in path.parts)


def crawl_and_index(cursor, conn, root_dir: str, print_paths: bool = False, md: bool = False):
    subdirs = []
    files_indexed = 0
    errors = 0

    if root_dir is None:
        return

    cursor.execute("SELECT path FROM stored_directories WHERE path = ?", (root_dir,))
    if cursor.fetchone() is not None:
        print(f"Path already indexed: {root_dir}")
        return

    root_path = Path(root_dir)
    if not root_path.exists():
        print(f"Error: Path does not exist: {root_dir}")
        raise SystemExit(1)
    if not root_path.is_dir():
        print(f"Error: Path is not a directory: {root_dir}")
        raise SystemExit(1)

    start_time = time.time()

    def _on_walk_error(err):
        nonlocal errors
        errors += 1
        print(f"Warning: Error accessing directory: {err}")

    for current_root, dirs, files in os.walk(root_path, topdown=True, onerror=_on_walk_error):
        try:
            current_root_path = Path(current_root)

            dirs[:] = [d for d in dirs if d not in ignored_folders]

            for d in dirs:
                subdirs.append(str(current_root_path / d))

            for filename in files:
                file_path = current_root_path / filename

                if _path_contains_ignored_folder(file_path):
                    continue

                if file_path.suffix.lower() in ignored_extensions:
                    continue

                files_indexed += 1
                if print_paths:
                    if md:
                        size = file_path.stat().st_size
                        modified = datetime.fromtimestamp(file_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                        print(f"{file_path.name:<50} | Size: {size:>10,} bytes | Modified: {modified}")
                    else:
                        print(file_path)
                else:
                    if files_indexed % 10 == 0:
                        print(f"Indexed {files_indexed} files...")
                        print(f"Encountered {errors} errors so far...")

                content = ""
                preview = ""
                if file_path.suffix.lower() in text_extensions:
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                            preview = content[:50]
                    except Exception as e:
                        print(f"Warning: Could not read {file_path}: {e}")

                try:
                    cursor.execute(
                        """
                        INSERT INTO file_index (filepath, filename, extension, content, preview, modified_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (str(file_path), file_path.name, file_path.suffix, content, preview, datetime.now()),
                    )
                    conn.commit()
                except Exception as e:
                    print(f"Warning: Could not insert file metadata: {e}")
        except PermissionError:
            errors += 1
            print(f"Warning: Permission denied: {current_root}")
        except (OSError, IOError) as e:
            errors += 1
            print(f"Warning: Error accessing {current_root}: {e}")
        except Exception as e:
            errors += 1
            print(f"Warning: Unexpected error for {current_root}: {e}")

    try:
        cursor.execute("INSERT INTO stored_directories (path) VALUES (?)", (root_dir,))
        for subdir in subdirs:
            cursor.execute("INSERT INTO stored_directories (path) VALUES (?)", (subdir,))
        conn.commit()
    except Exception as e:
        print(f"Warning: Could not store indexed path: {e}")

    elapsed_time = time.time() - start_time
    print(f"Finished indexing {files_indexed} files with {errors} errors in {elapsed_time:.2f} seconds.")
