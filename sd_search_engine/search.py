import sys
import time
import shlex
from datetime import datetime


def _order_by_relevance(use_fts: bool):
    score_expr = "COALESCE(file_path_scores.path_score, 0.50)"
    if use_fts:
        return f"ORDER BY bm25(file_index, 10.0, 4.0, 7.0, 1.0) ASC, {score_expr} DESC"
    return f"ORDER BY {score_expr} DESC, file_index.filename ASC"


def _order_by_alphabetical(use_fts: bool):
    return "ORDER BY file_index.filename ASC, file_index.filepath ASC"


def _order_by_date_accessed(use_fts: bool):
    return "ORDER BY COALESCE(file_path_scores.accessed_at, '') DESC, file_index.filename ASC"


RANKING_STRATEGIES = {
    "relevance": _order_by_relevance,
    "alphabetical": _order_by_alphabetical,
    "date-accessed": _order_by_date_accessed,
}


class SearchObserver:
    def update(self, event_name: str, payload: dict):
        print(f"Observer received event '{event_name}' with payload: {payload}")


class SearchSubject:
    def __init__(self):
        self._observers = []

    def attach(self, observer: SearchObserver):
        self._observers.append(observer)

    def notify(self, event_name: str, payload: dict):
        for observer in self._observers:
            observer.update(event_name, payload)


class SearchHistoryObserver(SearchObserver):
    def __init__(self, cursor, conn):
        self.cursor = cursor
        self.conn = conn
        self.query_counts = {}
        self.query_file_counts = {}
        self._load_history()

    def _load_history(self):
        self.cursor.execute(
            """
            SELECT query, COUNT(*)
            FROM search_history
            GROUP BY query
            """
        )
        # Store total counts for each query
        self.query_counts = {row[0]: row[1] for row in self.cursor.fetchall()}

        self.cursor.execute(
            """
            SELECT query, filepath, hit_count
            FROM query_file_history
            """
        )
        # Store hit counts for each query-file pair
        for query, filepath, hit_count in self.cursor.fetchall():
            self.query_file_counts.setdefault(query, {})[filepath] = hit_count

    # Normalize query by lowercasing and collapsing whitespace
    def _normalize_query(self, query: str):
        return " ".join(query.lower().strip().split())

    def suggest_queries(self, query_prefix: str, limit: int = 3):
        prefix = self._normalize_query(query_prefix)
        if len(prefix) < 2:
            return []

        matches = [
            (query, count)
            for query, count in self.query_counts.items()
            if query.startswith(prefix)
        ]
        # Sort by count desc, then alphabetically
        matches.sort(key=lambda item: (-item[1], item[0]))
        return [query for query, _ in matches[:limit]]

    def rerank_results(self, query: str, results: list):
        normalized = self._normalize_query(query)
        if not normalized:
            return results

        exact_counts = self.query_file_counts.get(normalized, {})
        if not exact_counts:
            return results

        # Rerank results based on how many times each file was returned for this query in the past
        indexed = list(enumerate(results))
        indexed.sort(
            key=lambda item: (
                -exact_counts.get(item[1][0], 0),
                item[0],
            )
        )
        return [item[1] for item in indexed]

    def update(self, event_name: str, payload: dict):
        if event_name != "search_executed":
            return

        raw_query = payload.get("query", "")
        normalized = self._normalize_query(raw_query)
        if len(normalized) < 2:
            return

        results = payload.get("results", [])
        now = datetime.now().isoformat(timespec="seconds")

        self.cursor.execute(
            """
            INSERT INTO search_history (query, searched_at)
            VALUES (?, ?)
            """,
            (normalized, now),
        )

        self.query_counts[normalized] = self.query_counts.get(normalized, 0) + 1

        for filepath, *_ in results:
            current = self.query_file_counts.setdefault(normalized, {}).get(filepath, 0) + 1
            self.query_file_counts[normalized][filepath] = current
            self.cursor.execute(
                """
                INSERT INTO query_file_history (query, filepath, hit_count, last_seen)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(query, filepath)
                DO UPDATE SET
                    hit_count = query_file_history.hit_count + 1,
                    last_seen = excluded.last_seen
                """,
                (normalized, filepath, current, now),
            )

        self.conn.commit()


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
        "color_terms": [],
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

            if qualifier == "color":
                parsed["color_terms"].append(value.lower())
                continue

        parsed["general_terms"].append(token)

    return parsed


