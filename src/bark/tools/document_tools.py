"""Tools for dealing with large documents, particularly spreadsheets.

These tools complement the basic sheets_read / sheets_write by adding:
- Spreadsheet metadata / sheet listing
- Paginated (chunked) reading so large sheets don't blow up the context
- Row-level search / filtering
- Append (rather than overwrite)
- Spreadsheet creation
- Large Google Docs chunked reading
"""

import csv
import io
import json
import logging
import re
from typing import Any

from bark.context.google_auth import get_google_auth
from bark.core.tools import tool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sheets_svc():
    """Get an authenticated Sheets service."""
    return get_google_auth().sheets


def _drive_svc():
    """Get an authenticated Drive service."""
    return get_google_auth().drive


def _col_letter(index: int) -> str:
    """Convert 0-based column index to A1-style column letter(s)."""
    result = ""
    while True:
        result = chr(ord("A") + index % 26) + result
        index = index // 26 - 1
        if index < 0:
            break
    return result


def _looks_like_header(row: list) -> bool:
    """Heuristic: guess whether a row is a column-header row or data.

    Returns False (= data) if the row contains email addresses,
    JSON-like strings, or is mostly numeric values.
    """
    if not row:
        return True  # empty row, treat as header to be safe

    email_pattern = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
    numeric_count = 0
    for cell in row:
        s = str(cell).strip()
        if not s:
            continue
        # Email addresses are almost never headers
        if email_pattern.search(s):
            return False
        # JSON / dict-like strings are data
        if s.startswith("{") or s.startswith("["):
            return False
        # Count pure numeric cells
        try:
            float(s.replace(",", ""))
            numeric_count += 1
        except ValueError:
            pass

    # If more than half the non-empty cells are numeric, it's probably data
    non_empty = sum(1 for c in row if str(c).strip())
    if non_empty > 0 and numeric_count / non_empty > 0.5:
        return False

    return True


def _format_table(rows: list[list[str]], offset: int = 0) -> str:
    """Format rows as a Markdown table.

    ``offset`` is the 0-based row offset in the original sheet so we can
    show correct row numbers.
    """
    if not rows:
        return "(empty)"

    # Normalise widths
    max_cols = max(len(r) for r in rows)
    normalised = [r + [""] * (max_cols - len(r)) for r in rows]

    header = normalised[0]
    lines = [
        "| Row | " + " | ".join(str(c) for c in header) + " |",
        "| --- | " + " | ".join("---" for _ in header) + " |",
    ]
    for i, row in enumerate(normalised[1:], start=1):
        row_num = offset + i + 1  # 1-indexed, after header
        lines.append(f"| {row_num} | " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


# =============================================================================
# SPREADSHEET METADATA
# =============================================================================


@tool(
    name="sheets_get_metadata",
    description=(
        "Get metadata about a Google Sheets spreadsheet: title, sheet/tab names, "
        "row counts, column counts.  Use this first to understand the structure of "
        "a spreadsheet before reading data."
    ),
    parameters={
        "type": "object",
        "properties": {
            "spreadsheet_id": {
                "type": "string",
                "description": "The spreadsheet ID (from the URL)",
            },
        },
        "required": ["spreadsheet_id"],
    },
)
def sheets_get_metadata(spreadsheet_id: str) -> str:
    """Return spreadsheet metadata including sheet names and sizes."""
    svc = _sheets_svc()

    meta = svc.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="properties.title,sheets(properties(sheetId,title,gridProperties))",
    ).execute()

    title = meta.get("properties", {}).get("title", "Untitled")
    sheets = meta.get("sheets", [])

    lines = [f"# 📊 {title}", f"Spreadsheet ID: `{spreadsheet_id}`", ""]
    lines.append(f"**{len(sheets)} sheet(s):**")
    for s in sheets:
        props = s.get("properties", {})
        name = props.get("title", "?")
        grid = props.get("gridProperties", {})
        rows = grid.get("rowCount", "?")
        cols = grid.get("columnCount", "?")
        sid = props.get("sheetId", "?")
        lines.append(f"- **{name}** — {rows} rows × {cols} cols (sheetId `{sid}`)")

    return "\n".join(lines)


