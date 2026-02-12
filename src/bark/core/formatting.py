"""Platform-specific formatting instructions for Bark.

Provides constants that tell the LLM how to format its output depending
on the target platform (Slack, Gmail, Google Docs).  These are injected
into the system prompt via `system_prompt_addendum` or referenced in
tool descriptions.
"""

# ---------------------------------------------------------------------------
# Slack  –  uses Slack's custom "mrkdwn" syntax
# ---------------------------------------------------------------------------
SLACK_FORMAT_INSTRUCTIONS = """\
Use Slack's mrkdwn syntax for formatting:
- Bold: *text* (not **text**)
- Italic: _text_ (not *text*)
- Strikethrough: ~text~
- Code: `code` or ```code block```
- Links: <URL|text>
- Blockquotes: > text
- Bullet lists: - item or • item
- Ordered lists: 1. item

Do NOT use standard Markdown syntax — it will not render correctly in Slack."""

# ---------------------------------------------------------------------------
# Gmail  –  HTML email bodies
# ---------------------------------------------------------------------------
GMAIL_FORMAT_INSTRUCTIONS = """\
When composing email bodies for Gmail, write valid HTML so the email renders
with rich formatting. Use these elements:
- Bold: <b>text</b> or <strong>text</strong>
- Italic: <i>text</i> or <em>text</em>
- Links: <a href="URL">text</a>
- Headings: <h3>heading</h3> (avoid <h1>/<h2> as they look too large in email)
- Bullet lists: <ul><li>item</li></ul>
- Numbered lists: <ol><li>item</li></ol>
- Paragraphs: <p>text</p>
- Line breaks: <br>
- Horizontal rule: <hr>

Keep the HTML simple — avoid external CSS, JavaScript, or complex layouts.
Do NOT use Markdown or Slack mrkdwn in email bodies."""

# ---------------------------------------------------------------------------
# Google Docs  –  plain text (the Docs API handles styling separately)
# ---------------------------------------------------------------------------
GOOGLE_DOCS_FORMAT_INSTRUCTIONS = """\
When writing content for Google Docs, use clean plain text only.
- Do NOT use Markdown syntax (no **, ##, [](), etc.)
- Do NOT use HTML tags.
- Use natural headings by writing them on their own line; the Docs API handles
  styling separately.
- Use simple numbered or bulleted lists with "- " or "1. " prefixes.
- Keep formatting minimal — the document owner will apply styling in Docs."""
