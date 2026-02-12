"""Google Workspace API tools for Bark.

Provides tools for Gmail, Calendar, Docs, Drive, Sheets, Forms, Chat,
Meet, Admin SDK, Apps Script, Postmaster, Drive Activity, and Drive Labels.
"""

import base64

from bark.core.formatting import GMAIL_FORMAT_INSTRUCTIONS, GOOGLE_DOCS_FORMAT_INSTRUCTIONS
import logging
from datetime import datetime, timezone
from email.mime.text import MIMEText
from typing import Any

from bark.context.google_auth import get_google_auth
from bark.core.tools import tool

logger = logging.getLogger(__name__)


def _safe(call, error_prefix: str = "API error") -> str:
    """Run a Google API call and return a friendly error on failure."""
    try:
        return call()
    except Exception as e:
        logger.error(f"{error_prefix}: {e}")
        return f"❌ {error_prefix}: {e}"


# =============================================================================
# GMAIL TOOLS
# =============================================================================


@tool(
    name="gmail_search",
    description=(
        "Search Gmail messages. Uses the same query syntax as the Gmail search box "
        "(e.g. 'from:alice subject:budget after:2025/01/01'). Returns subject, sender, "
        "date, and snippet for each result."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Gmail search query (same syntax as Gmail search box)",
            },
            "max_results": {
                "type": "integer",
                "description": "Max messages to return (default 10)",
            },
        },
        "required": ["query"],
    },
)
def gmail_search(query: str, max_results: int = 10) -> str:
    """Search Gmail messages."""
    auth = get_google_auth()
    svc = auth.gmail

    results = svc.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()

    messages = results.get("messages", [])
    if not messages:
        return f"No emails found for query: '{query}'"

    output = [f"Found {len(messages)} email(s):\n"]
    for msg_stub in messages:
        msg = svc.users().messages().get(
            userId="me", id=msg_stub["id"], format="metadata",
            metadataHeaders=["Subject", "From", "Date"],
        ).execute()
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        output.append(
            f"- **{headers.get('Subject', '(no subject)')}**\n"
            f"  From: {headers.get('From', '?')} | Date: {headers.get('Date', '?')}\n"
            f"  Snippet: {msg.get('snippet', '')}\n"
            f"  ID: `{msg['id']}`"
        )
    return "\n".join(output)


@tool(
    name="gmail_read",
    description="Read the full content of a Gmail message by its ID. Returns headers and body text.",
    parameters={
        "type": "object",
        "properties": {
            "message_id": {
                "type": "string",
                "description": "The Gmail message ID (from gmail_search results)",
            },
        },
        "required": ["message_id"],
    },
)
def gmail_read(message_id: str) -> str:
    """Read a specific Gmail message."""
    auth = get_google_auth()
    svc = auth.gmail
    msg = svc.users().messages().get(userId="me", id=message_id, format="full").execute()

    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
    output = [
        f"**Subject:** {headers.get('Subject', '(none)')}",
        f"**From:** {headers.get('From', '?')}",
        f"**To:** {headers.get('To', '?')}",
        f"**Date:** {headers.get('Date', '?')}",
        "",
    ]

    # Extract body text
    body = _extract_body(msg.get("payload", {}))
    output.append(body if body else "(no text body)")
    return "\n".join(output)


def _extract_body(payload: dict) -> str:
    """Recursively extract plain text from a Gmail message payload."""
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        text = _extract_body(part)
        if text:
            return text
    return ""


@tool(
    name="gmail_send",
    description=(
        "Send an email via Gmail. Specify recipient, subject, and body. "
        "Set html=true to send a rich HTML email (recommended for formatted content).\n\n"
        + GMAIL_FORMAT_INSTRUCTIONS
    ),
    parameters={
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Recipient email address"},
            "subject": {"type": "string", "description": "Email subject line"},
            "body": {
                "type": "string",
                "description": "Email body — plain text or HTML depending on the html flag",
            },
            "html": {
                "type": "boolean",
                "description": "If true, send body as HTML for rich formatting. Default false (plain text).",
            },
        },
        "required": ["to", "subject", "body"],
    },
)
def gmail_send(to: str, subject: str, body: str, html: bool = False) -> str:
    """Send an email."""
    auth = get_google_auth()
    svc = auth.gmail

    subtype = "html" if html else "plain"
    message = MIMEText(body, subtype)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    sent = svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    return f"✅ Email sent! Message ID: `{sent['id']}`"


