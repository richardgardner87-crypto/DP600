"""
Parse product information pasted from an iHerb product page.
iHerb blocks all automated access (Cloudflare); the user pastes the
"Other Ingredients" block directly from their browser.
"""

import re


def parse_pasted_block(text: str) -> dict:
    """
    Extract main ingredients and other ingredients from text pasted from
    the iHerb product page (the "Other Ingredients" info block).

    Returns dict with keys:
      main_ingredients  – str (active / supplement-facts ingredients)
      other_ingredients – str (excipients, capsule material, etc.)
      contains          – str (allergen statement, e.g. "Contains: Soy")
      ingredients       – str (combined, comma-separated — used for compliance)
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    sections: dict[str, list[str]] = {}
    current: str | None = None

    HEADERS = {
        "main ingredients":   "main",
        "other ingredients":  "other",
        "supplement facts":   "main",
        "ingredients":        "main",
    }

    for line in lines:
        ll = line.lower()
        matched = next((v for k, v in HEADERS.items() if ll == k or ll.startswith(k + ":")), None)
        if matched:
            current = matched
            # Handle "Other Ingredients: foo, bar" on same line
            rest = re.split(r":\s*", line, maxsplit=1)
            if len(rest) == 2 and rest[1].strip():
                sections.setdefault(current, []).append(rest[1].strip())
            continue

        if ll.startswith("contains:") or ll.startswith("contains "):
            sections["contains"] = [line]
            current = None
            continue

        if current:
            # Stop if we hit a clearly unrelated section
            if ll in {"directions", "suggested use", "warnings", "disclaimer"}:
                current = None
                continue
            sections.setdefault(current, []).append(line)

    main  = " ".join(sections.get("main",  [])).strip()
    other = " ".join(sections.get("other", [])).strip()
    contains = " ".join(sections.get("contains", [])).strip()

    # Combined for compliance engine
    combined_parts = [p for p in [main, other] if p]
    combined = ", ".join(combined_parts)

    return {
        "main_ingredients":  main,
        "other_ingredients": other,
        "contains":          contains,
        "ingredients":       combined,
    }


def iherb_search_url(product_name: str) -> str:
    """Return an iHerb search URL for the given product name."""
    from urllib.parse import quote
    return f"https://www.iherb.com/search?kw={quote(product_name)}"
