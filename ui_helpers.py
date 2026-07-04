from __future__ import annotations

import streamlit as st

from services import authenticate_user


def inject_styles() -> None:
    st.markdown(
        """
        <style>
            :root {
                --bg: #f5f1ea;
                --panel: rgba(255, 252, 247, 0.88);
                --panel-strong: #fffdfa;
                --border: #e4d7c5;
                --text: #2f2419;
                --muted: #776556;
                --accent: #b45d34;
                --accent-dark: #8b4323;
                --green: #4f7a5c;
                --shadow: 0 18px 40px rgba(70, 43, 22, 0.08);
            }
            .stApp {
                background:
                    radial-gradient(circle at top left, rgba(197, 133, 86, 0.14), transparent 28%),
                    radial-gradient(circle at top right, rgba(79, 122, 92, 0.16), transparent 24%),
                    linear-gradient(180deg, #fbf7f2 0%, #f3ede4 100%);
                color: var(--text);
            }
            .block-container {
                padding-top: 1.5rem;
                padding-bottom: 2.5rem;
                max-width: 1320px;
            }
            .hero-card {
                padding: 1.65rem 1.8rem;
                border-radius: 28px;
                background:
                    radial-gradient(circle at top right, rgba(255, 255, 255, 0.12), transparent 28%),
                    linear-gradient(135deg, #2f2419 0%, #6c3d25 54%, #b45d34 100%);
                color: white;
                box-shadow: 0 22px 50px rgba(65, 32, 16, 0.18);
                margin-bottom: 1.5rem;
            }
            div[data-testid="stMetric"] {
                background: var(--panel-strong);
                border: 1px solid var(--border);
                border-radius: 22px;
                padding: 1rem 1rem 0.9rem 1rem;
                box-shadow: var(--shadow);
                min-height: 132px;
            }
            div[data-testid="stSidebar"] {
                background: linear-gradient(180deg, #fcf7f0 0%, #f2e7d8 100%);
                border-right: 1px solid rgba(171, 133, 99, 0.18);
            }
            div[data-testid="stMetricLabel"] p {
                color: var(--muted);
                font-weight: 600;
                font-size: 0.93rem;
            }
            div[data-testid="stMetricValue"] {
                color: var(--text);
                font-size: 1.45rem;
            }
            .small-note {
                color: var(--muted);
                font-size: 0.92rem;
            }
            .section-card {
                background: var(--panel);
                border: 1px solid var(--border);
                border-radius: 24px;
                padding: 1rem 1.1rem 1.15rem 1.1rem;
                box-shadow: var(--shadow);
                backdrop-filter: blur(10px);
            }
            .section-title {
                font-size: 1.05rem;
                font-weight: 700;
                color: var(--text);
                margin-bottom: 0.25rem;
            }
            .section-subtitle {
                color: var(--muted);
                font-size: 0.93rem;
                margin-bottom: 0.9rem;
            }
            .legend-row {
                display: flex;
                gap: 0.5rem;
                flex-wrap: wrap;
                margin-top: 0.8rem;
            }
            .legend-badge {
                background: rgba(255,255,255,0.16);
                border: 1px solid rgba(255,255,255,0.14);
                padding: 0.35rem 0.65rem;
                border-radius: 999px;
                font-size: 0.86rem;
            }
            .category-card {
                background: linear-gradient(180deg, rgba(255, 250, 245, 0.95) 0%, rgba(249, 242, 234, 0.95) 100%);
                border: 1px solid var(--border);
                border-radius: 22px;
                padding: 1rem;
                box-shadow: var(--shadow);
                min-height: 170px;
            }
            .category-name {
                font-size: 1rem;
                font-weight: 700;
                color: var(--text);
                margin-bottom: 0.35rem;
            }
            .category-total {
                font-size: 1.35rem;
                font-weight: 800;
                color: var(--accent-dark);
                margin-bottom: 0.65rem;
            }
            .category-meta {
                color: var(--muted);
                font-size: 0.92rem;
                line-height: 1.55;
            }
            .expense-detail-card {
                background: rgba(255, 253, 250, 0.95);
                border: 1px solid var(--border);
                border-radius: 18px;
                padding: 0.9rem 1rem;
                margin-bottom: 0.7rem;
            }
            .expense-detail-title {
                font-size: 1rem;
                font-weight: 700;
                color: var(--text);
                margin-bottom: 0.25rem;
            }
            .expense-detail-meta {
                color: var(--muted);
                font-size: 0.92rem;
                line-height: 1.5;
            }
            div[data-baseweb="select"] > div,
            div[data-baseweb="input"] > div,
            div[data-baseweb="textarea"] > div,
            div[data-baseweb="base-input"] {
                border-radius: 16px !important;
                border-color: #dbcab6 !important;
            }
            div.stButton > button,
            div.stDownloadButton > button,
            div[data-testid="stFormSubmitButton"] button {
                border-radius: 16px !important;
                border: 1px solid transparent !important;
                background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%) !important;
                color: white !important;
                font-weight: 600 !important;
                box-shadow: 0 10px 24px rgba(139, 67, 35, 0.18);
            }
            div.stButton > button[kind="secondary"],
            div[data-testid="stFormSubmitButton"] button[kind="secondary"] {
                background: white !important;
                color: var(--text) !important;
                border: 1px solid var(--border) !important;
                box-shadow: none !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def initialize_session_state() -> None:
    if "selected_expense_id" not in st.session_state:
        st.session_state.selected_expense_id = None
    if "selected_category" not in st.session_state:
        st.session_state.selected_category = None
    if "is_authenticated" not in st.session_state:
        st.session_state.is_authenticated = False
    if "current_user" not in st.session_state:
        st.session_state.current_user = None
    if "filters" not in st.session_state:
        st.session_state.filters = {
            "month_label": "Tutti",
            "category": "Tutte",
            "payer": "Tutti",
            "expense_type": "Tutte",
        }
    if "current_section" not in st.session_state:
        st.session_state.current_section = "Home"
    if "current_view" not in st.session_state:
        st.session_state.current_view = "home"
    if "dashboard_metric" not in st.session_state:
        st.session_state.dashboard_metric = None
    if "show_filters" not in st.session_state:
        st.session_state.show_filters = True
    if "profile_view" not in st.session_state:
        st.session_state.profile_view = False


def render_login_page() -> None:
    spacer_left, center, spacer_right = st.columns([1, 1.15, 1])
    with center:
        st.markdown(
            """
            <div class="hero-card" style="margin-top: 3rem;">
                <div style="letter-spacing:0.08em; text-transform:uppercase; font-size:0.82rem; opacity:0.78; margin-bottom:0.45rem;">
                    Accesso riservato
                </div>
                <h1 style="margin:0; font-size:2rem;">Accedi al tuo monitor spese</h1>
                <p style="margin:0.8rem 0 0 0; opacity:0.92;">
                    Inserisci username e password per entrare nell'app. Le credenziali demo sono pronte per i test.
                </p>
                <div class="legend-row">
                    <span class="legend-badge">Utente demo: io / nessuna password</span>
                    <span class="legend-badge">Utente demo: compagna / demo123</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        open_section("Login", "Accesso locale semplice con utenti salvati in SQLite.")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Accedi", use_container_width=True)

            if submitted:
                user = authenticate_user(username, password)
                if user is None:
                    st.error("Credenziali non valide. Controlla username e password.")
                else:
                    st.session_state.is_authenticated = True
                    st.session_state.current_user = user
                    st.success("Accesso effettuato.")
                    st.rerun()
        close_section()


def render_topbar() -> None:
    user = st.session_state.current_user or {}
    left, right = st.columns([1, 0.42])
    with left:
        st.caption(f"Connesso come: {user.get('full_name', 'Utente')} ({user.get('username', '-')})")
    with right:
        if st.button("Logout", use_container_width=True):
            st.session_state.is_authenticated = False
            st.session_state.current_user = None
            st.rerun()


def open_section(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="section-card">
            <div class="section-title">{title}</div>
            <div class="section-subtitle">{subtitle}</div>
        """,
        unsafe_allow_html=True,
    )


def close_section() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def require_authentication() -> bool:
    initialize_session_state()
    inject_styles()
    if st.session_state.is_authenticated:
        return True
    render_login_page()
    return False
