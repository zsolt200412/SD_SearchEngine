from pathlib import Path
import os
import argparse
from datetime import datetime
import sqlite3

ignored_extensions = [".exe", ".dll", ".git", ".bin"]

def get_user_input():
    parser = argparse.ArgumentParser(description='My script description')
    parser.add_argument('path', help='Root directory')
    parser.add_argument('--print', action='store_true', help='Print file paths')
    parser.add_argument('--md', action='store_true', help='Print metadata')
    return parser.parse_args()

def crawl_and_index(args):
    try:
        root_path = Path(args.path)
        if not root_path.exists():
            print(f'Error: Path does not exist: {args.path}')
            exit(1)
        if not root_path.is_dir():
            print(f'Error: Path is not a directory: {args.path}')
            exit(1)
    except Exception as e:
        print(f'Error accessing root path: {e}')
        exit(1)

    root_path = Path(args.path)
    for file in root_path.rglob("*"):
        try:
            if file.is_file():
                if file.suffix in ignored_extensions:
                    continue
                if args.print:
                    if args.md:
                        # Print with metadata
                        size = file.stat().st_size
                        modified = datetime.fromtimestamp(file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                        print(f'{file.name:<50} | Size: {size:>10,} bytes | Modified: {modified}')
                    else:
                        print(file)

                content = ""
                preview = ""
                if file.suffix in ['.txt', '.md', '.py', '.java', '.c', '.cpp']:
                    try:
                        with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            preview = content[:50]  # Get the first 50 characters for preview
                    except Exception as e:
                        print(f'Warning: Could not read {file}: {e}')

                cursor.execute('''
                    INSERT INTO file_index (filepath, filename, extension, content, preview, modified_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (str(file), file.name, file.suffix, content, preview, datetime.now()))
                conn.commit()
        except PermissionError:
            print(f'Warning: Permission denied: {file}')
        except (OSError, IOError) as e:
            print(f'Warning: Error accessing {file}: {e}')
        except Exception as e:
            print(f'Warning: Unexpected error for {file}: {e}')


def init_db():
    conn = sqlite3.connect('file_metadata.db')
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS file_index')
    cursor.execute('''
    CREATE VIRTUAL TABLE IF NOT EXISTS file_index USING fts5(
    filepath UNINDEXED,   -- Path to the file (UNINDEXED because we don't search 'C:/')
    filename,             -- The name of the file
    extension,            -- File type (e.g., .txt, .pdf)
    content,              -- The full text extracted from the file
    preview,              -- The first 3 lines/100 chars for the UI [cite: 43, 51]
    modified_at UNINDEXED -- Timestamp for incremental indexing 
);
    ''')
    conn.commit()
    return conn, cursor

def _main__():
    global conn, cursor
    conn, cursor = init_db()
    args = get_user_input()
    print(f'Root directory: {args.path}')
    crawl_and_index(args)
    cursor.execute('SELECT * FROM file_index')
    rows = cursor.fetchall()
    # Print filename, extension, and preview for verification
    # for row in rows:
    #     print(f"Filename: {row[1]}, Extension: {row[2]}, Preview: {row[4]}...")
    while True:
        query = input("Enter file name to search (or 'exit' to quit): ")
        if query.lower() == 'exit':
            break
        cursor.execute('SELECT filepath, filename, extension, preview FROM file_index WHERE filename MATCH ?', (query,))
        results = cursor.fetchall()
        if results:
            print(f"Found {len(results)} results:")
            for filepath, filename, extension, preview in results:
                print(f"File: {filename} ({extension}) - Preview: {preview}...")
        else:
            print("No results found.")

if __name__ == "__main__":
    _main__()