def _build_search_statement(parsed_query: dict, limit: int, ranking_strategy: str = "relevance"):
    where_clauses = []
    params = []

    path_terms = parsed_query["path_terms"]
    content_terms = parsed_query["content_terms"]
    color_terms = parsed_query["color_terms"]
    general_terms = parsed_query["general_terms"]

    for term in path_terms:
        where_clauses.append("LOWER(file_index.filepath) LIKE ?")
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

    # Handle color queries
    if color_terms:
        color_conditions = []
        for color_term in color_terms:
            color_conditions.append("file_colors.dominant_color_name LIKE ?")
            params.append(f"%{color_term}%")
        where_clauses.append("(" + " OR ".join(color_conditions) + ")")

    if not where_clauses:
        where_clauses.append("1 = 0")

    ordering_builder = RANKING_STRATEGIES.get(ranking_strategy, _order_by_relevance)
    order_clause = ordering_builder(use_fts)

    # Include file_colors join if color queries are present
    left_join_colors = ""
    if color_terms:
        left_join_colors = "LEFT JOIN file_colors ON file_colors.filepath = file_index.filepath"

    sql = f"""
        SELECT file_index.filepath, file_index.filename, file_index.extension, file_index.preview
        FROM file_index
        LEFT JOIN file_path_scores ON file_path_scores.filepath = file_index.filepath
        {left_join_colors}
        WHERE {' AND '.join(where_clauses)}
        {order_clause}
        LIMIT ?
    """
    params.append(limit)
    return sql, params


def searchIndex(cursor, parsed_query: dict, limit: int = 10, ranking_strategy: str = "relevance"):
    sql, params = _build_search_statement(parsed_query, limit, ranking_strategy=ranking_strategy)
    cursor.execute(sql, params)
    return cursor.fetchall()


def formatResults(results: list, query: str):
    print(f"\n--- Results for {query} ({len(results)} found) ---")

    if not results:
        print("No results found.")
        return

    for i, (filepath, filename, extension, preview) in enumerate(results, 1):
        lower_filename = filename.lower()
        preview_text = preview[:60].replace("\n", " ").strip() if preview else ""

        print(f"{i:<2}. {lower_filename:<40} | {extension:<6} | {preview_text}...")


def display_search_results(
    cursor,
    query: str,
    limit: int = 10,
    ranking_strategy: str = "relevance",
    search_subject: SearchSubject = None,
    history_observer: SearchHistoryObserver = None,
):
    if not query:
        return

    parsed_query = parseQuery(query)
    results = searchIndex(cursor, parsed_query, limit, ranking_strategy=ranking_strategy)
    if history_observer is not None:
        suggestions = history_observer.suggest_queries(query, limit=3)
        suggestions = [s for s in suggestions if s != query.lower().strip()]
        if suggestions:
            print("Suggestions: " + " | ".join(suggestions))

        results = history_observer.rerank_results(query, results)

    if search_subject is not None:
        search_subject.notify("search_executed", {"query": query, "results": results})

    formatResults(results, query)


def _has_indexed_content(cursor):
    cursor.execute("SELECT COUNT(*) FROM file_index")
    return cursor.fetchone()[0] > 0


def search_as_you_type(cursor, conn, ranking_strategy: str = "relevance"):
    if not _has_indexed_content(cursor):
        print("\nNo indexed content found. Index your real file system first using --path.")
        return

    search_subject = SearchSubject()
    history_observer = SearchHistoryObserver(cursor, conn)
    search_subject.attach(history_observer)

    print("\n=== Search As You Type ===")
    print("Type to search in real-time (Backspace to delete, Ctrl+C to exit)\n")
    print(f"Ranking: {ranking_strategy}\n")

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
                        display_search_results(
                            cursor,
                            query,
                            ranking_strategy=ranking_strategy,
                            search_subject=search_subject,
                            history_observer=history_observer,
                        )
                        print()
                except:
                    pass
            else:
                time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n\nSearch cancelled.")
    except Exception as e:
        print(f"\nError during search: {e}")