@tool(
    name="gmail_list_labels",
    description="List all Gmail labels (inbox, sent, custom labels, etc.).",
    parameters={"type": "object", "properties": {}},
)
def gmail_list_labels() -> str:
    """List Gmail labels."""
    auth = get_google_auth()
    svc = auth.gmail
    results = svc.users().labels().list(userId="me").execute()
    labels = results.get("labels", [])
    if not labels:
        return "No labels found."
    lines = ["Gmail Labels:"]
    for lb in labels:
        lines.append(f"- **{lb['name']}** (type: {lb.get('type', '?')}, id: `{lb['id']}`)")
    return "\n".join(lines)


# =============================================================================
# CALENDAR TOOLS
# =============================================================================


@tool(
    name="calendar_list_events",
    description=(
        "List upcoming Google Calendar events. Optionally specify a calendar ID "
        "(defaults to primary) and max results."
    ),
    parameters={
        "type": "object",
        "properties": {
            "calendar_id": {
                "type": "string",
                "description": "Calendar ID (default: 'primary')",
            },
            "max_results": {
                "type": "integer",
                "description": "Max events to return (default 10)",
            },
        },
    },
)
def calendar_list_events(calendar_id: str = "primary", max_results: int = 10) -> str:
    """List upcoming calendar events."""
    auth = get_google_auth()
    svc = auth.calendar

    now = datetime.now(timezone.utc).isoformat()
    events_result = svc.events().list(
        calendarId=calendar_id,
        timeMin=now,
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events = events_result.get("items", [])
    if not events:
        return "No upcoming events found."

    lines = [f"Upcoming events ({len(events)}):"]
    for ev in events:
        start = ev["start"].get("dateTime", ev["start"].get("date", "?"))
        end = ev["end"].get("dateTime", ev["end"].get("date", ""))
        summary = ev.get("summary", "(no title)")
        lines.append(f"- **{summary}** — {start} to {end}")
        if ev.get("location"):
            lines.append(f"  📍 {ev['location']}")
        if ev.get("htmlLink"):
            lines.append(f"  🔗 {ev['htmlLink']}")
    return "\n".join(lines)


@tool(
    name="calendar_create_event",
    description=(
        "Create a Google Calendar event. Provide a summary, start/end times "
        "(ISO 8601 format, e.g. '2026-03-15T14:00:00-05:00'), and optional location/description."
    ),
    parameters={
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "Event title"},
            "start_time": {
                "type": "string",
                "description": "Start time in ISO 8601 format (e.g. '2026-03-15T14:00:00-05:00')",
            },
            "end_time": {
                "type": "string",
                "description": "End time in ISO 8601 format",
            },
            "description": {"type": "string", "description": "Event description (optional)"},
            "location": {"type": "string", "description": "Event location (optional)"},
            "calendar_id": {"type": "string", "description": "Calendar ID (default: 'primary')"},
            "attendees": {
                "type": "string",
                "description": "Comma-separated email addresses of attendees (optional)",
            },
        },
        "required": ["summary", "start_time", "end_time"],
    },
)
def calendar_create_event(
    summary: str,
    start_time: str,
    end_time: str,
    description: str = "",
    location: str = "",
    calendar_id: str = "primary",
    attendees: str = "",
) -> str:
    """Create a calendar event."""
    auth = get_google_auth()
    svc = auth.calendar

    event: dict[str, Any] = {
        "summary": summary,
        "start": {"dateTime": start_time},
        "end": {"dateTime": end_time},
    }
    if description:
        event["description"] = description
    if location:
        event["location"] = location
    if attendees:
        event["attendees"] = [{"email": e.strip()} for e in attendees.split(",") if e.strip()]

    created = svc.events().insert(calendarId=calendar_id, body=event).execute()
    return (
        f"✅ Event created: **{created.get('summary')}**\n"
        f"Link: {created.get('htmlLink', '(no link)')}"
    )


@tool(
    name="calendar_list_calendars",
    description="List all calendars the user has access to.",
    parameters={"type": "object", "properties": {}},
)
def calendar_list_calendars() -> str:
    """List available calendars."""
    auth = get_google_auth()
    svc = auth.calendar
    result = svc.calendarList().list().execute()
    calendars = result.get("items", [])
    if not calendars:
        return "No calendars found."
    lines = ["Available calendars:"]
    for cal in calendars:
        primary = " ⭐" if cal.get("primary") else ""
        lines.append(f"- **{cal.get('summary', '?')}**{primary} — `{cal['id']}`")
    return "\n".join(lines)


