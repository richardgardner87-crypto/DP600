import os
import json
import anthropic
from dotenv import load_dotenv

load_dotenv()

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


def analyse_ingredients(ingredient_text: str, product_name: str = "") -> dict:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not set in .env"}

    client = anthropic.Anthropic(api_key=api_key)

    user_content = f"Product: {product_name}\nIngredients: {ingredient_text}" if product_name else f"Ingredients: {ingredient_text}"

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        raw = response.content[0].text.strip()
        return json.loads(raw)
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {e}", "raw": raw}
    except anthropic.APIError as e:
        return {"error": f"API error: {e}"}
