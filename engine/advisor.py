import json
from datetime import date

import pandas as pd

from engine.rules import COUNTRIES

TOOLS = [
    {
        "name": "search_inventory",
        "description": (
            "Search the warehouse inventory. Call this before making any specific claim "
            "about products, quantities or values. Returns matching SKUs with their "
            "compliance status for every GCC country."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sku_id":               {"type": "string", "description": "Exact SKU ID"},
                "category":             {"type": "string", "description": "Product category e.g. Vitamins, Omega, Protein, Herbal"},
                "brand":                {"type": "string"},
                "worst_status":         {"type": "string", "enum": ["CLEAR","SHELF_LIFE","HALAL","INGREDIENT","RX_ONLY"]},
                "uae_status":           {"type": "string", "enum": ["CLEAR","SHELF_LIFE","HALAL","INGREDIENT","RX_ONLY"]},
                "ksa_status":           {"type": "string", "enum": ["CLEAR","SHELF_LIFE","HALAL","INGREDIENT","RX_ONLY"]},
                "uae_breach_within_days": {"type": "integer", "description": "Products whose UAE threshold breach is within N days"},
                "halal_certified":      {"type": "string", "enum": ["yes","no"]},
                "ingredient_keyword":   {"type": "string", "description": "Search for a word in the ingredients list e.g. 'melatonin', 'gelatin', 'whey'"},
            },
        },
    },
    {
        "name": "get_risk_summary",
        "description": (
            "Aggregate risk metrics — total stock value and unit count at risk of becoming "
            "non-compliant within a time horizon. Breaks down by country and optionally by category."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "horizon_days": {"type": "integer", "description": "Look-ahead window e.g. 30, 90, 180"},
                "country":      {"type": "string", "description": "Specific country — omit for all GCC"},
                "category":     {"type": "string", "description": "Limit to one product category"},
            },
            "required": ["horizon_days"],
        },
    },
]

SYSTEM = """You are a GCC customs compliance advisor for a dietary supplements distributor's Saudi Arabia logistics centre.
You have real-time access to the warehouse inventory via tools — always query before making specific claims.

Your role is to help warehouse managers understand:
- Which products can ship to which GCC country right now
- Which products are at risk of losing compliance soon
- What actions to take: reroute to lower-threshold countries, apply bulk discounts, or write off

Key rules you enforce:
- UAE requires 75% remaining shelf life at import — the strictest in GCC (MEDIUM confidence — well-sourced but some variation cited)
- Qatar requires 50% OR 12 months absolute remaining, whichever is more restrictive (MEDIUM confidence — 12-month absolute rule sourced from official registrar)
- Saudi Arabia: the old 50% SASO 457 rule was officially abolished; SFDA now reviews case-by-case — threshold in the engine is 50% as a conservative fallback (LOW confidence — treat as a guideline, not a hard rule)
- Kuwait: previous 50% rule reportedly relaxed; current rule unverified — engine uses 50% as a fallback (LOW confidence)
- Bahrain and Oman: no country-specific rule confirmed — engine assumes 50% GSO baseline (LOW confidence)
- Banned everywhere: CBD/cannabidiol, ephedrine/ephedra, DMAA, yohimbine, kava, kratom, DHEA
- UAE additional bans: 5-HTP, synephrine/citrus aurantium
- Melatonin = Rx-only in all GCC (classified as medicament under HS 3004, cannot import as supplement)
- Products with animal-derived ingredients (gelatin, fish oil, collagen, whey, casein, shellfish) need a Halal certificate

When discussing Saudi Arabia, Kuwait, Bahrain, or Oman compliance, mention the LOW confidence level if it's relevant to the decision — e.g. when a product is right on the borderline.

Response style:
- Be specific: name products, quote quantities and dollar values
- Lead with the most urgent finding
- Give a clear recommendation — not just a status
- Keep it concise — warehouse managers are busy"""


