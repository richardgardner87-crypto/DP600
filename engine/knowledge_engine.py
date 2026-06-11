"""
Knowledge Engine — farms GCC regulatory sources for ingredient rule changes.

Pipeline per source:
  1. Fetch index page (no LLM)
  2. Hash content → compare to iherb.source_hashes
  3. If changed: Haiku identifies relevant document links
  4. For each new/changed document: Opus extracts structured rules
  5. Suggestions written to iherb.suggested_rules (PENDING)
  6. All LLM calls logged to finops.token_usage via TrackedClient

Run from the Streamlit UI or directly:
    python -c "from engine.knowledge_engine import run_check; run_check()"
"""

import hashlib
import json
import uuid
import warnings
from datetime import datetime

from engine.db import execute, execute_batch, query_df
from engine.llm_client import TrackedClient

_PROJECT_ID = "iherb-gcc"
_PAGE       = "Knowledge Engine"

_EXTRACTION_SYSTEM = """You are a regulatory intelligence analyst specialising in GCC dietary supplement import rules.

Given text from an official regulatory source, identify any rules relating to:
1. Banned or restricted substances (ingredient name, scope, countries)
2. Rx-only / prescription-only classifications
3. Halal certification requirements
4. Shelf life thresholds at import

Return ONLY valid JSON in this exact structure (no markdown, no explanation):
{
  "rules": [
    {
      "canonical_name": "primary substance name in English",
      "restriction_type": "BANNED | RX_ONLY | HALAL_TRIGGER",
      "countries": ["ALL_GCC"] or ["Saudi Arabia", "UAE", ...],
      "aliases": ["every alternative name found in the text"],
      "source_text": "verbatim passage this was extracted from",
      "confidence": "HIGH | MEDIUM | LOW",
      "notes": "caveats, effective dates, or uncertainties"
    }
  ]
}

If no relevant rules are found, return {"rules": []}. Never invent rules not present in the source text."""

_NAVIGATION_SYSTEM = """You are a web navigation assistant. Given the HTML of a regulatory index page,
return a JSON list of URLs that likely contain dietary supplement import regulations, banned ingredient
lists, or food safety rules. Only include URLs present in the HTML.
Return ONLY valid JSON: {"urls": ["url1", "url2", ...]}"""


def _hash(content: str | bytes) -> str:
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()[:16]


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; GCC-Compliance-Engine/1.0; "
        "regulatory research bot; contact: compliance@riadyh.com)"
    )
}


def _fetch_page(url: str, timeout: int = 20) -> str | None:
    """
    Fetch a URL and return its text content.
    Uses httpx (pure Python, no binary deps). Falls back to Playwright
    for JS-heavy pages if httpx returns an empty or error body.
    """
    try:
        import httpx
        resp = httpx.get(url, headers=_HEADERS, timeout=timeout,
                         follow_redirects=True)
        if resp.status_code == 200 and len(resp.text) > 200:
            return resp.text
    except Exception as exc:
        warnings.warn(f"Knowledge Engine: httpx failed for {url} — {exc}")

    # Playwright fallback for JS-rendered pages (requires browser installation)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(extra_http_headers=_HEADERS)
            page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            content = page.content()
            browser.close()
            return content if len(content) > 200 else None
    except Exception as exc:
        warnings.warn(f"Knowledge Engine: Playwright fallback failed for {url} — {exc}")

    return None


def _stored_hash(url: str) -> str | None:
    df = query_df("SELECT content_hash FROM iherb.source_hashes WHERE url = %s", (url,))
    return df["content_hash"].iloc[0] if not df.empty else None


def _update_hash(url: str, new_hash: str, changed: bool):
    now = datetime.now().isoformat()
    execute(
        """INSERT INTO iherb.source_hashes (url, content_hash, last_checked, last_changed)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT (url) DO UPDATE SET
               content_hash = EXCLUDED.content_hash,
               last_checked = EXCLUDED.last_checked,
               last_changed = CASE WHEN iherb.source_hashes.content_hash != EXCLUDED.content_hash
                                   THEN EXCLUDED.last_changed
                                   ELSE iherb.source_hashes.last_changed END""",
        (url, new_hash, now, now if changed else None),
    )


