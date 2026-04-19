import sys
import time
import shlex


def _escape_fts_term(term: str):
    escaped = term.replace('"', '""')
    return f'"{escaped}"'


def _build_and_fts_query(terms: list[str]):
    cleaned_terms = [s for s in (t.strip() for t in terms if t) if s]
    if not cleaned_terms:
        return ""
    return " AND ".join(f"{_escape_fts_term(term)}*" for term in cleaned_terms)


def _tokenize_query(query: str):
    try:
        lexer = shlex.shlex(query, posix=True)
        lexer.whitespace_split = True
        lexer.commenters = ""
        lexer.escape = ""
        return list(lexer)
    except ValueError:
        return query.split()


def parseQuery(query: str):
    parsed = {
        "path_terms": [],
        "content_terms": [],
        "general_terms": [],
        "raw_query": query,
    }

    if not query:
        return parsed
    

    for token in _tokenize_query(query):
        if ":" in token:
            qualifier, value = token.split(":", 1)
            qualifier = qualifier.lower().strip()
            value = value.strip()

            if not value:
                continue

            if qualifier == "path":
                parsed["path_terms"].append(value)
                continue

            if qualifier == "content":
                parsed["content_terms"].append(value)
                continue

        parsed["general_terms"].append(token)

    return parsed


def _build_search_statement(parsed_query: dict, limit: int):
    where_clauses = []
    params = []

    path_terms = parsed_query["path_terms"]
    print(f"Parsed query: {parsed_query}")
    content_terms = parsed_query["content_terms"]
    general_terms = parsed_query["general_terms"]

    for term in path_terms:
        where_clauses.append("LOWER(filepath) LIKE ?")
        params.append(f"%{term.lower()}%")

    content_fts_query = _build_and_fts_query(content_terms)
    general_fts_query = _build_and_fts_query(general_terms)

    fts_clauses = []
    if content_fts_query:
        fts_clauses.append(f"content:({content_fts_query})")
    if general_fts_query:
        fts_clauses.append(f"({general_fts_query})")

    fts_query = " AND ".join(fts_clauses)
    use_fts = bool(fts_query)

    if use_fts:
        where_clauses.append("file_index MATCH ?")
        params.append(fts_query)

    if not where_clauses:
        where_clauses.append("1 = 0")

    order_clause = (
        "ORDER BY bm25(file_index, 10.0, 4.0, 7.0, 1.0) ASC"
        if use_fts
        else "ORDER BY filename ASC"
    )

    sql = f"""
        SELECT filepath, filename, extension, preview
        FROM file_index
        WHERE {' AND '.join(where_clauses)}
        {order_clause}
        LIMIT ?
    """
    params.append(limit)
    return sql, params


def searchIndex(cursor, parsed_query: dict, limit: int = 10):
    sql, params = _build_search_statement(parsed_query, limit)
    print(f"Executing SQL: {sql} with params {params}")
    cursor.execute(sql, params)
    return cursor.fetchall()


def formatResults(results: list, query: str):
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

    parsed_query = parseQuery(query)
    results = searchIndex(cursor, parsed_query, limit)
    formatResults(results, query)


def _has_indexed_content(cursor):
    cursor.execute("SELECT COUNT(*) FROM file_index")
    return cursor.fetchone()[0] > 0


def search_as_you_type(cursor):
    if not _has_indexed_content(cursor):
        print("\nNo indexed content found. Index your real file system first using --path.")
        return

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