# =============================================================================
# PAGINATED / CHUNKED READING
# =============================================================================


@tool(
    name="sheets_read_chunk",
    description=(
        "Read a chunk (page) of rows from a large spreadsheet.  Use this instead "
        "of sheets_read when a sheet has many rows.  Specify the sheet name and "
        "start_row / max_rows to paginate through the data.  Returns a Markdown "
        "table of the requested rows plus a header row."
    ),
    parameters={
        "type": "object",
        "properties": {
            "spreadsheet_id": {
                "type": "string",
                "description": "The spreadsheet ID",
            },
            "sheet_name": {
                "type": "string",
                "description": "Sheet/tab name (e.g. 'Sheet1')",
            },
            "start_row": {
                "type": "integer",
                "description": (
                    "1-indexed row number to start reading from. Row 1 is the "
                    "header. Pass 2 for the first data row. Default 1."
                ),
            },
            "max_rows": {
                "type": "integer",
                "description": "Maximum number of rows to return (default 50, max 200).",
            },
            "columns": {
                "type": "string",
                "description": (
                    "Optional column range in A1 notation, e.g. 'A:F'. "
                    "Leave empty to read all columns."
                ),
            },
        },
        "required": ["spreadsheet_id", "sheet_name"],
    },
)
def sheets_read_chunk(
    spreadsheet_id: str,
    sheet_name: str,
    start_row: int = 1,
    max_rows: int = 50,
    columns: str = "",
) -> str:
    """Read a page of rows from a spreadsheet."""
    svc = _sheets_svc()
    max_rows = min(max_rows, 200)

    # Always grab the header (row 1) so the result is self-describing
    end_row = start_row + max_rows - 1

    if columns:
        col_part = columns  # e.g. "A:F"
    else:
        col_part = ""

    # Build ranges: header + requested chunk
    ranges = []
    if start_row > 1:
        header_range = f"'{sheet_name}'!{col_part}1:1" if col_part else f"'{sheet_name}'!1:1"
        ranges.append(header_range)

    if col_part:
        data_range = f"'{sheet_name}'!{col_part}{start_row}:{end_row}"
    else:
        data_range = f"'{sheet_name}'!{start_row}:{end_row}"
    ranges.append(data_range)

    result = svc.spreadsheets().values().batchGet(
        spreadsheetId=spreadsheet_id,
        ranges=ranges,
    ).execute()

    value_ranges = result.get("valueRanges", [])
    all_rows: list[list[str]] = []
    for vr in value_ranges:
        all_rows.extend(vr.get("values", []))

    if not all_rows:
        return f"No data found in **{sheet_name}** starting at row {start_row}."

    # De-duplicate header if start_row == 1
    if start_row == 1:
        offset = 0
    else:
        offset = start_row - 2  # so row numbers align

    table = _format_table(all_rows, offset=offset)
    total_returned = len(all_rows) - (1 if start_row > 1 else 1)  # minus header
    note = (
        f"Showing rows {start_row}–{start_row + total_returned - 1} of **{sheet_name}**. "
        f"Use `start_row={start_row + total_returned}` to read the next chunk."
    )
    return f"{table}\n\n_{note}_"


# =============================================================================
# SEARCH / FILTER
# =============================================================================