# =============================================================================
# GOOGLE DOCS TOOLS
# =============================================================================


@tool(
    name="docs_get",
    description="Get the text content of a Google Doc by its document ID.",
    parameters={
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "The Google Docs document ID (from the URL)",
            },
        },
        "required": ["document_id"],
    },
)
def docs_get(document_id: str) -> str:
    """Get Google Doc content."""
    auth = get_google_auth()
    svc = auth.docs
    doc = svc.documents().get(documentId=document_id).execute()

    title = doc.get("title", "Untitled")
    body = doc.get("body", {})
    text = _extract_doc_text(body)
    return f"# {title}\n\n{text}"


def _extract_paragraph_text(paragraph: dict) -> str:
    """Extract text from a single Google Docs paragraph element.

    Handles hyperlinks by rendering them as Markdown links.
    """
    parts: list[str] = []
    for pe in paragraph.get("elements", []):
        text_run = pe.get("textRun")
        if text_run:
            content = text_run.get("content", "")
            # Check for hyperlinks
            text_style = text_run.get("textStyle", {})
            link = text_style.get("link", {})
            url = link.get("url", "")
            if url and content.strip():
                # Render as Markdown link — keep trailing whitespace outside
                stripped = content.rstrip()
                trailing = content[len(stripped):]
                parts.append(f"[{stripped}]({url}){trailing}")
            else:
                parts.append(content)
    return "".join(parts)


def _extract_table_markdown(table: dict) -> str:
    """Convert a Google Docs table element into a Markdown table."""
    rows: list[list[str]] = []
    for table_row in table.get("tableRows", []):
        cells: list[str] = []
        for cell in table_row.get("tableCells", []):
            # Each cell contains its own content array (paragraphs, etc.)
            cell_parts: list[str] = []
            for element in cell.get("content", []):
                paragraph = element.get("paragraph")
                if paragraph:
                    text = _extract_paragraph_text(paragraph).strip()
                    if text:
                        cell_parts.append(text)
                # Nested tables are rare but possible — flatten to text
                nested_table = element.get("table")
                if nested_table:
                    cell_parts.append(_extract_table_markdown(nested_table))
            # Join multi-paragraph cells with " / " to keep them on one line
            cells.append(" / ".join(cell_parts) if cell_parts else "")
        rows.append(cells)

    if not rows:
        return ""

    # Normalise column count
    max_cols = max(len(r) for r in rows)
    normalised = [r + [""] * (max_cols - len(r)) for r in rows]

    # Escape pipes in cell content
    def esc(s: str) -> str:
        return s.replace("|", "\\|")

    header = normalised[0]
    lines = [
        "| " + " | ".join(esc(c) for c in header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in normalised[1:]:
        lines.append("| " + " | ".join(esc(c) for c in row) + " |")

    return "\n".join(lines)


def _extract_doc_content(content: list[dict]) -> str:
    """Recursively extract text and tables from a Google Docs content array.

    Handles paragraphs, tables, table-of-contents, and section breaks.
    Tables are rendered as Markdown tables.
    """
    parts: list[str] = []
    for element in content:
        # --- Paragraphs ---
        paragraph = element.get("paragraph")
        if paragraph:
            parts.append(_extract_paragraph_text(paragraph))
            continue

        # --- Tables ---
        table = element.get("table")
        if table:
            md_table = _extract_table_markdown(table)
            if md_table:
                parts.append("\n" + md_table + "\n\n")
            continue

        # --- Table of contents ---
        toc = element.get("tableOfContents")
        if toc:
            toc_content = toc.get("content", [])
            if toc_content:
                parts.append(_extract_doc_content(toc_content))
            continue

        # --- Section breaks (just add spacing) ---
        if element.get("sectionBreak"):
            parts.append("\n---\n\n")
            continue

    return "".join(parts)


def _extract_doc_text(body: dict) -> str:
    """Extract text and tables from a Google Docs body as Markdown."""
    return _extract_doc_content(body.get("content", []))


@tool(
    name="docs_create",
    description=(
        "Create a new Google Doc with a title and optional body text.\n\n"
        + GOOGLE_DOCS_FORMAT_INSTRUCTIONS
    ),
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Document title"},
            "body_text": {
                "type": "string",
                "description": "Initial text content for the document (optional). Use clean plain text — no Markdown or HTML.",
            },
        },
        "required": ["title"],
    },
)
def docs_create(title: str, body_text: str = "") -> str:
    """Create a new Google Doc."""
    auth = get_google_auth()
    svc = auth.docs
    doc = svc.documents().create(body={"title": title}).execute()
    doc_id = doc["documentId"]

    if body_text:
        svc.documents().batchUpdate(
            documentId=doc_id,
            body={
                "requests": [
                    {"insertText": {"location": {"index": 1}, "text": body_text}}
                ]
            },
        ).execute()

    url = f"https://docs.google.com/document/d/{doc_id}/edit"
    return f"✅ Created Google Doc: **{title}**\nURL: {url}"


