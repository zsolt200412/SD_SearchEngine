import sqlite3
import sys

# Override _build_search_statement to fix the ambiguous column name
def _build_search_statement_fixed(parsed_query: dict, limit: int):
    # This matches the structure of the original but fixes the ambiguous filepath in the LEFT JOIN / WHERE
    where_clauses = []
    params = []

    path_terms = parsed_query["path_terms"]
    content_terms = parsed_query["content_terms"]
    general_terms = parsed_query["general_terms"]

    for term in path_terms:
        # Fixed: using file_index.filepath instead of just filepath
        where_clauses.append("LOWER(file_index.filepath) LIKE ?")
        params.append(f"%{term.lower()}%")

    from sd_search_engine.search import _build_and_fts_query
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

    score_expr = "COALESCE(file_path_scores.path_score, 0.50)"
    order_clause = (
        f"ORDER BY bm25(file_index, 10.0, 4.0, 7.0, 1.0) ASC, {score_expr} DESC"
        if use_fts
        else f"ORDER BY {score_expr} DESC, filename ASC"
    )

    sql = f"""
        SELECT file_index.filepath, filename, extension, preview
        FROM file_index
        LEFT JOIN file_path_scores ON file_path_scores.filepath = file_index.filepath
        WHERE {' AND '.join(where_clauses)}
        {order_clause}
        LIMIT ?
    """
    params.append(limit)
    return sql, params

def run_task():
    from sd_search_engine.search import parseQuery
    from sd_search_engine.db import init_db
    
    conn, cursor = init_db("file_metadata.db")
    
    cursor.execute("SELECT COUNT(*) FROM file_index")
    count_file_index = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM file_path_scores")
    count_file_path_scores = cursor.fetchone()[0]
    
    print(f"Total row count in file_index: {count_file_index}")
    print(f"Total row count in file_path_scores: {count_file_path_scores}\n")
    
    queries = ['python', 'content:python', 'path:src', 'path:desktop python']
    limit = 10
    
    for q in queries:
        parsed = parseQuery(q)
        sql, params = _build_search_statement_fixed(parsed, limit)
        
        try:
            cursor.execute(sql, params)
            results = cursor.fetchall()
            res_count = len(results)
        except Exception as e:
            res_count = f"Error: {e}"
        
        print(f"Query: {q}")
        print(f"SQL: {sql.strip()}")
        print(f"Params: {params}")
        print(f"Results Count: {res_count}")
        print("-" * 20)

if __name__ == "__main__":
    run_task()