@tool(
    name="sheets_search",
    description=(
        "Search for rows in a Google Sheet that match a query string in any column.  "
        "Returns matching rows (up to max_results) as a Markdown table.  "
        "The search is case-insensitive and matches partial cell values."
    ),
    parameters={
        "type": "object",
        "properties": {
            "spreadsheet_id": {
                "type": "string",
                "description": "The spreadsheet ID",
            },
            "query": {
                "type": "string",
                "description": "Text to search for (case-insensitive substring match)",
            },
            "sheet_name": {
                "type": "string",
                "description": "Sheet/tab name (default 'Sheet1')",
            },
            "max_results": {
                "type": "integer",
                "description": "Max matching rows to return (default 20)",
            },
        },
        "required": ["spreadsheet_id", "query"],
    },
)
def sheets_search(
    spreadsheet_id: str,
    query: str,
    sheet_name: str = "Sheet1",
    max_results: int = 20,
) -> str:
    """Search rows that contain the query string."""
    svc = _sheets_svc()

    # Read the whole sheet (Sheets API doesn't have server-side search)
    result = svc.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'",
    ).execute()

    values = result.get("values", [])
    if not values:
        return f"Sheet **{sheet_name}** is empty."

    # Auto-detect whether row 1 is a real header or data.
    # Heuristic: if row 1 contains emails, JSON-like strings, or is mostly
    # numeric, it's probably data, not headers.
    first_row = values[0]
    has_header = _looks_like_header(first_row)

    if has_header:
        header = first_row
        data_rows = values[1:]
        row_offset = 2  # 1-indexed, first data row is row 2
    else:
        # Generate synthetic column headers (A, B, C, ...)
        max_cols = max(len(r) for r in values) if values else 0
        header = [_col_letter(i) for i in range(max_cols)]
        data_rows = values  # ALL rows are data
        row_offset = 1  # first data row is row 1

    query_lower = query.lower()

    matches: list[tuple[int, list[str]]] = []
    for i, row in enumerate(data_rows):
        if any(query_lower in str(cell).lower() for cell in row):
            matches.append((row_offset + i, row))
            if len(matches) >= max_results:
                break

    if not matches:
        return f"No rows matching **\"{query}\"** found in **{sheet_name}**."

    # Build table
    max_cols = len(header)
    lines = [
        "| Row | " + " | ".join(str(c) for c in header) + " |",
        "| --- | " + " | ".join("---" for _ in header) + " |",
    ]
    for row_num, row in matches:
        padded = (row + [""] * max_cols)[:max_cols]
        lines.append(f"| {row_num} | " + " | ".join(str(c) for c in padded) + " |")

    total_rows = len(data_rows)
    return (
        "\n".join(lines)
        + f"\n\n_Found {len(matches)} match(es) for **\"{query}\"** "
        f"(searched {total_rows} rows in **{sheet_name}**)._"
    )