# =============================================================================
# GOOGLE DRIVE TOOLS (enhanced)
# =============================================================================


@tool(
    name="drive_list_files",
    description=(
        "List files in a Google Drive folder. Optionally specify a folder ID "
        "(defaults to the configured ScottyLabs Drive folder)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "folder_id": {
                "type": "string",
                "description": "Folder ID to list (optional, defaults to configured root)",
            },
            "max_results": {
                "type": "integer",
                "description": "Max files to return (default 20)",
            },
        },
    },
)
def drive_list_files(folder_id: str = "", max_results: int = 20) -> str:
    """List files in a Drive folder."""
    from bark.core.config import get_settings

    auth = get_google_auth()
    svc = auth.drive

    if not folder_id:
        folder_id = get_settings().google_drive_folder_id or "root"

    query = f"'{folder_id}' in parents and trashed=false"
    results = svc.files().list(
        q=query,
        pageSize=max_results,
        fields="files(id, name, mimeType, modifiedTime, webViewLink)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()

    files = results.get("files", [])
    if not files:
        return "No files found in this folder."

    lines = [f"Files in folder ({len(files)}):"]
    for f in files:
        icon = "📁" if "folder" in f.get("mimeType", "") else "📄"
        link = f.get("webViewLink", "")
        modified = f.get("modifiedTime", "")[:10]
        lines.append(f"- {icon} **{f['name']}** (modified {modified})")
        lines.append(f"  ID: `{f['id']}` | [Open]({link})")
    return "\n".join(lines)


@tool(
    name="drive_create_folder",
    description="Create a new folder in Google Drive.",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Folder name"},
            "parent_folder_id": {
                "type": "string",
                "description": "Parent folder ID (optional, defaults to configured root)",
            },
        },
        "required": ["name"],
    },
)
def drive_create_folder(name: str, parent_folder_id: str = "") -> str:
    """Create a new Drive folder."""
    from bark.core.config import get_settings

    auth = get_google_auth()
    svc = auth.drive

    metadata: dict[str, Any] = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    parent = parent_folder_id or get_settings().google_drive_folder_id
    if parent:
        metadata["parents"] = [parent]

    folder = svc.files().create(
        body=metadata, fields="id, webViewLink", supportsAllDrives=True
    ).execute()
    return f"✅ Created folder **{name}**\nID: `{folder['id']}`\nLink: {folder.get('webViewLink', '')}"


@tool(
    name="drive_get_file_content",
    description=(
        "Get the text content of a Google Drive file by its file ID. "
        "Works with Google Docs, Sheets (exports as CSV), Slides, and text files."
    ),
    parameters={
        "type": "object",
        "properties": {
            "file_id": {
                "type": "string",
                "description": "The Drive file ID",
            },
        },
        "required": ["file_id"],
    },
)
def drive_get_file_content(file_id: str) -> str:
    """Get file content from Drive."""
    auth = get_google_auth()
    svc = auth.drive

    # Get file metadata to determine type
    meta = svc.files().get(fileId=file_id, fields="name, mimeType").execute()
    mime = meta.get("mimeType", "")
    name = meta.get("name", "Untitled")

    export_map = {
        "application/vnd.google-apps.document": ("text/plain", "Google Doc"),
        "application/vnd.google-apps.spreadsheet": ("text/csv", "Google Sheet"),
        "application/vnd.google-apps.presentation": ("text/plain", "Google Slides"),
    }

    if mime in export_map:
        export_mime, doc_type = export_map[mime]
        content = svc.files().export(fileId=file_id, mimeType=export_mime).execute()
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        return f"# {name} ({doc_type})\n\n{content}"
    else:
        import io
        from googleapiclient.http import MediaIoBaseDownload

        request = svc.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        content = buffer.getvalue()
        try:
            text = content.decode("utf-8")
            return f"# {name}\n\n{text}"
        except UnicodeDecodeError:
            return f"# {name}\n\n(Binary file — {len(content)} bytes, cannot display as text)"


