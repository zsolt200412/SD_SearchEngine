import sqlite3


def _column_exists(cursor, table_name: str, column_name: str):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return any(row[1] == column_name for row in cursor.fetchall())


def init_db(db_path="file_metadata.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS stored_directories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL UNIQUE
        )
        """
    )
    cursor.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS file_index USING fts5(
            filepath UNINDEXED,
            filename,
            extension,
            content,
            preview,
            modified_at UNINDEXED
        );
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS file_path_scores (
            filepath TEXT PRIMARY KEY,
            path_score REAL NOT NULL,
            accessed_at TEXT
        )
        """
    )
    if not _column_exists(cursor, "file_path_scores", "accessed_at"):
        cursor.execute("ALTER TABLE file_path_scores ADD COLUMN accessed_at TEXT")
    conn.commit()
    return conn, cursor
