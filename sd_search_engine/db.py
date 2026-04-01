import sqlite3


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
    conn.commit()
    return conn, cursor
