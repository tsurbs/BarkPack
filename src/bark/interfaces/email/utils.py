"""Email formatting utilities for Bark's email interface.

Handles HTML-to-text extraction, email quoting, signature generation,
and MIME message construction for replies.
"""

import base64
import html
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMAIL_SIGNATURE_HTML = """\
<br><br>
<div style="font-size: 13px; color: #666; border-top: 1px solid #ddd; padding-top: 10px; margin-top: 20px;">
    <b>Bark</b> | ScottyLabs Assistant<br>
    <a href="https://scottylabs.org" style="color: #c41230;">scottylabs.org</a>
</div>"""

EMAIL_SIGNATURE_PLAIN = """
--
Bark | ScottyLabs Assistant
scottylabs.org"""


# ---------------------------------------------------------------------------
# HTML / text extraction
# ---------------------------------------------------------------------------

def extract_text_from_html(html_content: str) -> str:
    """Extract readable plain text from an HTML email body.

    Strips tags, decodes entities, and normalises whitespace while
    preserving paragraph breaks.
    """
    if not html_content:
        return ""

    text = html_content

    # Replace block-level elements with newlines
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</div>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<hr\s*/?>", "\n---\n", text, flags=re.IGNORECASE)

    # Strip remaining tags
    text = re.sub(r"<[^>]+>", "", text)

    # Decode HTML entities
    text = html.unescape(text)

    # Collapse excessive whitespace but keep paragraph breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def extract_body_text(payload: dict) -> str:
    """Recursively extract plain text from a Gmail message payload.

    Prefers text/plain parts; falls back to text/html with tag stripping.
    """
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")

    if mime_type == "text/plain" and body_data:
        return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

    if mime_type == "text/html" and body_data:
        raw_html = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
        return extract_text_from_html(raw_html)

    # Recurse into multipart parts
    for part in payload.get("parts", []):
        text = extract_body_text(part)
        if text:
            return text

    return ""


def extract_html_body(payload: dict) -> str:
    """Recursively extract HTML body from a Gmail message payload."""
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")

    if mime_type == "text/html" and body_data:
        return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        result = extract_html_body(part)
        if result:
            return result

    return ""


# ---------------------------------------------------------------------------
# Header helpers
# ---------------------------------------------------------------------------

def get_header(headers: list[dict], name: str) -> str:
    """Get a header value by name (case-insensitive) from a list of Gmail headers."""
    name_lower = name.lower()
    for h in headers:
        if h.get("name", "").lower() == name_lower:
            return h.get("value", "")
    return ""


def parse_email_address(raw: str) -> str:
    """Extract bare email address from a 'Name <email>' string."""
    match = re.search(r"<([^>]+)>", raw)
    if match:
        return match.group(1)
    return raw.strip()


def parse_sender_name(raw: str) -> str:
    """Extract the display name from a 'Name <email>' string."""
    match = re.match(r"^(.+?)\s*<", raw)
    if match:
        name = match.group(1).strip().strip('"')
        return name
    return raw.strip()


# ---------------------------------------------------------------------------
# Quoting & reply construction
# ---------------------------------------------------------------------------

def quote_original_message(
    sender: str, date: str, body_text: str
) -> str:
    """Format the original message as a quoted block for plain text replies."""
    quoted_lines = "\n".join(f"> {line}" for line in body_text.splitlines())
    return f"\n\nOn {date}, {sender} wrote:\n{quoted_lines}"


def quote_original_message_html(
    sender: str, date: str, body_html: str | None, body_text: str
) -> str:
    """Format the original message as a quoted block for HTML replies."""
    if body_html:
        original_content = body_html
    else:
        # Convert plain text to simple HTML
        escaped = html.escape(body_text)
        original_content = escaped.replace("\n", "<br>")

    return (
        '<div style="border-left: 2px solid #ccc; padding-left: 10px; margin-top: 20px; color: #555;">'
        f"<p>On {html.escape(date)}, {html.escape(sender)} wrote:</p>"
        f"{original_content}"
        "</div>"
    )


# ---------------------------------------------------------------------------
# MIME message building
# ---------------------------------------------------------------------------

def build_reply_message(
    to: str,
    subject: str,
    body_html: str,
    body_plain: str,
    original_message_id: str,
    references: str = "",
    thread_id: str | None = None,
    from_addr: str | None = None,
) -> dict:
    """Build a Gmail API-ready reply message with proper threading headers.

    Returns a dict with 'raw' (base64url-encoded) and optionally 'threadId'.
    """
    msg = MIMEMultipart("alternative")
    if from_addr:
        msg["From"] = f"Bark <{from_addr}>"
    msg["To"] = to
    msg["Subject"] = subject
    if original_message_id:
        msg["In-Reply-To"] = original_message_id
    msg["References"] = f"{references} {original_message_id}".strip() if references else (original_message_id or "")

    # Attach plain text part first (fallback), then HTML (preferred)
    part_plain = MIMEText(body_plain + EMAIL_SIGNATURE_PLAIN, "plain")
    part_html = MIMEText(body_html + EMAIL_SIGNATURE_HTML, "html")
    msg.attach(part_plain)
    msg.attach(part_html)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    result: dict = {"raw": raw}
    if thread_id:
        result["threadId"] = thread_id
    return result