@tool(
    name="sheets_filter_column",
    description=(
        "Filter rows in a Google Sheet where a specific column matches a value.  "
        "Supports exact match, 'contains', 'starts_with', and 'regex' modes."
    ),
    parameters={
        "type": "object",
        "properties": {
            "spreadsheet_id": {
                "type": "string",
                "description": "The spreadsheet ID",
            },
            "sheet_name": {
                "type": "string",
                "description": "Sheet/tab name",
            },
            "column": {
                "type": "string",
                "description": "Column header name to filter on (case-insensitive)",
            },
            "value": {
                "type": "string",
                "description": "Value to match against",
            },
            "match_mode": {
                "type": "string",
                "description": (
                    "How to match: 'exact', 'contains', 'starts_with', 'regex'. "
                    "Default 'contains'."
                ),
            },
            "max_results": {
                "type": "integer",
                "description": "Max rows to return (default 30)",
            },
        },
        "required": ["spreadsheet_id", "sheet_name", "column", "value"],
    },
)
def sheets_filter_column(
    spreadsheet_id: str,
    sheet_name: str,
    column: str,
    value: str,
    match_mode: str = "contains",
    max_results: int = 30,
) -> str:
    """Filter rows by a specific column value."""
    svc = _sheets_svc()

    result = svc.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'",
    ).execute()

    values = result.get("values", [])
    if not values:
        return f"Sheet **{sheet_name}** is empty."

    header = [str(h).strip().lower() for h in values[0]]
    col_lower = column.strip().lower()

    if col_lower not in header:
        available = ", ".join(f"`{h}`" for h in values[0])
        return f"Column **\"{column}\"** not found. Available columns: {available}"

    col_idx = header.index(col_lower)
    val_lower = value.lower()

    def matches(cell_val: str) -> bool:
        cv = cell_val.lower()
        if match_mode == "exact":
            return cv == val_lower
        elif match_mode == "starts_with":
            return cv.startswith(val_lower)
        elif match_mode == "regex":
            try:
                return bool(re.search(value, cell_val, re.IGNORECASE))
            except re.error:
                return False
        else:  # contains
            return val_lower in cv

    matched: list[tuple[int, list[str]]] = []
    for i, row in enumerate(values[1:], start=2):
        cell = str(row[col_idx]) if col_idx < len(row) else ""
        if matches(cell):
            matched.append((i, row))
            if len(matched) >= max_results:
                break

    if not matched:
        return (
            f"No rows where column **\"{column}\"** {match_mode} "
            f"**\"{value}\"** in **{sheet_name}**."
        )

    orig_header = values[0]
    max_cols = len(orig_header)
    lines = [
        "| Row | " + " | ".join(str(c) for c in orig_header) + " |",
        "| --- | " + " | ".join("---" for _ in orig_header) + " |",
    ]
    for row_num, row in matched:
        padded = (row + [""] * max_cols)[:max_cols]
        lines.append(f"| {row_num} | " + " | ".join(str(c) for c in padded) + " |")

    return (
        "\n".join(lines)
        + f"\n\n_Found {len(matched)} row(s) where **\"{column}\"** "
        f"{match_mode} **\"{value}\"**._"
    )


# =============================================================================
# COLUMN SUMMARY / STATS
# =============================================================================


