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

# ── Token logger (Azure Blob + Parquet) ───────────────────────────────────────
from engine.token_logger import TokenLogger
from engine.llm_client import TrackedClient

_token_logger = TokenLogger(project_id="iherb-gcc")

if "session_id" not in st.session_state:
    import uuid as _uuid
    st.session_state.session_id = _uuid.uuid4().hex[:8]
if "session_calls" not in st.session_state:
    st.session_state.session_calls = []  # current session only, for instant display

def _make_client(page: str) -> TrackedClient:
    return TrackedClient(
        project_id="iherb-gcc",
        session_id=st.session_state.session_id,
        page=page,
        session_log=st.session_state.session_calls,
    )


def _notes(content: str, label: str = "Notes"):
    """Render a floating Notes popover button."""
    with st.popover(f"📝 {label}"):
        st.markdown(content)


# Streamlit Cloud stores secrets in st.secrets — push them into env so all
# modules (advisor, scraper) pick them up via os.getenv() unchanged.
for _k in ("ANTHROPIC_API_KEY", "APIFY_TOKEN", "AZURE_STORAGE_CONNECTION_STRING"):
    if _k in st.secrets and not os.getenv(_k):
        os.environ[_k] = st.secrets[_k]

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="GCC Dietary Supplements Compliance Engine",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)


