from pathlib import Path
import os
import time
from datetime import datetime
import json

from .config import ignored_extensions, ignored_folders, text_extensions, image_extensions
from .file_processors import FileProcessorFactory, TextFileProcessor, ImageFileProcessor


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


def _path_contains_ignored_folder(path):
    return any(part in ignored_folders for part in path.parts)

def check_if_current_path_or_subdir_already_indexed(cursor, path):
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

    # Initialize file processor factory with strategies
    processor_factory = FileProcessorFactory()
    processor_factory.register_processor(TextFileProcessor(text_extensions))
    processor_factory.register_processor(ImageFileProcessor(image_extensions))

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

                # Skip if no processor can handle this file
                processor = processor_factory.get_processor(file_path)
                if processor is None:
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

                try:
                    # Process file using appropriate strategy
                    processed_data = processor_factory.process_file(file_path)
                    if processed_data is None:
                        continue

                    path_score = _compute_path_score(file_path, root_path)
                    accessed_at = datetime.fromtimestamp(file_path.stat().st_atime).isoformat(timespec="seconds")

                    # Insert into file_index with file_type
                    cursor.execute(
                        """
                        INSERT INTO file_index (filepath, filename, extension, content, preview, modified_at, file_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            processed_data.filepath,
                            processed_data.filename,
                            processed_data.extension,
                            processed_data.content,
                            processed_data.preview,
                            datetime.now(),
                            processed_data.file_type,
                        ),
                    )
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO file_path_scores (filepath, path_score, accessed_at)
                        VALUES (?, ?, ?)
                        """,
                        (processed_data.filepath, path_score, accessed_at),
                    )

                    # Store color metadata for image files
                    if processed_data.file_type == "image" and processed_data.metadata:
                        color_palette_json = json.dumps(processed_data.metadata.get("color_palette", []))
                        cursor.execute(
                            """
                            INSERT OR REPLACE INTO file_colors (filepath, file_type, dominant_color, dominant_color_name, dominant_color_hex, color_palette)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                processed_data.filepath,
                                processed_data.file_type,
                                str(processed_data.metadata.get("dominant_color", "")),
                                processed_data.metadata.get("dominant_color_name", ""),
                                processed_data.metadata.get("dominant_color_hex", ""),
                                color_palette_json,
                            ),
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
