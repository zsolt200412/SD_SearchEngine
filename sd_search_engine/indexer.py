from pathlib import Path
import os
import time
from datetime import datetime

from .config import ignored_extensions, ignored_folders, text_extensions


def _clamp(value: float, minimum: float, maximum: float):
    return max(minimum, min(maximum, value))


def _compute_path_score(file_path: Path, root_path: Path):
    directory_weights = {
        "src": 0.10,
        "app": 0.08,
        "lib": 0.07,
        "docs": 0.05,
        "tests": -0.05,
        "test": -0.05,
        "build": -0.10,
        "dist": -0.10,
        "node_modules": -0.25,
        ".git": -0.25,
        "__pycache__": -0.20,
        "venv": -0.20,
        ".venv": -0.20,
    }
    extension_bonus = {
        ".cpp": 0.10,
        ".py": 0.10,
        ".md": 0.03,
        ".json": 0.02,
    }

    try:
        relative = file_path.relative_to(root_path)
        directory_parts = relative.parts[:-1]
    except ValueError:
        directory_parts = file_path.parts[:-1]

    base_score = 0.50

    # Weight calculated based on directory
    dir_weight_sum = 0.0
    for part in directory_parts:
        dir_weight_sum += directory_weights.get(part.lower(), 0.0)
    dir_weight_sum = _clamp(dir_weight_sum, -0.25, 0.25)

    # Weight based on depth (more shallow = higher score)
    depth = len(directory_parts)
    depth_bonus = max(0.0, 0.20 - 0.015 * depth)

    # Weight based on file extension
    ext_bonus = extension_bonus.get(file_path.suffix.lower(), 0.0)

    final_score = base_score + dir_weight_sum + depth_bonus + ext_bonus
    return _clamp(final_score, 0.0, 1.0)


def _path_contains_ignored_folder(path: Path) -> bool:
    return any(part in ignored_folders for part in path.parts)

def check_if_current_path_or_subdir_already_indexed(cursor, path: str) -> bool:
    cursor.execute("SELECT path FROM stored_directories WHERE path = ?", (path,))
    if cursor.fetchone() is not None:
        return True

    cursor.execute("SELECT path FROM stored_directories")
    indexed_paths = [row[0] for row in cursor.fetchall()]
    return any(path.startswith(indexed_path) for indexed_path in indexed_paths)


def crawl_and_index(cursor, conn, root_dir: str, print_paths: bool = False, md: bool = False):
    subdirs = []
    files_indexed = 0
    errors = 0

    # --path is optinal, so if it's not provided we just return without doing anything
    if root_dir is None:
        return

    if check_if_current_path_or_subdir_already_indexed(cursor, root_dir):
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

            dirs[:] = [d for d in dirs if d not in ignored_folders and not os.path.islink(current_root_path / d)]

            for d in dirs:
                subdirs.append(str(current_root_path / d))

            for filename in files:
                file_path = current_root_path / filename

                if os.path.islink(file_path):
                    continue

                if _path_contains_ignored_folder(file_path):
                    continue

                if file_path.suffix.lower()  not in text_extensions:
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
                        print(f'Indexed {files_indexed} files, errors: {errors}, elapsed time: {time.time() - start_time:.2f} seconds, speed: {files_indexed / (time.time() - start_time):.2f} files/sec', end='\r')

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
                    path_score = _compute_path_score(file_path, root_path)
                    accessed_at = datetime.fromtimestamp(file_path.stat().st_atime).isoformat(timespec="seconds")

                    cursor.execute(
                        """
                        INSERT INTO file_index (filepath, filename, extension, content, preview, modified_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (str(file_path), file_path.name, file_path.suffix, content, preview, datetime.now()),
                    )
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO file_path_scores (filepath, path_score, accessed_at)
                        VALUES (?, ?, ?)
                        """,
                        (str(file_path), path_score, accessed_at),
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
