import sqlite3
from sd_search_engine.search import parseQuery, searchIndex, _build_search_statement
from sd_search_engine.db import init_db

def run_task():
    conn, cursor = init_db("file_metadata.db")
    
    # Get row counts
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
        sql, params = _build_search_statement(parsed, limit)
        results = searchIndex(cursor, parsed, limit)
        
        print(f"Query: {q}")
        print(f"SQL: {sql.strip()}")
        print(f"Params: {params}")
        print(f"Results Count: {len(results)}")
        print("-" * 20)

if __name__ == "__main__":
    run_task()
