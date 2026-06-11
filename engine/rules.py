from datetime import date
from dataclasses import dataclass
from typing import Optional

COUNTRIES = ["Saudi Arabia", "UAE", "Kuwait", "Qatar", "Bahrain", "Oman"]

# ── Shelf life constants (still used by migration script + SHELF_LIFE_CONFIDENCE display) ──
SHELF_LIFE_THRESHOLDS = {
    "Saudi Arabia": 0.50,
    "UAE":          0.75,
    "Kuwait":       0.50,
    "Qatar":        0.50,
    "Bahrain":      0.50,
    "Oman":         0.50,
}

SHELF_LIFE_MIN_DAYS = {
    "Qatar": 365,
}

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

CONFIDENCE_ICON  = {"HIGH": "✓", "MEDIUM": "~", "LOW": "?"}
CONFIDENCE_COLOR = {"HIGH": "#2ecc71", "MEDIUM": "#f39c12", "LOW": "#e74c3c"}


# ── Loaded rules dataclass ─────────────────────────────────────────────────────

@dataclass
class LoadedRules:
    """
    Ingredient rules loaded from iherb.ingredient_master + aliases.
    Passed into check_compliance() so the DB is queried once per batch,
    not once per product.
    """
    # alias → set of countries it is banned in ('ALL_GCC' means every GCC country)
    banned: dict[str, set[str]]
    # set of aliases whose canonical ingredient is Rx-only
    rx: set[str]
    # set of aliases whose canonical ingredient triggers a Halal certificate requirement
    halal: set[str]


def load_compliance_rules() -> LoadedRules:
    """
    Read ingredient_master + ingredient_aliases + ingredient_country_bans from
    PostgreSQL and return a LoadedRules ready for check_compliance().
    """
    from engine.db import query_df

    df = query_df("""
        SELECT
            ia.alias,
            im.restriction,
            COALESCE(
                array_agg(icb.country) FILTER (WHERE icb.country IS NOT NULL),
                ARRAY[]::text[]
            ) AS countries
        FROM iherb.ingredient_aliases ia
        JOIN iherb.ingredient_master im ON ia.ingredient_id = im.ingredient_id
        LEFT JOIN iherb.ingredient_country_bans icb ON im.ingredient_id = icb.ingredient_id
        GROUP BY ia.alias, im.restriction
    """)

    banned: dict[str, set[str]] = {}
    rx:     set[str] = set()
    halal:  set[str] = set()

    for _, row in df.iterrows():
        alias       = row["alias"]
        restriction = row["restriction"]
        countries   = set(row["countries"]) if row["countries"] is not None else set()

        if restriction == "BANNED":
            banned[alias] = countries
        elif restriction == "RX_ONLY":
            rx.add(alias)
        elif restriction == "HALAL_TRIGGER":
            halal.add(alias)

    return LoadedRules(banned=banned, rx=rx, halal=halal)


# ── Compliance result ──────────────────────────────────────────────────────────

@dataclass
class ComplianceResult:
    country: str
    status: str          # CLEAR | SHELF_LIFE | INGREDIENT | RX_ONLY | HALAL
    days_remaining: int
    remaining_pct: float
    threshold_pct: float
    days_until_breach: int
    flagged_ingredients: list
    needs_halal_cert: bool
    is_rx: bool
    confidence: str = "LOW"
    confidence_note: str = ""


def check_compliance(
    expiry_date: date,
    manufacture_date: date,
    total_shelf_life_days: int,
    ingredients: str,
    halal_certified: str,
    hs_code: str,
    rules: LoadedRules,
    as_of: Optional[date] = None,
) -> dict[str, ComplianceResult]:
    today              = as_of or date.today()
    ingredients_lower  = ingredients.lower()

    days_remaining = (expiry_date - today).days
    remaining_pct  = days_remaining / total_shelf_life_days if total_shelf_life_days > 0 else 0

    # Rx check
    is_rx = any(alias in ingredients_lower for alias in rules.rx)

    # Halal check
    needs_halal = any(alias in ingredients_lower for alias in rules.halal)
    halal_ok    = halal_certified.strip().lower() == "yes"

    # Banned aliases present in this product
    present_banned: dict[str, set[str]] = {
        alias: countries
        for alias, countries in rules.banned.items()
        if alias in ingredients_lower
    }

    results = {}
    for country in COUNTRIES:
        pct_threshold = SHELF_LIFE_THRESHOLDS[country]
        abs_min_days  = SHELF_LIFE_MIN_DAYS.get(country, 0)

        required_days     = max(pct_threshold * total_shelf_life_days, abs_min_days)
        effective_threshold = required_days / total_shelf_life_days if total_shelf_life_days > 0 else pct_threshold
        days_until_breach = int(days_remaining - required_days)

        # Flagged = banned everywhere OR specifically banned in this country
        flagged = [
            alias for alias, countries in present_banned.items()
            if "ALL_GCC" in countries or country in countries
        ]

        conf = SHELF_LIFE_CONFIDENCE[country]

        if is_rx:
            status = "RX_ONLY"
        elif flagged:
            status = "INGREDIENT"
        elif needs_halal and not halal_ok:
            status = "HALAL"
        elif days_remaining < required_days:
            status = "SHELF_LIFE"
        else:
            status = "CLEAR"

        # Include matching Rx aliases in flagged_ingredients so the display can show them
        rx_flagged = [alias for alias in rules.rx if alias in ingredients_lower] if is_rx else []

        results[country] = ComplianceResult(
            country=country,
            status=status,
            days_remaining=days_remaining,
            remaining_pct=round(remaining_pct, 4),
            threshold_pct=round(effective_threshold, 4),
            days_until_breach=days_until_breach,
            flagged_ingredients=flagged + rx_flagged,
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
