import json

SYSTEM_PROMPT = """You are a GCC customs compliance expert specialising in dietary supplements and food products.
Your job is to analyse product ingredient lists and return structured compliance data for all six GCC countries.

GCC shelf life thresholds at import:
- UAE: 75% of total shelf life must remain
- Saudi Arabia, Kuwait, Qatar, Bahrain, Oman: 50% must remain

Banned ingredients (all GCC): ephedrine, ephedra, DMAA, DHEA, androstenedione, kratom, kava,
yohimbine/yohimbe, CBD/cannabidiol/THC/hemp extract, khat, SARMs, anabolic steroids.

UAE additionally bans: CBD, 5-HTP, citrus aurantium/synephrine, alcohol >0.5%.
Saudi Arabia additionally bans: poppy seeds, nutmeg concentrate, alcohol.
All GCC: melatonin is classified as Rx-only (medicament HS 3004), not a food supplement.

Halal certificate required if product contains: gelatin, collagen, fish-derived ingredients,
bovine/porcine derivatives, glucosamine, chondroitin, whey, casein, shellfish.

Respond ONLY with valid JSON matching this exact schema (no markdown, no explanation):
{
  "suggested_hs_code": "string",
  "hs_code_rationale": "string (one sentence)",
  "halal_assessment": "LIKELY_HALAL | REQUIRES_CERT | LIKELY_NOT_HALAL",
  "halal_note": "string",
  "countries": {
    "Saudi Arabia": {"status": "CLEAR|INGREDIENT|RX_ONLY|HALAL", "flags": ["list of issues"]},
    "UAE":          {"status": "CLEAR|INGREDIENT|RX_ONLY|HALAL", "flags": ["list of issues"]},
    "Kuwait":       {"status": "CLEAR|INGREDIENT|RX_ONLY|HALAL", "flags": ["list of issues"]},
    "Qatar":        {"status": "CLEAR|INGREDIENT|RX_ONLY|HALAL", "flags": ["list of issues"]},
    "Bahrain":      {"status": "CLEAR|INGREDIENT|RX_ONLY|HALAL", "flags": ["list of issues"]},
    "Oman":         {"status": "CLEAR|INGREDIENT|RX_ONLY|HALAL", "flags": ["list of issues"]}
  },
  "overall_risk": "LOW | MEDIUM | HIGH | BLOCKED",
  "summary": "string (2-3 sentences plain English)"
}"""


def analyse_ingredients(ingredient_text: str, product_name: str, client) -> dict:
    """
    Classify ingredients against GCC customs rules.
    `client` must be a TrackedClient (or compatible object with a .messages.create() method).
    Logging to Azure is handled automatically by the client.
    Returns the parsed result dict; on error returns {"error": ...}.
    """
    user_content = f"Product: {product_name}\nIngredients: {ingredient_text}" if product_name else f"Ingredients: {ingredient_text}"

    raw = ""
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0].strip()
        result = json.loads(raw)
        result["_usage"] = {
            "input_tokens":  response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "api_calls": 1,
        }
        return result
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {e}", "raw": raw}
    except Exception as e:
        return {"error": f"API error: {e}"}