# =============================================================================
# DRIVE ACTIVITY TOOLS
# =============================================================================


@tool(
    name="drive_activity_query",
    description=(
        "Query recent activity on a Drive item or folder. "
        "Shows who did what (edits, comments, shares, etc.) and when."
    ),
    parameters={
        "type": "object",
        "properties": {
            "item_id": {
                "type": "string",
                "description": "Drive file or folder ID to query activity for",
            },
            "max_results": {
                "type": "integer",
                "description": "Max activities to return (default 10)",
            },
        },
        "required": ["item_id"],
    },
)
def drive_activity_query(item_id: str, max_results: int = 10) -> str:
    """Query Drive activity."""
    auth = get_google_auth()
    svc = auth.drive_activity

    result = svc.activity().query(
        body={
            "itemName": f"items/{item_id}",
            "pageSize": max_results,
        }
    ).execute()

    activities = result.get("activities", [])
    if not activities:
        return "No recent activity found for this item."

    lines = [f"Recent activity ({len(activities)} events):"]
    for act in activities:
        # Extract the primary action
        primary = act.get("primaryActionDetail", {})
        action_type = next(iter(primary.keys()), "unknown") if primary else "unknown"

        # Actor
        actors = act.get("actors", [{}])
        actor_name = "Unknown"
        for a in actors:
            user = a.get("user", {}).get("knownUser", {})
            actor_name = user.get("personName", actor_name)

        # Timestamp
        timestamp = act.get("timestamp", "?")

        lines.append(f"- **{action_type}** by {actor_name} at {timestamp}")

    return "\n".join(lines)


# =============================================================================
# DRIVE LABELS TOOLS
# =============================================================================


@tool(
    name="drive_labels_list",
    description="List available Google Drive labels that can be applied to files.",
    parameters={
        "type": "object",
        "properties": {
            "max_results": {
                "type": "integer",
                "description": "Max labels to return (default 20)",
            },
        },
    },
)
def drive_labels_list(max_results: int = 20) -> str:
    """List Drive labels."""
    auth = get_google_auth()
    svc = auth.drive_labels

    result = svc.labels().list(
        view="LABEL_VIEW_FULL",
        pageSize=max_results,
    ).execute()

    labels = result.get("labels", [])
    if not labels:
        return "No Drive labels found."

    lines = ["Drive Labels:"]
    for lb in labels:
        name = lb.get("properties", {}).get("title", lb.get("name", "?"))
        label_id = lb.get("id", "?")
        lines.append(f"- **{name}** (id: `{label_id}`)")
    return "\n".join(lines)


# =============================================================================
# GOOGLE SHEETS TOOLS
# =============================================================================


@tool(
    name="sheets_read",
    description=(
        "Read data from a Google Sheets spreadsheet. Specify the spreadsheet ID "
        "and an optional range (e.g. 'Sheet1!A1:D10'). Returns data as a formatted table."
    ),
    parameters={
        "type": "object",
        "properties": {
            "spreadsheet_id": {
                "type": "string",
                "description": "The spreadsheet ID (from the URL)",
            },
            "range": {
                "type": "string",
                "description": "Cell range to read (e.g. 'Sheet1!A1:D10'). Defaults to 'Sheet1'.",
            },
        },
        "required": ["spreadsheet_id"],
    },
)
def sheets_read(spreadsheet_id: str, range: str = "Sheet1") -> str:
    """Read spreadsheet data."""
    auth = get_google_auth()
    svc = auth.sheets

    result = svc.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=range
    ).execute()

    values = result.get("values", [])
    if not values:
        return "No data found in the specified range."

    # Format as markdown table
    lines = []
    header = values[0]
    lines.append("| " + " | ".join(str(c) for c in header) + " |")
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    for row in values[1:]:
        # Pad row to match header length
        padded = row + [""] * (len(header) - len(row))
        lines.append("| " + " | ".join(str(c) for c in padded) + " |")

    return f"**Range:** {range}\n\n" + "\n".join(lines)