def _find_document_links(html: str, base_url: str, client: TrackedClient) -> list[str]:
    """Use Haiku to identify relevant document URLs from an index page."""
    # Truncate HTML to avoid excessive tokens — keep first 8k chars
    snippet = html[:8000]
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=_NAVIGATION_SYSTEM,
            messages=[{"role": "user", "content": f"Base URL: {base_url}\n\nHTML:\n{snippet}"}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        data = json.loads(raw)
        return data.get("urls", [])
    except Exception as exc:
        warnings.warn(f"Knowledge Engine: link discovery failed — {exc}")
        return []


def _extract_rules(text: str, source_name: str, country: str, source_url: str,
                   client: TrackedClient) -> list[dict]:
    """Use Opus to extract structured rules from document text."""
    # Truncate to ~15k chars to stay within token limits while preserving context
    snippet = text[:15000]
    try:
        response = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=2048,
            system=_EXTRACTION_SYSTEM,
            messages=[{
                "role": "user",
                "content": (
                    f"Source: {source_name} ({country})\n"
                    f"URL: {source_url}\n\n"
                    f"Document text:\n{snippet}"
                ),
            }],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return json.loads(raw).get("rules", [])
    except Exception as exc:
        warnings.warn(f"Knowledge Engine: extraction failed for {source_url} — {exc}")
        return []


def _save_suggestions(rules: list[dict], source_name: str, country: str, source_url: str):
    if not rules:
        return
    rows = [
        (
            source_url,
            source_name,
            country,
            rule.get("source_text"),
            json.dumps(rule),
        )
        for rule in rules
    ]
    execute_batch(
        """INSERT INTO iherb.suggested_rules
           (source_url, source_name, country, extracted_text, proposed_change)
           VALUES (%s, %s, %s, %s, %s::jsonb)""",
        rows,
    )


def run_check(session_id: str | None = None) -> dict:
    """
    Run a full knowledge engine check across all active sources.
    Returns a summary dict: {checked, changed, suggestions_created}.
    """
    session_id = session_id or uuid.uuid4().hex[:8]
    client = TrackedClient(project_id=_PROJECT_ID, session_id=session_id, page=_PAGE)

    sources = query_df(
        "SELECT * FROM iherb.source_watch WHERE active = TRUE ORDER BY source_id"
    )

    checked = changed = suggestions = 0

    for _, src in sources.iterrows():
        url         = src["index_url"]
        source_name = src["source_name"]
        country     = src["country"] or "ALL_GCC"

        html = _fetch_page(url)
        if html is None:
            continue

        checked += 1
        new_hash   = _hash(html)
        old_hash   = _stored_hash(url)
        is_changed = new_hash != old_hash

        _update_hash(url, new_hash, is_changed)
        execute(
            "UPDATE iherb.source_watch SET last_checked = NOW() WHERE index_url = %s",
            (url,),
        )

        if not is_changed:
            continue

        changed += 1

        # Find document links on the changed index page
        doc_urls = _find_document_links(html, url, client)

        # Process each linked document
        for doc_url in doc_urls[:10]:  # cap per source to limit token burn
            doc_html = _fetch_page(doc_url)
            if doc_html is None:
                continue

            doc_hash     = _hash(doc_html)
            old_doc_hash = _stored_hash(doc_url)
            _update_hash(doc_url, doc_hash, doc_hash != old_doc_hash)

            if doc_hash == old_doc_hash:
                continue

            rules = _extract_rules(doc_html, source_name, country, doc_url, client)
            _save_suggestions(rules, source_name, country, doc_url)
            suggestions += len(rules)

        # Also extract directly from the index page itself
        index_rules = _extract_rules(html, source_name, country, url, client)
        _save_suggestions(index_rules, source_name, country, url)
        suggestions += len(index_rules)

    return {"checked": checked, "changed": changed, "suggestions_created": suggestions}


def accept_suggestion(suggestion_id: int, accepted_by: str, modified_change: dict | None = None):
    """
    Accept a PENDING suggestion, writing an SCD2 record to ingredient_rules
    and optionally updating ingredient_master / ingredient_aliases.
    """
    row = query_df(
        "SELECT * FROM iherb.suggested_rules WHERE suggestion_id = %s", (suggestion_id,)
    )
    if row.empty:
        raise ValueError(f"Suggestion {suggestion_id} not found")

    change = modified_change or json.loads(row["proposed_change"].iloc[0])

    # Close any active rule for this ingredient + country
    existing_id = row["existing_rule_id"].iloc[0]
    if existing_id:
        execute(
            """UPDATE iherb.ingredient_rules
               SET end_date = CURRENT_DATE,
                   supersession_notes = %s
               WHERE ingredient_id = %s AND end_date IS NULL""",
            (f"Superseded by suggestion {suggestion_id}", existing_id),
        )

    # Write new SCD2 rule row
    execute(
        """INSERT INTO iherb.ingredient_rules
           (ingredient_id, country, restriction_type, source_url, source_text, accepted_by)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (
            existing_id,
            change.get("countries", ["ALL_GCC"])[0],
            change.get("restriction_type", "BANNED"),
            row["source_url"].iloc[0],
            change.get("source_text"),
            accepted_by,
        ),
    )

    # Mark suggestion as accepted
    execute(
        """UPDATE iherb.suggested_rules
           SET status = 'ACCEPTED', reviewed_by = %s, reviewed_at = NOW()
           WHERE suggestion_id = %s""",
        (accepted_by, suggestion_id),
    )


def dismiss_suggestion(suggestion_id: int, reviewer: str, status: str, notes: str = ""):
    """Mark a suggestion as MODIFIED or IGNORED."""
    execute(
        """UPDATE iherb.suggested_rules
           SET status = %s, reviewed_by = %s, reviewed_at = NOW(), sme_notes = %s
           WHERE suggestion_id = %s""",
        (status, reviewer, notes, suggestion_id),
    )
