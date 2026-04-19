import sys
import time


def _escape_fts_query(query: str) -> str:
    return f'"{query}"'


def parseQuery(query: str) -> tuple:
    if not query:
        return "", ""
    escaped_query = _escape_fts_query(query)
    return escaped_query, query


def searchIndex(cursor, escaped_query: str, exact_query: str, limit: int = 10) -> list:
    cursor.execute(
        """
        SELECT filepath, filename, extension, preview
        FROM file_index
        WHERE filename MATCH ? OR content MATCH ?
        ORDER BY (filename = ?) DESC, bm25(file_index, 10.0, 4.0, 7.0, 1.0) ASC
        LIMIT ?
        """,
        (escaped_query + "*", escaped_query + "*", exact_query, limit),
    )
    return cursor.fetchall()


def formatResults(results: list, query: str) -> None:
    print(f"\n--- Results for {query} ({len(results)} found) ---")

    if not results:
        print("No results found.")
        return

    for i, (filepath, filename, extension, preview) in enumerate(results, 1):
        lower_filename = filename.lower()
        lower_query = query.lower()
        filename_idx = lower_filename.find(lower_query)

        if filename_idx != -1:
            highlighted_filename = filename.replace(
                filename[filename_idx:filename_idx + len(query)],
                filename[filename_idx:filename_idx + len(query)]
            )
        else:
            highlighted_filename = filename

        if preview:
            lower_preview = preview.lower()
            idx = lower_preview.find(lower_query)

            if idx != -1:
                start = max(idx - 30, 0)
                end = min(idx + len(query) + 30, len(preview))
                snippet = preview[start:end]

                highlighted = snippet.replace(
                    preview[idx:idx + len(query)],
                    preview[idx:idx + len(query)]
                )
                preview_text = highlighted.replace("\n", " ")
            else:
                preview_text = preview[:60].replace("\n", " ")
        else:
            preview_text = "No preview"

        print(f"{i:<2}. {highlighted_filename:<40} | {extension:<6} | {preview_text}...")


def display_search_results(cursor, query: str, limit: int = 10):
    if not query:
        return

    escaped_query, original_query = parseQuery(query)
    results = searchIndex(cursor, escaped_query, original_query, limit)
    formatResults(results, original_query)


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
                        print(query)
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