@tool(
    name="sheets_write",
    description=(
        "Write data to a Google Sheets spreadsheet. Provide the data as rows of "
        "comma-separated values, one row per line."
    ),
    parameters={
        "type": "object",
        "properties": {
            "spreadsheet_id": {
                "type": "string",
                "description": "The spreadsheet ID",
            },
            "range": {
                "type": "string",
                "description": "Cell range to write to (e.g. 'Sheet1!A1')",
            },
            "data": {
                "type": "string",
                "description": "Data to write. Each line is a row, columns separated by commas.",
            },
        },
        "required": ["spreadsheet_id", "range", "data"],
    },
)
def sheets_write(spreadsheet_id: str, range: str, data: str) -> str:
    """Write data to a spreadsheet."""
    auth = get_google_auth()
    svc = auth.sheets

    rows = [line.split(",") for line in data.strip().split("\n")]

    result = svc.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range,
        valueInputOption="USER_ENTERED",
        body={"values": rows},
    ).execute()

    updated = result.get("updatedCells", 0)
    return f"✅ Updated {updated} cells in range `{range}`."


# =============================================================================
# GOOGLE FORMS TOOLS
# =============================================================================


@tool(
    name="forms_get",
    description="Get a Google Form's structure (questions, options) by its form ID.",
    parameters={
        "type": "object",
        "properties": {
            "form_id": {
                "type": "string",
                "description": "The Google Form ID",
            },
        },
        "required": ["form_id"],
    },
)
def forms_get(form_id: str) -> str:
    """Get Form structure."""
    auth = get_google_auth()
    svc = auth.forms

    form = svc.forms().get(formId=form_id).execute()
    title = form.get("info", {}).get("title", "Untitled Form")
    desc = form.get("info", {}).get("description", "")

    lines = [f"# {title}"]
    if desc:
        lines.append(f"*{desc}*\n")

    items = form.get("items", [])
    for i, item in enumerate(items, 1):
        q_title = item.get("title", "(untitled question)")
        q_type = next(iter(item.get("questionItem", {}).get("question", {}).keys()), "unknown")
        lines.append(f"**Q{i}.** {q_title} *(type: {q_type})*")

        # Show options for choice questions
        question = item.get("questionItem", {}).get("question", {})
        choice_q = question.get("choiceQuestion", {})
        if choice_q:
            for opt in choice_q.get("options", []):
                lines.append(f"  - {opt.get('value', '?')}")

    return "\n".join(lines)


@tool(
    name="forms_list_responses",
    description="List responses to a Google Form by its form ID.",
    parameters={
        "type": "object",
        "properties": {
            "form_id": {
                "type": "string",
                "description": "The Google Form ID",
            },
            "max_results": {
                "type": "integer",
                "description": "Max responses to return (default 20)",
            },
        },
        "required": ["form_id"],
    },
)
def forms_list_responses(form_id: str, max_results: int = 20) -> str:
    """List form responses."""
    auth = get_google_auth()
    svc = auth.forms

    result = svc.forms().responses().list(formId=form_id, pageSize=max_results).execute()
    responses = result.get("responses", [])

    if not responses:
        return "No responses found for this form."

    lines = [f"Form responses ({len(responses)} total):"]
    for i, resp in enumerate(responses, 1):
        ts = resp.get("lastSubmittedTime", "?")
        lines.append(f"\n### Response {i} (submitted {ts})")
        answers = resp.get("answers", {})
        for qid, answer in answers.items():
            text_answers = answer.get("textAnswers", {}).get("answers", [])
            answer_text = ", ".join(a.get("value", "?") for a in text_answers)
            lines.append(f"- Q`{qid}`: {answer_text}")

    return "\n".join(lines)


# =============================================================================
# GOOGLE CHAT TOOLS
# =============================================================================


@tool(
    name="chat_list_spaces",
    description="List Google Chat spaces (rooms, DMs, group conversations) the account has access to.",
    parameters={"type": "object", "properties": {}},
)
def chat_list_spaces() -> str:
    """List Chat spaces."""
    auth = get_google_auth()
    svc = auth.chat

    result = svc.spaces().list().execute()
    spaces = result.get("spaces", [])

    if not spaces:
        return "No Chat spaces found."

    lines = ["Chat spaces:"]
    for sp in spaces:
        name = sp.get("displayName", sp.get("name", "?"))
        sp_type = sp.get("spaceType", sp.get("type", "?"))
        lines.append(f"- **{name}** (type: {sp_type}, id: `{sp['name']}`)")
    return "\n".join(lines)


@tool(
    name="chat_send_message",
    description="Send a message to a Google Chat space.",
    parameters={
        "type": "object",
        "properties": {
            "space_name": {
                "type": "string",
                "description": "The Chat space resource name (e.g. 'spaces/AAAA...')",
            },
            "text": {
                "type": "string",
                "description": "Message text to send",
            },
        },
        "required": ["space_name", "text"],
    },
)
def chat_send_message(space_name: str, text: str) -> str:
    """Send a Chat message."""
    auth = get_google_auth()
    svc = auth.chat

    result = svc.spaces().messages().create(
        parent=space_name, body={"text": text}
    ).execute()
    return f"✅ Message sent to {space_name}. Message ID: `{result.get('name', '?')}`"


