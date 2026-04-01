import sys
import time


def display_search_results(cursor, query: str, limit: int = 10):
    if not query:
        return

    exact = query
    cursor.execute(
        """
        SELECT filepath, filename, extension, preview
        FROM file_index
        WHERE filename MATCH ? OR content MATCH ?
        ORDER BY (filename = ?) DESC, bm25(file_index, 10.0, 4.0, 7.0, 1.0) ASC
        LIMIT ?
        """,
        (query + "*", query + "*", exact, limit),
    )

    results = cursor.fetchall()
    print(f"\n--- Results for '{query}' ({len(results)} found) ---")

    if results:
        for i, (filepath, filename, extension, preview) in enumerate(results, 1):
            preview_text = preview[:60].replace("\n", " ") if preview else "No preview"
            print(f"{i}. {filename:<40} | {extension:<6} | {preview_text}...")
    else:
        print("No results found.")


def search_as_you_type(cursor):
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

                if key == b"\x03":
                    raise KeyboardInterrupt

                if key == b"\x08":
                    query = query[:-1]
                    continue

                if key == b"\r":
                    print()
                    continue

                try:
                    char = key.decode("utf-8", errors="ignore")
                    if char and char.isprintable():
                        query += char
                        display_search_results(cursor, query)
                        print()
                except:
                    pass
            else:
                time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n\nSearch cancelled.")
    except Exception as e:
        print(f"\nError during search: {e}")
