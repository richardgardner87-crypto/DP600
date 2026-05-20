from datetime import date
from dataclasses import dataclass, field
from typing import Optional

COUNTRIES = ["Saudi Arabia", "UAE", "Kuwait", "Qatar", "Bahrain", "Oman"]

# ── Shelf life thresholds ──────────────────────────────────────────────────────
# Minimum remaining shelf life as a fraction of total shelf life at time of import.
# These are the PERCENTAGE-based rules. Some countries also have ABSOLUTE minimums.
SHELF_LIFE_THRESHOLDS = {
    "Saudi Arabia": 0.50,
    "UAE":          0.75,
    "Kuwait":       0.50,
    "Qatar":        0.50,
    "Bahrain":      0.50,
    "Oman":         0.50,
}

# Absolute minimum remaining days — applied IN ADDITION to the percentage threshold
# (whichever is more restrictive wins). Qatar requires 12 months absolute for supplements.
SHELF_LIFE_MIN_DAYS = {
    "Qatar": 365,
}

# Confidence metadata for each country's shelf life rule
SHELF_LIFE_CONFIDENCE = {
    "Saudi Arabia": {
        "level": "LOW",
        "threshold_display": "~50% (unverified)",
        "note": "Old SASO 457 50% rule officially abolished; replacement unconfirmed. "
                "SFDA now assesses on a case-by-case basis.",
        "source": "saudifoodregistration.com",
    },
    "UAE": {
        "level": "MEDIUM",
        "threshold_display": "75%",
        "note": "Multiple sources confirm ~75%; some cite 50–75% range — "
                "may vary by product type and emirate.",
        "source": "productregistrationuae.com, bagason.com",
    },
    "Kuwait": {
        "level": "LOW",
        "threshold_display": "~50% (unverified)",
        "note": "Previous 50% rule reportedly eliminated under newer standards. "
                "Current requirement unverified.",
        "source": "USDA GAIN report",
    },
    "Qatar": {
        "level": "MEDIUM",
        "threshold_display": "50% + 12 months absolute",
        "note": "Sources cite a 12-month absolute minimum remaining for supplements "
                "(not purely percentage-based). More restrictive than 50% for products "
                "with shelf life under 24 months.",
        "source": "productregistrationqatar.com",
    },
    "Bahrain": {
        "level": "LOW",
        "threshold_display": "~50% (assumed)",
        "note": "No country-specific rule confirmed. Assumed to follow GSO baseline.",
        "source": "Assumed — not verified",
    },
    "Oman": {
        "level": "LOW",
        "threshold_display": "~50% (assumed)",
        "note": "No country-specific rule confirmed. Assumed to follow GSO baseline.",
        "source": "Assumed — not verified",
    },
}

CONFIDENCE_ICON = {"HIGH": "✓", "MEDIUM": "~", "LOW": "?"}
CONFIDENCE_COLOR = {"HIGH": "#2ecc71", "MEDIUM": "#f39c12", "LOW": "#e74c3c"}

# ── Banned ingredients ─────────────────────────────────────────────────────────
BANNED_ALL = [
    "ephedrine", "ephedra", "ephedra sinica", "pseudoephedrine", "ephedra alkaloids",
    "dmaa", "1,3-dimethylamylamine", "dimethylamylamine",
    "dhea", "dehydroepiandrosterone",
    "androstenedione",
    "kratom", "mitragyna speciosa",
    "kava", "piper methysticum", "kava kava",
    "yohimbine", "yohimbe",
    "thc", "cannabis", "cbd", "cannabidiol", "hemp extract", "hemp-derived",
    "khat", "catha edulis",
    "sarms",
]

BANNED_COUNTRY = {
    "Saudi Arabia": ["poppy seed", "papaver somniferum", "nutmeg extract", "alcohol", "ethanol"],
    "UAE":          ["poppy seed", "papaver somniferum", "5-htp", "5-hydroxytryptophan",
                     "citrus aurantium", "synephrine", "alcohol", "ethanol"],
    "Kuwait":       ["poppy seed"],
    "Qatar":        ["poppy seed"],
    "Bahrain":      ["poppy seed"],
    "Oman":         ["poppy seed", "ephedra"],
}

RX_RECLASSIFY = ["melatonin"]

HALAL_SENSITIVE_KEYWORDS = [
    "gelatin", "collagen", "fish oil", "fish", "bovine", "porcine",
    "glucosamine", "chondroitin", "bone broth", "whey", "casein",
    "shellfish", "marine", "albumin",
]


@dataclass
class ComplianceResult:
    country: str
    status: str          # CLEAR | SHELF_LIFE | INGREDIENT | RX_ONLY | HALAL
    days_remaining: int
    remaining_pct: float
    threshold_pct: float           # effective threshold used (accounts for absolute minimums)
    days_until_breach: int         # -ve means already breached
    flagged_ingredients: list
    needs_halal_cert: bool
    is_rx: bool
    confidence: str = "LOW"        # HIGH | MEDIUM | LOW
    confidence_note: str = ""


def check_compliance(
    expiry_date: date,
    manufacture_date: date,
    total_shelf_life_days: int,
    ingredients: str,
    halal_certified: str,
    hs_code: str,
    as_of: Optional[date] = None,
) -> dict[str, ComplianceResult]:
    today = as_of or date.today()
    ingredients_lower = ingredients.lower()

    days_remaining = (expiry_date - today).days
    remaining_pct = days_remaining / total_shelf_life_days if total_shelf_life_days > 0 else 0

    flagged_all = [i for i in BANNED_ALL if i in ingredients_lower]
    is_rx = any(r in ingredients_lower for r in RX_RECLASSIFY)
    needs_halal = any(k in ingredients_lower for k in HALAL_SENSITIVE_KEYWORDS)
    halal_ok = halal_certified.strip().lower() == "yes"

    results = {}
    for country in COUNTRIES:
        pct_threshold = SHELF_LIFE_THRESHOLDS[country]
        abs_min_days = SHELF_LIFE_MIN_DAYS.get(country, 0)

        # Effective required days: whichever rule is more restrictive
        required_days = max(pct_threshold * total_shelf_life_days, abs_min_days)
        effective_threshold = required_days / total_shelf_life_days if total_shelf_life_days > 0 else pct_threshold

        days_until_breach = int(days_remaining - required_days)

        country_banned = [i for i in BANNED_COUNTRY.get(country, []) if i in ingredients_lower]
        all_flagged = flagged_all + country_banned

        conf = SHELF_LIFE_CONFIDENCE[country]

        if is_rx:
            status = "RX_ONLY"
        elif all_flagged:
            status = "INGREDIENT"
        elif needs_halal and not halal_ok:
            status = "HALAL"
        elif days_remaining < required_days:
            status = "SHELF_LIFE"
        else:
            status = "CLEAR"

        results[country] = ComplianceResult(
            country=country,
            status=status,
            days_remaining=days_remaining,
            remaining_pct=round(remaining_pct, 4),
            threshold_pct=round(effective_threshold, 4),
            days_until_breach=days_until_breach,
            flagged_ingredients=all_flagged,
            needs_halal_cert=needs_halal and not halal_ok,
            is_rx=is_rx,
            confidence=conf["level"],
            confidence_note=conf["note"],
        )
    return results


def status_priority(status: str) -> int:
    return {"RX_ONLY": 0, "INGREDIENT": 1, "HALAL": 2, "SHELF_LIFE": 3, "CLEAR": 4}.get(status, 9)


def worst_status(results: dict) -> str:
    return min(results.values(), key=lambda r: status_priority(r.status)).status