# =============================================================================
# GOOGLE MEET TOOLS
# =============================================================================


@tool(
    name="meet_create_space",
    description="Create a new Google Meet meeting space and return a join link.",
    parameters={"type": "object", "properties": {}},
)
def meet_create_space() -> str:
    """Create a Meet space."""
    auth = get_google_auth()
    svc = auth.meet

    space = svc.spaces().create(body={}).execute()
    meeting_uri = space.get("meetingUri", "?")
    space_name = space.get("name", "?")
    return f"✅ Meeting created!\nJoin: {meeting_uri}\nSpace: `{space_name}`"


@tool(
    name="meet_list_conference_records",
    description="List recent Google Meet conference records (past meetings).",
    parameters={
        "type": "object",
        "properties": {
            "max_results": {
                "type": "integer",
                "description": "Max records to return (default 10)",
            },
        },
    },
)
def meet_list_conference_records(max_results: int = 10) -> str:
    """List conference records."""
    auth = get_google_auth()
    svc = auth.meet

    result = svc.conferenceRecords().list(pageSize=max_results).execute()
    records = result.get("conferenceRecords", [])

    if not records:
        return "No conference records found."

    lines = ["Recent meetings:"]
    for rec in records:
        name = rec.get("name", "?")
        space = rec.get("space", "?")
        start = rec.get("startTime", "?")
        end = rec.get("endTime", "?")
        lines.append(f"- **{name}** | Space: `{space}` | {start} → {end}")
    return "\n".join(lines)


# =============================================================================
# ADMIN SDK TOOLS
# =============================================================================


@tool(
    name="admin_list_users",
    description="List users in the Google Workspace domain. Requires admin privileges.",
    parameters={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "Domain to list users for (e.g. 'scottylabs.org')",
            },
            "max_results": {
                "type": "integer",
                "description": "Max users to return (default 20)",
            },
        },
        "required": ["domain"],
    },
)
def admin_list_users(domain: str, max_results: int = 20) -> str:
    """List workspace users."""
    auth = get_google_auth()
    svc = auth.admin

    result = svc.users().list(domain=domain, maxResults=max_results).execute()
    users = result.get("users", [])

    if not users:
        return f"No users found for domain {domain}."

    lines = [f"Users in {domain} ({len(users)}):"]
    for u in users:
        name = u.get("name", {}).get("fullName", "?")
        email = u.get("primaryEmail", "?")
        suspended = " ⛔ suspended" if u.get("suspended") else ""
        lines.append(f"- **{name}** — {email}{suspended}")
    return "\n".join(lines)


@tool(
    name="admin_list_groups",
    description="List groups in the Google Workspace domain. Requires admin privileges.",
    parameters={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "Domain to list groups for (e.g. 'scottylabs.org')",
            },
            "max_results": {
                "type": "integer",
                "description": "Max groups to return (default 20)",
            },
        },
        "required": ["domain"],
    },
)
def admin_list_groups(domain: str, max_results: int = 20) -> str:
    """List workspace groups."""
    auth = get_google_auth()
    svc = auth.admin

    result = svc.groups().list(domain=domain, maxResults=max_results).execute()
    groups = result.get("groups", [])

    if not groups:
        return f"No groups found for domain {domain}."

    lines = [f"Groups in {domain} ({len(groups)}):"]
    for g in groups:
        name = g.get("name", "?")
        email = g.get("email", "?")
        members = g.get("directMembersCount", "?")
        lines.append(f"- **{name}** — {email} ({members} members)")
    return "\n".join(lines)


# =============================================================================
# APPS SCRIPT TOOLS
# =============================================================================


