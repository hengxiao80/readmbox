import email
import email.header
import email.utils
import mailbox
import re
import sqlite3
from datetime import timezone
from pathlib import Path

from tqdm import tqdm


BATCH_SIZE = 500

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id       INTEGER PRIMARY KEY,
    msg_id   TEXT,
    date     TEXT,
    from_    TEXT,
    to_      TEXT,
    subject  TEXT,
    snippet  TEXT,
    offset   INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    subject,
    body,
    content='',
    tokenize='unicode61'
);
"""


def _decode_header(value: str | None) -> str:
    if not value:
        return ""
    parts = email.header.decode_header(value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try:
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            except LookupError:
                decoded.append(part.decode("latin-1", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def _extract_body(msg: email.message.Message) -> str:
    """Return plain-text body, falling back to stripped HTML."""
    plain = None
    html = None
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain" and plain is None:
                plain = _decode_part(part)
            elif ct == "text/html" and html is None:
                html = _decode_part(part)
    else:
        ct = msg.get_content_type()
        if ct == "text/plain":
            plain = _decode_part(msg)
        elif ct == "text/html":
            html = _decode_part(msg)

    if plain:
        return plain
    if html:
        return re.sub(r"<[^>]+>", " ", html)
    return ""


def _decode_part(part: email.message.Message) -> str:
    payload = part.get_payload(decode=True)
    if not payload:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("latin-1", errors="replace")


def _parse_date(msg: email.message.Message) -> str:
    raw = msg.get("Date", "")
    try:
        ts = email.utils.parsedate_to_datetime(raw)
        return ts.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def db_path(mbox_path: Path) -> Path:
    return mbox_path.with_suffix(mbox_path.suffix + ".db")


def index(mbox_path: Path, rebuild: bool = False) -> None:
    db = db_path(mbox_path)

    if db.exists() and not rebuild:
        print(f"Index already exists at {db}. Use --rebuild to recreate it.")
        return

    if db.exists():
        db.unlink()

    mbox_size = mbox_path.stat().st_size

    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")

    batch_msgs: list[tuple] = []
    batch_bodies: list[tuple[str, str]] = []

    def flush(commit: bool = True) -> None:
        if not batch_msgs:
            return
        con.executemany(
            "INSERT INTO messages(msg_id, date, from_, to_, subject, snippet, offset) "
            "VALUES (?,?,?,?,?,?,?)",
            batch_msgs,
        )
        # SQLite assigns sequential rowids; last_insert_rowid() is the last one.
        last_id: int = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        start_id = last_id - len(batch_msgs) + 1
        fts_rows = [
            (start_id + i, subj, body)
            for i, (subj, body) in enumerate(batch_bodies)
        ]
        con.executemany(
            "INSERT INTO messages_fts(rowid, subject, body) VALUES (?,?,?)",
            fts_rows,
        )
        batch_msgs.clear()
        batch_bodies.clear()
        if commit:
            con.commit()

    with open(mbox_path, "rb") as raw_file:
        with tqdm(total=mbox_size, unit="B", unit_scale=True, desc="Indexing") as bar:
            mbox = mailbox.mbox(str(mbox_path))
            mbox._file = raw_file  # type: ignore[attr-defined]

            for key in mbox.keys():
                start_off, stop_off = mbox._toc[key]  # type: ignore[attr-defined]
                raw_file.seek(start_off)
                raw_msg_bytes = raw_file.read(stop_off - start_off)
                bar.update(len(raw_msg_bytes))

                msg = email.message_from_bytes(raw_msg_bytes)
                body = _extract_body(msg)
                subject = _decode_header(msg.get("Subject"))
                batch_msgs.append((
                    _decode_header(msg.get("Message-ID")),
                    _parse_date(msg),
                    _decode_header(msg.get("From")),
                    _decode_header(msg.get("To")),
                    subject,
                    body[:200],
                    start_off,
                ))
                batch_bodies.append((subject, body))

                if len(batch_msgs) >= BATCH_SIZE:
                    flush()

    flush()
    con.execute("INSERT OR REPLACE INTO meta VALUES('mbox_path', ?)", (str(mbox_path.resolve()),))
    con.commit()
    con.close()
    print(f"Done. Index saved to {db}")