PRODUCTS_PATH = Path(__file__).parent / "data" / "products.csv"
STOCK_PATH    = Path(__file__).parent / "data" / "stock.csv"
SALES_PATH    = Path(__file__).parent / "data" / "sales_events.csv"

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
    inv = load_inventory(
        products_path=str(PRODUCTS_PATH),
        stock_path=str(STOCK_PATH),
        sales_path=str(SALES_PATH),
    )
    compliance = run_compliance(inv)
    return build_report(compliance)


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("GCC Compliance Engine")
    st.caption("Dietary Supplements — Allocation Risk Monitor")
    st.divider()

    _pages = ["Introduction", "Process Flow", "Dashboard", "Allocation Table", "Compliance Chat", "Risk Actions", "Product Lookup", "Token Usage"]
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
    st.caption(f"Source: Mock inventory · {len(get_report())} SKUs")

    if st.button("Refresh data"):
        st.cache_data.clear()
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
        .pt-purple { background: #EDE8F8; color: #4A2D8E; }  /* Behaviour — purple */
        .pt-teal   { background: #FEF0D8; color: #7A4200; }  /* Knowledge  — orange */
        .pt-coral  { background: #EDF2E0; color: #3A5218; }  /* Action     — sage green */
        /* Placeholder / coming-soon card */
        .proj-card-soon {
            border-radius: 14px;
            border: 1px dashed rgba(128,128,128,0.35);
            border-left: 3px dashed rgba(128,128,128,0.45);
            padding: 1.75rem 2.25rem 1.5rem;
            opacity: 0.68;
        }
        .proj-card-soon .proj-card-title { color: inherit; }
        .soon-badge {
            display: inline-block;
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.07em;
            text-transform: uppercase;
            background: rgba(128,128,128,0.13);
            border-radius: 4px;
            padding: 2px 8px;
            margin-left: 10px;
            vertical-align: middle;
        }
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

    # ── Framework diagram ─────────────────────────────────────────────────────
    st.image("AI.png", use_container_width=False, width=520)

    st.markdown(
        "Done well, this is not a replacement for your people or your systems. "
        "It is a way of making both more effective.\n\n"
        "The projects below are practical demonstrations of these ideas, applied to "
        "business problems in the GCC market."
    )

    st.markdown('<hr class="lp-divider">', unsafe_allow_html=True)
    st.markdown('<p class="lp-section-label">Projects</p>', unsafe_allow_html=True)

    # ── Project card ──────────────────────────────────────────────────────────
    st.markdown(
        '<div class="proj-card">'
        '<p class="proj-card-title">GCC Customs Compliance Engine &mdash; Dietary Supplements</p>'
        "<p>A dietary supplements distributor operates a distribution centre in Saudi Arabia serving the wider GCC market. "
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

    if st.button("Open — GCC Compliance Engine →", type="primary", use_container_width=True):
        from engine.advisor import warm_cache
        warm_cache(_make_client("Cache Warm-up"))
        st.session_state["nav_page"] = "Dashboard"
        st.rerun()

    st.markdown(
        '<div class="proj-card-soon">'
        '<p class="proj-card-title">MIDP / Aconex Reconciliation'
        '<span class="soon-badge">In Progress</span></p>'
        "<p>AI assistance for a heavily manual process reconciling MIDP deliverables with "
        "controlled documents in Aconex. Construction and engineering projects generate "
        "thousands of controlled documents — cross-referencing deliverable registers against "
        "submission records by hand is slow, error-prone, and a poor use of document "
        "controllers' time.</p>"
        "<p>This project explores the use case within a SharePoint environment, using "
        "Microsoft's Graph API to leverage delta changes and optimise RAG — so the model "
        "reasons over what has <em>changed</em> rather than re-ingesting the entire document "
        "corpus on every query.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="proj-card-soon">'
        '<p class="proj-card-title">Job Board Assistant'
        '<span class="soon-badge">In Progress</span></p>'
        "<p>Job hunting is time-consuming and repetitive. This project uses Claude to monitor "
        "job boards, identify relevant roles, and assist with applications — without allowing "
        "it to make the most common AI-assisted CV error: fabricating experience or "
        "embellishing qualifications to pass ATS screening.</p>"
        "<p>The constraint is deliberate. I wear several hats — ERP Implementation, "
        "Logistics Integration, Business Intelligence, and Data Architecture — and maintain "
        "four CVs with different slants to reflect this. The model is given bullet points "
        "from all four as a constrained source of truth, and constructs a tailored CV that "
        "fits the specific requirement — drawing only from what is genuinely there, not "
        "inventing credentials to clear filters it would otherwise not pass.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

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
        st.caption(f"Shows how many of the {len(df)} SKUs can ship to each destination right now, and why others are blocked.")

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
                    reply, updated, usage = chat(list(st.session_state.chat_messages), df, _make_client("Compliance Chat"))
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
                        _make_client("Compliance Chat"),
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
    _notes("""\
I haven't spent too much time on this page — I simply asked Claude to create a discounting
action when a product approaches its UAE import threshold.

It's not very realistic. You probably shouldn't be discounting a product just because it's
approaching its UAE shelf-life threshold — the point at which remaining shelf life drops
below 75% and the product can no longer clear UAE customs. What about the other five
countries? What's the sales profile of that product anyway? It may sell predominantly in
Saudi Arabia, in which case the UAE threshold is largely irrelevant.

To give adequate decision support here you would want to plug this into a **forecast model**
— something like XGBoost would do it — generate a demand forecast by country, and only
recommend discounting when the forecast suggests you cannot sell through the stock before
the compliance window closes. That is a significantly more useful signal than a simple
threshold comparison.

---

**A note on AI vs ML**

The market seems to be confused between the two. **Machine Learning is not AI** — it never
has been and never will be. ML is a mathematical model applied to data: gradient descent,
decision trees, regression. It finds patterns. It does not reason.

**AI** is an interpretation of cause and effect, working over data to arrive at conclusions,
weigh trade-offs, and recommend action. The demand forecast is ML. The advisor that decides
what to do with it is AI. Both are useful. They are not the same thing.
""")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Reroute to Lower-Threshold Countries",
        "Discount Candidates",
        "Fully Blocked",
        "Halal Certification",
    ])

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
                prods = pd.read_csv(str(PRODUCTS_PATH))
                for _, row in edited.iterrows():
                    prods.loc[
                        prods["product_id"] == row["SKU"], "halal_certified"
                    ] = "yes" if row["Halal Certified"] else "no"
                prods.to_csv(str(PRODUCTS_PATH), index=False)
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

Of course, care must be taken, but this is a relatively well-bounded problem domain. Training an
LLM to make these comparisons is a far better long-term solution than a brittle SQL or Python script.

When mistakes do occur, the first requirement is non-negotiable: **a human with domain knowledge
must identify and correct them**. From there, the correction options are:

The lightweight options — **prompt engineering** (explicit rules in the system prompt) and **RAG**
(injecting known corrections at call time) — can be applied immediately and are human-maintainable.
At greater cost and effort, **training a private model** (e.g. GPT-4o mini) with your own labelled
correction data bakes the improvements into the model itself.

All of these approaches have trade-offs between cost and effectiveness.
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
                result = analyse_ingredients(sel["ingredients"], sel["name"], _make_client("Product Lookup"))

            if "error" in result:
                st.error(result["error"])
                st.session_state.pop("last_classification", None)
            else:
                usage = result.pop("_usage", {})
                st.session_state.last_classification = {"product": sel["name"], "result": result, "usage": usage}
                if usage:
                    for k in ("input_tokens", "output_tokens", "api_calls"):
                        st.session_state.classifier_usage[k] += usage.get(k, 0)

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
        prods = pd.read_csv(str(PRODUCTS_PATH))
        nums     = prods["product_id"].str.extract(r"(\d+)")[0].dropna().astype(int)
        next_num = int(nums.max()) + 1 if not nums.empty else 1
        new_product_id = f"SKU{next_num:03d}"
        new_batch_id   = f"BATCH-{today.strftime('%Y%m')}-{next_num:03d}"

        new_product = {
            "product_id":        new_product_id,
            "product_name":      sel["name"],
            "brand":             brand,
            "category":          category,
            "hs_code":           hs_code,
            "ingredients":       p_ingr,
            "halal_certified":   halal,
            "country_of_origin": origin,
        }
        updated_prods = pd.concat([prods, pd.DataFrame([new_product])], ignore_index=True)
        updated_prods.to_csv(str(PRODUCTS_PATH), index=False)

        stock_df = pd.read_csv(str(STOCK_PATH))
        new_stock = {
            "batch_id":             new_batch_id,
            "product_id":           new_product_id,
            "manufacture_date":     str(manufacture_date),
            "expiry_date":          str(expiry_date),
            "total_shelf_life_days": shelf_days,
            "qty_initial":          qty,
            "unit_cost_usd":        unit_cost,
        }
        updated_stock = pd.concat([stock_df, pd.DataFrame([new_stock])], ignore_index=True)
        updated_stock.to_csv(str(STOCK_PATH), index=False)

        st.cache_data.clear()
        st.success(f"Added **{new_product_id}** — {sel['name']} to inventory.")
        st.caption("Navigate to the Dashboard or Allocation Table to see the updated data.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 6 — TOKEN USAGE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Token Usage":
    components.html(_SCROLL_JS, height=0, scrolling=False)
    st.header("Token Usage")
    st.caption("Persistent log of every API call — this session and since inception.")

    session_calls = st.session_state.get("session_calls", [])

    def _usage_metrics(df, label):
        st.subheader(label)
        if df.empty:
            st.info("No calls recorded.")
            return
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Cost",         f"${df['cost_usd'].sum():.4f}")
        m2.metric("Input tokens", f"{int(df['in_tokens'].sum()):,}")
        m3.metric("Output tokens",f"{int(df['out_tokens'].sum()):,}")
        m4.metric("API calls",    f"{int(df['api_calls'].sum()):,}")

    def _by_page_table(df):
        if df.empty:
            return
        by_page = (
            df.groupby("page")
            .agg(calls=("api_calls","sum"), in_tokens=("in_tokens","sum"),
                 out_tokens=("out_tokens","sum"), cost_usd=("cost_usd","sum"))
            .reset_index().sort_values("cost_usd", ascending=False)
        )
        by_page["cost_usd"]   = by_page["cost_usd"].map("${:.4f}".format)
        by_page["in_tokens"]  = by_page["in_tokens"].map("{:,}".format)
        by_page["out_tokens"] = by_page["out_tokens"].map("{:,}".format)
        by_page.columns = ["Page", "API Calls", "In Tokens", "Out Tokens", "Cost"]
        st.dataframe(by_page.set_index("Page"), use_container_width=True)

    def _call_log_table(df):
        if df.empty:
            return
        d = df[["date","time","page","model","in_tokens","out_tokens","api_calls","cost_usd"]].copy()
        d["cost_usd"]   = d["cost_usd"].map("${:.4f}".format)
        d["in_tokens"]  = d["in_tokens"].map("{:,}".format)
        d["out_tokens"] = d["out_tokens"].map("{:,}".format)
        d.columns = ["Date","Time","Page","Model","In","Out","Calls","Cost"]
        st.dataframe(d.set_index("Date"), use_container_width=True)

    @st.cache_data(ttl=300, show_spinner="Loading usage history…")
    def _load_all_usage():
        return _token_logger.query_df()

    tab_session, tab_all = st.tabs(["This Session", "Since Inception"])

    with tab_session:
        df_session = pd.DataFrame(session_calls)
        _usage_metrics(df_session, "This Session")
        if not df_session.empty:
            st.divider()
            st.markdown("**By page**")
            _by_page_table(df_session)
            st.divider()
            st.markdown("**Call log**")
            _call_log_table(df_session)

    with tab_all:
        col_refresh, _ = st.columns([1, 5])
        if col_refresh.button("Refresh", use_container_width=True):
            st.cache_data.clear()
        df_all = _load_all_usage()
        _usage_metrics(df_all, "All Time")
        if not df_all.empty:
            st.divider()
            st.markdown("**By page**")
            _by_page_table(df_all)
            st.divider()
            st.markdown("**By session**")
            by_sess = (
                df_all.groupby(["session_id","date"])
                .agg(calls=("api_calls","sum"), cost_usd=("cost_usd","sum"))
                .reset_index().sort_values("date", ascending=False)
            )
            by_sess["cost_usd"] = by_sess["cost_usd"].map("${:.4f}".format)
            by_sess.columns = ["Session", "Date", "API Calls", "Cost"]
            st.dataframe(by_sess.set_index("Session"), use_container_width=True)
            st.divider()
            st.markdown("**Full call log**")
            _call_log_table(df_all)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE — ARCHITECTURE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Process Flow":
    components.html(_SCROLL_JS, height=0, scrolling=False)
    st.header("Process Flow")
    st.caption("How the compliance engine plugs in to existing 3PL processes.")
    _notes("""
**What this diagram shows**

The flow covers two distinct processes that run in parallel:

**Product onboarding (left column)**
When a client advises a new product, it is classified by the AI Compliance Engine before it can
enter the Product Master. HS codes are checked, ingredients are screened against GCC banned and
restricted lists, halal requirements are assessed, and shelf-life viability is confirmed for the
intended destination. Nothing enters the Product Master unless it clears this gate. Products that
fail are routed to Compliance Reporting.

**Inbound shipments (right column)**
When stock is enroute, an Advanced Shipping Notification triggers the receiving process. On
arrival, products are checked against the Product Master — this is an operational gate, not an AI
function. Stock that cannot be matched or has not passed compliance is quarantined or refused.
Stock that clears is received into inventory.

**The AI plays two different roles in this process** — see the cards below.

The **ERP System** sits at the base as the system of record, receiving clean validated product
data after it has passed through the compliance engine.
""")

    _arch_img = Path(__file__).parent / "architecture_slide.png"
    if _arch_img.exists():
        st.image(str(_arch_img), use_container_width=True)
    else:
        st.warning("architecture_slide.png not found. Run the PowerShell export step to regenerate it.")

    st.markdown("---")
    components.html("""
<style>
  .ai-role-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 8px 0 4px; font-family: sans-serif; }
  .ai-role-card { border-radius: 10px; padding: 22px 26px 20px; }
  .ai-role-card.gatekeeper { background: #1A2340; color: #fff; }
  .ai-role-card.monitor    { background: #00D4AA; color: #0a3a30; }
  .ai-role-card h3 { margin: 0 0 4px; font-size: 13px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; opacity: 0.7; }
  .ai-role-card h2 { margin: 0 0 14px; font-size: 20px; font-weight: 700; }
  .ai-role-card p  { margin: 0 0 10px; font-size: 14px; line-height: 1.6; }
  .ai-role-card p:last-child { margin-bottom: 0; }
  .ai-role-card .tag { display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; margin-bottom: 14px; }
  .gatekeeper .tag { background: rgba(255,255,255,0.15); color: #fff; }
  .monitor    .tag { background: rgba(0,0,0,0.12); color: #0a3a30; }
</style>
<div class="ai-role-grid">

  <div class="ai-role-card gatekeeper">
    <h3>Role 1</h3>
    <h2>Compliance Gatekeeper</h2>
    <span class="tag">Pre-landing &mdash; one-time</span>
    <p>When a new product is introduced, the AI classifies it against GCC customs rules before
    it can enter the Product Master. It checks HS codes, flags banned or restricted ingredients,
    assesses halal requirements, and confirms the shelf life is viable for the intended destination.</p>
    <p>The outcome is binary: the product either passes and enters the master file, or it is
    flagged for compliance reporting and does not proceed. Nothing lands in the system without
    clearing this gate.</p>
  </div>

  <div class="ai-role-card monitor">
    <h3>Role 2</h3>
    <h2>Ongoing Compliance Monitor</h2>
    <span class="tag">Post-landing &mdash; continuous</span>
    <p>Once stock is live in the warehouse, compliance doesn&rsquo;t stop. Shelf life erodes daily
    &mdash; a product that met UAE&rsquo;s 75% threshold last month may not meet it today. A product
    can be received with permissible ingredients but without its halal certificate: it can be stocked
    but not yet shipped.</p>
    <p>The AI monitors these states continuously, surfacing which products are approaching a threshold,
    which are on hold pending paperwork, and which destinations are still viable &mdash; so the
    warehouse team can act before stock becomes a write-off.</p>
  </div>

</div>
""", height=380)
