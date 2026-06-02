import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .indexer import db_path


@dataclass
class SearchResult:
    id: int
    msg_id: str
    date: str
    from_: str
    to_: str
    subject: str
    snippet: str
    offset: int
    rank: float


def search(
    mbox_path: Path,
    query: str,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 50,
) -> list[SearchResult]:
    db = db_path(mbox_path)
    if not db.exists():
        raise FileNotFoundError(f"No index found at {db}. Run 'readmbox index' first.")

    conditions = ["messages_fts MATCH ?"]
    params: list = [query]

    if from_date:
        conditions.append("m.date >= ?")
        params.append(from_date + " 00:00:00")
    if to_date:
        conditions.append("m.date <= ?")
        params.append(to_date + " 23:59:59")

    where = " AND ".join(conditions)
    sql = f"""
        SELECT m.id, m.msg_id, m.date, m.from_, m.to_, m.subject, m.snippet, m.offset,
               f.rank
        FROM messages_fts f
        JOIN messages m ON m.id = f.rowid
        WHERE {where}
        ORDER BY f.rank
        LIMIT ?
    """
    params.append(limit)

    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(sql, params).fetchall()
    finally:
        con.close()

    return [SearchResult(**dict(r)) for r in rows]