@tool(
    name="sheets_column_stats",
    description=(
        "Get summary statistics for a column in a Google Sheet.  "
        "For numeric columns: count, sum, mean, min, max.  "
        "For text columns: count, unique count, top values."
    ),
    parameters={
        "type": "object",
        "properties": {
            "spreadsheet_id": {
                "type": "string",
                "description": "The spreadsheet ID",
            },
            "sheet_name": {
                "type": "string",
                "description": "Sheet/tab name",
            },
            "column": {
                "type": "string",
                "description": "Column header name (case-insensitive)",
            },
        },
        "required": ["spreadsheet_id", "sheet_name", "column"],
    },
)
def sheets_column_stats(
    spreadsheet_id: str,
    sheet_name: str,
    column: str,
) -> str:
    """Get summary statistics for a column."""
    svc = _sheets_svc()

    result = svc.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'",
    ).execute()

    values = result.get("values", [])
    if not values:
        return f"Sheet **{sheet_name}** is empty."

    header = [str(h).strip().lower() for h in values[0]]
    col_lower = column.strip().lower()

    if col_lower not in header:
        available = ", ".join(f"`{h}`" for h in values[0])
        return f"Column **\"{column}\"** not found. Available columns: {available}"

    col_idx = header.index(col_lower)
    col_values = []
    for row in values[1:]:
        if col_idx < len(row) and str(row[col_idx]).strip():
            col_values.append(str(row[col_idx]).strip())

    if not col_values:
        return f"Column **\"{column}\"** has no non-empty values."

    lines = [f"## Stats for column **\"{values[0][col_idx]}\"** in **{sheet_name}**", ""]

    # Try numeric
    numeric_vals: list[float] = []
    for v in col_values:
        try:
            # Handle common number formats: $1,234.56 → 1234.56
            cleaned = re.sub(r"[,$%]", "", v)
            numeric_vals.append(float(cleaned))
        except ValueError:
            pass

    if len(numeric_vals) > len(col_values) * 0.5:
        # Treat as numeric column
        lines.append(f"- **Count:** {len(col_values)}")
        lines.append(f"- **Numeric values:** {len(numeric_vals)}")
        lines.append(f"- **Sum:** {sum(numeric_vals):,.2f}")
        lines.append(f"- **Mean:** {sum(numeric_vals) / len(numeric_vals):,.2f}")
        lines.append(f"- **Min:** {min(numeric_vals):,.2f}")
        lines.append(f"- **Max:** {max(numeric_vals):,.2f}")
        sorted_vals = sorted(numeric_vals)
        mid = len(sorted_vals) // 2
        median = (
            sorted_vals[mid]
            if len(sorted_vals) % 2
            else (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
        )
        lines.append(f"- **Median:** {median:,.2f}")
    else:
        # Text column
        from collections import Counter
        counter = Counter(col_values)
        lines.append(f"- **Count:** {len(col_values)}")
        lines.append(f"- **Unique values:** {len(counter)}")
        lines.append("")
        lines.append("**Top values:**")
        for val, count in counter.most_common(10):
            lines.append(f"- `{val}` — {count} occurrence(s)")

    return "\n".join(lines)


# =============================================================================
# APPEND ROWS
# =============================================================================


@tool(
    name="sheets_append",
    description=(
        "Append rows to the end of a Google Sheet (after the last row with data).  "
        "Provide data as rows of comma-separated values, one row per line."
    ),
    parameters={
        "type": "object",
        "properties": {
            "spreadsheet_id": {
                "type": "string",
                "description": "The spreadsheet ID",
            },
            "sheet_name": {
                "type": "string",
                "description": "Sheet/tab name to append to (default 'Sheet1')",
            },
            "data": {
                "type": "string",
                "description": (
                    "Data to append (CSV format). Each line is a row, "
                    "columns separated by commas."
                ),
            },
        },
        "required": ["spreadsheet_id", "data"],
    },
)
def sheets_append(
    spreadsheet_id: str,
    data: str,
    sheet_name: str = "Sheet1",
) -> str:
    """Append rows to the end of a sheet."""
    svc = _sheets_svc()

    # Use csv reader to handle quoted commas properly
    reader = csv.reader(io.StringIO(data.strip()))
    rows = list(reader)

    result = svc.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ).execute()

    updates = result.get("updates", {})
    updated_rows = updates.get("updatedRows", 0)
    updated_range = updates.get("updatedRange", "?")

    return (
        f"✅ Appended **{updated_rows}** row(s) to **{sheet_name}**.\n"
        f"Range: `{updated_range}`"
    )


# =============================================================================
# CREATE SPREADSHEET
# =============================================================================


@tool(
    name="sheets_create",
    description=(
        "Create a new Google Sheets spreadsheet with a title and optional "
        "initial sheet names."
    ),
    parameters={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Title for the new spreadsheet",
            },
            "sheet_names": {
                "type": "string",
                "description": (
                    "Comma-separated list of sheet/tab names to create "
                    "(default: just 'Sheet1')"
                ),
            },
        },
        "required": ["title"],
    },
)
def sheets_create(title: str, sheet_names: str = "") -> str:
    """Create a new spreadsheet."""
    svc = _sheets_svc()

    body: dict[str, Any] = {
        "properties": {"title": title},
    }

    if sheet_names:
        names = [n.strip() for n in sheet_names.split(",") if n.strip()]
        body["sheets"] = [
            {"properties": {"title": name}} for name in names
        ]

    spreadsheet = svc.spreadsheets().create(body=body).execute()
    ss_id = spreadsheet["spreadsheetId"]
    url = spreadsheet.get("spreadsheetUrl", f"https://docs.google.com/spreadsheets/d/{ss_id}")

    created_sheets = [
        s["properties"]["title"] for s in spreadsheet.get("sheets", [])
    ]

    return (
        f"✅ Created spreadsheet **{title}**\n"
        f"ID: `{ss_id}`\n"
        f"URL: {url}\n"
        f"Sheets: {', '.join(created_sheets)}"
    )


