import os
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from engine.allocator import build_report, expiry_timeline, load_inventory, run_compliance, value_at_risk
from datetime import timedelta

from engine.rules import (
    COUNTRIES, CONFIDENCE_COLOR, CONFIDENCE_ICON,
    SHELF_LIFE_CONFIDENCE, check_compliance,
)

load_dotenv()

# Seed navigation state before any widget is rendered
if "nav_page" not in st.session_state:
    st.session_state["nav_page"] = "Introduction"

# ── Centralised token logger ───────────────────────────────────────────────────
_MODEL_PRICING = {
    "claude-sonnet-4-6":        {"in": 3.00,  "out": 15.0},
    "claude-haiku-4-5-20251001": {"in": 0.80,  "out":  4.0},
}

def _log_tokens(page: str, model: str, usage: dict):
    if not usage:
        return
    if "token_log" not in st.session_state:
        st.session_state.token_log = []
    from datetime import datetime as _dt
    pricing = _MODEL_PRICING.get(model, {"in": 3.0, "out": 15.0})
    cost = (usage.get("input_tokens", 0) * pricing["in"]
            + usage.get("output_tokens", 0) * pricing["out"]) / 1_000_000
    st.session_state.token_log.append({
        "time":       _dt.now().strftime("%H:%M:%S"),
        "page":       page,
        "model":      model,
        "in_tokens":  usage.get("input_tokens", 0),
        "out_tokens": usage.get("output_tokens", 0),
        "api_calls":  usage.get("api_calls", 1),
        "cost":       cost,
    })


def _notes(content: str, label: str = "Notes"):
    """Render a floating Notes popover button."""
    with st.popover(f"📝 {label}"):
        st.markdown(content)


# Streamlit Cloud stores secrets in st.secrets — push them into env so all
# modules (advisor, scraper) pick them up via os.getenv() unchanged.
for _k in ("ANTHROPIC_API_KEY", "APIFY_TOKEN"):
    if _k in st.secrets and not os.getenv(_k):
        os.environ[_k] = st.secrets[_k]

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="GCC Compliance Engine — iHerb",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)


DATA_PATH = Path(__file__).parent / "data" / "mock_inventory.csv"

STATUS_COLOR = {
    "CLEAR":      "#2ecc71",
    "SHELF_LIFE": "#f39c12",
    "HALAL":      "#3498db",
    "INGREDIENT": "#e74c3c",
    "RX_ONLY":    "#8e44ad",
}

STATUS_LABEL = {
    "CLEAR":      "Clear",
    "SHELF_LIFE": "Shelf Life",
    "HALAL":      "Halal Cert",
    "INGREDIENT": "Banned Ingredient",
    "RX_ONLY":    "Rx Only",
}


# ── Data loading (cached) ──────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_report() -> pd.DataFrame:
    inv = load_inventory(str(DATA_PATH))
    compliance = run_compliance(inv)
    return build_report(compliance)


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://www.iherb.com/favicon.ico", width=32)
    st.title("GCC Compliance Engine")
    st.caption("iHerb Saudi Logistics — Allocation Risk Monitor")
    st.divider()

    _pages = ["Introduction", "Dashboard", "Allocation Table", "Compliance Chat", "Risk Actions", "Product Lookup", "Token Usage"]
    _idx = _pages.index(st.session_state.get("nav_page", "Introduction"))
    page = st.radio(
        "Navigate",
        _pages,
        index=_idx,
        label_visibility="collapsed",
    )
    st.session_state["nav_page"] = page

    st.divider()
    st.caption(f"Data as of: {date.today().strftime('%d %b %Y')}")
    st.caption("Source: Mock inventory · 100 SKUs")

    if st.button("Refresh data"):
        st.cache_data.clear()
        st.rerun()


# ── Auth guard — intro is public; all other pages require authentication ───────
if page != "Introduction" and not st.session_state.get("_auth"):
    st.session_state["nav_page"] = "Introduction"
    st.rerun()

# ── Load data ──────────────────────────────────────────────────────────────────
df = get_report()

