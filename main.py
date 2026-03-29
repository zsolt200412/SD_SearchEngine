from pathlib import Path
import os
import sys
import argparse
from datetime import datetime
import sqlite3
import time

ignored_extensions = [".exe", ".dll", ".git", ".bin"]

def get_user_input():
    parser = argparse.ArgumentParser(description='My script description')
    parser.add_argument('path', help='Root directory')
    parser.add_argument('--print', action='store_true', help='Print file paths')
    parser.add_argument('--md', action='store_true', help='Print metadata')
    return parser.parse_args()

def crawl_and_index(args):
    subdirs = []
    cursor.execute('SELECT path FROM stored_directories WHERE path = ?', (args.path,))
    if cursor.fetchone() is not None:
        print(f'Path already indexed: {args.path}')
        return
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
            if file.is_dir():
                subdirs.append(str(file))
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
    
    cursor.execute('INSERT INTO stored_directories (path) VALUES (?)', (args.path,))
    for subdir in subdirs:
        cursor.execute('INSERT INTO stored_directories (path) VALUES (?)', (subdir,))
    conn.commit()

def init_db():
    conn = sqlite3.connect('file_metadata.db')
    cursor = conn.cursor()
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS stored_directories (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   path TEXT NOT NULL UNIQUE
               )
    ''')
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

def display_search_results(query):
    """Display search results for a query"""
    if not query:
        return
    
    cursor.execute('''
        SELECT filepath, filename, extension, preview 
        FROM file_index 
        WHERE filename MATCH ? OR content MATCH ?
        LIMIT 5
    ''', (query + '*', query + '*'))
    
    results = cursor.fetchall()
    print(f"\n--- Results for '{query}' ({len(results)} found) ---")
    
    if results:
        for i, (filepath, filename, extension, preview) in enumerate(results, 1):
            preview_text = preview[:60].replace('\n', ' ') if preview else "No preview"
            print(f"{i}. {filename:<40} | {extension:<6} | {preview_text}...")
    else:
        print("No results found.")

def search_as_you_type():
    """Real-time search as user types each character"""
    print("\n=== Search As You Type ===")
    print("Type to search in real-time (Backspace to delete, Ctrl+C to exit)\n")
    
    query = ""
    
    try:
        import msvcrt
        while True:
            sys.stdout.write(f"\rSearch: {query:<50}")
            sys.stdout.flush()
            
            if msvcrt.kbhit():
                key = msvcrt.getch()
                
                if key == b'\x03':
                    raise KeyboardInterrupt
                
                if key == b'\x08':
                    query = query[:-1]
                    continue
                
                if key == b'\r':  # Enter key
                    print()
                    continue
                
                try:
                    char = key.decode('utf-8', errors='ignore')
                    if char and char.isprintable():
                        query += char
                        display_search_results(query)
                        print()
                except:
                    pass
            else:
                time.sleep(0.01)
    
    except KeyboardInterrupt:
        print("\n\nSearch cancelled.")
    except Exception as e:
        print(f"\nError during search: {e}")

def _main__():
    global conn, cursor
    conn, cursor = init_db()
    args = get_user_input()
    print(f'Root directory: {args.path}')
    crawl_and_index(args)

    search_as_you_type()

    conn.close()

if __name__ == "__main__":
    _main__()