# =============================================================================
# ADD / DELETE SHEETS (TABS)
# =============================================================================


@tool(
    name="sheets_add_sheet",
    description="Add a new sheet (tab) to an existing Google Spreadsheet.",
    parameters={
        "type": "object",
        "properties": {
            "spreadsheet_id": {
                "type": "string",
                "description": "The spreadsheet ID",
            },
            "sheet_title": {
                "type": "string",
                "description": "Name of the new sheet/tab",
            },
        },
        "required": ["spreadsheet_id", "sheet_title"],
    },
)
def sheets_add_sheet(spreadsheet_id: str, sheet_title: str) -> str:
    """Add a new sheet tab to a spreadsheet."""
    svc = _sheets_svc()

    body = {
        "requests": [
            {
                "addSheet": {
                    "properties": {"title": sheet_title}
                }
            }
        ]
    }

    result = svc.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id, body=body
    ).execute()

    new_sheet = result["replies"][0]["addSheet"]["properties"]
    return (
        f"✅ Added sheet **{new_sheet['title']}** "
        f"(sheetId `{new_sheet['sheetId']}`)"
    )


# =============================================================================
# CLEAR A RANGE
# =============================================================================


@tool(
    name="sheets_clear",
    description="Clear all values from a range in a Google Sheet (keeps formatting).",
    parameters={
        "type": "object",
        "properties": {
            "spreadsheet_id": {
                "type": "string",
                "description": "The spreadsheet ID",
            },
            "range": {
                "type": "string",
                "description": "A1 range to clear, e.g. 'Sheet1!A2:Z' or 'Sheet1'",
            },
        },
        "required": ["spreadsheet_id", "range"],
    },
)
def sheets_clear(spreadsheet_id: str, range: str) -> str:
    """Clear values from a range."""
    svc = _sheets_svc()

    result = svc.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=range,
        body={},
    ).execute()

    cleared = result.get("clearedRange", range)
    return f"✅ Cleared range `{cleared}`."


# =============================================================================
# LARGE DOC CHUNKED READING
# =============================================================================


@tool(
    name="docs_read_chunk",
    description=(
        "Read a chunk of a large Google Doc by character offset.  "
        "Use this for very long documents that are too large to read at once.  "
        "First call with start=0 to get the beginning; use the returned "
        "next_start value to read subsequent chunks."
    ),
    parameters={
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "The Google Docs document ID",
            },
            "start": {
                "type": "integer",
                "description": "Character offset to start reading from (default 0)",
            },
            "max_chars": {
                "type": "integer",
                "description": "Maximum characters to return (default 4000, max 8000)",
            },
        },
        "required": ["document_id"],
    },
)
def docs_read_chunk(
    document_id: str,
    start: int = 0,
    max_chars: int = 4000,
) -> str:
    """Read a chunk of a large Google Doc."""
    from bark.tools.google_workspace_tools import _extract_doc_content

    auth = get_google_auth()
    svc = auth.docs

    doc = svc.documents().get(documentId=document_id).execute()
    title = doc.get("title", "Untitled")

    # Extract full text (including tables rendered as Markdown)
    body_content = doc.get("body", {}).get("content", [])
    full_text = _extract_doc_content(body_content)
    total_len = len(full_text)

    max_chars = min(max_chars, 8000)
    chunk = full_text[start : start + max_chars]
    end = start + len(chunk)
    has_more = end < total_len

    lines = [f"# {title}"]
    lines.append(f"_Characters {start}–{end} of {total_len} total_")
    if has_more:
        lines.append(f"_Use `start={end}` to read the next chunk._")
    else:
        lines.append("_(End of document)_")
    lines.append("")
    lines.append(chunk)

    return "\n".join(lines)


# =============================================================================
# SPREADSHEET EXPORT TO CSV
# =============================================================================


