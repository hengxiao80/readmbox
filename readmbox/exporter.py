import email
import html
import re
from pathlib import Path

from .searcher import SearchResult


_CSS = """
body { font-family: system-ui, sans-serif; max-width: 860px; margin: 2rem auto; padding: 0 1rem; color: #222; }
table { border-collapse: collapse; width: 100%; margin-bottom: 1.5rem; }
td { padding: 0.3rem 0.6rem; vertical-align: top; border-bottom: 1px solid #e0e0e0; }
td:first-child { font-weight: 600; white-space: nowrap; color: #555; width: 7rem; }
.body { white-space: pre-wrap; font-size: 0.95rem; line-height: 1.6; }
.html-body { font-size: 0.95rem; line-height: 1.6; }
"""


def _safe_filename(date: str, subject: str) -> str:
    safe_date = date[:10] if date else "0000-00-00"
    safe_subj = re.sub(r"[^\w\s-]", "", subject)[:60].strip().replace(" ", "_")
    return f"{safe_date}_{safe_subj or 'no_subject'}.html"


def _get_body_part(msg: email.message.Message) -> tuple[str, bool]:
    """Return (body_text, is_html)."""
    plain = None
    html_body = None
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/html" and html_body is None:
                html_body = _decode_part(part)
            elif ct == "text/plain" and plain is None:
                plain = _decode_part(part)
    else:
        ct = msg.get_content_type()
        if ct == "text/html":
            html_body = _decode_part(msg)
        else:
            plain = _decode_part(msg)

    if html_body:
        return html_body, True
    return plain or "", False


def _decode_part(part: email.message.Message) -> str:
    payload = part.get_payload(decode=True)
    if not payload:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("latin-1", errors="replace")


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


def _render_html(msg: email.message.Message) -> str:
    subject = html.escape(_decode_header(msg.get("Subject", "")))
    from_ = html.escape(_decode_header(msg.get("From", "")))
    to_ = html.escape(_decode_header(msg.get("To", "")))
    date = html.escape(msg.get("Date", ""))

    body_text, is_html = _get_body_part(msg)

    if is_html:
        body_html = f'<div class="html-body">{body_text}</div>'
    else:
        body_html = f'<pre class="body">{html.escape(body_text)}</pre>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{subject}</title>
<style>{_CSS}</style>
</head>
<body>
<table>
  <tr><td>From</td><td>{from_}</td></tr>
  <tr><td>To</td><td>{to_}</td></tr>
  <tr><td>Date</td><td>{date}</td></tr>
  <tr><td>Subject</td><td>{subject}</td></tr>
</table>
{body_html}
</body>
</html>
"""


def export(results: list[SearchResult], mbox_path: Path, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    with open(mbox_path, "rb") as f:
        for result in results:
            f.seek(result.offset)
            # read until next "From " separator or EOF
            lines = []
            while True:
                line = f.readline()
                if not line:
                    break
                if line.startswith(b"From ") and lines:
                    break
                lines.append(line)
            raw = b"".join(lines)
            msg = email.message_from_bytes(raw)

            out_path = output_dir / _safe_filename(result.date, result.subject)
            # avoid collisions
            if out_path.exists():
                stem = out_path.stem
                for i in range(1, 10000):
                    candidate = out_path.with_name(f"{stem}_{i}.html")
                    if not candidate.exists():
                        out_path = candidate
                        break

            out_path.write_text(_render_html(msg), encoding="utf-8")
            saved.append(out_path)

    return saved