_SCROLL_JS = """<script>
(function() {
    function scrollTop() {
        var p = window.parent;
        p.scrollTo(0, 0);
        p.document.body.scrollTop = 0;
        p.document.documentElement.scrollTop = 0;
        var sels = [
            '[data-testid="stAppViewContainer"]',
            'section[data-testid="stMain"]',
            '[data-testid="stMainBlockContainer"]',
            '.main'
        ];
        for (var i = 0; i < sels.length; i++) {
            var el = p.document.querySelector(sels[i]);
            if (el) { el.scrollTop = 0; }
        }
    }
    // Fire twice: once quickly (handles most cases) and once after layout settles
    setTimeout(scrollTop, 50);
    setTimeout(scrollTop, 350);
})();
</script>"""

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 0 — INTRODUCTION
# ══════════════════════════════════════════════════════════════════════════════
if page == "Introduction":
    # Hide sidebar — introduction is a standalone landing page
    st.markdown(
        """<style>
        section[data-testid="stSidebar"] { display: none !important; }
        button[data-testid="collapsedControl"] { display: none !important; }
        /* Tighten Streamlit's default block container for a centred reading column */
        .block-container { max-width: 760px !important; padding-top: 3.5rem !important; padding-bottom: 4rem !important; }
        </style>""",
        unsafe_allow_html=True,
    )

    # Read SVG for inline embedding
    _svg_path = Path(__file__).parent / "assets" / "ai_framework_triangle.svg"
    _svg = _svg_path.read_text(encoding="utf-8") if _svg_path.exists() else ""

    # ── Styles ────────────────────────────────────────────────────────────────
    st.markdown(
        """<style>
        /* Eyebrow label above title */
        .lp-eyebrow {
            font-size: 0.72rem;
            font-weight: 600;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            opacity: 0.45;
            margin-bottom: 0.6rem;
        }
        /* Override Streamlit h1 for the landing page */
        .block-container h1 {
            font-size: 2.8rem !important;
            font-weight: 700 !important;
            letter-spacing: -0.025em !important;
            line-height: 1.15 !important;
            margin-bottom: 0.2rem !important;
        }
        .lp-accent {
            width: 48px; height: 4px;
            background: #534AB7;
            border-radius: 2px;
            margin: 0.7rem 0 2rem 0;
        }
        /* Body copy */
        .lp-body p {
            font-size: 1.03rem;
            line-height: 1.8;
            opacity: 0.85;
            margin-bottom: 1.1rem;
        }
        .lp-body ul {
            font-size: 1.03rem;
            line-height: 1.8;
            opacity: 0.85;
            padding-left: 1.3rem;
            margin-bottom: 1.3rem;
        }
        .lp-body li { margin-bottom: 0.35rem; }
        .lp-body a { opacity: 1; }
        /* Divider */
        .lp-divider {
            border: none;
            border-top: 1px solid rgba(128,128,128,0.18);
            margin: 2.5rem 0 2rem;
        }
        /* Section label above project card */
        .lp-section-label {
            font-size: 0.72rem;
            font-weight: 600;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            opacity: 0.4;
            margin-bottom: 1rem;
        }
        /* Project card */
        .proj-card {
            border-radius: 14px;
            border: 1px solid rgba(128,128,128,0.22);
            border-left: 3px solid #534AB7;
            border-radius: 0 14px 14px 0;
            padding: 1.75rem 2.25rem 1.5rem;
            transition: box-shadow 0.25s ease, border-color 0.25s ease;
        }
        .proj-card:hover {
            box-shadow: 0 8px 32px rgba(83,74,183,0.12);
        }
        .proj-card-title {
            font-size: 1.08rem;
            font-weight: 650;
            margin: 0 0 0.85rem 0;
            line-height: 1.4;
        }
        .proj-card p {
            font-size: 0.93rem;
            line-height: 1.72;
            opacity: 0.75;
            margin-bottom: 0.65rem;
        }
        /* Pillar tiles */
        .pillar-row {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin: 1.25rem 0 1.4rem;
        }
        .pillar-tile {
            flex: 1;
            min-width: 150px;
            border-radius: 8px;
            padding: 12px 14px;
            font-size: 0.82rem;
            line-height: 1.55;
        }
        .pillar-tile strong {
            display: block;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-bottom: 4px;
        }
        .pt-purple { background: #EEEDFE; color: #3C3489; }
        .pt-teal   { background: #E1F5EE; color: #085041; }
        .pt-coral  { background: #FAECE7; color: #712B13; }
        /* Button tuck under card */
        div[data-testid="stButton"] > button[kind="primaryFormSubmit"],
        div[data-testid="stButton"] > button[kind="primary"] {
            border-radius: 0 0 13px 13px !important;
            margin-top: -2px !important;
        }
        </style>""",
        unsafe_allow_html=True,
    )

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown('<p class="lp-eyebrow">Portfolio &nbsp;·&nbsp; GCC Market</p>', unsafe_allow_html=True)
    st.title("AI Projects")
    st.markdown('<div class="lp-accent"></div>', unsafe_allow_html=True)

    # ── Body copy — plain markdown avoids Streamlit's HTML→code-block bug ────
    st.markdown(
        "Saudi businesses are making significant investments in AI. "
        "The question is not whether to adopt it — it is how to adopt it without "
        "introducing risk into the systems that run your operations.\n\n"
        "Your ERP, your financial controls, your operational workflows — these represent "
        "years of process design and governance. They are the source of truth for your "
        "business. AI works best when it is built around them, not instead of them.\n\n"
        "There are three things that determine whether an AI implementation delivers "
        "value or creates problems.\n\n"
        "- How you define the agent's behaviour — the boundaries, the purpose, the rules it operates within.\n"
        "- What knowledge you give it access to — grounding it in your own business data so it reasons accurately rather than guesses.\n"
        "- What you allow it to do in your systems — connecting it to your existing processes through the same governance and audit controls you already have in place."
    )

    # ── Triangle diagram ──────────────────────────────────────────────────────
    if _svg:
        components.html(
            f"""<style>
            body {{ margin:0; padding:0; background:transparent; }}
            .diagram-wrap {{
                background: rgba(83,74,183,0.05);
                border: 1px solid rgba(83,74,183,0.14);
                border-radius: 16px;
                padding: 2rem 1.5rem 1.5rem;
                display: flex;
                justify-content: center;
                align-items: center;
            }}
            svg {{ width:100% !important; height:auto !important; max-width:580px; display:block; }}
            </style>
            <div class="diagram-wrap">{_svg}</div>""",
            height=460,
            scrolling=False,
        )

    st.markdown(
        "Done well, this is not a replacement for your people or your systems. "
        "It is a way of making both more effective.\n\n"
        "The projects below are practical demonstrations of these ideas, applied to "
        "business problems in the GCC market. All were built using "
        "[Claude Code](https://claude.ai/code)."
    )

    st.markdown('<hr class="lp-divider">', unsafe_allow_html=True)
    st.markdown('<p class="lp-section-label">Projects</p>', unsafe_allow_html=True)

    # ── Project card ──────────────────────────────────────────────────────────
    st.markdown(
        '<div class="proj-card">'
        '<p class="proj-card-title">GCC Customs Compliance Engine &mdash; iHerb Saudi Logistics</p>'
        "<p>iHerb operates a distribution centre in Saudi Arabia serving the wider GCC market. "
        "Every product in the warehouse must meet the import regulations of each destination "
        "country before it ships — shelf life thresholds, ingredient restrictions, Halal "
        "certification requirements, and Rx classification rules that vary across six "
        "jurisdictions. Getting this wrong means stock write-offs, customs delays, or "
        "regulatory penalties.</p>"
        "<p>This engine monitors the warehouse inventory in real time, flags products at risk "
        "of becoming non-compliant, and recommends concrete actions: reroute to a "
        "lower-threshold country, apply a discount to clear stock before the window closes, "
        "or write off. A natural language compliance advisor lets warehouse managers ask "
        "questions directly and get specific, data-grounded answers.</p>"
        '<div class="pillar-row">'
        '<div class="pillar-tile pt-purple"><strong>Behaviour</strong>Rules engine encodes GCC regulations per country — shelf life thresholds, banned ingredient lists, Halal and Rx rules — with confidence levels where rules are unverified.</div>'
        '<div class="pillar-tile pt-teal"><strong>Knowledge</strong>The warehouse inventory is the knowledge base. The compliance advisor queries it with structured tools rather than guessing — quantities, values, and expiry dates grounded in real data.</div>'
        '<div class="pillar-tile pt-coral"><strong>Action</strong>The compliance data writes directly to the allocations table — switching batch picks by destination so stock is automatically routed to the countries where it remains compliant.</div>'
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    @st.dialog("Access required")
    def _pw_dialog():
        st.caption("Enter the password to open the GCC Compliance Engine.")
        pwd = st.text_input("Password", type="password",
                            label_visibility="collapsed",
                            placeholder="Password")
        if st.button("Enter →", type="primary", use_container_width=True):
            expected = st.secrets.get("APP_PASSWORD", "")
            if pwd and pwd == expected:
                st.session_state["_auth"] = True
                st.session_state["nav_page"] = "Dashboard"
                st.rerun()
            else:
                st.error("Incorrect password.")

    if st.button("Open — GCC Compliance Engine →", type="primary", use_container_width=True):
        if st.session_state.get("_auth"):
            st.session_state["nav_page"] = "Dashboard"
            st.rerun()
        else:
            _pw_dialog()

    st.markdown('<hr class="lp-divider">', unsafe_allow_html=True)
    st.caption(
        "These projects are intended to demonstrate how a business process can be modelled "
        "and augmented with AI. In practice, a significant proportion of the effort in any "
        "AI project goes into testing and achieving consistent, reliable outputs. Here, the "
        "emphasis has been placed on illustrating a coherent and well-structured business "
        "process — the AI layer is built on top of that foundation, not instead of it."
    )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Dashboard":
    components.html(_SCROLL_JS, height=0, scrolling=False)
    st.header("Inventory Compliance Dashboard")
    st.info(
        "I asked AI to create an inventory of supplemental products and their ingredients. "
        "I then asked it to assemble a list of customs rules for GCC countries and evaluate "
        "each product against the customs regulations of each country. It has evaluated any "
        "non-conforming products and presented a costed inventory of compliant and "
        "non-compliant products."
    )

    # ── KPI row ───────────────────────────────────────────────────────────────
    total_skus     = len(df)
    blocked        = df[df["worst_status"].isin(["INGREDIENT", "RX_ONLY"])].shape[0]
    at_risk_uae    = df[(df["status_UAE"] == "CLEAR") & (df["breach_days_UAE"].between(0, 90))].shape[0]
    at_risk_all    = df[(df["worst_status"] == "SHELF_LIFE")].shape[0]
    value_at_risk_ = df[df["breach_days_UAE"].between(0, 90)]["stock_value_usd"].sum()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total SKUs", total_skus)
    c2.metric("Ingredient Blocked", blocked, delta=f"{blocked} SKUs", delta_color="inverse")
    c3.metric("UAE Breach ≤90d", at_risk_uae, delta="needs action", delta_color="inverse")
    c4.metric("Shelf Life Issues", at_risk_all, delta_color="inverse")
    c5.metric("Value at Risk (90d)", f"${value_at_risk_:,.0f}", delta_color="inverse")

    st.divider()

    col_left, col_right = st.columns([3, 2])

    # ── Shippable SKUs by country (stacked bar) ───────────────────────────────
    with col_left:
        st.subheader("SKUs Shippable to Each Country — by Block Reason")
        st.caption("Shows how many of the 100 SKUs can ship to each destination right now, and why others are blocked.")

        bar_rows = []
        for country in COUNTRIES:
            for status, label in STATUS_LABEL.items():
                n = df[df[f"status_{country}"] == status].shape[0]
                bar_rows.append({"Country": country, "Status": label, "SKUs": n})

        bar_df = pd.DataFrame(bar_rows)
        fig_bar = px.bar(
            bar_df,
            x="Country", y="SKUs", color="Status",
            color_discrete_map={v: STATUS_COLOR[k] for k, v in STATUS_LABEL.items()},
            text="SKUs",
        )
        fig_bar.update_traces(textposition="inside", textfont_size=11)
        fig_bar.update_layout(
            barmode="stack",
            margin=dict(t=20, b=20, l=20, r=20),
            height=420,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            yaxis_title="Number of SKUs",
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # ── Status donut ──────────────────────────────────────────────────────────
    with col_right:
        st.subheader("Overall Status Distribution")
        status_counts = df["worst_status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]
        status_counts["Label"] = status_counts["Status"].map(STATUS_LABEL)
        status_counts["Color"] = status_counts["Status"].map(STATUS_COLOR)

        fig_pie = px.pie(
            status_counts,
            names="Label",
            values="Count",
            color="Label",
            color_discrete_map={v: STATUS_COLOR[k] for k, v in STATUS_LABEL.items()},
            hole=0.45,
        )
        fig_pie.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=280)
        st.plotly_chart(fig_pie, use_container_width=True)

        st.subheader("Blocked Ingredients Breakdown")
        flagged = df[df["flagged_ingredients"] != "—"]["flagged_ingredients"]
        if not flagged.empty:
            all_flags = [i.strip() for row in flagged for i in row.split(", ")]
            flag_counts = pd.Series(all_flags).value_counts().head(8).reset_index()
            flag_counts.columns = ["Ingredient", "Count"]
            fig_flags = px.bar(
                flag_counts, x="Ingredient", y="Count",
                color_discrete_sequence=["#e74c3c"],
            )
            fig_flags.update_layout(
                margin=dict(t=10, b=10, l=10, r=10),
                height=220,
                showlegend=False,
                xaxis_tickangle=-35,
            )
            st.plotly_chart(fig_flags, use_container_width=True)
        else:
            st.info("No flagged ingredients in current inventory.")

    st.divider()

    # ── Expiry timeline ───────────────────────────────────────────────────────
    st.subheader("Value Becoming Non-Compliant — Next 12 Months")
    tl = expiry_timeline(df, horizon_days=365)
    if not tl.empty:
        fig_tl = px.bar(
            tl,
            x="month",
            y="value_lost",
            color="country",
            barmode="group",
            labels={"value_lost": "Stock Value ($)", "month": "Month", "country": "Country"},
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_tl.update_layout(
            height=300,
            margin=dict(t=20, b=20, l=20, r=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig_tl, use_container_width=True)
    else:
        st.info("No shelf life breaches projected in the next 12 months.")

    st.divider()

    # ── Regulatory confidence panel ───────────────────────────────────────────
    with st.expander("Regulatory Threshold Confidence", expanded=False):
        st.caption(
            "Shelf life thresholds used by this engine. Confidence reflects how well-sourced "
            "each country's rule is — LOW means the rule is assumed or unverified."
        )
        conf_cols = st.columns(3)
        for i, country in enumerate(COUNTRIES):
            conf = SHELF_LIFE_CONFIDENCE[country]
            color = CONFIDENCE_COLOR[conf["level"]]
            icon = CONFIDENCE_ICON[conf["level"]]
            with conf_cols[i % 3]:
                st.markdown(
                    f"""<div style="border-left:4px solid {color}; padding:8px 12px; margin-bottom:10px; border-radius:4px; background:rgba(255,255,255,0.04);">
                    <strong>{country}</strong><br>
                    <span style="color:{color}; font-weight:bold;">{icon} {conf['level']}</span>
                    &nbsp;·&nbsp;<span style="font-size:0.9em;">{conf['threshold_display']}</span><br>
                    <span style="font-size:0.82em; color:#aaa;">{conf['note']}</span><br>
                    <span style="font-size:0.78em; color:#888;">Source: {conf['source']}</span>
                    </div>""",
                    unsafe_allow_html=True,
                )



# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — ALLOCATION TABLE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Allocation Table":
    components.html(_SCROLL_JS, height=0, scrolling=False)
    st.header("Allocation Compliance Table")

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        cat_filter = st.multiselect("Category", sorted(df["category"].unique()), placeholder="All categories")
    with col_f2:
        status_filter = st.multiselect("Worst Status", list(STATUS_LABEL.values()), placeholder="All statuses")
    with col_f3:
        horizon = st.slider("UAE breach horizon (days)", 30, 365, 90)

    filtered = df.copy()
    if cat_filter:
        filtered = filtered[filtered["category"].isin(cat_filter)]
    if status_filter:
        reverse_label = {v: k for k, v in STATUS_LABEL.items()}
        filtered = filtered[filtered["worst_status"].isin([reverse_label[s] for s in status_filter])]

    # Build display table
    display_cols = ["sku_id", "product_name", "brand", "category", "hs_code",
                    "expiry_date", "days_remaining", "qty_on_hand", "stock_value_usd"]
    for c in COUNTRIES:
        display_cols.append(f"status_{c}")
    display_cols += ["flagged_ingredients", "recommended_action"]

    # Build country column display names with confidence icons
    country_display = {
        c: f"{c} {CONFIDENCE_ICON[SHELF_LIFE_CONFIDENCE[c]['level']]}"
        for c in COUNTRIES
    }

    show_df = filtered[display_cols].copy()
    show_df = show_df.rename(columns={
        "sku_id": "SKU",
        "product_name": "Product",
        "brand": "Brand",
        "category": "Category",
        "hs_code": "HS Code",
        "expiry_date": "Expiry",
        "days_remaining": "Days Left",
        "qty_on_hand": "Qty",
        "stock_value_usd": "Value ($)",
        "flagged_ingredients": "Flagged Ingredients",
        "recommended_action": "Recommended Action",
        **{f"status_{c}": country_display[c] for c in COUNTRIES},
    })

    country_display_cols = list(country_display.values())

    def color_status(val):
        color = STATUS_COLOR.get(val, "#ffffff")
        text = "#ffffff" if val in ("INGREDIENT", "RX_ONLY") else "#000000"
        return f"background-color: {color}; color: {text}; font-weight: bold; border-radius: 4px; padding: 2px 6px"

    styled = show_df.style.map(color_status, subset=country_display_cols).hide(axis="index")

    st.dataframe(styled, use_container_width=True, height=550)
    st.caption(
        f"Showing {len(show_df)} of {len(df)} SKUs  ·  "
        "Column confidence: ✓ Verified  ~ Partially verified  ? Assumed/unverified"
    )

    csv_bytes = show_df.to_csv(index=False).encode()
    st.download_button("Export CSV", csv_bytes, "gcc_compliance_export.csv", "text/csv")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — COMPLIANCE CHAT
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Compliance Chat":
    from engine.advisor import chat
    components.html(_SCROLL_JS, height=0, scrolling=False)
    st.header("Compliance Advisor")

    if not os.getenv("ANTHROPIC_API_KEY"):
        st.error("ANTHROPIC_API_KEY is not set. Add it to your .env file and restart the app.")
        st.stop()

    st.caption(
        "Ask anything about your GCC compliance situation. "
        "Claude has live access to the inventory and reasons over it — "
        "it queries the data, calculates values, and gives specific recommendations."
    )

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "chat_usage" not in st.session_state:
        st.session_state.chat_usage = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0}

    # Approximate Sonnet pricing
    _IN_CPT  = 3.0  / 1_000_000
    _OUT_CPT = 15.0 / 1_000_000

    # Render conversation history
    for msg in st.session_state.chat_messages:
        role = msg.get("role") if isinstance(msg, dict) else None
        if role not in ("user", "assistant"):
            continue
        content = msg["content"]
        if isinstance(content, list):
            text = next((b.text for b in content if hasattr(b, "text")), None)
            if text is None:
                continue
        else:
            text = content
        with st.chat_message(role):
            st.markdown(text.replace("$", r"\$"))

    # Auto-respond if the last message is an unanswered user query
    # (happens when an example-question button is clicked — it appends + reruns
    # without going through the chat_input handler below)
    _last = st.session_state.chat_messages[-1] if st.session_state.chat_messages else None
    if (
        _last is not None
        and isinstance(_last, dict)
        and _last.get("role") == "user"
        and isinstance(_last.get("content"), str)
    ):
        with st.chat_message("assistant"):
            with st.spinner("Checking inventory…"):
                try:
                    reply, updated, usage = chat(list(st.session_state.chat_messages), df)
                except Exception as e:
                    st.error(f"Chat error: {e}")
                    st.stop()
            st.markdown(reply.replace("$", r"\$"))
            if usage:
                st.caption(
                    f"↑ {usage['input_tokens']:,} in · {usage['output_tokens']:,} out "
                    f"· {usage['api_calls']} API call{'s' if usage['api_calls'] != 1 else ''} "
                    f"· ~${usage['input_tokens']*_IN_CPT + usage['output_tokens']*_OUT_CPT:.4f}"
                )
                for k in ("input_tokens", "output_tokens", "api_calls"):
                    st.session_state.chat_usage[k] += usage.get(k, 0)
                _log_tokens("Compliance Chat", "claude-sonnet-4-6", usage)
        st.session_state.chat_messages = updated
        st.rerun()

    # Example questions (shown only when conversation is empty)
    if not st.session_state.chat_messages:
        st.markdown("**Try asking:**")
        examples = [
            "Which products will lose UAE compliance in the next 30 days?",
            "What's the total value of stock I can't ship to UAE right now?",
            "Show me everything shippable to Saudi Arabia but not UAE",
            "What should I do with the whey protein approaching expiry?",
            "Why is melatonin blocked for all GCC countries?",
            "Which categories have the worst compliance rate for UAE?",
        ]
        cols = st.columns(2)
        for i, q in enumerate(examples):
            with cols[i % 2]:
                if st.button(q, key=f"ex_{i}", use_container_width=True):
                    st.session_state.chat_messages.append({"role": "user", "content": q})
                    st.rerun()

    # Chat input
    if prompt := st.chat_input("Ask about your inventory…"):
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.chat_messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            with st.spinner("Checking inventory…"):
                try:
                    reply, updated, usage = chat(
                        [m for m in st.session_state.chat_messages],
                        df,
                    )
                except Exception as e:
                    st.error(f"Chat error: {e}")
                    st.stop()
            st.markdown(reply.replace("$", r"\$"))
            if usage:
                st.caption(
                    f"↑ {usage['input_tokens']:,} in · {usage['output_tokens']:,} out "
                    f"· {usage['api_calls']} API call{'s' if usage['api_calls'] != 1 else ''} "
                    f"· ~${usage['input_tokens']*_IN_CPT + usage['output_tokens']*_OUT_CPT:.4f}"
                )
                for k in ("input_tokens", "output_tokens", "api_calls"):
                    st.session_state.chat_usage[k] += usage.get(k, 0)
                _log_tokens("Compliance Chat", "claude-sonnet-4-6", usage)

        st.session_state.chat_messages = updated

    if st.session_state.chat_messages:
        tot = st.session_state.chat_usage
        tot_cost = tot["input_tokens"] * _IN_CPT + tot["output_tokens"] * _OUT_CPT
        st.caption(
            f"Session total — {tot['input_tokens']:,} in · {tot['output_tokens']:,} out "
            f"· {tot['api_calls']} API calls · ~${tot_cost:.4f}"
        )
        if st.button("Clear conversation", type="secondary"):
            st.session_state.chat_messages = []
            st.session_state.chat_usage = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0}
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — RISK ACTIONS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Risk Actions":
    components.html(_SCROLL_JS, height=0, scrolling=False)
    st.header("Risk Actions & Recommendations")

    tab1, tab2, tab3, tab4 = st.tabs(["Reroute to Lower-Threshold Countries", "Discount Candidates", "Fully Blocked", "Halal Certification"])

    # ── Tab 1: Reroute ────────────────────────────────────────────────────────
    with tab1:
        st.markdown(
            "Products currently clear for UAE but approaching the 75% threshold — "
            "still viable for KSA/Kuwait/Qatar/Bahrain/Oman (50% threshold). "
            "Route these to lower-threshold destinations before the UAE window closes."
        )
        reroute = value_at_risk(df, horizon_days=180)
        if reroute.empty:
            st.success("No products require rerouting in the next 180 days.")
        else:
            reroute_show = reroute[[
                "sku_id", "product_name", "category", "expiry_date",
                "days_remaining", "qty_on_hand", "stock_value_usd",
                "breach_days_UAE", "recommended_action",
            ]].rename(columns={
                "sku_id": "SKU", "product_name": "Product", "category": "Category",
                "expiry_date": "Expiry", "days_remaining": "Days Left",
                "qty_on_hand": "Qty", "stock_value_usd": "Value ($)",
                "breach_days_UAE": "UAE Breach (d)", "recommended_action": "Action",
            }).sort_values("UAE Breach (d)")
            st.dataframe(reroute_show, use_container_width=True, height=400)
            st.metric("Total value at rerouting risk", f"${reroute['stock_value_usd'].sum():,.0f}")

    # ── Tab 2: Discount ───────────────────────────────────────────────────────
    with tab2:
        st.markdown(
            "Products where proactive discounting can clear stock before it becomes "
            "non-compliant. Sorted by urgency (nearest UAE breach first)."
        )
        disc = df[
            (df["worst_status"] == "CLEAR") &
            (df["breach_days_UAE"].between(0, 90))
        ].sort_values("breach_days_UAE")

        if disc.empty:
            st.success("No discount candidates in the next 90 days.")
        else:
            disc_show = disc[[
                "sku_id", "product_name", "category", "expiry_date",
                "qty_on_hand", "stock_value_usd", "breach_days_UAE", "recommended_action",
            ]].rename(columns={
                "sku_id": "SKU", "product_name": "Product", "category": "Category",
                "expiry_date": "Expiry", "qty_on_hand": "Qty",
                "stock_value_usd": "Value ($)", "breach_days_UAE": "UAE Breach (d)",
                "recommended_action": "Suggested Action",
            })
            st.dataframe(disc_show, use_container_width=True, height=400)

            col_d1, col_d2 = st.columns(2)
            col_d1.metric("SKUs needing discount", len(disc_show))
            col_d2.metric("Total value", f"${disc['stock_value_usd'].sum():,.0f}")

    # ── Tab 3: Fully blocked ──────────────────────────────────────────────────
    with tab3:
        st.markdown(
            "Products blocked across all GCC destinations due to ingredients, Rx classification, "
            "or expired shelf life. These cannot be shipped to any GCC country."
        )
        blocked_df = df[df["worst_status"].isin(["INGREDIENT", "RX_ONLY"])]

        all_blocked_statuses = [
            (c, df[df[f"status_{c}"] == "SHELF_LIFE"])
            for c in COUNTRIES
        ]
        shelf_blocked = df[df["days_remaining"] < 0]
        combined_blocked = pd.concat([
            blocked_df,
            shelf_blocked[~shelf_blocked["sku_id"].isin(blocked_df["sku_id"])]
        ]).drop_duplicates("sku_id")

        if combined_blocked.empty:
            st.success("No fully blocked SKUs.")
        else:
            blocked_show = combined_blocked[[
                "sku_id", "product_name", "category", "worst_status",
                "flagged_ingredients", "qty_on_hand", "stock_value_usd",
            ]].rename(columns={
                "sku_id": "SKU", "product_name": "Product", "category": "Category",
                "worst_status": "Block Reason", "flagged_ingredients": "Flagged Ingredients",
                "qty_on_hand": "Qty", "stock_value_usd": "Value ($)",
            })

            def highlight_block(val):
                if val in ("INGREDIENT", "RX_ONLY"):
                    return "background-color: #e74c3c; color: white; font-weight: bold"
                return ""

            st.dataframe(
                blocked_show.style.map(highlight_block, subset=["Block Reason"]).hide(axis="index"),
                use_container_width=True,
                height=400,
            )
            st.metric(
                "Total blocked inventory value",
                f"${combined_blocked['stock_value_usd'].sum():,.0f}",
                delta="cannot ship to GCC",
                delta_color="inverse",
            )

    # ── Tab 4: Halal certification ────────────────────────────────────────────
    with tab4:
        from engine.rules import HALAL_SENSITIVE_KEYWORDS

        st.markdown(
            "Products whose ingredients include animal-derived substances "
            "(gelatin, fish oil, collagen, whey, etc.) require a Halal certificate "
            "to ship to GCC countries. Tick the checkbox to mark a product as certified — "
            "this updates the inventory and recalculates compliance across all pages."
        )

        def _halal_match(ingr: str) -> str:
            il = str(ingr).lower()
            return ", ".join(k for k in HALAL_SENSITIVE_KEYWORDS if k in il) or ""

        halal_mask = df["ingredients"].apply(
            lambda i: bool(_halal_match(i))
        )
        halal_df = df[halal_mask].copy()
        halal_df["animal_ingredients"] = halal_df["ingredients"].apply(_halal_match)

        if halal_df.empty:
            st.success("No products with animal-derived ingredients in the current inventory.")
        else:
            edit_df = halal_df[[
                "sku_id", "product_name", "category",
                "animal_ingredients", "qty_on_hand", "stock_value_usd",
                "halal_certified", "worst_status",
            ]].copy()
            edit_df["Halal Certified"] = edit_df["halal_certified"].str.lower() == "yes"
            edit_df = edit_df.rename(columns={
                "sku_id":            "SKU",
                "product_name":      "Product",
                "category":          "Category",
                "animal_ingredients":"Animal-Derived Ingredients",
                "qty_on_hand":       "Qty",
                "stock_value_usd":   "Value ($)",
                "worst_status":      "Status",
            }).drop(columns=["halal_certified"])

            edited = st.data_editor(
                edit_df,
                column_config={
                    "Halal Certified": st.column_config.CheckboxColumn(
                        "Halal Certified",
                        help="Tick to mark this product as Halal certified",
                        default=False,
                    ),
                },
                disabled=["SKU", "Product", "Category", "Animal-Derived Ingredients",
                          "Qty", "Value ($)", "Status"],
                use_container_width=True,
                hide_index=True,
                height=420,
            )

            n_certified   = int(edited["Halal Certified"].sum())
            n_uncertified = len(edited) - n_certified
            m1, m2, m3 = st.columns(3)
            m1.metric("Total with animal ingredients", len(edited))
            m2.metric("Certified", n_certified)
            m3.metric("Uncertified — blocked", n_uncertified,
                      delta=f"{n_uncertified} SKUs", delta_color="inverse")

            col_sv, col_cap = st.columns([1, 4])
            with col_sv:
                save = st.button("Save Changes", type="primary", use_container_width=True)
            with col_cap:
                st.caption("Writes updated Halal status to the inventory CSV and refreshes all pages.")

            if save:
                inv_csv = pd.read_csv(str(DATA_PATH))
                for _, row in edited.iterrows():
                    inv_csv.loc[
                        inv_csv["sku_id"] == row["SKU"], "halal_certified"
                    ] = "yes" if row["Halal Certified"] else "no"
                inv_csv.to_csv(str(DATA_PATH), index=False)
                st.cache_data.clear()
                st.success("Halal certification updated — compliance recalculated.")
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5 — PRODUCT LOOKUP
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Product Lookup":
    from engine.classifier import analyse_ingredients
    import json as _json
    components.html(_SCROLL_JS, height=0, scrolling=False)
    st.header("Product Lookup")
    st.caption(
        "Select a sample product to classify its ingredients against GCC customs rules, "
        "then add it to your warehouse inventory."
    )
    _notes("""\
One of the massive advantages of LLMs is their ability to do string comparisons.

I have spent a lot of my career matching strings — a staff taxi usage application using
Levenshtein distances, forced UPPER to compare misspelled surnames, regex for standardising
phone numbers to calculate taxable benefits for staff using the corporate taxi account.
Sending parcels to the notoriously exacting German delivery networks, ensuring town names
exist on labels and postcodes are conformant. There are always messy applications that have
historically needed a lot of TLC to deliver results.

Where LLMs really shine is comparing strings that are not the same — they understand that
**5-Hydroxytryptophan** and **5-HTP** are the same product, whereas in the past my code
would be littered with lookup tables making exactly these kinds of comparisons.

Better yet, you do not need a frontier model to do these kinds of comparisons — I am using
**Haiku** for this part of the demonstration, at far lower costs.

Of course, care must be taken, but this is a relatively enclosed training exercise, and
training an LLM to make these comparisons is a far better long-term solution than a brittle
SQL or Python script.
""")

    # ── Sample selector ────────────────────────────────────────────────────────
    _SAMPLE_PATH = Path(__file__).parent / "data" / "sample_products.json"
    _samples     = _json.loads(_SAMPLE_PATH.read_text(encoding="utf-8"))
    _sample_names = [p["name"] for p in _samples]

    if "classifier_usage" not in st.session_state:
        st.session_state.classifier_usage = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0}

    _CL_IN_CPT  = 0.80 / 1_000_000   # Haiku 4.5
    _CL_OUT_CPT = 4.0  / 1_000_000
    _STATUS_ICON = {"CLEAR": "✅", "INGREDIENT": "🚫", "RX_ONLY": "💊", "HALAL": "☪️", "BLOCKED": "⛔"}
    _RISK_COLOUR = {"LOW": "green", "MEDIUM": "orange", "HIGH": "red", "BLOCKED": "red"}

    sel_name = st.selectbox("Product", _sample_names)
    sel      = next(p for p in _samples if p["name"] == sel_name)

    with st.expander("Ingredients", expanded=False):
        st.write(sel["ingredients"])

    # ── AI classifier ──────────────────────────────────────────────────────────
    if st.button("Classify with AI", type="primary", key="run_classifier"):
        if not os.getenv("ANTHROPIC_API_KEY"):
            st.error("ANTHROPIC_API_KEY not set.")
        else:
            with st.spinner("Classifying…"):
                result = analyse_ingredients(sel["ingredients"], sel["name"])

            if "error" in result:
                st.error(result["error"])
                st.session_state.pop("last_classification", None)
            else:
                usage = result.pop("_usage", {})
                st.session_state.last_classification = {"product": sel["name"], "result": result, "usage": usage}
                if usage:
                    for k in ("input_tokens", "output_tokens", "api_calls"):
                        st.session_state.classifier_usage[k] += usage.get(k, 0)
                    _log_tokens("Product Lookup", "claude-haiku-4-5-20251001", usage)

    # Render persisted classification result
    if "last_classification" in st.session_state:
        lc     = st.session_state.last_classification
        result = lc["result"]
        usage  = lc["usage"]
        risk   = result.get("overall_risk", "")

        st.markdown(
            f"**Overall risk:** :{_RISK_COLOUR.get(risk, 'grey')}[{risk}]  ·  "
            f"**HS Code:** `{result.get('suggested_hs_code', '—')}`  ·  "
            f"**Halal:** {result.get('halal_assessment', '—')}"
        )
        st.caption(result.get("halal_note", ""))
        st.info(result.get("summary", ""))

        countries_data = result.get("countries", {})
        if countries_data:
            rows = [
                {
                    "Country": country,
                    "Status":  f"{_STATUS_ICON.get(data.get('status',''), '')} {data.get('status','')}",
                    "Flags":   ", ".join(data.get("flags", [])) or "—",
                }
                for country, data in countries_data.items()
            ]
            st.dataframe(pd.DataFrame(rows).set_index("Country"), use_container_width=True)

        if usage:
            cost = usage["input_tokens"] * _CL_IN_CPT + usage["output_tokens"] * _CL_OUT_CPT
            st.caption(
                f"↑ {usage['input_tokens']:,} in · {usage['output_tokens']:,} out · ~${cost:.4f}"
            )

    tot_cl = st.session_state.classifier_usage
    if tot_cl["api_calls"] > 0:
        tot_cost = tot_cl["input_tokens"] * _CL_IN_CPT + tot_cl["output_tokens"] * _CL_OUT_CPT
        st.caption(
            f"Session classifier total — {tot_cl['input_tokens']:,} in · "
            f"{tot_cl['output_tokens']:,} out · {tot_cl['api_calls']} call(s) · ~${tot_cost:.4f}"
        )

    st.divider()

    # ── Warehouse details ──────────────────────────────────────────────────────
    st.subheader("Warehouse Details")

    _categories = ["Vitamins", "Omega", "Protein", "Herbal", "Minerals",
                   "Probiotics", "Collagen", "Beauty", "Sports", "Other"]
    _hs_options = {
        "2106.90 — General supplement": "2106.90",
        "2936.xx — Vitamins / minerals": "2936.90",
        "3004.xx — Medicament (Rx)":     "3004.90",
        "1302.19 — Herbal extract":      "1302.19",
        "1504.20 — Fish / marine oil":   "1504.20",
        "3504.00 — Collagen / protein":  "3504.00",
    }
    _hs_default_label = next(
        (lbl for lbl, code in _hs_options.items() if code == sel.get("hs_code")),
        list(_hs_options.keys())[0],
    )
    _cat_default = sel["category"] if sel["category"] in _categories else "Other"

    today = date.today()
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        brand    = st.text_input("Brand", value=sel["brand"])
        category = st.selectbox("Category", _categories,
                                index=_categories.index(_cat_default))
        halal    = st.selectbox("Halal Certified", ["no", "yes"],
                                index=["no","yes"].index(sel.get("halal_certified","no")))
    with col_b:
        hs_label  = st.selectbox("HS Code", list(_hs_options.keys()),
                                  index=list(_hs_options.keys()).index(_hs_default_label))
        hs_code   = _hs_options[hs_label]
        qty       = st.number_input("Qty on Hand", min_value=1, value=100, step=10)
        unit_cost = st.number_input("Unit Cost (USD)", min_value=0.01, value=15.00,
                                     step=0.50, format="%.2f")
    with col_c:
        expiry_date  = st.date_input("Expiry Date", value=today.replace(year=today.year + 2))
        shelf_months = st.number_input("Total Shelf Life (months)", min_value=1,
                                        value=sel.get("shelf_life_months", 24))
        shelf_days   = int(shelf_months * 30.44)
        origin       = st.text_input("Country of Origin", value="USA")

    manufacture_date = expiry_date - timedelta(days=shelf_days)

    # ── Live compliance preview ────────────────────────────────────────────────
    st.divider()
    st.subheader("Compliance Preview")

    p_ingr = sel["ingredients"]
    compliance = check_compliance(
        expiry_date=expiry_date,
        manufacture_date=manufacture_date,
        total_shelf_life_days=shelf_days,
        ingredients=p_ingr,
        halal_certified=halal,
        hs_code=hs_code,
    )

    prev_cols = st.columns(6)
    for i, country in enumerate(COUNTRIES):
        r     = compliance[country]
        bg    = STATUS_COLOR[r.status]
        fg    = "white" if r.status in ("INGREDIENT", "RX_ONLY") else "#111"
        icon  = CONFIDENCE_ICON[r.confidence]
        lbl   = STATUS_LABEL[r.status]
        tip   = (
            f"{r.days_remaining}d remaining · "
            f"{r.remaining_pct*100:.0f}% of shelf life · "
            f"threshold {r.threshold_pct*100:.0f}%"
        )
        with prev_cols[i]:
            st.markdown(
                f"""<div title="{tip}" style="text-align:center; background:{bg};
                color:{fg}; border-radius:6px; padding:10px 4px;
                font-size:0.82em; font-weight:bold; line-height:1.5;">
                {country} {icon}<br>{lbl}</div>""",
                unsafe_allow_html=True,
            )

    days_left = (expiry_date - today).days
    st.caption(
        f"Days remaining: **{days_left}** · "
        f"Shelf life used: **{max(0, shelf_days - days_left)}d** of **{shelf_days}d** · "
        f"Manufacture date: **{manufacture_date}**"
    )

    blocked_ing = sorted({ing for c in COUNTRIES for ing in compliance[c].flagged_ingredients})
    if blocked_ing:
        st.error(f"Banned ingredients detected: {', '.join(blocked_ing)}")
    if any(compliance[c].is_rx for c in COUNTRIES):
        st.warning("Contains a substance classified as Rx-only in GCC (e.g. melatonin). "
                   "Cannot be imported as a supplement.")

    # ── Add to inventory ───────────────────────────────────────────────────────
    st.divider()
    st.subheader("Add to Inventory")

    col_add, col_note = st.columns([1, 3])
    with col_add:
        add_clicked = st.button("Add to Inventory", type="primary", use_container_width=True)
    with col_note:
        st.caption("Writes a new row to the inventory CSV. "
                   "The Dashboard and Allocation Table will update automatically.")

    if add_clicked:
        existing_inv = pd.read_csv(str(DATA_PATH))
        nums     = existing_inv["sku_id"].str.extract(r"(\d+)")[0].dropna().astype(int)
        next_num = int(nums.max()) + 1 if not nums.empty else 1
        new_sku  = f"SKU-{next_num:05d}"

        new_row = {
            "sku_id":                new_sku,
            "product_name":          sel["name"],
            "brand":                 brand,
            "category":              category,
            "hs_code":               hs_code,
            "ingredients":           p_ingr,
            "batch_id":              f"BATCH-{today.strftime('%Y%m')}-{next_num:03d}",
            "manufacture_date":      str(manufacture_date),
            "expiry_date":           str(expiry_date),
            "total_shelf_life_days": shelf_days,
            "qty_on_hand":           qty,
            "unit_cost_usd":         unit_cost,
            "halal_certified":       halal,
            "country_of_origin":     origin,
        }

        updated_inv = pd.concat([existing_inv, pd.DataFrame([new_row])], ignore_index=True)
        updated_inv.to_csv(str(DATA_PATH), index=False)
        st.cache_data.clear()
        st.success(f"Added **{new_sku}** — {sel['name']} to inventory.")
        st.caption("Navigate to the Dashboard or Allocation Table to see the updated data.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 6 — TOKEN USAGE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Token Usage":
    components.html(_SCROLL_JS, height=0, scrolling=False)
    st.header("Token Usage")
    st.caption("API calls made this session, which page triggered them, and their cost.")

    log = st.session_state.get("token_log", [])

    if not log:
        st.info("No API calls made yet this session. Use the Compliance Chat or Product Lookup to generate some.")
    else:
        df_log = pd.DataFrame(log)

        # ── Session totals ─────────────────────────────────────────────────────
        total_cost = df_log["cost"].sum()
        total_in   = df_log["in_tokens"].sum()
        total_out  = df_log["out_tokens"].sum()
        total_calls = df_log["api_calls"].sum()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total cost",        f"${total_cost:.4f}")
        m2.metric("Input tokens",      f"{total_in:,}")
        m3.metric("Output tokens",     f"{total_out:,}")
        m4.metric("API calls",         f"{int(total_calls)}")

        st.divider()

        # ── By page breakdown ──────────────────────────────────────────────────
        st.subheader("By Page")
        by_page = (
            df_log.groupby("page")
            .agg(
                calls    =("api_calls",  "sum"),
                in_tokens=("in_tokens",  "sum"),
                out_tokens=("out_tokens", "sum"),
                cost     =("cost",        "sum"),
            )
            .reset_index()
            .sort_values("cost", ascending=False)
        )
        by_page["cost"] = by_page["cost"].map("${:.4f}".format)
        by_page["in_tokens"]  = by_page["in_tokens"].map("{:,}".format)
        by_page["out_tokens"] = by_page["out_tokens"].map("{:,}".format)
        by_page.columns = ["Page", "API Calls", "Input Tokens", "Output Tokens", "Cost"]
        st.dataframe(by_page.set_index("Page"), use_container_width=True)

        st.divider()

        # ── Full call log ──────────────────────────────────────────────────────
        st.subheader("Call Log")
        df_display = df_log.copy()
        df_display["cost"] = df_display["cost"].map("${:.4f}".format)
        df_display["in_tokens"]  = df_display["in_tokens"].map("{:,}".format)
        df_display["out_tokens"] = df_display["out_tokens"].map("{:,}".format)
        df_display.columns = ["Time", "Page", "Model", "Input", "Output", "API Calls", "Cost"]
        st.dataframe(df_display.set_index("Time"), use_container_width=True)

        st.divider()
        if st.button("Clear usage log", type="secondary"):
            st.session_state.token_log = []
            st.rerun()