@tool(
    name="sheets_export_csv",
    description=(
        "Export a sheet as CSV text.  Useful for piping into other tools or "
        "saving to memory.  For very large sheets the output will be truncated."
    ),
    parameters={
        "type": "object",
        "properties": {
            "spreadsheet_id": {
                "type": "string",
                "description": "The spreadsheet ID",
            },
            "sheet_name": {
                "type": "string",
                "description": "Sheet/tab name (default 'Sheet1')",
            },
            "max_rows": {
                "type": "integer",
                "description": "Maximum rows to include (default 500)",
            },
        },
        "required": ["spreadsheet_id"],
    },
)
def sheets_export_csv(
    spreadsheet_id: str,
    sheet_name: str = "Sheet1",
    max_rows: int = 500,
) -> str:
    """Export a sheet as CSV text."""
    svc = _sheets_svc()

    result = svc.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'",
    ).execute()

    values = result.get("values", [])
    if not values:
        return f"Sheet **{sheet_name}** is empty."

    truncated = len(values) > max_rows
    values = values[:max_rows]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerows(values)
    csv_text = output.getvalue()

    header = f"# {sheet_name} (CSV export)\n"
    if truncated:
        header += f"_⚠️ Truncated to {max_rows} rows._\n"
    header += "\n```csv\n"
    footer = "\n```"

    return header + csv_text + footer


# =============================================================================
# BATCH GET SPECIFIC ROWS
# =============================================================================


@tool(
    name="sheets_get_rows",
    description=(
        "Get specific rows from a Google Sheet by row numbers.  "
        "Useful for reading a handful of scattered rows without loading the "
        "entire sheet."
    ),
    parameters={
        "type": "object",
        "properties": {
            "spreadsheet_id": {
                "type": "string",
                "description": "The spreadsheet ID",
            },
            "sheet_name": {
                "type": "string",
                "description": "Sheet/tab name",
            },
            "row_numbers": {
                "type": "string",
                "description": (
                    "Comma-separated 1-indexed row numbers to retrieve, "
                    "e.g. '1,5,10,42'.  Row 1 is typically the header."
                ),
            },
        },
        "required": ["spreadsheet_id", "sheet_name", "row_numbers"],
    },
)
def sheets_get_rows(
    spreadsheet_id: str,
    sheet_name: str,
    row_numbers: str,
) -> str:
    """Get specific rows by number."""
    svc = _sheets_svc()

    nums = []
    for part in row_numbers.split(","):
        part = part.strip()
        if part.isdigit():
            nums.append(int(part))
    if not nums:
        return "❌ No valid row numbers provided."

    # Always include row 1 (header) if not already present
    if 1 not in nums:
        nums = [1] + nums
    nums = sorted(set(nums))

    # Build ranges
    ranges = [f"'{sheet_name}'!{n}:{n}" for n in nums]

    result = svc.spreadsheets().values().batchGet(
        spreadsheetId=spreadsheet_id,
        ranges=ranges,
    ).execute()

    value_ranges = result.get("valueRanges", [])

    # Collect header and data
    all_rows: list[tuple[int, list[str]]] = []
    for vr, row_num in zip(value_ranges, nums):
        vals = vr.get("values", [[]])
        if vals:
            all_rows.append((row_num, vals[0]))

    if not all_rows:
        return "No data found for the requested rows."

    # Use first row as header
    header_row = all_rows[0][1] if all_rows else []
    max_cols = len(header_row)

    lines = [
        "| Row | " + " | ".join(str(c) for c in header_row) + " |",
        "| --- | " + " | ".join("---" for _ in header_row) + " |",
    ]
    for row_num, row in all_rows[1:]:
        padded = (row + [""] * max_cols)[:max_cols]
        lines.append(f"| {row_num} | " + " | ".join(str(c) for c in padded) + " |")

    return "\n".join(lines)