@tool(
    name="apps_script_list_projects",
    description="List Google Apps Script projects the user has access to.",
    parameters={"type": "object", "properties": {}},
)
def apps_script_list_projects() -> str:
    """List Apps Script projects."""
    auth = get_google_auth()
    svc = auth.script

    result = svc.projects().list().execute() if hasattr(svc.projects(), 'list') else {}
    # The Apps Script API doesn't have a list method via discovery;
    # projects are found via Drive search for script files.
    drive_svc = auth.drive
    results = drive_svc.files().list(
        q="mimeType='application/vnd.google-apps.script'",
        pageSize=20,
        fields="files(id, name, modifiedTime, webViewLink)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()

    files = results.get("files", [])
    if not files:
        return "No Apps Script projects found."

    lines = ["Apps Script projects:"]
    for f in files:
        modified = f.get("modifiedTime", "")[:10]
        link = f.get("webViewLink", "")
        lines.append(f"- **{f['name']}** (modified {modified})")
        lines.append(f"  ID: `{f['id']}` | [Open]({link})")
    return "\n".join(lines)


@tool(
    name="apps_script_get_content",
    description="Get the source code of an Apps Script project by its script ID.",
    parameters={
        "type": "object",
        "properties": {
            "script_id": {
                "type": "string",
                "description": "The Apps Script project/script ID",
            },
        },
        "required": ["script_id"],
    },
)
def apps_script_get_content(script_id: str) -> str:
    """Get Apps Script project content."""
    auth = get_google_auth()
    svc = auth.script

    content = svc.projects().getContent(scriptId=script_id).execute()
    files = content.get("files", [])

    if not files:
        return "No files found in this Apps Script project."

    lines = [f"Apps Script project `{script_id}` ({len(files)} files):"]
    for f in files:
        name = f.get("name", "?")
        file_type = f.get("type", "?")
        source = f.get("source", "")
        lines.append(f"\n### {name}.{_script_ext(file_type)}")
        lines.append(f"```{'javascript' if file_type == 'SERVER_JS' else 'html'}")
        lines.append(source)
        lines.append("```")
    return "\n".join(lines)


def _script_ext(file_type: str) -> str:
    return {"SERVER_JS": "gs", "HTML": "html", "JSON": "json"}.get(file_type, "txt")


# =============================================================================
# GMAIL POSTMASTER TOOLS
# =============================================================================


@tool(
    name="postmaster_list_domains",
    description="List verified domains in Gmail Postmaster Tools.",
    parameters={"type": "object", "properties": {}},
)
def postmaster_list_domains() -> str:
    """List Postmaster domains."""
    auth = get_google_auth()
    svc = auth.postmaster

    result = svc.domains().list().execute()
    domains = result.get("domains", [])

    if not domains:
        return "No verified domains found in Postmaster Tools."

    lines = ["Postmaster domains:"]
    for d in domains:
        name = d.get("name", "?")
        permission = d.get("permission", "?")
        lines.append(f"- **{name}** (permission: {permission})")
    return "\n".join(lines)


@tool(
    name="postmaster_get_traffic_stats",
    description="Get email traffic stats for a domain from Gmail Postmaster Tools.",
    parameters={
        "type": "object",
        "properties": {
            "domain_name": {
                "type": "string",
                "description": "The domain resource name (from postmaster_list_domains)",
            },
        },
        "required": ["domain_name"],
    },
)
def postmaster_get_traffic_stats(domain_name: str) -> str:
    """Get Postmaster traffic stats."""
    auth = get_google_auth()
    svc = auth.postmaster

    result = svc.domains().trafficStats().list(parent=domain_name).execute()
    stats = result.get("trafficStats", [])

    if not stats:
        return "No traffic stats available for this domain."

    lines = [f"Traffic stats for {domain_name}:"]
    for s in stats:
        name = s.get("name", "?")
        lines.append(f"\n### {name}")
        for key in ["userReportedSpamRatio", "ipReputations", "domainReputation",
                     "spfSuccessRatio", "dkimSuccessRatio", "dmarcSuccessRatio"]:
            val = s.get(key)
            if val is not None:
                lines.append(f"- **{key}**: {val}")
    return "\n".join(lines)


# =============================================================================
# GOOGLE KEEP (STUB — API is restricted)
# =============================================================================


@tool(
    name="keep_note",
    description=(
        "⚠️ The Google Keep API is restricted and not generally available. "
        "This tool cannot create or read Keep notes. Consider using Google Docs "
        "or Drive for note-taking instead."
    ),
    parameters={"type": "object", "properties": {}},
)
def keep_note() -> str:
    """Stub for Keep API."""
    return (
        "⚠️ The Google Keep API is restricted and not publicly available via the standard "
        "Google API client. As alternatives, you can:\n"
        "- Use **docs_create** to create a quick note as a Google Doc\n"
        "- Use **drive_create_folder** + **docs_create** to organize notes in Drive\n"
        "- Use **gmail_send** to email yourself a note"
    )