def _run_tool(name: str, inputs: dict, df: pd.DataFrame) -> str:
    if name == "search_inventory":
        result = df.copy()

        if "sku_id" in inputs:
            result = result[result["sku_id"] == inputs["sku_id"]]
        if "category" in inputs:
            result = result[result["category"].str.lower() == inputs["category"].lower()]
        if "brand" in inputs:
            result = result[result["brand"].str.lower().str.contains(inputs["brand"].lower())]
        if "worst_status" in inputs:
            result = result[result["worst_status"] == inputs["worst_status"]]
        if "uae_status" in inputs:
            result = result[result["status_UAE"] == inputs["uae_status"]]
        if "ksa_status" in inputs:
            result = result[result["status_Saudi Arabia"] == inputs["ksa_status"]]
        if "halal_certified" in inputs:
            result = result[result["halal_certified"].str.lower() == inputs["halal_certified"]]
        if "ingredient_keyword" in inputs:
            kw = inputs["ingredient_keyword"].lower()
            result = result[result["ingredients"].str.lower().str.contains(kw, na=False)]
        if "uae_breach_within_days" in inputs:
            d = inputs["uae_breach_within_days"]
            result = result[(result["breach_days_UAE"] >= 0) & (result["breach_days_UAE"] <= d)]

        if result.empty:
            return json.dumps({"count": 0, "total_value_usd": 0, "products": []})

        products = []
        for _, r in result.iterrows():
            products.append({
                "sku": r["sku_id"],
                "name": r["product_name"],
                "category": r["category"],
                "qty": int(r["qty_on_hand"]),
                "value_usd": float(r["stock_value_usd"]),
                "days_remaining": int(r["days_remaining"]),
                "remaining_pct": f"{r['remaining_pct']*100:.1f}%",
                "uae_breach_in_days": int(r["breach_days_UAE"]),
                "country_statuses": {c: r[f"status_{c}"] for c in COUNTRIES},
                "flagged_ingredients": r["flagged_ingredients"] if r["flagged_ingredients"] != "—" else None,
                "halal_certified": r["halal_certified"],
                "recommended_action": r["recommended_action"],
            })

        return json.dumps({
            "count": len(products),
            "total_value_usd": round(result["stock_value_usd"].sum(), 2),
            "total_qty": int(result["qty_on_hand"].sum()),
            "products": products[:25],
        })

    elif name == "get_risk_summary":
        horizon = inputs["horizon_days"]
        filter_country = inputs.get("country")
        filter_category = inputs.get("category")

        scope = df.copy()
        if filter_category:
            scope = scope[scope["category"].str.lower() == filter_category.lower()]

        countries = [filter_country] if filter_country else COUNTRIES
        out = {}
        for c in countries:
            breach_col = f"breach_days_{c}"
            at_risk = scope[
                (scope[f"status_{c}"] == "CLEAR") &
                (scope[breach_col] >= 0) &
                (scope[breach_col] <= horizon)
            ]
            blocked = scope[scope[f"status_{c}"] != "CLEAR"]
            out[c] = {
                "currently_shippable": int((scope[f"status_{c}"] == "CLEAR").sum()),
                "at_risk_next_n_days": {"count": len(at_risk), "value_usd": round(at_risk["stock_value_usd"].sum(), 2)},
                "already_blocked":     {"count": len(blocked),  "value_usd": round(blocked["stock_value_usd"].sum(), 2)},
            }

        return json.dumps({
            "horizon_days": horizon,
            "total_inventory_value_usd": round(scope["stock_value_usd"].sum(), 2),
            "by_country": out,
        })

    return json.dumps({"error": f"Unknown tool: {name}"})


# System prompt formatted for prompt caching — must be identical across warm-up
# and real calls so Anthropic's cache key matches.
_CACHED_SYSTEM = [{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}]


def warm_cache(client) -> None:
    """
    Fire a minimal API call in a background thread to load the system prompt
    into Anthropic's prompt cache. Call this when the user enters the app so
    the cache is warm before they reach Compliance Chat.
    """
    import threading

    def _call():
        try:
            client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1,
                system=_CACHED_SYSTEM,
                tools=TOOLS,
                messages=[{"role": "user", "content": "Ready."}],
            )
        except Exception:
            pass  # warm-up failure is silent — real calls still work uncached

    threading.Thread(target=_call, daemon=True).start()


def chat(messages: list, df: pd.DataFrame, client) -> tuple[str, list, dict]:
    """
    One turn of the agentic chat loop.
    Returns (reply_text, updated_messages, usage) where usage is the aggregate
    across all tool-call rounds — used by the caller for per-message UI captions.
    Logging to Azure is handled automatically by the TrackedClient.
    """
    working_messages = list(messages)
    usage = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0}

    for _ in range(3):  # max tool-call rounds
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=_CACHED_SYSTEM,
            tools=TOOLS,
            messages=working_messages,
        )

        usage["input_tokens"]  += response.usage.input_tokens
        usage["output_tokens"] += response.usage.output_tokens
        usage["api_calls"]     += 1

        if response.stop_reason == "end_turn":
            text = next((b.text for b in response.content if hasattr(b, "text")), "")
            working_messages.append({"role": "assistant", "content": response.content})
            return text, working_messages, usage

        if response.stop_reason == "tool_use":
            working_messages.append({"role": "assistant", "content": response.content})
            results = [
                {
                    "type": "tool_result",
                    "tool_use_id": b.id,
                    "content": _run_tool(b.name, b.input, df),
                }
                for b in response.content if b.type == "tool_use"
            ]
            working_messages.append({"role": "user", "content": results})

    return "Reached tool call limit — please rephrase your question.", messages, usage
