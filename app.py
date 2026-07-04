from __future__ import annotations

import base64
from datetime import date
from html import escape
from pathlib import Path
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from database import initialize_database
from services import (
    EXPENSE_TYPE_OPTIONS,
    SHARED_SPLIT_OPTIONS,
    add_category,
    apply_filters,
    apply_income_filters,
    authenticate_user,
    build_calendar_data,
    build_category_summary,
    build_dashboard_metrics,
    build_income_vs_expense_summary,
    create_expense,
    create_income,
    compute_couple_balance,
    delete_income,
    delete_category,
    delete_expense,
    export_expenses_to_csv,
    export_expenses_to_pdf,
    filter_couple_balance_expenses,
    format_currency,
    compute_balance,
    get_categories,
    get_expense_by_id,
    get_shared_expenses,
    get_income_by_id,
    get_expenses,
    get_incomes,
    get_partner_username,
    get_user_by_id,
    get_usernames,
    get_visible_expenses,
    get_visible_incomes,
    get_month_options,
    update_expense,
    update_expense_settled,
    update_income,
    update_user_profile,
    validate_expense_data,
    validate_income_data,
    REPORTLAB_AVAILABLE,
)
from ui_helpers import close_section, open_section, render_topbar, require_authentication


st.set_page_config(page_title="Monitor Spese", page_icon="€", layout="wide")

EXPENSE_LIVE_SEARCH = components.declare_component(
    "expense_live_search",
    path=str(Path(__file__).with_name("components") / "live_search"),
)
EXPENSE_SEARCH_RESET_SIGNAL = "__expense_search_reset__"
EXPENSE_SEARCH_CONFIRM_PREFIX = "__expense_search_confirm__::"


MONTH_NAMES = {
    "01": "Gennaio",
    "02": "Febbraio",
    "03": "Marzo",
    "04": "Aprile",
    "05": "Maggio",
    "06": "Giugno",
    "07": "Luglio",
    "08": "Agosto",
    "09": "Settembre",
    "10": "Ottobre",
    "11": "Novembre",
    "12": "Dicembre",
}


def render_expense_live_search(value: str, key: str, placeholder: str) -> str:
    component_value = EXPENSE_LIVE_SEARCH(
        value=value,
        placeholder=placeholder,
        key=key,
        default=value,
    )
    if component_value is None:
        return value
    return str(component_value)


def render_live_search(value: str, key: str, placeholder: str) -> str:
    return render_expense_live_search(value=value, key=key, placeholder=placeholder)


def format_month_heading(month_label: str) -> str:
    if month_label == "Tutti":
        today = date.today()
        return f"{MONTH_NAMES[today.strftime('%m')]} {today.strftime('%Y')}"

    year, month = month_label.split("-")
    return f"{MONTH_NAMES.get(month, month)} {year}"


def resolve_month_label(month_label: str) -> str:
    if month_label == "Tutti":
        return date.today().strftime("%Y-%m")
    return month_label


def shift_month_label(month_label: str, delta: int) -> str:
    active_month = resolve_month_label(month_label)
    year_text, month_text = active_month.split("-")
    year = int(year_text)
    month = int(month_text) + delta

    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1

    return f"{year}-{month:02d}"


def clear_page_navigation_intent() -> None:
    st.session_state.page = "home"
    st.session_state.expense_filter = None


def queue_sidebar_filter_overrides(**overrides: str) -> None:
    pending = dict(st.session_state.get("pending_sidebar_filter_overrides", {}))
    pending.update({key: value for key, value in overrides.items() if value is not None})
    st.session_state.pending_sidebar_filter_overrides = pending


def navigate_to_expenses(expense_filter: str = "tutte") -> None:
    st.session_state.page = "uscite"
    st.session_state.expense_filter = expense_filter
    st.session_state.current_section = "Uscite"
    st.session_state.pending_section_navigation_sync = True
    queue_sidebar_filter_overrides(expense_type="Tutte")


def navigate_to_couple_balance() -> None:
    st.session_state.page = "saldo_coppia"
    st.session_state.expense_filter = None
    st.session_state.current_section = "Saldo di coppia"
    st.session_state.pending_section_navigation_sync = True
    st.session_state.expense_edit_mode = False
    clear_expense_delete_mode()
    queue_sidebar_filter_overrides(expense_type="Tutte")


def build_couple_balance_label(balance: float) -> str:
    if balance < 0:
        return f"Devo {format_currency(abs(balance))}"
    if balance > 0:
        return f"Mi devono {format_currency(balance)}"
    return "Siamo in pari"


CATEGORY_ICONS = {
    "Spesa": "🛒",
    "Casa": "🏠",
    "Trasporti": "🚗",
    "Ristoranti": "🍽️",
    "Svago": "🎟️",
    "Salute": "💊",
    "Abbonamenti": "💳",
    "Viaggi": "✈️",
    "Regali": "🎁",
    "Altro": "●",
}

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
            header[data-testid="stHeader"] {
                display: none !important;
            }
            .block-container {
                padding-top: 0.32rem;
                padding-bottom: 2.5rem;
                max-width: 1320px;
            }
            .hero-card {
                padding: 1rem 1.2rem;
                border-radius: 24px;
                background:
                    radial-gradient(circle at 78% 28%, rgba(99, 223, 255, 0.18), transparent 20%),
                    radial-gradient(circle at 72% 78%, rgba(240, 191, 85, 0.18), transparent 18%),
                    radial-gradient(circle at bottom left, rgba(242, 203, 170, 0.12), transparent 22%),
                    linear-gradient(135deg, #241b14 0%, #4a2c1e 48%, #8c542e 100%);
                color: white;
                box-shadow: 0 16px 36px rgba(65, 32, 16, 0.12);
                margin-bottom: 0;
                transform-origin: top center;
            }
            .hero-container {
                position: relative;
                opacity: 1;
                margin: 0 0 0.2rem 0;
            }
            .expense-total-sticky {
                position: relative;
                top: auto;
                z-index: 20;
                display: flex;
                flex-direction: column;
                align-items: flex-end;
                gap: 0.42rem;
                justify-content: flex-end;
                margin: 0;
                pointer-events: none;
                transform: translateY(-0.18rem);
            }
            .expense-total-pill {
                display: inline-flex;
                align-items: center;
                gap: 0.55rem;
                min-height: 46px;
                height: 46px;
                width: 196px;
                min-width: 196px;
                max-width: 196px;
                padding: 0.5rem 1.05rem;
                border-radius: 999px;
                background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%);
                border: 1px solid transparent;
                box-shadow: 0 8px 18px rgba(139, 67, 35, 0.18);
                pointer-events: none;
                justify-content: center;
                white-space: nowrap;
            }
            .expense-total-label {
                color: rgba(255, 255, 255, 0.82);
                font-size: 0.8rem;
                text-transform: uppercase;
                letter-spacing: 0.06em;
                line-height: 1;
            }
            .expense-total-value {
                color: white;
                font-size: 1.02rem;
                font-weight: 600;
                line-height: 1;
            }
            .expense-balance-pill {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-height: 34px;
                padding: 0.38rem 0.82rem;
                border-radius: 999px;
                background: rgba(255, 253, 250, 0.92);
                border: 1px solid rgba(180, 93, 52, 0.18);
                box-shadow: 0 6px 14px rgba(139, 67, 35, 0.08);
                color: var(--accent-dark);
                font-size: 0.82rem;
                font-weight: 600;
                line-height: 1;
                white-space: nowrap;
            }
            .expense-list {
                display: flex;
                flex-direction: column;
                gap: 0;
            }
            .expense-card {
                border-bottom: 1px solid rgba(196, 170, 145, 0.45);
                padding: 0;
            }
            .expense-row {
                display: grid;
                grid-template-columns: 86px 1.35fr 1.05fr 0.95fr 0.95fr 120px;
                align-items: center;
                column-gap: 1rem;
                height: 52px;
                width: 100%;
            }
            .expense-cell {
                display: flex;
                align-items: center;
                height: 52px;
                margin: 0;
                line-height: 1;
            }
            .expense-cell-name {
                color: var(--text);
                font-size: 1rem;
                font-weight: 700;
            }
            .expense-cell-secondary {
                color: var(--muted);
                font-size: 0.96rem;
                font-weight: 500;
            }
            .expense-cell-user {
                color: var(--text);
                font-size: 0.98rem;
                font-weight: 700;
            }
            .expense-cell-amount {
                justify-content: flex-end;
                color: var(--text);
                font-size: 1rem;
                font-weight: 700;
                white-space: nowrap;
            }
            .expense-cell-amount-self {
                color: var(--accent);
            }
            .expense-cell-amount-partner {
                color: var(--muted);
            }
            div.st-key-section_navigation_shell {
                position: sticky;
                top: 0.4rem;
                z-index: 40;
                padding: 0.12rem 0 0.35rem 0;
                background: transparent !important;
                backdrop-filter: none !important;
            }
            div.st-key-section_navigation_shell > div,
            div.st-key-section_navigation_shell div[data-testid="stVerticalBlock"],
            div.st-key-section_navigation_shell div[data-testid="stElementContainer"] {
                background: transparent !important;
                box-shadow: none !important;
            }
            section[data-testid="stSidebar"],
            button[kind="header"][data-testid="stSidebarCollapsedControl"] {
                display: none !important;
            }
            .home-toolbar-shell {
                display: flex;
                justify-content: flex-end;
                align-items: center;
                margin: 0.16rem 0 0.82rem 0;
            }
            div.st-key-home_toolbar_actions > div,
            div.st-key-home_toolbar_actions div[data-testid="stVerticalBlock"],
            div.st-key-home_toolbar_actions div[data-testid="stElementContainer"] {
                background: transparent !important;
                box-shadow: none !important;
            }
            div.st-key-home_toolbar_actions button[kind="secondary"],
            div.st-key-home_toolbar_actions div.stButton > button,
            div.st-key-home_filter_popover button[kind="secondary"],
            div.st-key-home_filter_popover div.stButton > button {
                min-width: 38px !important;
                width: 38px !important;
                min-height: 38px !important;
                height: 38px !important;
                border-radius: 999px !important;
                padding: 0 !important;
                background: rgba(255, 251, 246, 0.96) !important;
                color: var(--text) !important;
                border: 1px solid #e4d7c5 !important;
                box-shadow: none !important;
            }
            div.st-key-home_filter_popover div[data-testid="stPopover"] {
                min-width: 320px;
            }
            .home-filter-count {
                color: var(--muted);
                font-size: 0.82rem;
                font-weight: 500;
                margin-top: 0.5rem;
            }
            div.st-key-expense_fixed_stack {
                position: relative;
                z-index: 30;
                padding: 0.1rem 0 0 0;
                display: flex;
                flex-direction: column;
                flex: 0 0 auto;
                min-height: 0;
                background: transparent !important;
                backdrop-filter: none !important;
                box-shadow: none !important;
            }
            div.st-key-expense_fixed_stack > div,
            div.st-key-expense_fixed_stack div[data-testid="stVerticalBlock"],
            div.st-key-expense_fixed_stack div[data-testid="stElementContainer"] {
                background: transparent !important;
                box-shadow: none !important;
            }
            div.st-key-expense_fixed_stack > div,
            div.st-key-income_fixed_stack > div {
                width: 100%;
            }
            div.st-key-expense_month_row,
            div.st-key-income_month_row,
            div.st-key-expense_main_block_frame,
            div.st-key-income_main_block_frame,
            div.st-key-expense_toolbar_frame,
            div.st-key-income_toolbar_frame,
            div.st-key-expense_controls_row,
            div.st-key-income_controls_row {
                margin: 0;
                padding: 0;
                background: transparent !important;
            }
            div.st-key-expense_month_row,
            div.st-key-income_month_row {
                width: 100%;
                margin: 0 0 0.58rem 0;
            }
            div.st-key-expense_main_block_frame > div,
            div.st-key-expense_main_block_frame div[data-testid="stVerticalBlock"],
            div.st-key-expense_main_block_frame div[data-testid="stElementContainer"],
            div.st-key-income_main_block_frame > div,
            div.st-key-income_main_block_frame div[data-testid="stVerticalBlock"],
            div.st-key-income_main_block_frame div[data-testid="stElementContainer"],
            div.st-key-expense_toolbar_frame > div,
            div.st-key-expense_toolbar_frame div[data-testid="stVerticalBlock"],
            div.st-key-expense_toolbar_frame div[data-testid="stElementContainer"],
            div.st-key-income_toolbar_frame > div,
            div.st-key-income_toolbar_frame div[data-testid="stVerticalBlock"],
            div.st-key-income_toolbar_frame div[data-testid="stElementContainer"],
            div.st-key-expense_controls_row > div,
            div.st-key-expense_controls_row div[data-testid="stVerticalBlock"],
            div.st-key-expense_controls_row div[data-testid="stElementContainer"],
            div.st-key-income_controls_row > div,
            div.st-key-income_controls_row div[data-testid="stVerticalBlock"],
            div.st-key-income_controls_row div[data-testid="stElementContainer"] {
                background: transparent !important;
                box-shadow: none !important;
            }
            div.st-key-expense_main_block_frame,
            div.st-key-income_main_block_frame {
                width: 100%;
                min-height: 5.10rem;
                height: 5.10rem;
                max-height: 5.10rem;
                overflow: hidden;
                display: flex;
                align-items: flex-start;
                margin: 0 0 0.12rem 0;
            }
            div.st-key-expense_toolbar_frame,
            div.st-key-income_toolbar_frame {
                width: min(34rem, 100%);
                max-width: 34rem;
                min-height: 2.34rem;
                height: 2.34rem;
                max-height: 2.34rem;
                display: flex;
                align-items: center;
                box-shadow: inset 0 -1px 0 rgba(207, 138, 93, 0.18);
            }
            div.st-key-expense_header_content,
            div.st-key-income_header_content {
                width: min(34rem, 100%);
                max-width: 34rem;
                margin: 0;
                padding: 0;
                display: grid;
                grid-template-rows: 2.72rem 1.98rem;
                row-gap: 0.40rem;
                align-content: start;
                min-height: 5.10rem;
                height: 5.10rem;
                max-height: 5.10rem;
                overflow: hidden;
                background: transparent !important;
            }
            div.st-key-expense_header_content > div,
            div.st-key-expense_header_content div[data-testid="stVerticalBlock"],
            div.st-key-expense_header_content div[data-testid="stElementContainer"],
            div.st-key-income_header_content > div,
            div.st-key-income_header_content div[data-testid="stVerticalBlock"],
            div.st-key-income_header_content div[data-testid="stElementContainer"] {
                background: transparent !important;
                box-shadow: none !important;
            }
            div.st-key-expense_header_content > div,
            div.st-key-income_header_content > div,
            div.st-key-expense_header_content div[data-testid="stVerticalBlock"],
            div.st-key-income_header_content div[data-testid="stVerticalBlock"] {
                min-height: 0;
                height: 100%;
            }
            div.st-key-expense_primary_tabs_row,
            div.st-key-expense_secondary_tabs_row {
                width: 100%;
                margin: 0;
                padding: 0;
                background: transparent !important;
                overflow: hidden;
            }
            div.st-key-expense_primary_tabs_row {
                min-height: 2.72rem;
                height: 2.72rem;
                max-height: 2.72rem;
            }
            div.st-key-expense_secondary_tabs_row {
                min-height: 1.98rem;
                height: 1.98rem;
                max-height: 1.98rem;
            }
            div.st-key-expense_primary_tabs_row > div,
            div.st-key-expense_primary_tabs_row div[data-testid="stVerticalBlock"],
            div.st-key-expense_primary_tabs_row div[data-testid="stElementContainer"],
            div.st-key-expense_secondary_tabs_row > div,
            div.st-key-expense_secondary_tabs_row div[data-testid="stVerticalBlock"],
            div.st-key-expense_secondary_tabs_row div[data-testid="stElementContainer"] {
                background: transparent !important;
                box-shadow: none !important;
                min-height: 0;
                height: 100%;
            }
            div.st-key-expense_controls_row {
                margin: 0 0 0.18rem 0;
                min-height: 2.34rem;
                height: 2.34rem;
            }
            div.st-key-income_controls_row {
                margin: 0 0 0.18rem 0;
                min-height: 2.34rem;
                height: 2.34rem;
            }
            div.st-key-expense_controls_row div[data-testid="stHorizontalBlock"],
            div.st-key-income_controls_row div[data-testid="stHorizontalBlock"] {
                align-items: center;
                min-height: 2.34rem;
            }
            div.st-key-expense_section_shell {
                display: flex;
                flex-direction: column;
                min-height: 0;
                height: auto;
                max-height: none;
                overflow: visible;
                background: transparent !important;
                box-shadow: none !important;
            }
            div.st-key-expense_lower_shell {
                display: flex;
                flex-direction: column;
                min-height: 0;
                flex: 0 0 auto;
                background: transparent !important;
            }
            div.st-key-expense_lower_shell > div,
            div.st-key-expense_lower_shell div[data-testid="stVerticalBlock"],
            div.st-key-expense_lower_shell div[data-testid="stElementContainer"] {
                background: transparent !important;
                box-shadow: none !important;
                min-height: 0;
            }
            div.st-key-expense_feed_scroll {
                flex: 0 0 auto;
                min-height: auto;
                height: auto;
                max-height: none;
                overflow: visible;
                padding-right: 0;
                padding-bottom: 0;
                margin-top: 0;
            }
            div.st-key-expense_feed_scroll > div {
                min-height: 0;
                padding-top: 0;
            }
            div.st-key-income_fixed_stack {
                position: relative;
                z-index: 30;
                display: flex;
                flex-direction: column;
                flex: 0 0 auto;
                min-height: 0;
                padding: 0.1rem 0 0 0;
                background: transparent !important;
                backdrop-filter: none !important;
                box-shadow: none !important;
            }
            div.st-key-income_fixed_stack > div,
            div.st-key-income_fixed_stack div[data-testid="stVerticalBlock"],
            div.st-key-income_fixed_stack div[data-testid="stElementContainer"] {
                background: transparent !important;
                box-shadow: none !important;
            }
            div.st-key-income_section_shell {
                display: flex;
                flex-direction: column;
                min-height: 0;
                height: auto;
                max-height: none;
                overflow: visible;
                background: transparent !important;
                box-shadow: none !important;
            }
            div.st-key-income_lower_shell {
                display: flex;
                flex-direction: column;
                min-height: 0;
                flex: 0 0 auto;
                background: transparent !important;
            }
            div.st-key-income_lower_shell > div,
            div.st-key-income_lower_shell div[data-testid="stVerticalBlock"],
            div.st-key-income_lower_shell div[data-testid="stElementContainer"] {
                background: transparent !important;
                box-shadow: none !important;
                min-height: 0;
            }
            div.st-key-income_feed_scroll {
                flex: 0 0 auto;
                min-height: auto;
                height: auto;
                max-height: none;
                overflow: visible;
                padding-right: 0;
                padding-bottom: 0;
                margin-top: 0;
            }
            div.st-key-income_feed_scroll > div {
                min-height: 0;
                padding-top: 0;
            }
            div.st-key-income_feed_stack,
            div.st-key-income_feed_scroll {
                padding-top: 0;
            }
            div.st-key-income_feed_stack > div,
            div.st-key-income_feed_stack div[data-testid="stVerticalBlock"],
            div.st-key-income_feed_stack div[data-testid="stElementContainer"],
            div.st-key-income_feed_scroll div[data-testid="stVerticalBlock"],
            div.st-key-income_feed_scroll div[data-testid="stElementContainer"] {
                background: transparent !important;
                box-shadow: none !important;
            }
            div.st-key-home_hero_shell {
                border-radius: 24px;
                background:
                    radial-gradient(circle at 78% 28%, rgba(99, 223, 255, 0.18), transparent 20%),
                    radial-gradient(circle at 72% 78%, rgba(240, 191, 85, 0.18), transparent 18%),
                    radial-gradient(circle at bottom left, rgba(242, 203, 170, 0.12), transparent 22%),
                    linear-gradient(135deg, #241b14 0%, #4a2c1e 48%, #8c542e 100%);
                box-shadow: 0 16px 36px rgba(65, 32, 16, 0.12);
                margin-bottom: 0;
                padding: 1.2rem 1.2rem 1.15rem 1.2rem;
                color: white;
            }
            .home-welcome-shell {
                margin: 0.52rem 0 1.04rem 0.08rem;
            }
            .home-welcome-eyebrow {
                color: rgba(104, 77, 56, 0.72);
                font-size: 0.72rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                margin-bottom: 0.14rem;
            }
            .home-welcome-title {
                margin: 0;
                color: var(--text);
                font-size: 2.1rem;
                font-weight: 800;
                line-height: 1.02;
                letter-spacing: -0.03em;
            }
            .home-welcome-copy {
                margin: 0.28rem 0 0 0;
                color: var(--muted);
                font-size: 0.98rem;
                font-weight: 500;
                line-height: 1.35;
            }
            div.st-key-home_hero_shell > div,
            div.st-key-home_hero_shell div[data-testid="stVerticalBlock"],
            div.st-key-home_hero_shell div[data-testid="stElementContainer"] {
                background: transparent !important;
                box-shadow: none !important;
            }
            .home-finance-panel {
                background: linear-gradient(180deg, rgba(255, 250, 244, 0.14) 0%, rgba(255, 250, 244, 0.09) 100%);
                border: 1px solid rgba(255, 244, 232, 0.22);
                border-radius: 22px;
                padding: 0.88rem;
                box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
                backdrop-filter: blur(10px);
            }
            .home-finance-head {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 0.8rem;
                margin-bottom: 0.82rem;
            }
            .home-finance-eyebrow {
                color: rgba(255, 246, 236, 0.72);
                font-size: 0.72rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                margin-bottom: 0.18rem;
            }
            .home-finance-period {
                color: white;
                font-size: 1.02rem;
                font-weight: 700;
                line-height: 1.1;
            }
            .home-finance-kpi-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 0.64rem;
            }
            .home-finance-card {
                min-width: 0;
                border-radius: 18px;
                padding: 0.82rem 0.9rem;
                background: rgba(255, 252, 247, 0.92);
                border: 1px solid rgba(233, 215, 196, 0.72);
                box-shadow: 0 10px 22px rgba(34, 21, 12, 0.08);
            }
            .home-finance-card-balance {
                grid-column: 1 / -1;
                background: linear-gradient(180deg, rgba(255, 252, 247, 0.98) 0%, rgba(252, 246, 238, 0.96) 100%);
            }
            .home-finance-card-couple {
                grid-column: 1 / -1;
                background: linear-gradient(180deg, rgba(251, 245, 237, 0.98) 0%, rgba(247, 238, 228, 0.96) 100%);
            }
            .home-finance-card-label {
                color: var(--muted);
                font-size: 0.72rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                margin-bottom: 0.38rem;
            }
            .home-finance-card-value {
                color: var(--text);
                font-size: 1.16rem;
                font-weight: 800;
                line-height: 1.05;
                letter-spacing: -0.01em;
            }
            .home-finance-card-note {
                margin-top: 0.32rem;
                color: rgba(44, 33, 23, 0.64);
                font-size: 0.78rem;
                line-height: 1.25;
            }
            .home-finance-card-accent-expense {
                color: var(--accent-dark);
            }
            .home-finance-card-accent-income {
                color: var(--green);
            }
            .home-finance-card-accent-balance-positive {
                color: var(--green);
            }
            .home-finance-card-accent-balance-negative {
                color: var(--accent-dark);
            }
            .home-finance-card-accent-balance-neutral {
                color: var(--text);
            }
            .home-finance-card-accent-couple-positive {
                color: var(--green);
            }
            .home-finance-card-accent-couple-negative {
                color: var(--accent-dark);
            }
            .home-finance-card-accent-couple-neutral {
                color: var(--text);
            }
            div.st-key-home_finance_scope {
                width: 100%;
                max-width: 220px;
                margin-top: -0.18rem;
                margin-bottom: 0.36rem;
            }
            div.st-key-home_finance_scope div[data-testid="stHorizontalBlock"] {
                gap: 0.18rem;
            }
            div.st-key-home_finance_scope div[data-testid="stElementContainer"],
            div.st-key-home_finance_scope div[data-testid="stVerticalBlock"] {
                margin: 0 !important;
                padding: 0 !important;
            }
            div.st-key-home_finance_scope div.stButton > button,
            div.st-key-home_finance_scope button[kind="secondary"],
            div.st-key-home_finance_scope button[kind="primary"] {
                min-height: 28px !important;
                height: 28px !important;
                padding: 0 0.72rem !important;
                border-radius: 14px !important;
                border: 1px solid rgba(255, 245, 233, 0.18) !important;
                background: rgba(255, 248, 240, 0.08) !important;
                color: rgba(255, 248, 240, 0.82) !important;
                box-shadow: none !important;
                font-size: 0.76rem !important;
                font-weight: 600 !important;
                letter-spacing: 0.01em !important;
                transform: none !important;
            }
            div.st-key-home_finance_scope div.stButton > button[kind="primary"],
            div.st-key-home_finance_scope button[kind="primary"] {
                background: rgba(255, 251, 246, 0.96) !important;
                color: var(--accent-dark) !important;
                border-color: rgba(255, 244, 232, 0.26) !important;
            }
            div.st-key-home_finance_scope div.stButton > button p,
            div.st-key-home_finance_scope button[kind="secondary"] p,
            div.st-key-home_finance_scope button[kind="primary"] p {
                font-size: 0.76rem !important;
                font-weight: 600 !important;
                line-height: 1 !important;
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
            div[data-testid="stMetricDelta"] {
                color: var(--green);
            }
            .small-note {
                color: var(--muted);
                font-size: 0.92rem;
            }
            .topbar-text {
                color: var(--muted);
                font-size: 0.9rem;
                display: flex;
                align-items: center;
                min-height: 26px;
                line-height: 1;
                padding-top: 0;
            }
            .topbar-row {
                padding-top: 0.52rem;
                margin-bottom: 0.28rem;
            }
            div.st-key-topbar_actions {
                display: flex;
                justify-content: flex-end;
                align-items: center;
                min-height: 26px;
                padding-top: 0;
                position: relative;
                top: 6px;
            }
            div.st-key-topbar_actions > div,
            div.st-key-topbar_actions div[data-testid="stVerticalBlock"],
            div.st-key-topbar_actions div[data-testid="stElementContainer"] {
                background: transparent !important;
                box-shadow: none !important;
            }
            div.st-key-topbar_profile_icon div.stButton > button,
            div.st-key-topbar_home_icon div.stButton > button,
            div.st-key-topbar_filter_icon button,
            div.st-key-topbar_menu_icon button,
            div.st-key-topbar_logout_icon div.stButton > button,
            div.st-key-topbar_filter_icon button[kind="secondary"],
            div.st-key-topbar_menu_icon button[kind="secondary"] {
                min-width: 26px !important;
                width: 26px !important;
                min-height: 26px !important;
                height: 26px !important;
                border-radius: 0 !important;
                padding: 0 !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                background: transparent !important;
                color: var(--text) !important;
                border: none !important;
                box-shadow: none !important;
            }
            div.st-key-topbar_profile_icon div.stButton > button:hover,
            div.st-key-topbar_home_icon div.stButton > button:hover,
            div.st-key-topbar_filter_icon button:hover,
            div.st-key-topbar_menu_icon button:hover,
            div.st-key-topbar_logout_icon div.stButton > button:hover {
                background: transparent !important;
                color: var(--accent-dark) !important;
            }
            div.st-key-topbar_filter_icon [data-testid="stPopover"] > div::before,
            div.st-key-topbar_filter_icon [data-testid="stPopover"] > div::after,
            div.st-key-topbar_menu_icon [data-testid="stPopover"] > div::before,
            div.st-key-topbar_menu_icon [data-testid="stPopover"] > div::after {
                display: none !important;
            }
            div.st-key-topbar_filter_icon button svg:last-child,
            div.st-key-topbar_menu_icon button svg:last-child {
                display: none !important;
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
            .hero-title {
                margin: 0;
                font-size: 1.48rem;
                line-height: 1.05;
                text-align: left;
            }
            .hero-copy {
                margin: 0.3rem 0 0 0;
                max-width: 520px;
                opacity: 0.88;
                font-size: 0.88rem;
                line-height: 1.35;
                text-align: left;
            }
            .hero-meta {
                max-width: 540px;
                display: flex;
                flex-direction: column;
                align-items: flex-start;
            }
            .legend-row {
                display: flex;
                flex-wrap: wrap;
                gap: 0.42rem;
                margin-top: 0.58rem;
            }
            .legend-badge {
                display: inline-flex;
                align-items: center;
                padding: 0.28rem 0.52rem;
                border-radius: 999px;
                background: rgba(255, 255, 255, 0.13);
                font-size: 0.76rem;
                line-height: 1;
            }
            .calendar-shell {
                background: rgba(255, 252, 247, 0.86);
                border: 1px solid var(--border);
                border-radius: 28px;
                padding: 1rem;
                box-shadow: var(--shadow);
            }
            .calendar-toolbar {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 0.35rem;
                margin-bottom: 0.75rem;
            }
            .calendar-toolbar-label-wrap {
                height: 46px;
                display: flex;
                align-items: center;
                justify-content: center;
                transform: translateY(-6px);
            }
            .calendar-toolbar-label {
                min-width: 160px;
                height: 46px;
                display: flex;
                align-items: center;
                justify-content: center;
                text-align: center;
                color: var(--text);
                font-size: 0.96rem;
                font-weight: 600;
                line-height: 1;
                margin: 0;
                padding: 0;
            }
            .calendar-toolbar-label-home {
                font-size: 1.14rem;
                font-weight: 700;
            }
            div[class*="st-key-"][class*="_prev_month"],
            div[class*="st-key-"][class*="_next_month"] {
                display: flex;
                justify-content: center;
            }
            div[class*="st-key-"][class*="_prev_month"] div.stButton > button,
            div[class*="st-key-"][class*="_next_month"] div.stButton > button,
            div[class*="st-key-"][class*="_prev_month"] button[kind],
            div[class*="st-key-"][class*="_next_month"] button[kind] {
                min-height: 46px !important;
                height: 46px !important;
                width: 46px !important;
                min-width: 46px !important;
                max-width: 46px !important;
                padding: 0 !important;
                border-radius: 999px !important;
                background: rgba(255, 250, 244, 0.85) !important;
                color: var(--text) !important;
                border: 1px solid var(--border) !important;
                box-shadow: 0 10px 26px rgba(70, 43, 22, 0.06) !important;
                font-weight: 600 !important;
                flex: 0 0 46px !important;
            }
            div[class*="st-key-"][class*="_prev_month"] div.stButton > button:hover,
            div[class*="st-key-"][class*="_next_month"] div.stButton > button:hover,
            div[class*="st-key-"][class*="_prev_month"] button[kind]:hover,
            div[class*="st-key-"][class*="_next_month"] button[kind]:hover {
                transform: none !important;
                background: rgba(255, 252, 247, 0.96) !important;
                color: var(--text) !important;
                border-color: #d6bea6 !important;
                box-shadow: 0 10px 26px rgba(70, 43, 22, 0.06) !important;
            }
            div[class*="st-key-"][class*="_prev_month"] div.stButton > button p,
            div[class*="st-key-"][class*="_next_month"] div.stButton > button p,
            div[class*="st-key-"][class*="_prev_month"] button[kind] p,
            div[class*="st-key-"][class*="_next_month"] button[kind] p {
                font-size: 1rem !important;
                font-weight: 600 !important;
            }
            div[class*="st-key-"][class*="_prev_month"] div.stButton > button:hover p,
            div[class*="st-key-"][class*="_next_month"] div.stButton > button:hover p,
            div[class*="st-key-"][class*="_prev_month"] button[kind]:hover p,
            div[class*="st-key-"][class*="_next_month"] button[kind]:hover p {
                color: var(--text) !important;
            }
            .calendar-grid {
                display: grid;
                grid-template-columns: repeat(7, minmax(0, 1fr));
                gap: 0.65rem;
            }
            .calendar-weekday {
                padding: 0 0.3rem 0.25rem 0.3rem;
                color: var(--muted);
                font-size: 0.8rem;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.04em;
            }
            .calendar-day {
                min-height: 126px;
                border-radius: 22px;
                border: 1px solid rgba(216, 198, 175, 0.88);
                background: rgba(255, 255, 255, 0.72);
                padding: 0.7rem;
                display: flex;
                flex-direction: column;
                gap: 0.4rem;
            }
            .calendar-day.is-other-month {
                opacity: 0.42;
                background: rgba(250, 246, 239, 0.52);
            }
            .calendar-day.is-today {
                border-color: rgba(180, 93, 52, 0.58);
                box-shadow: 0 0 0 1px rgba(180, 93, 52, 0.18);
            }
            .calendar-day-top {
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .calendar-day-number {
                font-size: 0.96rem;
                font-weight: 700;
                color: var(--text);
            }
            .calendar-today-dot {
                width: 8px;
                height: 8px;
                border-radius: 999px;
                background: var(--accent);
            }
            .calendar-day-total {
                font-size: 0.8rem;
                color: var(--muted);
            }
            .calendar-event-list {
                display: flex;
                flex-direction: column;
                gap: 0.28rem;
            }
            .calendar-event {
                display: flex;
                align-items: center;
                gap: 0.38rem;
                min-width: 0;
                font-size: 0.76rem;
                color: var(--text);
            }
            .calendar-event-dot {
                width: 8px;
                height: 8px;
                border-radius: 999px;
                flex: 0 0 8px;
            }
            .calendar-event-dot.expense {
                background: var(--accent);
            }
            .calendar-event-dot.income {
                background: var(--green);
            }
            .calendar-event-text {
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            div.st-key-income_header_info {
                width: 100%;
                max-width: none;
                margin: 0.02rem 0 0 0;
                padding: 0.24rem 0.24rem 0.46rem 0.24rem;
                min-height: 4.72rem;
                display: flex;
                flex-direction: column;
                justify-content: flex-start;
                border-radius: 22px;
                background: rgba(255, 250, 244, 0.72);
                border: 1px solid rgba(196, 170, 145, 0.34);
                box-shadow: 0 10px 24px rgba(70, 43, 22, 0.05);
                overflow: hidden;
            }
            div.st-key-income_info_tabs_row div[data-testid="stHorizontalBlock"] {
                align-items: stretch;
                gap: 0.18rem;
            }
            div.st-key-income_info_tabs_row div[data-testid="column"] {
                min-width: 0;
            }
            div.st-key-income_info_tabs_row div[data-testid="column"] > div {
                width: 100%;
            }
            div.st-key-income_info_source_tab > button,
            div.st-key-income_info_source_tab div.stButton > button,
            div.st-key-income_info_latest_tab > button,
            div.st-key-income_info_latest_tab div.stButton > button {
                width: 100% !important;
                min-width: 0 !important;
                min-height: 34px !important;
                height: 34px !important;
                padding: 0.28rem 0.7rem !important;
                border-radius: 999px !important;
                border: none !important;
                box-shadow: none !important;
                background: transparent !important;
                color: rgba(47, 36, 25, 0.78) !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                white-space: nowrap !important;
                line-height: 1 !important;
                text-align: center !important;
            }
            div.st-key-income_info_source_tab > button p,
            div.st-key-income_info_source_tab div.stButton > button p,
            div.st-key-income_info_latest_tab > button p,
            div.st-key-income_info_latest_tab div.stButton > button p {
                margin: 0 !important;
                font-size: 0.8rem !important;
                font-weight: 500 !important;
                line-height: 1 !important;
                text-align: center !important;
                white-space: nowrap !important;
            }
            div.st-key-income_info_source_tab > button:hover,
            div.st-key-income_info_source_tab div.stButton > button:hover,
            div.st-key-income_info_latest_tab > button:hover,
            div.st-key-income_info_latest_tab div.stButton > button:hover {
                background: rgba(255, 252, 247, 0.58) !important;
                color: var(--text) !important;
                transform: none !important;
            }
            div.st-key-income_info_source_tab > button[kind="primary"],
            div.st-key-income_info_source_tab div.stButton > button[kind="primary"],
            div.st-key-income_info_latest_tab > button[kind="primary"],
            div.st-key-income_info_latest_tab div.stButton > button[kind="primary"] {
                background: linear-gradient(135deg, #cf8a5d 0%, #b56b42 100%) !important;
                color: white !important;
            }
            div.st-key-income_info_source_tab > button[kind="primary"] p,
            div.st-key-income_info_source_tab div.stButton > button[kind="primary"] p,
            div.st-key-income_info_latest_tab > button[kind="primary"] p,
            div.st-key-income_info_latest_tab div.stButton > button[kind="primary"] p {
                color: white !important;
            }
            div.st-key-income_info_value_row {
                margin-top: 0.18rem;
                min-height: 1.28rem;
            }
            .income-info-value-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                align-items: center;
                gap: 0.18rem;
                min-height: 1.28rem;
                width: 100%;
            }
            .income-info-value-cell {
                display: flex;
                align-items: center;
                justify-content: center;
                min-width: 0;
                min-height: 1.28rem;
            }
            .income-info-active-value {
                margin: 0;
                color: var(--text);
                font-size: 0.8rem;
                font-weight: 500;
                line-height: 1;
                text-align: center;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                padding: 0 0.24rem;
                width: 100%;
            }
            .income-tools-row {
                display: flex;
                align-items: center;
                gap: 0.38rem;
                margin: 0 0 0.38rem 0;
            }
            .income-edit-backdrop {
                position: fixed;
                inset: 0;
                background: rgba(47, 36, 25, 0.08);
                pointer-events: none;
                z-index: 18;
            }
            .income-edit-focus {
                position: relative;
                z-index: 31;
            }
            div.st-key-income_edit_mode_toggle > button,
            div.st-key-income_edit_mode_toggle div.stButton > button {
                min-width: 132px !important;
                width: auto !important;
                min-height: 40px !important;
                height: 40px !important;
                padding: 0 0.9rem !important;
                border-radius: 999px !important;
                background: transparent !important;
                color: var(--text) !important;
                border: none !important;
                box-shadow: none !important;
                font-size: 0.74rem !important;
                font-weight: 500 !important;
                line-height: 1 !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                white-space: nowrap !important;
            }
            div.st-key-income_edit_mode_toggle > button:hover,
            div.st-key-income_edit_mode_toggle div.stButton > button:hover {
                background: transparent !important;
                color: var(--accent-dark) !important;
                transform: none !important;
            }
            div.st-key-income_sort_toggle button,
            div.st-key-income_sort_toggle div.stButton > button {
                min-width: 40px !important;
                width: 40px !important;
                min-height: 40px !important;
                height: 40px !important;
                padding: 0 !important;
                border-radius: 999px !important;
                background: transparent !important;
                color: var(--text) !important;
                border: none !important;
                box-shadow: none !important;
                font-size: 0.92rem !important;
                line-height: 1 !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
            }
            div.st-key-income_sort_toggle button:hover,
            div.st-key-income_sort_toggle div.stButton > button:hover {
                background: transparent !important;
                color: var(--accent-dark) !important;
                transform: none !important;
            }
            div.st-key-income_sort_menu div[data-testid="stRadio"] > div {
                background: transparent !important;
                border: none !important;
                box-shadow: none !important;
                padding: 0 !important;
                display: flex !important;
                flex-direction: column !important;
                gap: 0.15rem !important;
            }
            div.st-key-income_sort_menu div[data-testid="stRadio"] label[data-baseweb="radio"] {
                min-width: auto !important;
                justify-content: flex-start !important;
                padding: 0.2rem 0 !important;
                background: transparent !important;
                border: none !important;
                border-radius: 0 !important;
                box-shadow: none !important;
            }
            div.st-key-income_sort_menu div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {
                background: transparent !important;
                box-shadow: none !important;
            }
            div.st-key-income_sort_menu div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) p,
            div.st-key-income_sort_menu div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) p * {
                color: var(--accent-dark) !important;
            }
            div.st-key-income_sort_menu div[data-testid="stRadio"] p {
                font-size: 0.84rem !important;
                font-weight: 500 !important;
                color: var(--text) !important;
            }
            .income-list {
                display: flex;
                flex-direction: column;
                gap: 0;
                margin-top: 0;
            }
            .income-card {
                border-bottom: 1px solid rgba(196, 170, 145, 0.45);
                padding: 0;
            }
            .income-row {
                display: grid;
                grid-template-columns: 110px 1.5fr 1.8fr 140px;
                align-items: center;
                column-gap: 1rem;
                height: 52px;
                width: 100%;
            }
            .income-cell {
                display: flex;
                align-items: center;
                height: 52px;
                margin: 0;
                line-height: 1;
            }
            .income-cell-source {
                color: var(--text);
                font-size: 1rem;
                font-weight: 700;
            }
            .income-cell-secondary {
                color: var(--muted);
                font-size: 0.96rem;
                font-weight: 500;
            }
            .income-cell-amount {
                color: var(--green);
                font-size: 1rem;
                font-weight: 700;
                justify-content: flex-end;
                white-space: nowrap;
            }
            div.st-key-hero_layout_shell > div,
            div.st-key-hero_layout_shell div[data-testid="stVerticalBlock"],
            div.st-key-hero_layout_shell div[data-testid="stElementContainer"] {
                background: transparent !important;
                box-shadow: none !important;
            }
            .hero-layout {
                width: 100%;
            }
            .hero-left-stack,
            .home-finance-column {
                width: 100%;
                min-width: 0;
            }
            .hero-left-stack {
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 0.46rem;
            }
            .hero-visual {
                width: 100%;
                min-width: 0;
                display: flex;
                justify-content: center;
                align-items: flex-start;
            }
            .hero-visual-frame {
                position: relative;
                width: 100%;
                max-width: 468px;
                aspect-ratio: 3 / 2;
                height: auto;
                display: flex;
                justify-content: center;
                align-items: center;
                overflow: hidden;
                border-radius: 28px;
                background: #eef0f4;
                box-shadow: 0 18px 36px rgba(18, 13, 9, 0.10);
            }
            .hero-visual-frame::before {
                content: none;
            }
            .hero-image {
                position: relative;
                z-index: 1;
                width: 100%;
                height: 100%;
                object-fit: cover;
                object-position: center center;
                border-radius: 28px;
                background: #eef0f4;
                mix-blend-mode: normal;
                filter: brightness(1.02) saturate(1.02);
            }
            .home-summary-mini {
                width: 100%;
                max-width: 468px;
                margin-left: auto;
                margin-right: auto;
                padding: 0.64rem 0.74rem 0.58rem 0.74rem;
                border-radius: 15px;
                background: linear-gradient(180deg, rgba(255, 248, 240, 0.07) 0%, rgba(255, 248, 240, 0.03) 100%);
                border: 1px solid rgba(255, 244, 232, 0.12);
                box-shadow: none;
            }
            .home-summary-mini-eyebrow {
                color: rgba(255, 246, 236, 0.72);
                font-size: 0.68rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                margin-bottom: 0.18rem;
            }
            .home-summary-mini-copy {
                color: rgba(255, 244, 232, 0.82);
                font-size: 0.76rem;
                line-height: 1.32;
                margin-bottom: 0.48rem;
            }
            div.st-key-home_summary_cta {
                width: 100%;
                max-width: 404px;
                margin-left: auto;
                margin-right: auto;
                margin-top: 0.1rem;
            }
            div.st-key-home_summary_cta div.stButton > button,
            div.st-key-home_summary_cta button[kind="secondary"] {
                width: 100% !important;
                min-height: 34px !important;
                height: 34px !important;
                border-radius: 12px !important;
                padding: 0 0.82rem !important;
                background: rgba(255, 248, 240, 0.96) !important;
                color: var(--accent-dark) !important;
                border: 1px solid rgba(255, 244, 232, 0.18) !important;
                box-shadow: 0 6px 14px rgba(34, 21, 12, 0.07) !important;
                font-size: 0.8rem !important;
                font-weight: 700 !important;
                transform: none !important;
            }
            div.st-key-home_summary_cta div.stButton > button:hover,
            div.st-key-home_summary_cta button[kind="secondary"]:hover {
                background: rgba(255, 251, 246, 0.98) !important;
                color: var(--accent-dark) !important;
            }
            div.st-key-home_summary_cta div.stButton > button p,
            div.st-key-home_summary_cta button[kind="secondary"] p {
                color: var(--accent-dark) !important;
                font-size: 0.8rem !important;
                font-weight: 700 !important;
                line-height: 1 !important;
            }
            .home-hero-copy-shell {
                padding: 1.02rem 0.35rem 0.15rem 0.35rem;
            }
            .couple-balance-status-pill {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-height: 34px;
                padding: 0.3rem 0.72rem;
                border-radius: 999px;
                font-size: 0.8rem;
                font-weight: 700;
                line-height: 1;
                text-transform: uppercase;
                letter-spacing: 0.03em;
                white-space: nowrap;
            }
            .couple-balance-status-open {
                color: var(--accent-dark);
                background: rgba(180, 93, 52, 0.12);
                border: 1px solid rgba(180, 93, 52, 0.18);
            }
            .couple-balance-status-settled {
                color: var(--green);
                background: rgba(79, 122, 92, 0.12);
                border: 1px solid rgba(79, 122, 92, 0.18);
            }
            .couple-balance-toggle-label {
                color: var(--muted);
                font-size: 0.86rem;
                font-weight: 600;
            }
            div[data-testid="stDialog"] div[role="dialog"] {
                max-width: 760px !important;
            }
            div[data-testid="stDialog"] div[role="dialog"] > div {
                border-radius: 24px !important;
            }
            div[data-testid="stDialog"] div[role="dialog"] [data-testid="stDialogHeader"] {
                display: none !important;
            }
            div[data-testid="stDialog"] div[role="dialog"] > div > div {
                padding-top: 0 !important;
            }
            div[data-testid="stDialog"] button[aria-label="Close"] {
                display: none !important;
            }
            div[data-testid="stDialog"] div[role="dialog"] div[data-testid="stVerticalBlock"] {
                gap: 0.68rem !important;
            }
            @media (max-width: 900px) {
                .hero-meta {
                    max-width: 100%;
                }
                .hero-visual,
                .home-finance-column,
                .hero-left-stack {
                    width: 100%;
                    min-width: 0;
                }
                .home-summary-mini,
                div.st-key-home_summary_cta {
                    max-width: 100%;
                }
                .home-finance-head {
                    flex-direction: column;
                    align-items: flex-start;
                }
                .home-finance-kpi-grid {
                    grid-template-columns: 1fr;
                }
                .home-finance-card-balance {
                    grid-column: auto;
                }
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
            div.stButton > button:hover,
            div.stDownloadButton > button:hover,
            div[data-testid="stFormSubmitButton"] button:hover {
                transform: translateY(-1px);
            }
            div.stButton > button[kind="tertiary"] {
                background: transparent !important;
                border: none !important;
                box-shadow: none !important;
                color: var(--text) !important;
                padding: 0 !important;
                min-height: auto !important;
                height: auto !important;
                border-radius: 0 !important;
                font-size: 0.92rem !important;
                font-weight: 500 !important;
            }
            div.stButton > button[kind="tertiary"]:hover {
                background: transparent !important;
                color: var(--accent-dark) !important;
                transform: none !important;
            }
            section[data-testid="stSidebar"] div.stButton > button[kind="tertiary"] {
                justify-content: flex-start !important;
                text-align: left !important;
                width: auto !important;
                min-height: auto !important;
                padding: 0.1rem 0 !important;
                font-size: 0.9rem !important;
            }
            div.stButton > button[kind="secondary"],
            div[data-testid="stFormSubmitButton"] button[kind="secondary"] {
                background: linear-gradient(180deg, rgba(255, 251, 246, 0.99) 0%, rgba(246, 238, 228, 0.98) 100%) !important;
                color: var(--text) !important;
                border: 1px solid var(--border) !important;
                box-shadow: 0 16px 30px rgba(70, 43, 22, 0.07) !important;
            }
            div.stButton > button[kind="secondary"] {
                min-height: 176px !important;
                white-space: pre-line !important;
                text-align: left !important;
                line-height: 1.28 !important;
                padding: 1.15rem 1.15rem !important;
                border-radius: 24px !important;
                letter-spacing: 0.01em;
                position: relative;
                background: rgba(255, 251, 246, 0.98) !important;
                box-shadow: none !important;
                border: 1px solid var(--border) !important;
            }
            div.stButton > button[kind="secondary"] p {
                font-size: 1.25rem !important;
                font-weight: 500 !important;
                line-height: 1.15 !important;
            }
            div.stButton > button[kind="secondary"]:hover {
                border-color: #cfad8d !important;
                box-shadow: none !important;
                background: rgba(255, 252, 249, 1) !important;
            }
            div[data-testid="stDataFrame"] {
                border-radius: 20px;
                overflow: hidden;
                border: 1px solid var(--border);
            }
            div[data-testid="stRadio"] > div {
                background: rgba(255, 250, 244, 0.85);
                border: 1px solid var(--border);
                border-radius: 999px;
                padding: 0.32rem;
                box-shadow: 0 10px 26px rgba(70, 43, 22, 0.06);
                display: inline-flex;
            }
            div[data-testid="stRadio"] label {
                margin-right: 0.35rem;
            }
            div[data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child {
                display: none !important;
            }
            div[data-testid="stRadio"] label[data-baseweb="radio"] {
                background: transparent;
                border-radius: 999px;
                padding: 0.5rem 0.95rem;
                min-width: 130px;
                justify-content: center;
                transition: all 0.18s ease;
            }
            div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {
                background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%);
                box-shadow: 0 8px 18px rgba(139, 67, 35, 0.18);
            }
            div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) p {
                color: white !important;
            }
            div[data-testid="stRadio"] p {
                color: var(--text);
                font-weight: 600;
                font-size: 0.95rem;
            }
            div.st-key-calendar_content_filter div[data-testid="stRadio"] > div {
                background: rgba(255, 252, 247, 0.58);
                border: none;
                box-shadow: none;
                padding: 0.22rem;
            }
            div.st-key-calendar_content_filter div[data-testid="stRadio"] label[data-baseweb="radio"] {
                min-width: 102px;
                padding: 0.34rem 0.72rem;
            }
            div.st-key-calendar_content_filter div[data-testid="stRadio"] p {
                font-size: 0.86rem;
                font-weight: 500;
            }
            div.st-key-calendar_content_filter div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {
                background: linear-gradient(135deg, #cf8a5d 0%, #b56b42 100%);
                box-shadow: none;
            }
            div.st-key-expense_category_filter div[data-testid="stRadio"] > div {
                background: transparent;
                border: none;
                box-shadow: none;
                padding: 0;
                border-radius: 0;
                display: inline-flex;
                flex-wrap: wrap;
                gap: 0.9rem;
                width: 100%;
                align-content: flex-start;
            }
            div.st-key-expense_category_filter div[data-testid="stRadio"] label[data-baseweb="radio"] {
                min-width: auto;
                margin-right: 0 !important;
                padding: 0.14rem 0 0.22rem 0;
                background: transparent !important;
                border: none !important;
                box-shadow: none !important;
                border-radius: 0 !important;
                transform: translateY(0);
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                position: relative;
            }
            div.st-key-expense_category_filter div[data-testid="stRadio"] p {
                font-size: 0.88rem;
                font-weight: 600;
                color: rgba(44, 33, 23, 0.72);
                white-space: nowrap;
            }
            div.st-key-expense_category_filter div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {
                background: transparent !important;
                box-shadow: none !important;
                transform: translateY(2px);
                border-bottom: none !important;
            }
            div.st-key-expense_category_filter div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked)::after {
                content: "";
                position: absolute;
                left: 50%;
                transform: translateX(-50%);
                bottom: -2px;
                width: calc(100% - 0.1rem);
                height: 2px;
                background: rgba(181, 107, 66, 0.88);
                border-radius: 999px;
            }
            div.st-key-expense_category_filter div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) p,
            div.st-key-expense_category_filter div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) p *,
            div.st-key-expense_category_filter div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) span {
                color: rgba(181, 107, 66, 0.96) !important;
                font-weight: 600;
            }
            div.st-key-expense_type_filter div[data-testid="stRadio"] > div {
                background: rgba(255, 252, 247, 0.52);
                border: none;
                box-shadow: none;
                padding: 0.18rem;
                border-radius: 999px;
                display: inline-flex;
                flex-wrap: wrap;
                gap: 0.18rem;
                width: fit-content;
                max-width: 100%;
            }
            div.st-key-expense_type_filter div[data-testid="stRadio"] label[data-baseweb="radio"] {
                margin-right: 0 !important;
            }
            div.st-key-expense_type_filter div[data-testid="stRadio"] label[data-baseweb="radio"] {
                min-width: 110px;
                padding: 0.3rem 0.7rem;
            }
            div.st-key-expense_type_filter div[data-testid="stRadio"] p {
                font-size: 0.84rem;
                font-weight: 500;
            }
            div.st-key-expense_type_filter div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {
                background: linear-gradient(135deg, #cf8a5d 0%, #b56b42 100%);
                box-shadow: none;
            }
            div.st-key-couple_balance_status_filter div[data-testid="stRadio"] > div {
                background: rgba(255, 252, 247, 0.52);
                border: none;
                box-shadow: none;
                padding: 0.18rem;
                border-radius: 999px;
                display: inline-flex;
                flex-wrap: wrap;
                gap: 0.18rem;
                width: fit-content;
                max-width: 100%;
            }
            div.st-key-couple_balance_status_filter div[data-testid="stRadio"] label[data-baseweb="radio"] {
                margin-right: 0 !important;
                min-width: 110px;
                padding: 0.3rem 0.7rem;
            }
            div.st-key-couple_balance_status_filter div[data-testid="stRadio"] p {
                font-size: 0.84rem;
                font-weight: 500;
            }
            div.st-key-couple_balance_status_filter div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {
                background: linear-gradient(135deg, #cf8a5d 0%, #b56b42 100%);
                box-shadow: none;
            }
            .expense-tools-divider {
                width: 100%;
                height: 1px;
                margin: 0;
                background: linear-gradient(
                    90deg,
                    rgba(207, 138, 93, 0) 0%,
                    rgba(207, 138, 93, 0.12) 18%,
                    rgba(207, 138, 93, 0.18) 50%,
                    rgba(207, 138, 93, 0.12) 82%,
                    rgba(207, 138, 93, 0) 100%
                );
            }
            div.st-key-expense_list_separator_row,
            div.st-key-income_list_separator_row {
                width: 100%;
                margin: 0 0 0.22rem 0;
                padding: 0;
                background: transparent !important;
            }
            div.st-key-expense_list_separator_row > div,
            div.st-key-expense_list_separator_row div[data-testid="stVerticalBlock"],
            div.st-key-expense_list_separator_row div[data-testid="stElementContainer"],
            div.st-key-income_list_separator_row > div,
            div.st-key-income_list_separator_row div[data-testid="stVerticalBlock"],
            div.st-key-income_list_separator_row div[data-testid="stElementContainer"] {
                background: transparent !important;
                box-shadow: none !important;
                padding: 0 !important;
                margin: 0 !important;
            }
            div.st-key-expense_tools_row {
                margin: 0;
            }
            div.st-key-expense_tools_row div[data-testid="stHorizontalBlock"] {
                justify-content: flex-start;
                align-items: center;
                gap: 0.2rem;
                flex-wrap: nowrap;
            }
            div.st-key-expense_tools_row button {
                line-height: 1 !important;
            }
            div.st-key-expense_search_reset_button > button,
            div.st-key-expense_search_reset_button div.stButton > button {
                min-width: 24px !important;
                width: 24px !important;
                min-height: 24px !important;
                height: 24px !important;
                padding: 0 !important;
                border-radius: 0 !important;
                background: transparent !important;
                color: rgba(46, 38, 31, 0.86) !important;
                border: none !important;
                box-shadow: none !important;
                font-size: 0.8rem !important;
                font-weight: 500 !important;
                line-height: 1 !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                opacity: 1 !important;
                flex-shrink: 0 !important;
                vertical-align: middle !important;
            }
            div.st-key-expense_search_reset_button > button span[data-testid="stIconMaterial"],
            div.st-key-expense_search_reset_button div.stButton > button span[data-testid="stIconMaterial"],
            div.st-key-expense_sort_toggle > button span[data-testid="stIconMaterial"],
            div.st-key-expense_sort_toggle div.stButton > button span[data-testid="stIconMaterial"],
            div.st-key-expense_search_toggle > button span[data-testid="stIconMaterial"],
            div.st-key-expense_search_toggle div.stButton > button span[data-testid="stIconMaterial"],
            div.st-key-expense_delete_toggle > button span[data-testid="stIconMaterial"],
            div.st-key-expense_delete_toggle div.stButton > button span[data-testid="stIconMaterial"] {
                width: 0.8rem !important;
                min-width: 0.8rem !important;
                height: 0.8rem !important;
                font-size: 0.8rem !important;
                line-height: 1 !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                vertical-align: middle !important;
            }
            div.st-key-expense_search_reset_button > button span[data-testid="stIconMaterial"] svg,
            div.st-key-expense_search_reset_button div.stButton > button span[data-testid="stIconMaterial"] svg,
            div.st-key-expense_sort_toggle > button span[data-testid="stIconMaterial"] svg,
            div.st-key-expense_sort_toggle div.stButton > button span[data-testid="stIconMaterial"] svg,
            div.st-key-expense_search_toggle > button span[data-testid="stIconMaterial"] svg,
            div.st-key-expense_search_toggle div.stButton > button span[data-testid="stIconMaterial"] svg,
            div.st-key-expense_delete_toggle > button span[data-testid="stIconMaterial"] svg,
            div.st-key-expense_delete_toggle div.stButton > button span[data-testid="stIconMaterial"] svg {
                width: 0.8rem !important;
                height: 0.8rem !important;
                display: block !important;
            }
            div.st-key-expense_search_reset_button > button:hover,
            div.st-key-expense_search_reset_button div.stButton > button:hover {
                background: transparent !important;
                color: var(--accent-dark) !important;
                transform: none !important;
            }
            div.st-key-expense_search_reset_button > button:disabled,
            div.st-key-expense_search_reset_button div.stButton > button:disabled {
                color: rgba(46, 38, 31, 0.28) !important;
                opacity: 1 !important;
                cursor: default !important;
                pointer-events: none !important;
            }
            .expense-edit-backdrop {
                position: fixed;
                inset: 0;
                background: rgba(47, 36, 25, 0.08);
                pointer-events: none;
                z-index: 18;
            }
            .expense-edit-focus {
                position: relative;
                z-index: 31;
            }
            div.st-key-expense_edit_mode_toggle > button,
            div.st-key-expense_edit_mode_toggle div.stButton > button {
                min-width: 6.15rem !important;
                width: auto !important;
                min-height: 24px !important;
                height: 24px !important;
                padding: 0 0.06rem !important;
                border-radius: 0 !important;
                background: transparent !important;
                color: rgba(46, 38, 31, 0.78) !important;
                border: none !important;
                box-shadow: none !important;
                font-size: 0.8rem !important;
                font-weight: 500 !important;
                line-height: 1 !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: flex-start !important;
                white-space: nowrap !important;
                text-transform: uppercase !important;
                letter-spacing: 0.025em !important;
                flex-shrink: 0 !important;
                vertical-align: middle !important;
            }
            div.st-key-expense_edit_mode_toggle > button p,
            div.st-key-expense_edit_mode_toggle div.stButton > button p,
            div.st-key-expense_edit_mode_toggle > button span,
            div.st-key-expense_edit_mode_toggle div.stButton > button span {
                font-size: 0.8rem !important;
                line-height: 1 !important;
                font-weight: 500 !important;
                letter-spacing: 0.025em !important;
                text-transform: uppercase !important;
                margin: 0 !important;
                display: inline-flex !important;
                align-items: center !important;
            }
            div.st-key-expense_edit_mode_toggle > button:hover,
            div.st-key-expense_edit_mode_toggle div.stButton > button:hover {
                background: transparent !important;
                color: var(--accent-dark) !important;
                transform: none !important;
            }
            div.st-key-expense_edit_mode_toggle > button[kind="primary"],
            div.st-key-expense_edit_mode_toggle div.stButton > button[kind="primary"] {
                color: var(--accent-dark) !important;
                text-decoration: underline;
                text-decoration-thickness: 1px;
                text-underline-offset: 0.16rem;
            }
            .income-tools-divider {
                width: 100%;
                height: 1px;
                margin: 0.24rem 0 0 0;
                background: linear-gradient(
                    90deg,
                    rgba(207, 138, 93, 0) 0%,
                    rgba(207, 138, 93, 0.12) 18%,
                    rgba(207, 138, 93, 0.18) 50%,
                    rgba(207, 138, 93, 0.12) 82%,
                    rgba(207, 138, 93, 0) 100%
                );
            }
            div.st-key-income_tools_row {
                margin: 0;
            }
            div.st-key-income_tools_row div[data-testid="stHorizontalBlock"] {
                justify-content: flex-start;
                align-items: center;
                gap: 0.2rem;
                flex-wrap: nowrap;
            }
            div.st-key-income_search_reset_button > button,
            div.st-key-income_search_reset_button div.stButton > button {
                min-width: 24px !important;
                width: 24px !important;
                min-height: 24px !important;
                height: 24px !important;
                padding: 0 !important;
                border-radius: 0 !important;
                background: transparent !important;
                color: rgba(46, 38, 31, 0.86) !important;
                border: none !important;
                box-shadow: none !important;
                font-size: 0.82rem !important;
                font-weight: 500 !important;
                line-height: 1 !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                opacity: 1 !important;
                flex-shrink: 0 !important;
            }
            div.st-key-income_search_reset_button > button:hover,
            div.st-key-income_search_reset_button div.stButton > button:hover {
                background: transparent !important;
                color: var(--accent-dark) !important;
                transform: none !important;
            }
            div.st-key-income_search_reset_button > button:disabled,
            div.st-key-income_search_reset_button div.stButton > button:disabled {
                color: rgba(46, 38, 31, 0.28) !important;
                opacity: 1 !important;
                cursor: default !important;
                pointer-events: none !important;
            }
            div.st-key-income_edit_mode_toggle > button,
            div.st-key-income_edit_mode_toggle div.stButton > button {
                min-width: 6.75rem !important;
                width: auto !important;
                min-height: 24px !important;
                height: 24px !important;
                padding: 0 0.06rem !important;
                border-radius: 0 !important;
                background: transparent !important;
                color: rgba(46, 38, 31, 0.78) !important;
                border: none !important;
                box-shadow: none !important;
                font-size: 0.81rem !important;
                font-weight: 500 !important;
                line-height: 1 !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: flex-start !important;
                white-space: nowrap !important;
                text-transform: uppercase !important;
                letter-spacing: 0.025em !important;
                flex-shrink: 0 !important;
            }
            div.st-key-income_edit_mode_toggle > button p,
            div.st-key-income_edit_mode_toggle div.stButton > button p,
            div.st-key-income_edit_mode_toggle > button span,
            div.st-key-income_edit_mode_toggle div.stButton > button span {
                font-size: 0.81rem !important;
                line-height: 1 !important;
                font-weight: 500 !important;
                letter-spacing: 0.025em !important;
                text-transform: uppercase !important;
                margin: 0 !important;
            }
            div.st-key-income_edit_mode_toggle > button:hover,
            div.st-key-income_edit_mode_toggle div.stButton > button:hover {
                background: transparent !important;
                color: var(--accent-dark) !important;
                transform: none !important;
            }
            div.st-key-income_edit_mode_toggle > button[kind="primary"],
            div.st-key-income_edit_mode_toggle div.stButton > button[kind="primary"] {
                color: var(--accent-dark) !important;
                text-decoration: underline;
                text-decoration-thickness: 1px;
                text-underline-offset: 0.16rem;
            }
            div.st-key-expense_sort_toggle button {
                min-width: auto !important;
                width: auto !important;
                min-height: auto !important;
                height: auto !important;
                padding: 0 !important;
                border-radius: 0 !important;
                background: transparent !important;
                color: var(--text) !important;
                border: none !important;
                box-shadow: none !important;
                font-size: inherit !important;
                line-height: 1 !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
            }
            div.st-key-expense_sort_toggle button:hover {
                background: transparent !important;
                color: var(--accent-dark) !important;
                transform: none !important;
            }
            div.st-key-expense_sort_toggle > button,
            div.st-key-expense_sort_toggle div.stButton > button,
            div.st-key-income_sort_toggle > button,
            div.st-key-income_sort_toggle div.stButton > button {
                min-width: 24px !important;
                width: 24px !important;
                min-height: 24px !important;
                height: 24px !important;
                padding: 0 !important;
                border-radius: 0 !important;
                background: transparent !important;
                color: var(--text) !important;
                border: none !important;
                box-shadow: none !important;
                font-size: 0.8rem !important;
                line-height: 1 !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                flex-shrink: 0 !important;
                vertical-align: middle !important;
            }
            div.st-key-expense_sort_toggle > button:hover,
            div.st-key-expense_sort_toggle div.stButton > button:hover,
            div.st-key-income_sort_toggle > button:hover,
            div.st-key-income_sort_toggle div.stButton > button:hover {
                background: transparent !important;
                color: var(--accent-dark) !important;
                transform: none !important;
            }
            div.st-key-expense_delete_toggle > button,
            div.st-key-expense_delete_toggle div.stButton > button {
                min-width: 24px !important;
                width: 24px !important;
                min-height: 24px !important;
                height: 24px !important;
                padding: 0 !important;
                border-radius: 0 !important;
                background: transparent !important;
                color: var(--text) !important;
                border: none !important;
                box-shadow: none !important;
                font-size: 0.8rem !important;
                line-height: 1 !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                flex-shrink: 0 !important;
                vertical-align: middle !important;
            }
            div.st-key-expense_delete_toggle > button:hover,
            div.st-key-expense_delete_toggle div.stButton > button:hover {
                background: transparent !important;
                color: var(--accent-dark) !important;
                transform: none !important;
            }
            div.st-key-expense_delete_toggle > button[kind="primary"],
            div.st-key-expense_delete_toggle div.stButton > button[kind="primary"] {
                color: var(--accent-dark) !important;
            }
            div.st-key-expense_sort_toggle button::after,
            div.st-key-expense_sort_toggle div.stButton > button::after,
            div.st-key-expense_search_toggle button::after,
            div.st-key-expense_search_toggle div.stButton > button::after,
            div.st-key-expense_delete_toggle button::after,
            div.st-key-expense_delete_toggle div.stButton > button::after,
            div.st-key-income_sort_toggle button::after,
            div.st-key-income_sort_toggle div.stButton > button::after,
            div.st-key-income_search_toggle button::after,
            div.st-key-income_search_toggle div.stButton > button::after {
                content: none !important;
                display: none !important;
            }
            div.st-key-expense_sort_toggle button > span:last-child,
            div.st-key-expense_sort_toggle div.stButton > button > span:last-child,
            div.st-key-expense_search_toggle button > span:last-child,
            div.st-key-expense_search_toggle div.stButton > button > span:last-child,
            div.st-key-expense_search_reset_button > button > span:last-child,
            div.st-key-expense_search_reset_button div.stButton > button > span:last-child,
            div.st-key-expense_delete_toggle button > span:last-child,
            div.st-key-expense_delete_toggle div.stButton > button > span:last-child,
            div.st-key-income_sort_toggle button > span:last-child,
            div.st-key-income_sort_toggle div.stButton > button > span:last-child,
            div.st-key-income_search_toggle button > span:last-child,
            div.st-key-income_search_toggle div.stButton > button > span:last-child {
                display: none !important;
            }
            div.st-key-expense_search_toggle button,
            div.st-key-expense_search_toggle div.stButton > button,
            div.st-key-expense_delete_toggle button,
            div.st-key-expense_delete_toggle div.stButton > button,
            div.st-key-income_search_toggle button,
            div.st-key-income_search_toggle div.stButton > button {
                min-width: 24px !important;
                width: 24px !important;
                min-height: 24px !important;
                height: 24px !important;
                padding: 0 !important;
                border-radius: 0 !important;
                background: transparent !important;
                color: var(--text) !important;
                border: none !important;
                box-shadow: none !important;
                font-size: 0.8rem !important;
                line-height: 1 !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                flex-shrink: 0 !important;
                vertical-align: middle !important;
            }
            div.st-key-expense_search_toggle button p,
            div.st-key-expense_delete_toggle button p,
            div.st-key-income_search_toggle button p {
                font-size: 0.8rem !important;
                line-height: 1 !important;
                font-weight: 500 !important;
                margin: 0 !important;
            }
            div.st-key-expense_search_toggle button:hover,
            div.st-key-expense_search_toggle div.stButton > button:hover,
            div.st-key-expense_delete_toggle button:hover,
            div.st-key-expense_delete_toggle div.stButton > button:hover,
            div.st-key-income_search_toggle button:hover,
            div.st-key-income_search_toggle div.stButton > button:hover {
                background: transparent !important;
                color: var(--accent-dark) !important;
                transform: none !important;
            }
            div.st-key-expense_delete_actions_row {
                margin: 0.12rem 0 0.04rem 0;
            }
            div.st-key-expense_delete_actions_row div[data-testid="stHorizontalBlock"] {
                align-items: center;
                gap: 0.4rem;
            }
            .expense-delete-count {
                color: var(--muted);
                font-size: 0.74rem;
                font-style: italic;
                font-weight: 400;
                line-height: 1;
                white-space: nowrap;
            }
            div.st-key-expense_delete_toggle_all > button,
            div.st-key-expense_delete_toggle_all div.stButton > button,
            div.st-key-expense_delete_action > button,
            div.st-key-expense_delete_action div.stButton > button,
            div.st-key-expense_delete_confirm > button,
            div.st-key-expense_delete_confirm div.stButton > button,
            div.st-key-expense_delete_cancel > button,
            div.st-key-expense_delete_cancel div.stButton > button {
                min-height: 24px !important;
                height: 24px !important;
                padding: 0 !important;
                border-radius: 0 !important;
                border: none !important;
                background: transparent !important;
                box-shadow: none !important;
                color: var(--muted) !important;
                font-size: 0.76rem !important;
                font-weight: 500 !important;
                line-height: 1 !important;
                text-decoration: none !important;
            }
            div.st-key-expense_delete_toggle_all > button p,
            div.st-key-expense_delete_toggle_all div.stButton > button p,
            div.st-key-expense_delete_toggle_all > button span,
            div.st-key-expense_delete_toggle_all div.stButton > button span,
            div.st-key-expense_delete_action > button p,
            div.st-key-expense_delete_action div.stButton > button p,
            div.st-key-expense_delete_action > button span,
            div.st-key-expense_delete_action div.stButton > button span,
            div.st-key-expense_delete_confirm > button p,
            div.st-key-expense_delete_confirm div.stButton > button p,
            div.st-key-expense_delete_confirm > button span,
            div.st-key-expense_delete_confirm div.stButton > button span,
            div.st-key-expense_delete_cancel > button p,
            div.st-key-expense_delete_cancel div.stButton > button p,
            div.st-key-expense_delete_cancel > button span,
            div.st-key-expense_delete_cancel div.stButton > button span {
                font-size: 0.76rem !important;
                line-height: 1 !important;
                font-weight: 500 !important;
                margin: 0 !important;
            }
            div.st-key-expense_toolbar_shell {
                margin: 0;
            }
            div.st-key-expense_toolbar_shell div[data-testid="stHorizontalBlock"] {
                justify-content: flex-start;
                align-items: center;
                gap: 0.22rem;
                flex-wrap: nowrap;
            }
            div.st-key-expense_toolbar_back_item,
            div.st-key-expense_toolbar_edit_item,
            div.st-key-expense_toolbar_sort_item,
            div.st-key-expense_toolbar_search_item,
            div.st-key-expense_toolbar_delete_item {
                min-height: 24px;
                display: flex;
                align-items: center;
            }
            div.st-key-expense_toolbar_back_item button,
            div.st-key-expense_toolbar_back_item div.stButton > button,
            div.st-key-expense_toolbar_sort_item button,
            div.st-key-expense_toolbar_sort_item div.stButton > button,
            div.st-key-expense_toolbar_search_item button,
            div.st-key-expense_toolbar_search_item div.stButton > button,
            div.st-key-expense_toolbar_delete_item button,
            div.st-key-expense_toolbar_delete_item div.stButton > button {
                min-width: 24px !important;
                width: 24px !important;
                min-height: 24px !important;
                height: 24px !important;
                padding: 0 !important;
                margin: 0 !important;
                border: none !important;
                border-radius: 0 !important;
                background: transparent !important;
                box-shadow: none !important;
                color: rgba(46, 38, 31, 0.84) !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                line-height: 1 !important;
                vertical-align: middle !important;
                flex-shrink: 0 !important;
            }
            div.st-key-expense_toolbar_back_item button:hover,
            div.st-key-expense_toolbar_back_item div.stButton > button:hover,
            div.st-key-expense_toolbar_sort_item button:hover,
            div.st-key-expense_toolbar_sort_item div.stButton > button:hover,
            div.st-key-expense_toolbar_search_item button:hover,
            div.st-key-expense_toolbar_search_item div.stButton > button:hover,
            div.st-key-expense_toolbar_delete_item button:hover,
            div.st-key-expense_toolbar_delete_item div.stButton > button:hover {
                background: transparent !important;
                color: var(--accent-dark) !important;
                transform: none !important;
            }
            div.st-key-expense_toolbar_back_item button:disabled,
            div.st-key-expense_toolbar_back_item div.stButton > button:disabled {
                color: rgba(46, 38, 31, 0.28) !important;
                opacity: 1 !important;
                cursor: default !important;
                pointer-events: none !important;
            }
            div.st-key-expense_toolbar_delete_item button[kind="primary"],
            div.st-key-expense_toolbar_delete_item div.stButton > button[kind="primary"] {
                color: var(--accent-dark) !important;
            }
            div.st-key-expense_toolbar_back_item button::after,
            div.st-key-expense_toolbar_back_item div.stButton > button::after,
            div.st-key-expense_toolbar_sort_item button::after,
            div.st-key-expense_toolbar_sort_item div.stButton > button::after,
            div.st-key-expense_toolbar_search_item button::after,
            div.st-key-expense_toolbar_search_item div.stButton > button::after,
            div.st-key-expense_toolbar_delete_item button::after,
            div.st-key-expense_toolbar_delete_item div.stButton > button::after {
                content: none !important;
                display: none !important;
            }
            div.st-key-expense_toolbar_back_item button > span:last-child,
            div.st-key-expense_toolbar_back_item div.stButton > button > span:last-child,
            div.st-key-expense_toolbar_sort_item button > span:last-child,
            div.st-key-expense_toolbar_sort_item div.stButton > button > span:last-child,
            div.st-key-expense_toolbar_search_item button > span:last-child,
            div.st-key-expense_toolbar_search_item div.stButton > button > span:last-child,
            div.st-key-expense_toolbar_delete_item button > span:last-child,
            div.st-key-expense_toolbar_delete_item div.stButton > button > span:last-child {
                display: none !important;
            }
            div.st-key-expense_toolbar_back_item button span[data-testid="stIconMaterial"],
            div.st-key-expense_toolbar_back_item div.stButton > button span[data-testid="stIconMaterial"],
            div.st-key-expense_toolbar_sort_item button span[data-testid="stIconMaterial"],
            div.st-key-expense_toolbar_sort_item div.stButton > button span[data-testid="stIconMaterial"],
            div.st-key-expense_toolbar_search_item button span[data-testid="stIconMaterial"],
            div.st-key-expense_toolbar_search_item div.stButton > button span[data-testid="stIconMaterial"],
            div.st-key-expense_toolbar_delete_item button span[data-testid="stIconMaterial"],
            div.st-key-expense_toolbar_delete_item div.stButton > button span[data-testid="stIconMaterial"] {
                width: 0.8rem !important;
                min-width: 0.8rem !important;
                height: 0.8rem !important;
                font-size: 0.8rem !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                line-height: 1 !important;
                vertical-align: middle !important;
            }
            div.st-key-expense_toolbar_back_item button span[data-testid="stIconMaterial"] svg,
            div.st-key-expense_toolbar_back_item div.stButton > button span[data-testid="stIconMaterial"] svg,
            div.st-key-expense_toolbar_sort_item button span[data-testid="stIconMaterial"] svg,
            div.st-key-expense_toolbar_sort_item div.stButton > button span[data-testid="stIconMaterial"] svg,
            div.st-key-expense_toolbar_search_item button span[data-testid="stIconMaterial"] svg,
            div.st-key-expense_toolbar_search_item div.stButton > button span[data-testid="stIconMaterial"] svg,
            div.st-key-expense_toolbar_delete_item button span[data-testid="stIconMaterial"] svg,
            div.st-key-expense_toolbar_delete_item div.stButton > button span[data-testid="stIconMaterial"] svg {
                width: 0.8rem !important;
                height: 0.8rem !important;
                display: block !important;
            }
            div.st-key-expense_toolbar_edit_item button,
            div.st-key-expense_toolbar_edit_item div.stButton > button {
                min-height: 24px !important;
                height: 24px !important;
                width: auto !important;
                min-width: 6.15rem !important;
                padding: 0 0.06rem !important;
                margin: 0 !important;
                border: none !important;
                border-radius: 0 !important;
                background: transparent !important;
                box-shadow: none !important;
                color: rgba(46, 38, 31, 0.78) !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: flex-start !important;
                line-height: 1 !important;
                vertical-align: middle !important;
                white-space: nowrap !important;
                font-size: 0.8rem !important;
                font-weight: 500 !important;
                text-transform: uppercase !important;
                letter-spacing: 0.025em !important;
            }
            div.st-key-expense_toolbar_edit_item button p,
            div.st-key-expense_toolbar_edit_item div.stButton > button p,
            div.st-key-expense_toolbar_edit_item button span,
            div.st-key-expense_toolbar_edit_item div.stButton > button span {
                margin: 0 !important;
                font-size: 0.8rem !important;
                font-weight: 500 !important;
                line-height: 1 !important;
                text-transform: uppercase !important;
                letter-spacing: 0.025em !important;
                display: inline-flex !important;
                align-items: center !important;
            }
            div.st-key-expense_toolbar_edit_item button:hover,
            div.st-key-expense_toolbar_edit_item div.stButton > button:hover {
                background: transparent !important;
                color: var(--accent-dark) !important;
                transform: none !important;
            }
            div.st-key-expense_toolbar_edit_item button[kind="primary"],
            div.st-key-expense_toolbar_edit_item div.stButton > button[kind="primary"] {
                color: var(--accent-dark) !important;
                text-decoration: underline;
                text-decoration-thickness: 1px;
                text-underline-offset: 0.16rem;
            }
            div.st-key-income_toolbar_shell {
                margin: 0;
            }
            div.st-key-income_toolbar_shell div[data-testid="stHorizontalBlock"] {
                justify-content: flex-start;
                align-items: center;
                gap: 0.22rem;
                flex-wrap: nowrap;
            }
            div.st-key-income_toolbar_back_item,
            div.st-key-income_toolbar_edit_item,
            div.st-key-income_toolbar_sort_item,
            div.st-key-income_toolbar_search_item {
                min-height: 24px;
                display: flex;
                align-items: center;
            }
            div.st-key-income_toolbar_back_item button,
            div.st-key-income_toolbar_back_item div.stButton > button,
            div.st-key-income_toolbar_sort_item button,
            div.st-key-income_toolbar_sort_item div.stButton > button,
            div.st-key-income_toolbar_search_item button,
            div.st-key-income_toolbar_search_item div.stButton > button {
                min-width: 24px !important;
                width: 24px !important;
                min-height: 24px !important;
                height: 24px !important;
                padding: 0 !important;
                margin: 0 !important;
                border: none !important;
                border-radius: 0 !important;
                background: transparent !important;
                box-shadow: none !important;
                color: rgba(46, 38, 31, 0.84) !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                line-height: 1 !important;
                vertical-align: middle !important;
                flex-shrink: 0 !important;
            }
            div.st-key-income_toolbar_back_item button:hover,
            div.st-key-income_toolbar_back_item div.stButton > button:hover,
            div.st-key-income_toolbar_sort_item button:hover,
            div.st-key-income_toolbar_sort_item div.stButton > button:hover,
            div.st-key-income_toolbar_search_item button:hover,
            div.st-key-income_toolbar_search_item div.stButton > button:hover {
                background: transparent !important;
                color: var(--accent-dark) !important;
                transform: none !important;
            }
            div.st-key-income_toolbar_back_item button:disabled,
            div.st-key-income_toolbar_back_item div.stButton > button:disabled {
                color: rgba(46, 38, 31, 0.28) !important;
                opacity: 1 !important;
                cursor: default !important;
                pointer-events: none !important;
            }
            div.st-key-income_toolbar_back_item button::after,
            div.st-key-income_toolbar_back_item div.stButton > button::after,
            div.st-key-income_toolbar_sort_item button::after,
            div.st-key-income_toolbar_sort_item div.stButton > button::after,
            div.st-key-income_toolbar_search_item button::after,
            div.st-key-income_toolbar_search_item div.stButton > button::after {
                content: none !important;
                display: none !important;
            }
            div.st-key-income_toolbar_back_item button > span:last-child,
            div.st-key-income_toolbar_back_item div.stButton > button > span:last-child,
            div.st-key-income_toolbar_sort_item button > span:last-child,
            div.st-key-income_toolbar_sort_item div.stButton > button > span:last-child,
            div.st-key-income_toolbar_search_item button > span:last-child,
            div.st-key-income_toolbar_search_item div.stButton > button > span:last-child {
                display: none !important;
            }
            div.st-key-income_toolbar_back_item button span[data-testid="stIconMaterial"],
            div.st-key-income_toolbar_back_item div.stButton > button span[data-testid="stIconMaterial"],
            div.st-key-income_toolbar_sort_item button span[data-testid="stIconMaterial"],
            div.st-key-income_toolbar_sort_item div.stButton > button span[data-testid="stIconMaterial"],
            div.st-key-income_toolbar_search_item button span[data-testid="stIconMaterial"],
            div.st-key-income_toolbar_search_item div.stButton > button span[data-testid="stIconMaterial"] {
                width: 0.8rem !important;
                min-width: 0.8rem !important;
                height: 0.8rem !important;
                font-size: 0.8rem !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                line-height: 1 !important;
                vertical-align: middle !important;
            }
            div.st-key-income_toolbar_back_item button span[data-testid="stIconMaterial"] svg,
            div.st-key-income_toolbar_back_item div.stButton > button span[data-testid="stIconMaterial"] svg,
            div.st-key-income_toolbar_sort_item button span[data-testid="stIconMaterial"] svg,
            div.st-key-income_toolbar_sort_item div.stButton > button span[data-testid="stIconMaterial"] svg,
            div.st-key-income_toolbar_search_item button span[data-testid="stIconMaterial"] svg,
            div.st-key-income_toolbar_search_item div.stButton > button span[data-testid="stIconMaterial"] svg {
                width: 0.8rem !important;
                height: 0.8rem !important;
                display: block !important;
            }
            div.st-key-income_toolbar_edit_item button,
            div.st-key-income_toolbar_edit_item div.stButton > button {
                min-height: 24px !important;
                height: 24px !important;
                width: auto !important;
                min-width: 6.75rem !important;
                padding: 0 0.06rem !important;
                margin: 0 !important;
                border: none !important;
                border-radius: 0 !important;
                background: transparent !important;
                box-shadow: none !important;
                color: rgba(46, 38, 31, 0.78) !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: flex-start !important;
                line-height: 1 !important;
                vertical-align: middle !important;
                white-space: nowrap !important;
                font-size: 0.8rem !important;
                font-weight: 500 !important;
                text-transform: uppercase !important;
                letter-spacing: 0.025em !important;
            }
            div.st-key-income_toolbar_edit_item button p,
            div.st-key-income_toolbar_edit_item div.stButton > button p,
            div.st-key-income_toolbar_edit_item button span,
            div.st-key-income_toolbar_edit_item div.stButton > button span {
                margin: 0 !important;
                font-size: 0.8rem !important;
                font-weight: 500 !important;
                line-height: 1 !important;
                text-transform: uppercase !important;
                letter-spacing: 0.025em !important;
                display: inline-flex !important;
                align-items: center !important;
            }
            div.st-key-income_toolbar_edit_item button:hover,
            div.st-key-income_toolbar_edit_item div.stButton > button:hover {
                background: transparent !important;
                color: var(--accent-dark) !important;
                transform: none !important;
            }
            div.st-key-income_toolbar_edit_item button[kind="primary"],
            div.st-key-income_toolbar_edit_item div.stButton > button[kind="primary"] {
                color: var(--accent-dark) !important;
                text-decoration: underline;
                text-decoration-thickness: 1px;
                text-underline-offset: 0.16rem;
            }
            div.st-key-expense_delete_toggle_all > button:hover,
            div.st-key-expense_delete_toggle_all div.stButton > button:hover,
            div.st-key-expense_delete_action > button:hover,
            div.st-key-expense_delete_action div.stButton > button:hover,
            div.st-key-expense_delete_confirm > button:hover,
            div.st-key-expense_delete_confirm div.stButton > button:hover,
            div.st-key-expense_delete_cancel > button:hover,
            div.st-key-expense_delete_cancel div.stButton > button:hover {
                color: var(--accent-dark) !important;
                background: transparent !important;
                transform: none !important;
            }
            div.st-key-expense_delete_confirm > button,
            div.st-key-expense_delete_confirm div.stButton > button,
            div.st-key-expense_delete_action > button:not(:disabled),
            div.st-key-expense_delete_action div.stButton > button:not(:disabled) {
                color: var(--accent-dark) !important;
            }
            div.st-key-expense_delete_action > button:disabled,
            div.st-key-expense_delete_action div.stButton > button:disabled {
                color: rgba(46, 38, 31, 0.3) !important;
                opacity: 1 !important;
                pointer-events: none !important;
            }
            div[class*="st-key-expense_delete_row_toggle_"] div[data-testid="stCheckbox"],
            div[class*="st-key-expense_delete_row_toggle_"] label {
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                min-height: 52px !important;
                height: 52px !important;
                padding: 0 !important;
                margin: 0 !important;
            }
            div[class*="st-key-expense_delete_row_toggle_"] p {
                display: none !important;
            }
            div[class*="st-key-expense_delete_row_toggle_"] input {
                accent-color: var(--accent) !important;
            }
            div.st-key-expense_sort_menu,
            div.st-key-expense_search_menu,
            div.st-key-income_sort_menu,
            div.st-key-income_search_menu {
                margin-top: 0.18rem;
                padding: 0 !important;
                background: transparent !important;
                border: none !important;
                border-radius: 0 !important;
                box-shadow: none !important;
            }
            div.st-key-expense_search_menu input,
            div.st-key-income_search_menu input {
                font-size: 0.76rem !important;
                background: transparent !important;
                border: none !important;
                box-shadow: none !important;
                padding: 0 !important;
                line-height: 1 !important;
            }
            div.st-key-expense_search_menu div[data-baseweb="input"],
            div.st-key-expense_search_menu div[data-baseweb="input"] > div,
            div.st-key-expense_search_menu div[data-baseweb="base-input"],
            div.st-key-income_search_menu div[data-baseweb="input"],
            div.st-key-income_search_menu div[data-baseweb="input"] > div,
            div.st-key-income_search_menu div[data-baseweb="base-input"] {
                background: transparent !important;
                border: none !important;
                box-shadow: none !important;
                border-radius: 0 !important;
                padding: 0 !important;
                min-height: auto !important;
                line-height: 1 !important;
            }
            div.st-key-expense_sort_menu div[data-testid="stRadio"] > div {
                background: transparent !important;
                border: none !important;
                box-shadow: none !important;
                padding: 0 !important;
                display: flex !important;
                flex-direction: column !important;
                gap: 0.15rem !important;
            }
            div.st-key-expense_sort_menu div[data-testid="stRadio"] label[data-baseweb="radio"] {
                min-width: auto !important;
                justify-content: flex-start !important;
                padding: 0.2rem 0 !important;
                background: transparent !important;
                border: none !important;
                border-radius: 0 !important;
                box-shadow: none !important;
            }
            div.st-key-expense_sort_menu div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {
                background: transparent !important;
                box-shadow: none !important;
            }
            div.st-key-expense_sort_menu div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) p,
            div.st-key-expense_sort_menu div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) p * {
                color: var(--accent-dark) !important;
            }
            div.st-key-expense_sort_menu div[data-testid="stRadio"] p {
                font-size: 0.84rem !important;
                font-weight: 500 !important;
                color: var(--text) !important;
            }
            div.st-key-income_sort_menu div[data-testid="stRadio"] > div {
                background: transparent !important;
                border: none !important;
                box-shadow: none !important;
                padding: 0 !important;
                display: flex !important;
                flex-direction: column !important;
                gap: 0.15rem !important;
            }
            div.st-key-income_sort_menu div[data-testid="stRadio"] label[data-baseweb="radio"] {
                min-width: auto !important;
                justify-content: flex-start !important;
                padding: 0.2rem 0 !important;
                background: transparent !important;
                border: none !important;
                border-radius: 0 !important;
                box-shadow: none !important;
            }
            div.st-key-income_sort_menu div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {
                background: transparent !important;
                box-shadow: none !important;
            }
            div.st-key-income_sort_menu div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) p,
            div.st-key-income_sort_menu div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) p * {
                color: var(--accent-dark) !important;
            }
            div.st-key-income_sort_menu div[data-testid="stRadio"] p {
                font-size: 0.84rem !important;
                font-weight: 500 !important;
                color: var(--text) !important;
            }
            div[class*="st-key-expense_name_pick_"] > button,
            div[class*="st-key-expense_name_pick_"] div.stButton > button {
                background: transparent !important;
                border: none !important;
                box-shadow: none !important;
                color: var(--text) !important;
                padding: 0 !important;
                min-height: 52px !important;
                height: 52px !important;
                border-radius: 0 !important;
                font-size: 1rem !important;
                font-weight: 700 !important;
                text-align: left !important;
                justify-content: flex-start !important;
            }
            div[class*="st-key-expense_name_pick_"] > button:hover,
            div[class*="st-key-expense_name_pick_"] div.stButton > button:hover {
                background: transparent !important;
                color: var(--accent-dark) !important;
                transform: none !important;
            }
            div[class*="st-key-edit_expense_row_"] > button,
            div[class*="st-key-edit_expense_row_"] div.stButton > button {
                min-width: 28px !important;
                width: 28px !important;
                min-height: 28px !important;
                height: 28px !important;
                padding: 0 !important;
                border-radius: 999px !important;
                box-shadow: none !important;
                font-size: 0.74rem !important;
                line-height: 1 !important;
                white-space: nowrap !important;
                background: transparent !important;
                color: var(--muted) !important;
                border: 1px solid rgba(196, 170, 145, 0.72) !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                position: relative !important;
                top: 0 !important;
                margin: 0 !important;
                vertical-align: middle !important;
            }
            div[class*="st-key-edit_expense_row_"] > button:hover,
            div[class*="st-key-edit_expense_row_"] div.stButton > button:hover {
                background: rgba(255, 251, 246, 0.88) !important;
                color: var(--text) !important;
                border-color: #cfad8d !important;
                transform: none !important;
            }
            div[class*="st-key-edit_expense_row_"] {
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                min-height: 32px !important;
                margin: 0 !important;
                padding: 0 !important;
            }
            div[class*="st-key-edit_expense_row_"] div[data-testid="stButton"] {
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                width: 100% !important;
                margin: 0 !important;
                padding: 0 !important;
                min-height: 28px !important;
            }
            div[class*="st-key-expense_action_wrap_"] {
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                min-height: 28px !important;
                height: 28px !important;
                margin: 0 !important;
                padding: 0 !important;
            }
            div[class*="st-key-expense_action_wrap_"] > div,
            div[class*="st-key-expense_action_wrap_"] div[data-testid="stVerticalBlock"],
            div[class*="st-key-expense_action_wrap_"] div[data-testid="stElementContainer"] {
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                min-height: 28px !important;
                height: 28px !important;
                margin: 0 !important;
                padding: 0 !important;
            }
            div.st-key-top_new_expense > button,
            div.st-key-top_new_expense div.stButton > button,
            div.st-key-top_new_expense button[kind="primary"] {
                min-height: 46px !important;
                height: 46px !important;
                padding: 0.5rem 1.05rem !important;
                border-radius: 999px !important;
                background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%) !important;
                color: white !important;
                border: 1px solid transparent !important;
                box-shadow: 0 8px 18px rgba(139, 67, 35, 0.18) !important;
                font-weight: 600 !important;
                line-height: 1 !important;
                white-space: nowrap !important;
            }
            div.st-key-top_new_expense > button:hover,
            div.st-key-top_new_expense div.stButton > button:hover,
            div.st-key-top_new_expense button[kind="primary"]:hover {
                transform: none !important;
                background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%) !important;
                border-color: transparent !important;
                box-shadow: 0 8px 18px rgba(139, 67, 35, 0.18) !important;
            }
            div.st-key-top_new_expense > button p,
            div.st-key-top_new_expense div.stButton > button p,
            div.st-key-top_new_expense button[kind="primary"] p {
                font-size: 0.95rem !important;
                font-weight: 600 !important;
                color: white !important;
            }
            div.st-key-save_new_expense > button,
            div.st-key-save_new_expense div.stButton > button {
                min-height: 36px !important;
                height: 36px !important;
                padding: 0.34rem 0.9rem !important;
                border-radius: 999px !important;
                font-size: 0.88rem !important;
                font-weight: 600 !important;
                box-shadow: 0 6px 14px rgba(139, 67, 35, 0.12) !important;
                background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%) !important;
                color: white !important;
                border: 1px solid transparent !important;
                line-height: 1 !important;
                white-space: nowrap !important;
            }
            div.st-key-save_new_expense > button:hover,
            div.st-key-save_new_expense div.stButton > button:hover {
                transform: none !important;
                background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%) !important;
                border-color: transparent !important;
                box-shadow: 0 6px 14px rgba(139, 67, 35, 0.12) !important;
            }
            div.st-key-save_new_expense > button p,
            div.st-key-save_new_expense div.stButton > button p {
                font-size: 0.88rem !important;
                font-weight: 600 !important;
                color: white !important;
            }
            .new-expense-amount-shell {
                margin: 0.1rem 0 0.65rem 0;
                text-align: center;
            }
            div.st-key-edit_expense_amount_raw label,
            div.st-key-new_expense_amount_raw label,
            div.st-key-new_expense_amount label,
            div.st-key-new_expense_name label,
            div.st-key-new_expense_category label,
            div.st-key-new_expense_paid_by label,
            div.st-key-new_expense_type label {
                font-size: 0.76rem !important;
                color: var(--muted) !important;
                margin-bottom: 0.18rem !important;
            }
            div.st-key-edit_expense_amount_raw input,
            div.st-key-new_expense_amount_raw input {
                text-align: left !important;
                font-size: 2rem !important;
                font-weight: 700 !important;
                line-height: 1 !important;
                background: transparent !important;
                border: none !important;
                box-shadow: none !important;
                padding: 0 !important;
            }
            div.st-key-edit_expense_amount_raw [data-baseweb="base-input"],
            div.st-key-edit_expense_amount_raw [data-baseweb="input"],
            div.st-key-new_expense_amount_raw [data-baseweb="base-input"],
            div.st-key-new_expense_amount_raw [data-baseweb="input"] {
                background: transparent !important;
                border: none !important;
                box-shadow: none !important;
                justify-content: center !important;
                align-items: center !important;
                outline: none !important;
                min-height: 2.3rem !important;
            }
            div.st-key-edit_expense_amount_raw [data-baseweb="base-input"] > div,
            div.st-key-edit_expense_amount_raw [data-baseweb="input"] > div,
            div.st-key-new_expense_amount_raw [data-baseweb="base-input"] > div,
            div.st-key-new_expense_amount_raw [data-baseweb="input"] > div {
                background: transparent !important;
                border: none !important;
                box-shadow: none !important;
                outline: none !important;
                align-items: center !important;
            }
            div.st-key-edit_expense_amount_raw [data-baseweb="input"] button,
            div.st-key-edit_expense_amount_raw [data-baseweb="base-input"] button,
            div.st-key-new_expense_amount_raw [data-baseweb="input"] button,
            div.st-key-new_expense_amount_raw [data-baseweb="base-input"] button {
                display: none !important;
            }
            div.st-key-edit_expense_amount_raw input::placeholder,
            div.st-key-new_expense_amount_raw input::placeholder {
                color: rgba(44, 33, 23, 0.38) !important;
            }
            div.st-key-edit_expense_amount_row div[data-testid="stHorizontalBlock"],
            div.st-key-new_expense_amount_row div[data-testid="stHorizontalBlock"] {
                align-items: center !important;
                justify-content: center !important;
                gap: 0.82rem !important;
            }
            div.st-key-edit_expense_amount_row,
            div.st-key-new_expense_amount_row {
                max-width: 300px;
                margin: 0 auto 0.18rem auto;
            }
            div.st-key-edit_expense_amount_currency p,
            div.st-key-new_expense_amount_currency p {
                margin: 0 !important;
            }
            .new-expense-amount-currency {
                font-size: 2rem;
                font-weight: 700;
                color: var(--text);
                line-height: 1;
                display: flex;
                align-items: center;
                justify-content: flex-end;
                min-height: 2.3rem;
                transform: translateY(0);
            }
            div.st-key-new_expense_amount_stepper {
                margin: 0.08rem 0 1rem 0;
            }
            div.st-key-new_expense_amount_stepper > div,
            div.st-key-new_expense_amount_stepper div[data-testid="stHorizontalBlock"] {
                justify-content: center !important;
                align-items: center !important;
                gap: 0.12rem !important;
            }
            div.st-key-new_expense_amount_stepper button,
            div.st-key-new_expense_amount_stepper div.stButton > button {
                min-width: 18px !important;
                width: 18px !important;
                min-height: 18px !important;
                height: 18px !important;
                padding: 0 !important;
                border-radius: 0 !important;
                background: transparent !important;
                color: var(--text) !important;
                border: none !important;
                box-shadow: none !important;
                font-size: 0.72rem !important;
                font-weight: 500 !important;
                line-height: 1 !important;
            }
            div.st-key-new_expense_amount_stepper button:hover,
            div.st-key-new_expense_amount_stepper div.stButton > button:hover {
                background: transparent !important;
                color: var(--accent-dark) !important;
                transform: none !important;
            }
            div.st-key-new_expense_name input,
            div.st-key-new_expense_category div[data-baseweb="select"] input,
            div.st-key-new_expense_paid_by div[data-baseweb="select"] input,
            div.st-key-new_expense_type div[data-baseweb="select"] input {
                font-size: 0.98rem !important;
            }
            div.st-key-close_new_expense_modal_icon > button,
            div.st-key-close_new_income_modal_icon > button,
            div.st-key-close_new_expense_modal_icon div.stButton > button,
            div.st-key-close_new_income_modal_icon div.stButton > button {
                min-width: 20px !important;
                width: 20px !important;
                min-height: 20px !important;
                height: 20px !important;
                padding: 0 !important;
                border-radius: 999px !important;
                background: transparent !important;
                color: var(--muted) !important;
                border: none !important;
                box-shadow: none !important;
                font-size: 0.72rem !important;
                line-height: 1 !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
            }
            div.st-key-close_new_expense_modal_icon > button:hover,
            div.st-key-close_new_income_modal_icon > button:hover,
            div.st-key-close_new_expense_modal_icon div.stButton > button:hover,
            div.st-key-close_new_income_modal_icon div.stButton > button:hover {
                background: transparent !important;
                color: var(--accent-dark) !important;
                transform: none !important;
            }
            div.st-key-dashboard_total_month div.stButton > button,
            div.st-key-dashboard_my_personal div.stButton > button,
            div.st-key-dashboard_shared_total div.stButton > button,
            div.st-key-dashboard_net_month div.stButton > button,
            div.st-key-dashboard_balance div.stButton > button,
            div.st-key-dashboard_total_month button[kind="secondary"],
            div.st-key-dashboard_my_personal button[kind="secondary"],
            div.st-key-dashboard_shared_total button[kind="secondary"],
            div.st-key-dashboard_net_month button[kind="secondary"],
            div.st-key-dashboard_balance button[kind="secondary"] {
                min-height: 82px !important;
                height: 82px !important;
                padding-top: 0.48rem !important;
                padding-bottom: 0.48rem !important;
                padding-left: 0.55rem !important;
                padding-right: 0.55rem !important;
                border-radius: 18px !important;
                text-align: center !important;
                justify-content: center !important;
                align-items: center !important;
                white-space: pre-line !important;
            }
            div.st-key-dashboard_total_month div.stButton > button p,
            div.st-key-dashboard_my_personal div.stButton > button p,
            div.st-key-dashboard_shared_total div.stButton > button p,
            div.st-key-dashboard_net_month div.stButton > button p,
            div.st-key-dashboard_balance div.stButton > button p,
            div.st-key-dashboard_total_month button[kind="secondary"] p,
            div.st-key-dashboard_my_personal button[kind="secondary"] p,
            div.st-key-dashboard_shared_total button[kind="secondary"] p,
            div.st-key-dashboard_net_month button[kind="secondary"] p,
            div.st-key-dashboard_balance button[kind="secondary"] p {
                font-size: 0.88rem !important;
                line-height: 1.02 !important;
                text-align: center !important;
            }
            div.st-key-dashboard_total_month div.stButton > button:hover,
            div.st-key-dashboard_my_personal div.stButton > button:hover,
            div.st-key-dashboard_shared_total div.stButton > button:hover,
            div.st-key-dashboard_net_month div.stButton > button:hover,
            div.st-key-dashboard_balance div.stButton > button:hover,
            div.st-key-dashboard_total_month button[kind="secondary"]:hover,
            div.st-key-dashboard_my_personal button[kind="secondary"]:hover,
            div.st-key-dashboard_shared_total button[kind="secondary"]:hover,
            div.st-key-dashboard_net_month button[kind="secondary"]:hover,
            div.st-key-dashboard_balance button[kind="secondary"]:hover {
                background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%) !important;
                border-color: transparent !important;
                box-shadow: 0 8px 18px rgba(139, 67, 35, 0.18) !important;
                transform: none !important;
            }
            div.st-key-dashboard_total_month div.stButton > button:hover p,
            div.st-key-dashboard_my_personal div.stButton > button:hover p,
            div.st-key-dashboard_shared_total div.stButton > button:hover p,
            div.st-key-dashboard_net_month div.stButton > button:hover p,
            div.st-key-dashboard_balance div.stButton > button:hover p,
            div.st-key-dashboard_total_month button[kind="secondary"]:hover p,
            div.st-key-dashboard_my_personal button[kind="secondary"]:hover p,
            div.st-key-dashboard_shared_total button[kind="secondary"]:hover p,
            div.st-key-dashboard_net_month button[kind="secondary"]:hover p,
            div.st-key-dashboard_balance button[kind="secondary"]:hover p {
                color: white !important;
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
                background:
                    linear-gradient(180deg, rgba(255, 253, 249, 0.98) 0%, rgba(248, 241, 233, 0.98) 100%);
                border: 1px solid var(--border);
                border-radius: 22px;
                padding: 1rem 1.05rem;
                margin-bottom: 0.85rem;
                box-shadow: 0 14px 28px rgba(70, 43, 22, 0.06);
            }
            .expense-detail-title {
                font-size: 1.02rem;
                font-weight: 800;
                color: var(--text);
                margin-bottom: 0.3rem;
            }
            .expense-detail-meta {
                color: var(--muted);
                font-size: 0.93rem;
                line-height: 1.6;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_back_circle_button(key: str) -> bool:
    st.markdown(
        """
        <style>
            div.stButton > button[kind="secondary"]:has(p:only-child) {
                width: 34px !important;
                min-width: 34px !important;
                height: 34px !important;
                min-height: 34px !important;
                border-radius: 999px !important;
                padding: 0 !important;
                background: rgba(255, 251, 246, 0.98) !important;
                color: #2f2419 !important;
                border: 1px solid #e4d7c5 !important;
                box-shadow: none !important;
                font-size: 0.95rem !important;
                line-height: 1 !important;
            }
            div.stButton > button[kind="secondary"]:has(p:only-child):hover {
                background: rgba(255, 252, 249, 1) !important;
                border-color: #cfad8d !important;
            }
            div.stButton > button[kind="secondary"]:has(p:only-child) p {
                font-size: 0.95rem !important;
                font-weight: 600 !important;
                line-height: 1 !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    return st.button("←", key=key, type="secondary", use_container_width=False)


def main() -> None:
    initialize_database()
    if not require_authentication():
        return
    inject_styles()

    all_expenses = get_expenses()
    current_user = st.session_state.current_user or {}
    current_username = current_user.get("username", "")
    all_expenses = get_visible_expenses(all_expenses, current_username)
    all_incomes = get_incomes()
    all_incomes = get_visible_incomes(all_incomes, current_username)

    render_topbar(all_expenses)
    if st.session_state.get("current_view") == "new_expense":
        st.session_state.current_view = "home"
        st.session_state.show_new_expense_modal = True
    if st.session_state.get("current_view") == "new_income":
        st.session_state.current_view = "home"
        st.session_state.show_new_income_modal = True
    if st.session_state.get("current_view") == "edit_expense":
        st.session_state.current_view = "home"
        st.session_state.show_edit_expense_modal = True
    filtered_expenses, selected_month = apply_expense_filter_state(all_expenses)
    filtered_incomes = apply_income_filters(all_incomes, selected_month)
    current_section = st.session_state.get("current_section", "Home")
    if st.session_state.get("current_view") == "dashboard_detail":
        render_dashboard_detail_page(all_expenses, all_incomes, selected_month)
        return
    if st.session_state.get("current_view") == "category_detail":
        render_category_detail_page(filtered_expenses)
        return
    if st.session_state.get("current_view") == "profile":
        render_profile_page()
        return
    if st.session_state.get("current_view") != "home":
        render_operation_detail_page(filtered_expenses, filtered_incomes)
        return

    if st.session_state.get("pending_section_navigation_sync", False):
        st.session_state.section_navigation_value = st.session_state.get("current_section", "Home")
        st.session_state.pending_section_navigation_sync = False

    with st.container(key="section_navigation_shell"):
        current_section = render_section_navigation()
    if st.session_state.get("show_new_expense_modal", False):
        render_new_expense_dialog()
    if st.session_state.get("show_new_income_modal", False):
        render_new_income_dialog()
    if st.session_state.get("show_edit_income_modal", False):
        render_edit_income_dialog(filtered_incomes)
    if st.session_state.get("show_edit_expense_modal", False):
        render_edit_expense_dialog(filtered_expenses)
    if current_section == "Home":
        render_home_welcome()
        render_hero(all_expenses, all_incomes, selected_month)
        render_month_navigation_bar(selected_month, "home_month")
        render_dashboard(all_expenses, all_incomes, selected_month)
    render_main_content(current_section, filtered_expenses, filtered_incomes, all_expenses, all_incomes, selected_month)


def initialize_session_state() -> None:
    if "selected_expense_id" not in st.session_state:
        st.session_state.selected_expense_id = None
    if "selected_category" not in st.session_state:
        st.session_state.selected_category = None
    if "show_new_expense_modal" not in st.session_state:
        st.session_state.show_new_expense_modal = False
    if "show_new_income_modal" not in st.session_state:
        st.session_state.show_new_income_modal = False
    if "show_edit_income_modal" not in st.session_state:
        st.session_state.show_edit_income_modal = False
    if "show_edit_expense_modal" not in st.session_state:
        st.session_state.show_edit_expense_modal = False
    if "show_expense_sort_menu" not in st.session_state:
        st.session_state.show_expense_sort_menu = False
    if "show_expense_search_menu" not in st.session_state:
        st.session_state.show_expense_search_menu = False
    if "expense_search_confirmed" not in st.session_state:
        st.session_state.expense_search_confirmed = False
    if "expense_delete_mode" not in st.session_state:
        st.session_state.expense_delete_mode = False
    if "expense_delete_selected_ids" not in st.session_state:
        st.session_state.expense_delete_selected_ids = []
    if "expense_delete_confirm_pending" not in st.session_state:
        st.session_state.expense_delete_confirm_pending = False
    if "show_income_sort_menu" not in st.session_state:
        st.session_state.show_income_sort_menu = False
    if "show_income_search_menu" not in st.session_state:
        st.session_state.show_income_search_menu = False
    if "income_search_confirmed" not in st.session_state:
        st.session_state.income_search_confirmed = False
    if "income_info_focus" not in st.session_state:
        st.session_state.income_info_focus = "source"
    if "is_authenticated" not in st.session_state:
        st.session_state.is_authenticated = False
    if "current_user" not in st.session_state:
        st.session_state.current_user = None
    if "current_section" not in st.session_state:
        st.session_state.current_section = "Home"
    if "section_navigation_value" not in st.session_state:
        st.session_state.section_navigation_value = st.session_state.current_section
    if "show_filters" not in st.session_state:
        st.session_state.show_filters = True
    if "pending_section_navigation_sync" not in st.session_state:
        st.session_state.pending_section_navigation_sync = False
    if "pending_sidebar_filter_overrides" not in st.session_state:
        st.session_state.pending_sidebar_filter_overrides = {}
    if "current_view" not in st.session_state:
        st.session_state.current_view = "home"
    if "page" not in st.session_state:
        st.session_state.page = "home"
    if "expense_filter" not in st.session_state:
        st.session_state.expense_filter = None
    if "expense_type_filter" not in st.session_state:
        st.session_state.expense_type_filter = "Tutte"
    if "expense_category_filter" not in st.session_state:
        st.session_state.expense_category_filter = "Tutte"
    if "couple_balance_status_filter" not in st.session_state:
        st.session_state.couple_balance_status_filter = "Da regolare"


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
                    <span class="legend-badge">Utente demo: io / password vuota</span>
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


def render_topbar(dataframe: pd.DataFrame) -> None:
    user = st.session_state.current_user or {}
    filter_state = resolve_expense_filter_state(dataframe)
    st.markdown('<div class="topbar-row">', unsafe_allow_html=True)
    left, actions_col = st.columns([1, 0.24], vertical_alignment="center")
    with left:
        st.markdown(
            f'<div class="topbar-text">Connesso come: {user.get("full_name", "Utente")} ({user.get("username", "-")})</div>',
            unsafe_allow_html=True,
        )
    with actions_col:
        with st.container(key="topbar_actions"):
            profile_col, home_col, filter_col, menu_col, logout_col = st.columns(5, gap="medium", vertical_alignment="center")
            with profile_col:
                with st.container(key="topbar_profile_icon"):
                    if st.button("", key="topbar_profile_button", icon=":material/person:", use_container_width=False, type="secondary"):
                        st.session_state.current_view = "profile"
                        st.rerun()
            with home_col:
                with st.container(key="topbar_home_icon"):
                    if st.button("", key="topbar_home_button", icon=":material/home:", use_container_width=False, type="secondary"):
                        st.session_state.current_view = "home"
                        st.session_state.current_section = "Home"
                        st.session_state.pending_section_navigation_sync = True
                        clear_page_navigation_intent()
                        st.rerun()
            with filter_col:
                with st.container(key="topbar_filter_icon"):
                    with st.popover("", use_container_width=False, icon=":material/tune:"):
                        st.caption("Filtri")
                        year_options = filter_state["year_options"]
                        selected_year = filter_state["selected_year"]
                        selected_month = filter_state["selected_month"]
                        available_months = filter_state["available_months"]
                        if year_options:
                            selected_year = st.selectbox(
                                "Anno",
                                year_options,
                                index=year_options.index(selected_year) if selected_year in year_options else 0,
                                key="topbar_filter_year",
                            )
                        month_map = {
                            MONTH_NAMES.get(month.split("-")[1], month): month
                            for month in available_months
                            if month.startswith(selected_year)
                        }
                        month_labels = list(month_map.keys())
                        default_month_label = None
                        if selected_month != "Tutti" and selected_month.startswith(selected_year):
                            default_month_label = MONTH_NAMES.get(selected_month.split("-")[1], selected_month)
                        default_index = month_labels.index(default_month_label) if default_month_label in month_labels else 0
                        selected_month_label = st.selectbox(
                            "Mese",
                            month_labels,
                            index=default_index if month_labels else 0,
                            key="topbar_filter_month_label",
                        ) if month_labels else None
                        selected_category = st.selectbox(
                            "Categoria",
                            filter_state["category_options"],
                            index=filter_state["category_options"].index(filter_state["selected_category"]) if filter_state["selected_category"] in filter_state["category_options"] else 0,
                            key="topbar_filter_category",
                        )
                        selected_payer = st.selectbox(
                            "Persona",
                            filter_state["payer_options"],
                            index=filter_state["payer_options"].index(filter_state["selected_payer"]) if filter_state["selected_payer"] in filter_state["payer_options"] else 0,
                            key="topbar_filter_payer",
                        )
                        selected_type = st.selectbox(
                            "Tipo spesa",
                            filter_state["type_options"],
                            index=filter_state["type_options"].index(filter_state["selected_type"]) if filter_state["selected_type"] in filter_state["type_options"] else 0,
                            key="topbar_filter_type",
                        )
                        month_value = month_map.get(selected_month_label, "Tutti") if selected_month_label else "Tutti"
                        st.session_state.filters = {
                            "month_label": month_value,
                            "year_label": selected_year,
                            "category": selected_category,
                            "payer": selected_payer,
                            "expense_type": selected_type,
                        }
            with menu_col:
                with st.container(key="topbar_menu_icon"):
                    with st.popover("", use_container_width=False, icon=":material/more_horiz:"):
                        if st.button("Ricarica pagina", key="topbar_refresh_page", use_container_width=True, type="tertiary"):
                            st.rerun()
                        if st.button("Reset filtri", key="topbar_reset_filters", use_container_width=True, type="tertiary"):
                            st.session_state.filters = {
                                "month_label": "Tutti",
                                "year_label": date.today().strftime("%Y"),
                                "category": "Tutte",
                                "payer": "Tutti",
                                "expense_type": "Tutte",
                            }
                            st.rerun()
            with logout_col:
                with st.container(key="topbar_logout_icon"):
                    if st.button("", key="logout_small", icon=":material/logout:", use_container_width=False, type="secondary"):
                        st.session_state.is_authenticated = False
                        st.session_state.current_user = None
                        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def resolve_expense_filter_state(dataframe: pd.DataFrame) -> dict:
    month_options = get_month_options(dataframe)
    category_options = ["Tutte"] + get_categories()
    payer_values = sorted(dataframe["paid_by"].dropna().unique().tolist()) if not dataframe.empty else []
    payer_options = ["Tutti"] + payer_values
    type_options = ["Tutte"] + EXPENSE_TYPE_OPTIONS
    available_months = [month for month in month_options if month != "Tutti"]
    year_options = sorted({month.split("-")[0] for month in available_months}, reverse=True)
    previous_filters = st.session_state.get(
        "filters",
        {"month_label": "Tutti", "category": "Tutte", "payer": "Tutti", "expense_type": "Tutte"},
    )
    pending_overrides = dict(st.session_state.get("pending_sidebar_filter_overrides", {}))
    if pending_overrides:
        previous_filters = {**previous_filters, **pending_overrides}
        st.session_state.pending_sidebar_filter_overrides = {}

    selected_month = previous_filters.get("month_label", "Tutti")
    selected_category = previous_filters.get("category", "Tutte")
    selected_payer = previous_filters.get("payer", "Tutti")
    selected_type = previous_filters.get("expense_type", "Tutte")
    selected_year = selected_month.split("-")[0] if selected_month != "Tutti" else (year_options[0] if year_options else date.today().strftime("%Y"))
    if year_options and selected_year not in year_options:
        selected_year = year_options[0]

    return {
        "category_options": category_options,
        "payer_options": payer_options,
        "type_options": type_options,
        "available_months": available_months,
        "year_options": year_options,
        "selected_month": selected_month,
        "selected_category": selected_category,
        "selected_payer": selected_payer,
        "selected_type": selected_type,
        "selected_year": selected_year,
    }


def apply_expense_filter_state(dataframe: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    filter_state = resolve_expense_filter_state(dataframe)
    selected_month = filter_state["selected_month"]
    selected_category = filter_state["selected_category"]
    selected_payer = filter_state["selected_payer"]
    selected_type = filter_state["selected_type"]
    year_options = filter_state["year_options"]

    filtered = apply_filters(
        dataframe=dataframe,
        month_label=selected_month,
        category=selected_category,
        payer=selected_payer,
        expense_type=selected_type,
    )
    st.session_state.filters = {
        "month_label": selected_month,
        "year_label": selected_month.split("-")[0] if selected_month != "Tutti" else (year_options[0] if year_options else date.today().strftime("%Y")),
        "category": selected_category,
        "payer": selected_payer,
        "expense_type": selected_type,
    }
    return filtered, selected_month


def render_home_toolbar(dataframe: pd.DataFrame) -> None:
    filter_state = resolve_expense_filter_state(dataframe)
    st.markdown('<div class="home-toolbar-shell">', unsafe_allow_html=True)
    with st.container(key="home_toolbar_actions"):
        profile_col, home_col, filter_col = st.columns([0.06, 0.06, 0.06], gap="small", vertical_alignment="center")
        with profile_col:
            if st.button("", key="home_profile_icon", icon=":material/person:", use_container_width=False, type="secondary"):
                st.session_state.current_view = "profile"
                st.rerun()
        with home_col:
            if st.button("", key="home_go_home_icon", icon=":material/home:", use_container_width=False, type="secondary"):
                st.session_state.current_view = "home"
                st.session_state.current_section = "Home"
                st.session_state.pending_section_navigation_sync = True
                clear_page_navigation_intent()
                st.rerun()
        with filter_col:
            with st.container(key="home_filter_popover"):
                with st.popover("", use_container_width=False, icon=":material/tune:"):
                    year_options = filter_state["year_options"]
                    selected_year = filter_state["selected_year"]
                    selected_month = filter_state["selected_month"]
                    available_months = filter_state["available_months"]
                    if year_options:
                        selected_year = st.selectbox(
                            "Anno",
                            year_options,
                            index=year_options.index(selected_year) if selected_year in year_options else 0,
                            key="home_filter_year",
                        )
                    month_map = {
                        MONTH_NAMES.get(month.split("-")[1], month): month
                        for month in available_months
                        if month.startswith(selected_year)
                    }
                    month_labels = list(month_map.keys())
                    default_month_label = None
                    if selected_month != "Tutti" and selected_month.startswith(selected_year):
                        default_month_label = MONTH_NAMES.get(selected_month.split("-")[1], selected_month)
                    default_index = month_labels.index(default_month_label) if default_month_label in month_labels else 0
                    selected_month_label = st.selectbox(
                        "Mese",
                        month_labels,
                        index=default_index if month_labels else 0,
                        key="home_filter_month_label",
                    ) if month_labels else None
                    selected_category = st.selectbox(
                        "Categoria",
                        filter_state["category_options"],
                        index=filter_state["category_options"].index(filter_state["selected_category"]) if filter_state["selected_category"] in filter_state["category_options"] else 0,
                        key="home_filter_category",
                    )
                    selected_payer = st.selectbox(
                        "Persona",
                        filter_state["payer_options"],
                        index=filter_state["payer_options"].index(filter_state["selected_payer"]) if filter_state["selected_payer"] in filter_state["payer_options"] else 0,
                        key="home_filter_payer",
                    )
                    selected_type = st.selectbox(
                        "Tipo spesa",
                        filter_state["type_options"],
                        index=filter_state["type_options"].index(filter_state["selected_type"]) if filter_state["selected_type"] in filter_state["type_options"] else 0,
                        key="home_filter_type",
                    )
                    month_value = month_map.get(selected_month_label, "Tutti") if selected_month_label else "Tutti"
                    st.session_state.filters = {
                        "month_label": month_value,
                        "year_label": selected_year,
                        "category": selected_category,
                        "payer": selected_payer,
                        "expense_type": selected_type,
                    }
                    filtered_preview = apply_filters(
                        dataframe=dataframe,
                        month_label=month_value,
                        category=selected_category,
                        payer=selected_payer,
                        expense_type=selected_type,
                    )
                    st.markdown(
                        f"<div class='home-filter-count'>Spese mostrate: <strong>{len(filtered_preview)}</strong></div>",
                        unsafe_allow_html=True,
                    )
    st.markdown("</div>", unsafe_allow_html=True)


def render_home_scope_toggle() -> str:
    current_scope = st.session_state.get("home_counter_scope", "Mensile")
    with st.container(key="home_finance_scope"):
        monthly_col, yearly_col = st.columns(2, gap="small")
        with monthly_col:
            if st.button(
                "Mensile",
                key="home_scope_monthly",
                use_container_width=True,
                type="primary" if current_scope == "Mensile" else "secondary",
            ):
                st.session_state.home_counter_scope = "Mensile"
                st.rerun()
        with yearly_col:
            if st.button(
                "Annuale",
                key="home_scope_yearly",
                use_container_width=True,
                type="primary" if current_scope == "Annuale" else "secondary",
            ):
                st.session_state.home_counter_scope = "Annuale"
                st.rerun()
    return st.session_state.get("home_counter_scope", current_scope)


def build_home_financial_summary(
    all_expenses: pd.DataFrame,
    all_incomes: pd.DataFrame,
    selected_month: str,
) -> dict:
    filters = st.session_state.get("filters", {})
    selected_year = filters.get("year_label")
    active_month_label = resolve_month_label(selected_month)
    active_year = selected_year or active_month_label.split("-")[0]
    scope = st.session_state.get("home_counter_scope", "Mensile")

    if scope == "Annuale":
        scoped_expenses = all_expenses[all_expenses["month_label"].str.startswith(active_year)] if not all_expenses.empty else all_expenses
        scoped_incomes = all_incomes[all_incomes["month_label"].str.startswith(active_year)] if not all_incomes.empty else all_incomes
        period_label = active_year
        context_note = "Visione complessiva del periodo in corso."
    else:
        scoped_expenses = all_expenses[all_expenses["month_label"] == active_month_label] if not all_expenses.empty else all_expenses
        scoped_incomes = all_incomes[all_incomes["month_label"] == active_month_label] if not all_incomes.empty else all_incomes
        period_label = format_month_heading(active_month_label)
        context_note = "Panoramica del mese attivo con focus immediato sul saldo."

    total_expenses = float(scoped_expenses["amount"].sum()) if not scoped_expenses.empty else 0.0
    total_incomes = float(scoped_incomes["amount"].sum()) if not scoped_incomes.empty else 0.0
    savings = total_incomes - total_expenses
    expense_count = len(scoped_expenses) if not scoped_expenses.empty else 0
    income_count = len(scoped_incomes) if not scoped_incomes.empty else 0
    current_username = str((st.session_state.current_user or {}).get("username", "") or "")
    couple_balance = compute_couple_balance(current_username, scoped_expenses) if current_username else 0.0

    if savings > 0:
        balance_note = "Margine positivo rispetto alle uscite."
        balance_accent = "home-finance-card-accent-balance-positive"
    elif savings < 0:
        balance_note = "Le uscite stanno superando le entrate."
        balance_accent = "home-finance-card-accent-balance-negative"
    else:
        balance_note = "Entrate e uscite sono perfettamente allineate."
        balance_accent = "home-finance-card-accent-balance-neutral"

    if couple_balance > 0:
        couple_balance_note = f"Mi devono {format_currency(couple_balance)}"
        couple_balance_accent = "home-finance-card-accent-couple-positive"
    elif couple_balance < 0:
        couple_balance_note = f"Devo {format_currency(abs(couple_balance))}"
        couple_balance_accent = "home-finance-card-accent-couple-negative"
    else:
        couple_balance_note = "Siamo in pari"
        couple_balance_accent = "home-finance-card-accent-couple-neutral"

    return {
        "scope": scope,
        "period_label": period_label,
        "context_note": context_note,
        "total_expenses": total_expenses,
        "total_incomes": total_incomes,
        "savings": savings,
        "expense_count": expense_count,
        "income_count": income_count,
        "balance_note": balance_note,
        "balance_accent": balance_accent,
        "couple_balance": couple_balance,
        "couple_balance_note": couple_balance_note,
        "couple_balance_accent": couple_balance_accent,
    }


def render_home_financial_summary_panel(summary: dict) -> None:
    render_home_scope_toggle()
    st.markdown(
        f"""
        <div class="home-finance-panel">
            <div class="home-finance-head">
                <div>
                    <div class="home-finance-eyebrow">Quadro finanziario</div>
                    <div class="home-finance-period">{escape(str(summary["period_label"]))}</div>
                </div>
            </div>
            <div class="home-finance-kpi-grid">
                <div class="home-finance-card">
                    <div class="home-finance-card-label">Spese</div>
                    <div class="home-finance-card-value home-finance-card-accent-expense">{format_currency(float(summary["total_expenses"]))}</div>
                    <div class="home-finance-card-note">{int(summary["expense_count"])} movimenti in uscita</div>
                </div>
                <div class="home-finance-card">
                    <div class="home-finance-card-label">Risparmi</div>
                    <div class="home-finance-card-value {escape(str(summary["balance_accent"]))}">{format_currency(float(summary["savings"]))}</div>
                    <div class="home-finance-card-note">{escape(str(summary["balance_note"]))}</div>
                </div>
                <div class="home-finance-card home-finance-card-couple">
                    <div class="home-finance-card-label">Saldo di coppia</div>
                    <div class="home-finance-card-value {escape(str(summary["couple_balance_accent"]))}">{format_currency(abs(float(summary["couple_balance"])))}</div>
                    <div class="home-finance-card-note">{escape(str(summary["couple_balance_note"]))}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_home_summary_panel(summary: dict) -> None:
    st.markdown(
        f"""
        <div class="home-summary-mini">
            <div class="home-summary-mini-eyebrow">Resoconto mensile</div>
            <div class="home-summary-mini-copy">
                Analizza e scarica PDF o CSV dei tuoi movimenti mensili.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.container(key="home_summary_cta"):
        if st.button("Apri riepilogo", key="home_summary_cta_button", use_container_width=True, type="secondary"):
            st.session_state.current_view = "summary"
            st.rerun()


def render_home_welcome() -> None:
    current_user = st.session_state.current_user or {}
    username = str(current_user.get("username") or "Utente")
    st.markdown(
        f"""
        <div class="home-welcome-shell">
            <div class="home-welcome-title">Ciao {escape(username)}</div>
            <div class="home-welcome-copy">Ogni movimento che registri ti avvicina a un mese piu sereno.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero(all_expenses: pd.DataFrame, all_incomes: pd.DataFrame, selected_month: str) -> None:
    image_path = Path(__file__).with_name("hero-couple-balance-transparent.png")
    if not image_path.exists():
        image_path = Path(__file__).with_name("hero-couple-balance.png")
    hero_image_html = ""
    if image_path.exists():
        encoded_image = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        hero_image_html = (
            '<div class="hero-visual">'
            '<div class="hero-visual-frame">'
            f'<img src="data:image/png;base64,{encoded_image}" alt="Robot che gestiscono risparmi di coppia" class="hero-image">'
            "</div>"
            "</div>"
        )

    summary = build_home_financial_summary(all_expenses, all_incomes, selected_month)

    with st.container(key="home_hero_shell"):
        with st.container(key="hero_layout_shell"):
            image_col, finance_col = st.columns([0.49, 0.51], vertical_alignment="top")
            with image_col:
                st.markdown('<div class="hero-left-stack">', unsafe_allow_html=True)
                if hero_image_html:
                    st.markdown(hero_image_html, unsafe_allow_html=True)
                render_home_summary_panel(summary)
                st.markdown('</div>', unsafe_allow_html=True)
            with finance_col:
                st.markdown('<div class="home-finance-column">', unsafe_allow_html=True)
                render_home_financial_summary_panel(summary)
                st.markdown('</div>', unsafe_allow_html=True)


def render_main_content(
    section: str,
    filtered_expenses: pd.DataFrame,
    filtered_incomes: pd.DataFrame,
    all_expenses: pd.DataFrame,
    all_incomes: pd.DataFrame,
    selected_month: str,
) -> None:
    active_page = st.session_state.get("page", "home")

    if section == "Home":
        return

    elif section == "Entrate":
        clear_page_navigation_intent()
        render_incomes_section(filtered_incomes, selected_month)

    elif section == "Saldo di coppia":
        st.session_state.page = "saldo_coppia"
        render_couple_balance_page(selected_month)

    elif section == "Uscite":
        requested_filter = st.session_state.pop("expense_filter", None)
        if requested_filter == "personali":
            st.session_state.expense_type_filter = "Personali"
        elif requested_filter == "condivise":
            st.session_state.expense_type_filter = "Condivise"
        elif requested_filter == "tutte":
            st.session_state.expense_type_filter = "Tutte"
            st.session_state.expense_category_filter = "Tutte"

        st.session_state.page = "uscite"
        expense_view: dict[str, pd.DataFrame | None] = {
            "base_visible": None,
            "rendered": None,
        }

        def render_expense_main_block() -> None:
            base_visible_expenses, rendered_expenses = render_expense_header_block(filtered_expenses)
            expense_view["base_visible"] = base_visible_expenses
            expense_view["rendered"] = rendered_expenses

        render_expense_section_layout(
            month_label=selected_month,
            render_main_block=render_expense_main_block,
            render_lower_block=lambda: render_expense_lower_layout(
                render_tools_block=lambda: render_expense_tools(
                    expense_view["base_visible"] if isinstance(expense_view["base_visible"], pd.DataFrame) else pd.DataFrame()
                ),
                render_total_block=lambda: render_expense_total_sticky(
                    expense_view["rendered"] if isinstance(expense_view["rendered"], pd.DataFrame) else pd.DataFrame()
                ),
                render_feed_block=lambda: render_expense_feed(
                    expense_view["rendered"] if isinstance(expense_view["rendered"], pd.DataFrame) else pd.DataFrame()
                ),
                edit_mode=st.session_state.get("expense_edit_mode", False),
                render_post_tools_block=(
                    (lambda: render_expense_delete_actions(
                        expense_view["rendered"] if isinstance(expense_view["rendered"], pd.DataFrame) else pd.DataFrame()
                    ))
                    if st.session_state.get("expense_delete_mode", False)
                    else None
                ),
            ),
            edit_mode=st.session_state.get("expense_edit_mode", False),
        )

    elif section == "Riepilogo":
        clear_page_navigation_intent()
        render_month_navigation_bar(selected_month, "summary_month")
        st.caption("Tutte le spese visibili con i filtri attivi, con esportazione CSV.")
        render_expense_list(filtered_expenses)
        st.write("")
        render_export_section(filtered_expenses)

    elif section == "Calendario":
        clear_page_navigation_intent()
        render_calendar_section(filtered_expenses, filtered_incomes)


def render_expense_section_layout(
    *,
    month_label: str,
    render_main_block,
    render_lower_block,
    edit_mode: bool = False,
) -> None:
    with st.container(key="expense_section_shell"):
        with st.container(key="expense_fixed_stack"):
            with st.container(key="expense_month_row"):
                render_month_navigation_bar(month_label, "expense_month")
            with st.container(key="expense_main_block_frame"):
                render_main_block()

        if edit_mode:
            st.markdown('<div class="expense-edit-backdrop"></div>', unsafe_allow_html=True)

        render_lower_block()


def render_expense_lower_layout(
    *,
    render_tools_block,
    render_total_block,
    render_feed_block,
    edit_mode: bool = False,
    render_post_tools_block=None,
) -> None:
    with st.container(key="expense_lower_shell"):
        with st.container(key="expense_controls_row"):
            tools_col, total_col = st.columns([0.6, 0.4], vertical_alignment="bottom")
            with tools_col:
                with st.container(key="expense_toolbar_frame"):
                    render_tools_block()
            with total_col:
                render_total_block()

        render_soft_section_separator("expense")

        if render_post_tools_block is not None:
            render_post_tools_block()

        with st.container(key="expense_feed_scroll"):
            if edit_mode:
                st.markdown('<div class="expense-edit-focus">', unsafe_allow_html=True)
            render_feed_block()
            if edit_mode:
                st.markdown("</div>", unsafe_allow_html=True)


def render_income_section_layout(
    *,
    month_label: str | None,
    render_main_block,
    render_lower_block,
    edit_mode: bool = False,
) -> None:
    with st.container(key="income_section_shell"):
        with st.container(key="income_fixed_stack"):
            if month_label is not None:
                with st.container(key="income_month_row"):
                    render_month_navigation_bar(month_label, "income_month")
            with st.container(key="income_main_block_frame"):
                render_main_block()

        if edit_mode:
            st.markdown('<div class="income-edit-backdrop"></div>', unsafe_allow_html=True)

        render_lower_block()


def render_income_lower_layout(
    *,
    render_tools_block,
    render_total_block,
    render_feed_block,
    edit_mode: bool = False,
) -> None:
    with st.container(key="income_lower_shell"):
        with st.container(key="income_controls_row"):
            tools_col, total_col = st.columns([0.6, 0.4], vertical_alignment="bottom")
            with tools_col:
                with st.container(key="income_toolbar_frame"):
                    render_tools_block()
            with total_col:
                render_total_block()

        render_soft_section_separator("income")

        with st.container(key="income_feed_scroll"):
            if edit_mode:
                st.markdown('<div class="income-edit-focus">', unsafe_allow_html=True)
            render_feed_block()
            if edit_mode:
                st.markdown("</div>", unsafe_allow_html=True)


def render_soft_section_separator(section_key: str) -> None:
    with st.container(key=f"{section_key}_list_separator_row"):
        st.markdown('<div class="expense-tools-divider"></div>', unsafe_allow_html=True)


def render_section_header_layout(
    *,
    section_key: str,
    month_label: str | None,
    month_key_prefix: str,
    render_main_block,
    render_total_block,
    render_tools_block,
    render_feed_block,
    edit_mode: bool = False,
    focus_class: str | None = None,
    backdrop_class: str | None = None,
    render_post_tools_block=None,
) -> None:
    with st.container(key=f"{section_key}_section_shell"):
        with st.container(key=f"{section_key}_fixed_stack"):
            if month_label is not None:
                render_month_navigation_bar(month_label, month_key_prefix)
            with st.container(key=f"{section_key}_main_block_frame"):
                render_main_block()
            with st.container(key=f"{section_key}_controls_row"):
                tools_col, total_col = st.columns([0.6, 0.4], vertical_alignment="center")
                with tools_col:
                    with st.container(key=f"{section_key}_toolbar_frame"):
                        render_tools_block()
                with total_col:
                    render_total_block()
            if render_post_tools_block is not None:
                render_post_tools_block()

            render_soft_section_separator(section_key)

        if edit_mode and backdrop_class:
            st.markdown(f'<div class="{backdrop_class}"></div>', unsafe_allow_html=True)

        with st.container(key=f"{section_key}_feed_scroll"):
            if edit_mode and focus_class:
                st.markdown(f'<div class="{focus_class}">', unsafe_allow_html=True)
            render_feed_block()
            if edit_mode and focus_class:
                st.markdown("</div>", unsafe_allow_html=True)


def render_section_navigation() -> str:
    current_section = st.session_state.get("current_section", "Home")
    action_label = "Nuova entrata" if current_section == "Entrate" else "Nuova spesa"
    nav_col, action_col = st.columns([1, 0.22], vertical_alignment="center")
    with nav_col:
        section = st.radio(
            "Sezioni",
            ["Home", "Calendario", "Saldo di coppia", "Entrate", "Uscite"],
            horizontal=True,
            label_visibility="collapsed",
            key="section_navigation_value",
        )
    with action_col:
        if st.button(action_label, key="top_new_expense", use_container_width=True, type="primary"):
            if current_section == "Entrate":
                st.session_state.show_new_income_modal = True
            else:
                st.session_state.show_new_expense_modal = True
            st.rerun()
    st.session_state.current_section = section
    if section not in {"Uscite", "Saldo di coppia"}:
        clear_page_navigation_intent()
    elif section == "Uscite" and st.session_state.get("page") != "uscite":
        st.session_state.page = "uscite"
    elif section == "Saldo di coppia":
        st.session_state.page = "saldo_coppia"
    return section


def render_month_navigation_bar(selected_month: str, key_prefix: str) -> str:
    active_month_label = resolve_month_label(selected_month)
    year_text, month_text = active_month_label.split("-")
    month_title = f"{MONTH_NAMES.get(month_text, month_text)} {year_text}"
    title_class = "calendar-toolbar-label calendar-toolbar-label-home" if key_prefix == "home_month" else "calendar-toolbar-label"

    st.markdown('<div class="calendar-toolbar">', unsafe_allow_html=True)
    left_zone, header_center, right_zone = st.columns([0.22, 0.56, 0.22], vertical_alignment="center")
    with left_zone:
        left_spacer, left_button_col, left_spacer_2 = st.columns([1, 1, 1], vertical_alignment="center")
        with left_button_col:
            if st.button("←", key=f"{key_prefix}_prev_month", use_container_width=False):
                new_month = shift_month_label(active_month_label, -1)
                current_filters = dict(st.session_state.get("filters", {}))
                current_filters["month_label"] = new_month
                st.session_state.filters = current_filters
                st.rerun()
    with header_center:
        st.markdown(
            f"<div class='calendar-toolbar-label-wrap'><div class='{title_class}'>{month_title}</div></div>",
            unsafe_allow_html=True,
        )
    with right_zone:
        right_spacer, right_button_col, right_spacer_2 = st.columns([1, 1, 1], vertical_alignment="center")
        with right_button_col:
            if st.button("→", key=f"{key_prefix}_next_month", use_container_width=False):
                new_month = shift_month_label(active_month_label, 1)
                current_filters = dict(st.session_state.get("filters", {}))
                current_filters["month_label"] = new_month
                st.session_state.filters = current_filters
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    return active_month_label


def render_calendar_section(expenses: pd.DataFrame, incomes: pd.DataFrame) -> None:
    filters = st.session_state.get("filters", {})
    filter_month_label = filters.get("month_label", "Tutti")
    active_month_label = render_month_navigation_bar(filter_month_label, "calendar_month")
    calendar_filter = st.radio(
        "Filtro calendario",
        ["Tutto", "Entrate", "Uscite"],
        horizontal=True,
        label_visibility="collapsed",
        key="calendar_content_filter",
    )

    calendar_data = build_calendar_data(
        expenses,
        incomes,
        month_label=active_month_label,
        content_filter=calendar_filter,
        preview_limit=3,
    )

    html_parts = [
        '<div class="calendar-shell">',
        '<div class="calendar-grid">',
    ]

    for weekday in calendar_data["weekdays"]:
        html_parts.append(f'<div class="calendar-weekday">{weekday}</div>')

    for week in calendar_data["weeks"]:
        for day in week["days"]:
            classes = ["calendar-day"]
            if not day["is_current_month"]:
                classes.append("is-other-month")
            if day["is_today"]:
                classes.append("is-today")

            event_markup = []
            for event in day["preview_events"]:
                event_markup.append(
                    f'<div class="calendar-event"><span class="calendar-event-dot {event["type"]}"></span><span class="calendar-event-text">{escape(event["display_label"])}</span></div>'
                )
            if day["remaining_count"] > 0:
                event_markup.append(
                    f'<div class="calendar-event"><span class="calendar-event-text">+{day["remaining_count"]} altri</span></div>'
                )

            total_text = ""
            if day["is_current_month"]:
                expense_total = float(day["total_expenses"])
                income_total = float(day["total_incomes"])
                if expense_total > 0 or income_total > 0:
                    total_text = f'<div class="calendar-day-total">Uscite {format_currency(expense_total)} · Entrate {format_currency(income_total)}</div>'

            today_dot = '<span class="calendar-today-dot"></span>' if day["is_today"] else ""
            html_parts.append(
                f'<div class="{" ".join(classes)}">'
                f'<div class="calendar-day-top"><div class="calendar-day-number">{day["day_number"]}</div>{today_dot}</div>'
                f"{total_text}"
                f'<div class="calendar-event-list">{"".join(event_markup)}</div>'
                "</div>"
            )

    html_parts.extend(["</div>", "</div>"])
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def render_sidebar_filters(dataframe: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    user = st.session_state.current_user or {}

    st.sidebar.markdown("## Profilo")
    if st.sidebar.button(user.get("full_name", "Utente"), key="profile_button", use_container_width=False, type="tertiary"):
        st.session_state.current_view = "profile"
        st.rerun()
    st.sidebar.markdown(
        f"<div class='small-note'>{user.get('username', '-')}</div>",
        unsafe_allow_html=True,
    )
    st.sidebar.write("")

    st.sidebar.markdown("## Home")
    if st.sidebar.button("Vai alla home", use_container_width=False, type="tertiary"):
        st.session_state.current_view = "home"
        st.session_state.current_section = "Home"
        st.session_state.pending_section_navigation_sync = True
        clear_page_navigation_intent()
        st.rerun()

    st.sidebar.write("")
    st.sidebar.markdown("## Filtri")
    toggle_label = "Nascondi filtri" if st.session_state.show_filters else "Mostra filtri"
    if st.sidebar.button(toggle_label, use_container_width=False, type="tertiary"):
        st.session_state.show_filters = not st.session_state.show_filters
        st.rerun()

    month_options = get_month_options(dataframe)
    category_options = ["Tutte"] + get_categories()
    payer_values = sorted(dataframe["paid_by"].dropna().unique().tolist()) if not dataframe.empty else []
    payer_options = ["Tutti"] + payer_values
    type_options = ["Tutte"] + EXPENSE_TYPE_OPTIONS

    available_months = [month for month in month_options if month != "Tutti"]
    year_options = sorted({month.split("-")[0] for month in available_months}, reverse=True)
    previous_filters = st.session_state.get(
        "filters",
        {"month_label": "Tutti", "category": "Tutte", "payer": "Tutti", "expense_type": "Tutte"},
    )
    pending_overrides = dict(st.session_state.get("pending_sidebar_filter_overrides", {}))
    if pending_overrides:
        previous_filters = {**previous_filters, **pending_overrides}
        st.session_state.pending_sidebar_filter_overrides = {}
    selected_month = previous_filters.get("month_label", "Tutti")
    selected_category = previous_filters.get("category", "Tutte")
    selected_payer = previous_filters.get("payer", "Tutti")
    selected_type = previous_filters.get("expense_type", "Tutte")

    if not st.session_state.show_filters:
        st.sidebar.caption("Filtri nascosti.")
    else:
        st.sidebar.caption("Riduci il dataset e aggiorna l'app.")

    if st.session_state.show_filters and year_options:
        selected_year = selected_month.split("-")[0] if selected_month != "Tutti" else year_options[0]
        selected_year = st.sidebar.selectbox("Anno", year_options, index=year_options.index(selected_year))
        month_map = {
            MONTH_NAMES.get(month.split("-")[1], month): month
            for month in available_months
            if month.startswith(selected_year)
        }
        month_labels = list(month_map.keys())
        default_month_label = None
        if selected_month != "Tutti" and selected_month.startswith(selected_year):
            default_month_label = MONTH_NAMES.get(selected_month.split("-")[1], selected_month)
        default_index = month_labels.index(default_month_label) if default_month_label in month_labels else 0
        selected_month_label = st.sidebar.selectbox("Mese", month_labels, index=default_index) if month_labels else None
        selected_month = month_map[selected_month_label] if selected_month_label else "Tutti"

        selected_category = st.sidebar.selectbox(
            "Categoria",
            category_options,
            index=category_options.index(selected_category) if selected_category in category_options else 0,
        )
        selected_payer = st.sidebar.selectbox(
            "Persona",
            payer_options,
            index=payer_options.index(selected_payer) if selected_payer in payer_options else 0,
        )
        selected_type = st.sidebar.selectbox(
            "Tipo spesa",
            type_options,
            index=type_options.index(selected_type) if selected_type in type_options else 0,
        )

    filtered = apply_filters(
        dataframe=dataframe,
        month_label=selected_month,
        category=selected_category,
        payer=selected_payer,
        expense_type=selected_type,
    )

    st.sidebar.markdown(
        f"<div class='small-note'>Spese mostrate: <strong>{len(filtered)}</strong></div>",
        unsafe_allow_html=True,
    )
    st.session_state.filters = {
        "month_label": selected_month,
        "year_label": selected_month.split("-")[0] if selected_month != "Tutti" else (year_options[0] if year_options else date.today().strftime("%Y")),
        "category": selected_category,
        "payer": selected_payer,
        "expense_type": selected_type,
    }

    return filtered, selected_month


def render_dashboard(all_expenses: pd.DataFrame, all_incomes: pd.DataFrame, selected_month: str) -> None:
    current_user = st.session_state.current_user or {}
    current_username = current_user.get("username", "")
    month_data = all_expenses if selected_month == "Tutti" else all_expenses[all_expenses["month_label"] == selected_month]
    month_incomes = all_incomes if selected_month == "Tutti" else all_incomes[all_incomes["month_label"] == selected_month]
    metrics = build_dashboard_metrics(month_data, current_username)
    total_incomes = float(month_incomes["amount"].sum()) if not month_incomes.empty else 0.0
    net_month = total_incomes - float(metrics["total_month"])

    col1, col2, col3, col4, col5 = st.columns(5)
    render_dashboard_card(
        col1,
        "USCITE",
        format_currency(metrics["total_month"]),
        "total_month",
    )
    render_dashboard_card(
        col2,
        "PERSONALI",
        format_currency(metrics["my_personal"]),
        "my_personal",
    )
    render_dashboard_card(
        col3,
        "CONDIVISE",
        format_currency(metrics["shared_total"]),
        "shared_total",
    )
    render_dashboard_card(
        col4,
        "SALDO",
        format_currency(net_month),
        "net_month",
    )
    render_dashboard_card(
        col5,
        "SALDO COPPIA",
        build_couple_balance_label(metrics["balance"]),
        "balance",
    )

def render_dashboard_card(column, title: str, value: str, metric_key: str) -> None:
    label = f"{title}\n{value}"
    with column:
        if st.button(
            label,
            key=f"dashboard_{metric_key}",
            use_container_width=True,
            type="secondary",
        ):
            if metric_key == "total_month":
                navigate_to_expenses("tutte")
                st.session_state.current_view = "home"
            elif metric_key == "my_personal":
                navigate_to_expenses("personali")
                st.session_state.current_view = "home"
            elif metric_key == "shared_total":
                navigate_to_expenses("condivise")
                st.session_state.current_view = "home"
            elif metric_key == "balance":
                navigate_to_couple_balance()
                st.session_state.current_view = "home"
            else:
                st.session_state.dashboard_metric = metric_key
                st.session_state.current_view = "dashboard_detail"
            st.rerun()


@st.dialog(" ", width="small")
def render_new_expense_dialog() -> None:
    title_col, close_col = st.columns([0.9, 0.1], vertical_alignment="center")
    with title_col:
        st.markdown("<h3 style='margin:0; line-height:1;'>Nuova spesa</h3>", unsafe_allow_html=True)
    with close_col:
        if st.button("✕", key="close_new_expense_modal_icon", use_container_width=False, type="secondary"):
            st.session_state.show_new_expense_modal = False
            st.rerun()

    render_create_form()


@st.dialog(" ", width="small")
def render_edit_expense_dialog(dataframe: pd.DataFrame) -> None:
    title_col, close_col = st.columns([0.9, 0.1], vertical_alignment="center")
    with title_col:
        st.markdown("<h3 style='margin:0; line-height:1;'>Modifica spesa</h3>", unsafe_allow_html=True)
    with close_col:
        if st.button("✕", key="close_edit_expense_modal_icon", use_container_width=False, type="secondary"):
            st.session_state.show_edit_expense_modal = False
            st.rerun()

    render_edit_section(dataframe)


@st.dialog(" ", width="small")
def render_new_income_dialog() -> None:
    title_col, close_col = st.columns([0.9, 0.1], vertical_alignment="center")
    with title_col:
        st.markdown("<h3 style='margin:0; line-height:1;'>Nuova entrata</h3>", unsafe_allow_html=True)
    with close_col:
        if st.button("✕", key="close_new_income_modal_icon", use_container_width=False, type="secondary"):
            st.session_state.show_new_income_modal = False
            st.rerun()

    render_create_income_form()


@st.dialog(" ", width="small")
def render_edit_income_dialog(dataframe: pd.DataFrame) -> None:
    title_col, close_col = st.columns([0.9, 0.1], vertical_alignment="center")
    with title_col:
        st.markdown("<h3 style='margin:0; line-height:1;'>Modifica entrata</h3>", unsafe_allow_html=True)
    with close_col:
        if st.button("✕", key="close_edit_income_modal_icon", use_container_width=False, type="secondary"):
            st.session_state.show_edit_income_modal = False
            st.rerun()

    render_edit_income_section(dataframe)


def adjust_new_expense_amount(delta: float) -> None:
    current_raw = str(st.session_state.get("new_expense_amount_raw", "0") or "0").replace(",", ".").strip()
    try:
        current_amount = float(current_raw)
    except ValueError:
        current_amount = 0.0
    new_amount = max(0.0, round(current_amount + delta, 2))
    st.session_state.new_expense_amount_raw = f"{new_amount:.2f}".replace(".", ",")


def normalize_amount_input(session_key: str) -> None:
    raw_value = str(st.session_state.get(session_key, "") or "").strip()
    if not raw_value:
        st.session_state[session_key] = "0,00"
        return

    sanitized = raw_value.replace("€", "").replace(" ", "")
    sanitized = sanitized.replace(".", ",")

    if sanitized.count(",") > 1:
        first_part, *rest = sanitized.split(",")
        sanitized = first_part + "," + "".join(rest)

    if "," in sanitized:
        integer_part, decimal_part = sanitized.split(",", 1)
        integer_part = "".join(ch for ch in integer_part if ch.isdigit()) or "0"
        decimal_digits = "".join(ch for ch in decimal_part if ch.isdigit())[:2]
        sanitized = integer_part + "," + decimal_digits.ljust(2, "0")
    else:
        integer_digits = "".join(ch for ch in sanitized if ch.isdigit()) or "0"
        sanitized = integer_digits + ",00"

    st.session_state[session_key] = sanitized


def normalize_new_expense_amount_input() -> None:
    normalize_amount_input("new_expense_amount_raw")


def render_create_form() -> None:
    category_options = get_categories()
    paid_by_usernames = get_usernames()
    current_username = (st.session_state.current_user or {}).get("username", "")
    partner_username = get_partner_username(current_username)
    today = date.today()
    if st.session_state.pop("reset_new_expense_form", False):
        for key in [
            "new_expense_amount",
            "new_expense_amount_raw",
            "new_expense_name",
            "new_expense_date",
            "new_expense_description",
            "new_expense_category",
            "new_expense_paid_by",
            "new_expense_type",
            "new_expense_split_type",
            "new_expense_split_ratio",
        ]:
            st.session_state.pop(key, None)
    if "new_expense_date" not in st.session_state:
        st.session_state.new_expense_date = today

    default_amount_raw = st.session_state.get("new_expense_amount_raw", "0,00")
    if not default_amount_raw:
        default_amount_raw = "0,00"
        st.session_state.new_expense_amount_raw = default_amount_raw
    with st.container(key="new_expense_amount_row"):
        _, currency_col, amount_col, _ = st.columns([0.22, 0.12, 0.26, 0.40], vertical_alignment="center")
        with currency_col:
            with st.container(key="new_expense_amount_currency"):
                st.markdown('<div class="new-expense-amount-currency">€</div>', unsafe_allow_html=True)
        with amount_col:
            amount_raw = st.text_input(
                "Importo",
                value=default_amount_raw,
                placeholder="0,00",
                key="new_expense_amount_raw",
                label_visibility="collapsed",
                on_change=normalize_new_expense_amount_input,
            )
    normalized_amount = (amount_raw or "").replace(",", ".").strip()
    try:
        amount = float(normalized_amount) if normalized_amount else 0.0
    except ValueError:
        amount = 0.0
    st.session_state.new_expense_amount = amount
    with st.container(key="new_expense_amount_stepper"):
        _, minus_col, plus_col, _ = st.columns([0.39, 0.11, 0.11, 0.39], vertical_alignment="center")
        with minus_col:
            if st.button("−", key="new_expense_amount_minus", type="tertiary", use_container_width=False, on_click=adjust_new_expense_amount, args=(-1.0,)):
                pass
        with plus_col:
            if st.button("+", key="new_expense_amount_plus", type="tertiary", use_container_width=False, on_click=adjust_new_expense_amount, args=(1.0,)):
                pass

    name = st.text_input("Nome", placeholder="Spesa, bolletta, cena...", key="new_expense_name")

    col3, col4 = st.columns(2)
    category = col3.selectbox("Categoria", category_options, key="new_expense_category")
    expense_type = col4.selectbox("Tipo spesa", EXPENSE_TYPE_OPTIONS, key="new_expense_type")

    if expense_type == "Personale":
        paid_by = current_username
        st.text_input("Persona che ha pagato", value=current_username, disabled=True)
    else:
        paid_by = st.selectbox("Persona che ha pagato", paid_by_usernames, key="new_expense_paid_by")

    split_type = "equal"
    split_ratio = 1.0 if expense_type == "Personale" else 0.5
    if expense_type == "Personale":
        st.caption("Le spese personali sono visibili solo al proprietario e non influenzano il saldo.")
    else:
        split_type = st.segmented_control(
            "Divisione",
            SHARED_SPLIT_OPTIONS,
            format_func=lambda value: "50/50" if value == "equal" else "Personalizzata",
            default="equal",
            key="new_expense_split_type",
        )
        if split_type == "custom":
            split_ratio = st.slider(
                "Quota di chi paga vs quota partner",
                min_value=0,
                max_value=100,
                value=int(st.session_state.get("new_expense_split_ratio", 50)),
                key="new_expense_split_ratio",
                help="La percentuale rappresenta la quota di chi paga.",
            ) / 100
        payer_share = amount * split_ratio
        partner_share = amount - payer_share
        if paid_by == current_username:
            your_share = payer_share
            other_share = partner_share
        else:
            your_share = partner_share
            other_share = payer_share
        st.caption(
            f"Tu: {format_currency(your_share)} / Partner: {format_currency(other_share)}"
        )

    with st.expander("Dettagli opzionali", expanded=False):
        expense_date = st.date_input(
            "Data",
            value=st.session_state.new_expense_date,
            format="YYYY-MM-DD",
            key="new_expense_date",
        )
        description = st.text_area(
            "Note",
            placeholder="Facoltative",
            help="Aggiungi dettagli extra solo se ti servono.",
            key="new_expense_description",
        )

    current_balance = 0.0
    if current_username:
        current_expenses = get_visible_expenses(get_expenses(), current_username)
        current_balance = compute_balance(current_username, partner_username, current_expenses)

    balance_delta = 0.0
    if expense_type == "Condivisa":
        payer_share = amount * split_ratio
        partner_share = amount - payer_share
        if paid_by == current_username:
            balance_delta = partner_share
        else:
            balance_delta = -(amount - payer_share)

    new_balance = current_balance + balance_delta
    st.caption("Anteprima saldo")
    if expense_type == "Condivisa":
        st.write(
            f"Impatto: {build_balance_label(balance_delta)}"
        )
        st.write(
            f"Saldo stimato dopo questa spesa: {build_balance_label(new_balance)}"
        )
    else:
        st.write("Impatto: nessun effetto sul saldo di coppia")

    if st.button("Salva spesa", use_container_width=True, key="save_new_expense"):
        payload = {
            "amount": amount,
            "name": name,
            "description": description,
            "expense_type": expense_type,
            "split_type": split_type,
            "split_ratio": split_ratio,
        }
        errors = validate_expense_data(payload)
        if errors:
            for error in errors:
                st.error(error)
        else:
            create_expense(
                expense_date=expense_date,
                amount=amount,
                name=name,
                category=category,
                description=description,
                paid_by=paid_by,
                expense_type=expense_type,
                split_type=split_type,
                split_ratio=split_ratio,
            )
            st.success("Spesa salvata con successo.")
            st.session_state.reset_new_expense_form = True
            st.session_state.show_new_expense_modal = False
            st.rerun()


def render_expense_list(dataframe: pd.DataFrame) -> None:
    if dataframe.empty:
        st.info("Nessuna spesa trovata con i filtri selezionati.")
        return

    display_frame = dataframe[
        [
            "id",
            "expense_date",
            "amount",
            "name",
            "category",
            "description",
            "paid_by",
            "owner",
            "expense_type",
            "split_type",
            "split_ratio",
        ]
    ].copy()
    display_frame["expense_date"] = display_frame["expense_date"].dt.strftime("%Y-%m-%d")
    display_frame["amount"] = display_frame["amount"].map(format_currency)
    display_frame["owner"] = display_frame["owner"].fillna("-")
    display_frame["split_ratio"] = display_frame["split_ratio"].apply(
        lambda value: f"{int(float(value) * 100)}%" if pd.notna(value) else "-"
    )
    display_frame = display_frame.rename(
        columns={
            "id": "ID",
            "expense_date": "Data",
            "amount": "Importo",
            "name": "Nome",
            "category": "Categoria",
            "description": "Descrizione",
            "paid_by": "Pagato da",
            "owner": "Proprietario",
            "expense_type": "Tipo spesa",
            "split_type": "Divisione",
            "split_ratio": "Quota pagatore",
        }
    )

    st.dataframe(
        display_frame,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ID": st.column_config.NumberColumn(width="small"),
            "Data": st.column_config.TextColumn(width="small"),
            "Importo": st.column_config.TextColumn(width="small"),
            "Nome": st.column_config.TextColumn(width="medium"),
            "Categoria": st.column_config.TextColumn(width="small"),
            "Descrizione": st.column_config.TextColumn(width="medium"),
            "Pagato da": st.column_config.TextColumn(width="small"),
            "Proprietario": st.column_config.TextColumn(width="small"),
            "Tipo spesa": st.column_config.TextColumn(width="small"),
            "Divisione": st.column_config.TextColumn(width="small"),
            "Quota pagatore": st.column_config.TextColumn(width="small"),
        },
    )


def render_expense_category_filter_bar(dataframe: pd.DataFrame) -> str:
    categories = sorted([str(value) for value in dataframe["category"].dropna().unique().tolist()])
    options = ["Tutte", *categories]
    current_value = st.session_state.get("expense_category_filter", "Tutte")
    if current_value not in options:
        current_value = "Tutte"

    return st.radio(
        "Filtra categoria",
        options,
        index=options.index(current_value),
        horizontal=True,
        label_visibility="collapsed",
        key="expense_category_filter",
    )


def render_expense_type_filter_bar() -> str:
    options = ["Tutte", "Personali", "Condivise"]
    current_value = st.session_state.get("expense_type_filter", "Tutte")
    if current_value not in options:
        current_value = "Tutte"

    return st.radio(
        "Filtra tipo spesa",
        options,
        index=options.index(current_value),
        horizontal=True,
        label_visibility="collapsed",
        key="expense_type_filter",
    )


def render_expense_total_sticky(dataframe: pd.DataFrame) -> None:
    total_amount = float(dataframe["amount"].sum()) if not dataframe.empty else 0.0
    current_username = str((st.session_state.current_user or {}).get("username", "") or "")
    balance_text = ""
    if current_username and not dataframe.empty:
        partner_username = get_partner_username(current_username)
        balance = compute_balance(current_username, partner_username, dataframe)
        if balance < 0:
            balance_text = f"Devo {format_currency(abs(balance))} a {partner_username}"
        elif balance > 0:
            balance_text = f"{partner_username} deve {format_currency(balance)}"
        else:
            balance_text = "Siamo in pari"
    render_total_sticky_amount(total_amount, balance_text)


def render_total_sticky_amount(total_amount: float, secondary_text: str = "") -> None:
    secondary_html = f'<div class="expense-balance-pill">{escape(secondary_text)}</div>' if secondary_text else ""
    st.markdown(
        f"""
        <div class="expense-total-sticky">
            <div class="expense-total-pill">
                <span class="expense-total-label">Totale</span>
                <span class="expense-total-value">{format_currency(total_amount)}</span>
            </div>
            {secondary_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_couple_balance_view_dataset(
    dataframe: pd.DataFrame,
    selected_status: str,
    selected_category: str,
) -> pd.DataFrame:
    return filter_couple_balance_expenses(dataframe, selected_status, selected_category)


def build_expense_view_dataset(
    dataframe: pd.DataFrame,
    selected_type_view: str,
    selected_category: str,
) -> pd.DataFrame:
    visible_expenses = dataframe.copy()
    if selected_type_view == "Personali":
        visible_expenses = visible_expenses[visible_expenses["expense_type"] == "Personale"].copy()
    elif selected_type_view == "Condivise":
        visible_expenses = visible_expenses[visible_expenses["expense_type"] == "Condivisa"].copy()

    if selected_category != "Tutte":
        visible_expenses = visible_expenses[visible_expenses["category"] == selected_category].copy()

    return visible_expenses


def render_couple_balance_status_filter_bar() -> str:
    options = ["Da regolare", "Pagate", "Tutte"]
    current_value = st.session_state.get("couple_balance_status_filter", "Da regolare")
    if current_value not in options:
        current_value = "Da regolare"

    return st.radio(
        "Filtra stato saldo",
        options,
        index=options.index(current_value),
        horizontal=True,
        label_visibility="collapsed",
        key="couple_balance_status_filter",
    )


def render_couple_balance_header_block(shared_expenses: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    with st.container(key="expense_header_content"):
        with st.container(key="expense_primary_tabs_row"):
            selected_status = render_couple_balance_status_filter_bar()
        with st.container(key="expense_secondary_tabs_row"):
            selected_category = render_expense_category_filter_bar(shared_expenses)

        base_visible_expenses = build_couple_balance_view_dataset(
            shared_expenses,
            selected_status,
            selected_category,
        )
        rendered_expenses = build_rendered_expense_dataset(base_visible_expenses)
    return base_visible_expenses, rendered_expenses


def render_expense_header_block(filtered_expenses: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    with st.container(key="expense_header_content"):
        with st.container(key="expense_primary_tabs_row"):
            selected_type_view = render_expense_type_filter_bar()
        with st.container(key="expense_secondary_tabs_row"):
            selected_category = render_expense_category_filter_bar(filtered_expenses)
        base_visible_expenses = build_expense_view_dataset(
            filtered_expenses,
            selected_type_view,
            selected_category,
        )
        rendered_expenses = build_rendered_expense_dataset(base_visible_expenses)
    return base_visible_expenses, rendered_expenses


def build_rendered_expense_dataset(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty:
        return dataframe.copy()

    rendered_expenses = dataframe.copy()
    search_query = str(st.session_state.get("expense_search_query", "") or "").strip().lower()
    if search_query:
        rendered_expenses = rendered_expenses[
            rendered_expenses["name"].fillna("").astype(str).str.lower().str.contains(search_query, na=False)
        ].copy()

    sort_mode = st.session_state.get("expense_sort_mode", "Data piu recente")
    if rendered_expenses.empty:
        return rendered_expenses

    if sort_mode == "Importo maggiore":
        return rendered_expenses.sort_values(by=["amount", "expense_date", "id"], ascending=[False, False, False]).copy()
    if sort_mode == "Importo minore":
        return rendered_expenses.sort_values(by=["amount", "expense_date", "id"], ascending=[True, False, False]).copy()
    return rendered_expenses.sort_values(by=["expense_date", "id"], ascending=[False, False]).copy()


def clear_expense_delete_mode() -> None:
    st.session_state.expense_delete_mode = False
    st.session_state.expense_delete_selected_ids = []
    st.session_state.expense_delete_confirm_pending = False
    st.session_state.expense_delete_select_all = False


def render_expense_delete_actions(dataframe: pd.DataFrame) -> None:
    visible_ids = [int(value) for value in dataframe["id"].tolist()] if not dataframe.empty else []
    selected_ids = [int(value) for value in st.session_state.get("expense_delete_selected_ids", []) if int(value) in visible_ids]
    st.session_state.expense_delete_selected_ids = selected_ids

    all_selected = bool(visible_ids) and len(selected_ids) == len(visible_ids)
    st.session_state.expense_delete_select_all = all_selected

    with st.container(key="expense_delete_actions_row"):
        select_col, count_col, action_col, confirm_col, cancel_col, _ = st.columns(
            [0.16, 0.16, 0.16, 0.12, 0.12, 0.28],
            vertical_alignment="center",
        )
        with select_col:
            toggle_label = "Deseleziona tutte" if all_selected else "Seleziona tutte"
            if st.button(
                toggle_label,
                key="expense_delete_toggle_all",
                use_container_width=False,
                type="secondary",
                disabled=not visible_ids,
            ):
                next_selected = [] if all_selected else visible_ids
                st.session_state.expense_delete_selected_ids = next_selected
                st.session_state.expense_delete_confirm_pending = False
                st.session_state.expense_delete_select_all = bool(next_selected) and len(next_selected) == len(visible_ids)
                for expense_id in visible_ids:
                    st.session_state[f"expense_delete_pick_{expense_id}"] = expense_id in next_selected
                st.rerun()
        with count_col:
            selection_count = len(selected_ids)
            count_label = "1 selezione" if selection_count == 1 else f"{selection_count} selezioni"
            st.markdown(f'<div class="expense-delete-count">{count_label}</div>', unsafe_allow_html=True)
        with action_col:
            delete_disabled = not selected_ids
            if st.button(
                "elimina",
                key="expense_delete_action",
                use_container_width=False,
                type="secondary",
                disabled=delete_disabled,
            ):
                st.session_state.expense_delete_confirm_pending = True
                st.rerun()
        if st.session_state.get("expense_delete_confirm_pending", False) and selected_ids:
            with confirm_col:
                if st.button("conferma", key="expense_delete_confirm", use_container_width=False, type="secondary"):
                    deleted_count = 0
                    for expense_id in selected_ids:
                        if delete_expense(expense_id, current_username):
                            deleted_count += 1
                    if deleted_count == 0:
                        st.error("Non sei autorizzato a eliminare queste spese.")
                        st.session_state.expense_delete_confirm_pending = False
                        st.rerun()
                    clear_expense_delete_mode()
                    st.success("Spese eliminate con successo.")
                    st.rerun()
            with cancel_col:
                if st.button("annulla", key="expense_delete_cancel", use_container_width=False, type="secondary"):
                    st.session_state.expense_delete_confirm_pending = False
                    st.rerun()


def render_expense_tools(
    dataframe: pd.DataFrame,
    *,
    allow_edit_mode: bool = True,
    allow_delete_mode: bool = True,
) -> None:
    with st.container(key="expense_toolbar_shell"):
        back_col, edit_col, sort_col, search_col, delete_col, _ = st.columns([0.08, 0.22, 0.08, 0.08, 0.08, 0.46], vertical_alignment="center")
        with back_col:
            with st.container(key="expense_toolbar_back_item"):
                is_delete_mode = st.session_state.get("expense_delete_mode", False)
                is_confirmed_search = bool(st.session_state.get("expense_search_confirmed", False) and st.session_state.get("expense_search_query", ""))
                if st.button(
                    "",
                    key="expense_search_reset_button",
                    use_container_width=False,
                    type="secondary",
                    icon=":material/arrow_back:",
                    disabled=not (is_confirmed_search or is_delete_mode),
                ):
                        if is_delete_mode:
                            clear_expense_delete_mode()
                        else:
                            st.session_state.expense_search_query = ""
                            st.session_state.expense_search_confirmed = False
                        st.rerun()
        with edit_col:
            with st.container(key="expense_toolbar_edit_item"):
                is_edit_mode = st.session_state.get("expense_edit_mode", False)
                edit_label = "Modifica spesa"
                edit_button_type = "primary" if is_edit_mode else "secondary"
                if st.button(
                    edit_label,
                    key="expense_edit_mode_toggle",
                    use_container_width=False,
                    type=edit_button_type,
                    disabled=not allow_edit_mode,
                ):
                    if not is_edit_mode:
                        clear_expense_delete_mode()
                    st.session_state.expense_edit_mode = not is_edit_mode
                    st.rerun()
        with sort_col:
            with st.container(key="expense_toolbar_sort_item"):
                with st.container(key="expense_sort_toggle"):
                    with st.popover("", use_container_width=False, icon=":material/tune:"):
                        with st.container(key="expense_sort_menu"):
                            sort_options = [
                                "Data piu recente",
                                "Importo maggiore",
                                "Importo minore",
                            ]
                            current_sort = st.session_state.get("expense_sort_mode", sort_options[0])
                            selected_sort = st.radio(
                                "Ordina spese",
                                sort_options,
                                index=sort_options.index(current_sort) if current_sort in sort_options else 0,
                                label_visibility="collapsed",
                                key="expense_sort_mode",
                            )
                            if selected_sort != current_sort:
                                st.session_state.expense_sort_mode = selected_sort
                                st.rerun()
        with search_col:
            with st.container(key="expense_toolbar_search_item"):
                with st.container(key="expense_search_toggle"):
                    with st.popover("", use_container_width=False, icon=":material/search:"):
                        with st.container(key="expense_search_menu"):
                            live_value = render_expense_live_search(
                                st.session_state.get("expense_search_query", ""),
                                key="expense_search_query_live",
                                placeholder="Cerca per nome",
                            )
                            if live_value == EXPENSE_SEARCH_RESET_SIGNAL:
                                if st.session_state.get("expense_search_query", "") or st.session_state.get("expense_search_confirmed", False):
                                    st.session_state.expense_search_query = ""
                                    st.session_state.expense_search_confirmed = False
                                    st.rerun()
                            elif isinstance(live_value, str) and live_value.startswith(EXPENSE_SEARCH_CONFIRM_PREFIX):
                                confirmed_value = live_value.removeprefix(EXPENSE_SEARCH_CONFIRM_PREFIX)
                                st.session_state.expense_search_query = confirmed_value
                                st.session_state.expense_search_confirmed = bool(confirmed_value.strip())
                                st.rerun()
                            elif live_value != st.session_state.get("expense_search_query", ""):
                                st.session_state.expense_search_query = live_value
                                if not str(live_value).strip():
                                    st.session_state.expense_search_confirmed = False
                                st.rerun()
        with delete_col:
            with st.container(key="expense_toolbar_delete_item"):
                with st.container(key="expense_delete_toggle"):
                    delete_button_type = "primary" if is_delete_mode else "secondary"
                    if st.button(
                        "",
                        key="expense_delete_mode_toggle",
                        use_container_width=False,
                        type=delete_button_type,
                        icon=":material/delete_outline:",
                        disabled=not allow_delete_mode,
                    ):
                        if is_delete_mode:
                            clear_expense_delete_mode()
                        else:
                            st.session_state.expense_edit_mode = False
                            st.session_state.expense_delete_mode = True
                            st.session_state.expense_delete_confirm_pending = False
                            st.session_state.expense_delete_selected_ids = []
                        st.rerun()

def render_expense_feed(dataframe: pd.DataFrame) -> None:
    if dataframe.empty:
        if str(st.session_state.get("expense_search_query", "") or "").strip():
            st.info("Nessuna spesa trovata con questa ricerca.")
        else:
            st.info("Nessuna spesa trovata con i filtri selezionati.")
        return

    edit_mode = st.session_state.get("expense_edit_mode", False)
    delete_mode = st.session_state.get("expense_delete_mode", False)
    current_username = str((st.session_state.current_user or {}).get("username", "") or "")
    partner_username = get_partner_username(current_username) if current_username else ""
    visible_ids = {int(value) for value in dataframe["id"].tolist()}
    selected_ids = {
        int(value)
        for value in st.session_state.get("expense_delete_selected_ids", [])
        if int(value) in visible_ids
    }
    st.session_state.expense_delete_selected_ids = sorted(selected_ids)
    next_selected_ids: list[int] = []
    st.markdown('<div class="expense-list">', unsafe_allow_html=True)
    for _, row in dataframe.iterrows():
        expense_id = int(row["id"])
        expense_name = str(row.get("name") or row.get("description") or "Spesa")
        date_label = row["expense_date"].strftime("%d/%m")
        paid_by_username = str(row.get("paid_by") or "")
        amount_modifier = ""
        if current_username and paid_by_username == current_username:
            amount_modifier = " expense-cell-amount-self"
        elif partner_username and paid_by_username == partner_username:
            amount_modifier = " expense-cell-amount-partner"
        with st.container(key=f"expense_row_{expense_id}"):
            row_layout = [0.055, 0.125, 0.27, 0.19, 0.145, 0.11, 0.175] if delete_mode else [0.14, 0.28, 0.2, 0.16, 0.14, 0.18]
            row_cols = st.columns(row_layout, vertical_alignment="center")
            col_offset = 0
            if delete_mode:
                with row_cols[0]:
                    checkbox_key = f"expense_delete_pick_{expense_id}"
                    if checkbox_key not in st.session_state:
                        st.session_state[checkbox_key] = expense_id in selected_ids
                    with st.container(key=f"expense_delete_row_toggle_{expense_id}"):
                        is_checked = st.checkbox(
                            f"Seleziona spesa {expense_id}",
                            key=checkbox_key,
                            label_visibility="collapsed",
                        )
                    if is_checked:
                        next_selected_ids.append(expense_id)
                col_offset = 1
            with row_cols[0 + col_offset]:
                st.markdown(f'<div class="expense-cell expense-cell-secondary">{date_label}</div>', unsafe_allow_html=True)
            with row_cols[1 + col_offset]:
                if edit_mode:
                    if st.button(expense_name, key=f"expense_name_pick_{expense_id}", use_container_width=True, type="tertiary"):
                        st.session_state.preselected_expense_id = expense_id
                        st.session_state.show_edit_expense_modal = True
                        st.rerun()
                else:
                    st.markdown(f'<div class="expense-cell expense-cell-name">{expense_name}</div>', unsafe_allow_html=True)
            with row_cols[2 + col_offset]:
                st.markdown(f'<div class="expense-cell expense-cell-secondary">{row["category"]}</div>', unsafe_allow_html=True)
            with row_cols[3 + col_offset]:
                st.markdown(f'<div class="expense-cell expense-cell-user">{row["paid_by"]}</div>', unsafe_allow_html=True)
            with row_cols[4 + col_offset]:
                st.markdown(f'<div class="expense-cell expense-cell-secondary">{row["expense_type"]}</div>', unsafe_allow_html=True)
            with row_cols[5 + col_offset]:
                st.markdown(
                    f'<div class="expense-cell expense-cell-amount{amount_modifier}">{format_currency(float(row["amount"]))}</div>',
                    unsafe_allow_html=True,
                )
            st.markdown('<div class="expense-card"></div>', unsafe_allow_html=True)
    if delete_mode:
        normalized_selected_ids = sorted(next_selected_ids)
        st.session_state.expense_delete_selected_ids = normalized_selected_ids
        st.session_state.expense_delete_select_all = bool(normalized_selected_ids) and len(normalized_selected_ids) == len(visible_ids)
    st.markdown("</div>", unsafe_allow_html=True)


def render_couple_balance_total(dataframe: pd.DataFrame) -> None:
    unsettled_expenses = dataframe[~dataframe["is_settled"].astype(bool)].copy() if not dataframe.empty else dataframe
    unsettled_total = float(unsettled_expenses["amount"].sum()) if not unsettled_expenses.empty else 0.0
    current_username = str((st.session_state.current_user or {}).get("username", "") or "")
    balance = compute_couple_balance(current_username, dataframe)
    render_total_sticky_amount(unsettled_total, build_couple_balance_label(balance))


def render_couple_balance_feed(dataframe: pd.DataFrame) -> None:
    if dataframe.empty:
        if str(st.session_state.get("expense_search_query", "") or "").strip():
            st.info("Nessuna spesa condivisa trovata con questa ricerca.")
        else:
            st.info("Nessuna spesa condivisa trovata con i filtri selezionati.")
        return

    current_username = str((st.session_state.current_user or {}).get("username", "") or "")
    st.markdown('<div class="expense-list">', unsafe_allow_html=True)
    for _, row in dataframe.iterrows():
        expense_id = int(row["id"])
        is_settled = bool(row.get("is_settled", False))
        expense_name = str(row.get("name") or row.get("description") or "Spesa condivisa")
        date_label = row["expense_date"].strftime("%d/%m")
        status_label = "Pagata" if is_settled else "Da regolare"
        status_class = "couple-balance-status-settled" if is_settled else "couple-balance-status-open"
        action_label = "Ricevuta" if str(row.get("paid_by") or "") == current_username else "Pagata"

        with st.container(key=f"couple_balance_row_{expense_id}"):
            row_cols = st.columns([0.11, 0.24, 0.15, 0.13, 0.13, 0.12, 0.12], vertical_alignment="center")
            with row_cols[0]:
                st.markdown(f'<div class="expense-cell expense-cell-secondary">{date_label}</div>', unsafe_allow_html=True)
            with row_cols[1]:
                st.markdown(f'<div class="expense-cell expense-cell-name">{expense_name}</div>', unsafe_allow_html=True)
            with row_cols[2]:
                st.markdown(f'<div class="expense-cell expense-cell-secondary">{row["category"]}</div>', unsafe_allow_html=True)
            with row_cols[3]:
                st.markdown(f'<div class="expense-cell expense-cell-user">{row["paid_by"]}</div>', unsafe_allow_html=True)
            with row_cols[4]:
                st.markdown(
                    f'<div class="expense-cell expense-cell-amount">{format_currency(float(row["amount"]))}</div>',
                    unsafe_allow_html=True,
                )
            with row_cols[5]:
                st.markdown(
                    f'<div class="expense-cell"><span class="couple-balance-status-pill {status_class}">{status_label}</span></div>',
                    unsafe_allow_html=True,
                )
            with row_cols[6]:
                checkbox_value = st.checkbox(
                    action_label,
                    value=is_settled,
                    key=f"couple_balance_toggle_{expense_id}",
                    label_visibility="visible",
                )
                if checkbox_value != is_settled:
                    update_expense_settled(expense_id, checkbox_value)
                    st.rerun()
            st.markdown('<div class="expense-card"></div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render_couple_balance_page(selected_month: str) -> None:
    shared_expenses = get_shared_expenses()
    current_user = st.session_state.current_user or {}
    current_username = str(current_user.get("username", "") or "")
    if current_username:
        shared_expenses = get_visible_expenses(shared_expenses, current_username)

    if selected_month != "Tutti" and not shared_expenses.empty:
        shared_expenses = shared_expenses[shared_expenses["month_label"] == selected_month].copy()

    balance_view: dict[str, pd.DataFrame | None] = {
        "base_visible": None,
        "rendered": None,
    }

    def render_balance_main_block() -> None:
        base_visible_expenses, rendered_expenses = render_couple_balance_header_block(shared_expenses)
        balance_view["base_visible"] = base_visible_expenses
        balance_view["rendered"] = rendered_expenses

    render_section_header_layout(
        section_key="expense",
        month_label=selected_month,
        month_key_prefix="expense_month",
        render_main_block=render_balance_main_block,
        render_tools_block=lambda: render_expense_tools(
            balance_view["base_visible"] if isinstance(balance_view["base_visible"], pd.DataFrame) else pd.DataFrame(),
            allow_edit_mode=False,
            allow_delete_mode=False,
        ),
        render_total_block=lambda: render_couple_balance_total(shared_expenses),
        render_feed_block=lambda: render_couple_balance_feed(
            balance_view["rendered"] if isinstance(balance_view["rendered"], pd.DataFrame) else pd.DataFrame()
        ),
        render_post_tools_block=None,
        edit_mode=False,
    )


def render_edit_section(dataframe: pd.DataFrame) -> None:
    if dataframe.empty:
        st.info("Seleziona un filtro diverso o aggiungi una spesa per modificarla.")
        return

    category_options = get_categories()
    paid_by_usernames = get_usernames()
    current_username = (st.session_state.current_user or {}).get("username", "")

    options = {
        build_expense_option_label(row): int(row["id"])
        for _, row in dataframe.iterrows()
    }

    option_labels = list(options.keys())
    preselected_expense_id = st.session_state.pop("preselected_expense_id", None)
    default_index = 0
    if preselected_expense_id is not None:
        for index, label in enumerate(option_labels):
            if options[label] == preselected_expense_id:
                default_index = index
                break

    selected_label = st.selectbox("Scegli una spesa", option_labels, index=default_index)
    selected_expense_id = options[selected_label]
    expense = get_expense_by_id(selected_expense_id, current_username)

    if expense is None:
        st.warning("La spesa selezionata non esiste piu.")
        return

    amount_state_key = f"edit_expense_amount_raw_{selected_expense_id}"
    if amount_state_key not in st.session_state:
        st.session_state[amount_state_key] = f"{float(expense['amount']):.2f}".replace(".", ",")

    with st.form("edit_expense_form"):
        with st.container(key="edit_expense_amount_row"):
            _, currency_col, amount_col, _ = st.columns([0.22, 0.12, 0.26, 0.40], vertical_alignment="center")
            with currency_col:
                with st.container(key="edit_expense_amount_currency"):
                    st.markdown('<div class="new-expense-amount-currency">€</div>', unsafe_allow_html=True)
            with amount_col:
                amount_raw = st.text_input(
                    "Importo modifica",
                    value=st.session_state.get(amount_state_key, "0,00"),
                    key=amount_state_key,
                )

        normalize_amount_input(amount_state_key)
        normalized_amount = str(st.session_state.get(amount_state_key, "0,00")).replace(",", ".").strip()
        try:
            amount = float(normalized_amount) if normalized_amount else 0.0
        except ValueError:
            amount = float(expense["amount"])

        name = st.text_input("Nome modifica", value=expense.get("name", expense["description"]))
        expense_date = st.date_input("Data modifica", value=expense["expense_date"], format="YYYY-MM-DD")

        col3, col4 = st.columns(2)
        category = col3.selectbox(
            "Categoria modifica",
            category_options,
            index=category_options.index(expense["category"]) if expense["category"] in category_options else 0,
        )
        col4.write("")

        description = st.text_area("Descrizione modifica", value=expense["description"])

        col5, col6 = st.columns(2)
        expense_type = col6.selectbox(
            "Tipo spesa modifica",
            EXPENSE_TYPE_OPTIONS,
            index=EXPENSE_TYPE_OPTIONS.index(expense["expense_type"]),
        )
        if expense_type == "Personale":
            paid_by = current_username
            col5.text_input("Persona che ha pagato", value=current_username, disabled=True)
            split_type = "equal"
            split_ratio = 1.0
        else:
            paid_by = col5.selectbox(
                "Persona che ha pagato",
                paid_by_usernames,
                index=paid_by_usernames.index(expense["paid_by"]) if expense["paid_by"] in paid_by_usernames else 0,
            )
            default_split_type = expense.get("split_type", "equal") or "equal"
            split_type = st.segmented_control(
                "Divisione modifica",
                SHARED_SPLIT_OPTIONS,
                format_func=lambda value: "50/50" if value == "equal" else "Personalizzata",
                default=default_split_type,
                key=f"edit_expense_split_type_{selected_expense_id}",
            )
            split_ratio = 0.5 if split_type == "equal" else float(expense.get("split_ratio") or 0.5)
            if split_type == "custom":
                split_ratio = st.slider(
                    "Quota di chi paga vs quota partner",
                    min_value=0,
                    max_value=100,
                    value=int(split_ratio * 100),
                    key=f"edit_expense_split_ratio_{selected_expense_id}",
                    help="La percentuale rappresenta la quota di chi paga.",
                ) / 100
            st.caption("Per default le spese condivise sono 50/50.")
        if expense_type == "Personale":
            st.caption("Le spese personali restano private e fuori dal saldo.")

        save_col, delete_col = st.columns(2)
        save_clicked = save_col.form_submit_button("Aggiorna spesa", use_container_width=True)
        delete_clicked = delete_col.form_submit_button("Elimina spesa", use_container_width=True)

        if save_clicked:
            payload = {
                "amount": amount,
                "name": name,
                "description": description,
                "expense_type": expense_type,
                "split_type": split_type,
                "split_ratio": split_ratio,
            }
            errors = validate_expense_data(payload)
            if errors:
                for error in errors:
                    st.error(error)
            else:
                updated = update_expense(
                    expense_id=selected_expense_id,
                    current_username=current_username,
                    expense_date=expense_date,
                    amount=amount,
                    name=name,
                    category=category,
                    description=description,
                    paid_by=paid_by,
                    expense_type=expense_type,
                    split_type=split_type,
                    split_ratio=split_ratio,
                )
                if updated:
                    st.session_state.show_edit_expense_modal = False
                    st.success("Spesa aggiornata con successo.")
                    st.rerun()
                else:
                    st.error("Non sei autorizzato a modificare questa spesa.")

        if delete_clicked:
            if delete_expense(selected_expense_id, current_username):
                st.session_state.show_edit_expense_modal = False
                st.success("Spesa eliminata con successo.")
                st.rerun()
            else:
                st.error("Non sei autorizzato a eliminare questa spesa.")


def render_charts(dataframe: pd.DataFrame) -> None:
    if dataframe.empty:
        st.info("Non ci sono dati da visualizzare nei grafici.")
        return

    category_chart = dataframe.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
    monthly_chart = (
        dataframe.groupby("month_label", as_index=False)["amount"].sum().sort_values("month_label")
    )
    monthly_chart = monthly_chart.rename(columns={"month_label": "Mese", "amount": "Totale"})

    left_chart, right_chart = st.columns(2)
    with left_chart:
        st.caption("Spese per categoria")
        st.bar_chart(category_chart.set_index("category"), color="#b45d34")

    with right_chart:
        st.caption("Andamento mensile")
        st.line_chart(monthly_chart.set_index("Mese"), color="#4f7a5c")


def render_export_section(dataframe: pd.DataFrame) -> None:
    csv_data = export_expenses_to_csv(dataframe)
    if not csv_data:
        st.info("Non ci sono dati da esportare con i filtri attuali.")
        return

    st.caption("Esporta le spese filtrate")
    csv_col, pdf_col = st.columns(2)
    csv_col.download_button(
        label="Scarica CSV",
        data=csv_data,
        file_name="spese_filtrate.csv",
        mime="text/csv",
        use_container_width=True,
    )
    if REPORTLAB_AVAILABLE:
        pdf_data = export_expenses_to_pdf(dataframe)
        pdf_col.download_button(
            label="Scarica PDF",
            data=pdf_data,
            file_name="spese_filtrate.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    else:
        pdf_col.button(
            "Scarica PDF",
            disabled=True,
            use_container_width=True,
            help="Installa reportlab per attivare l'esportazione PDF.",
        )


def render_category_dashboard(dataframe: pd.DataFrame) -> None:
    if dataframe.empty:
        st.info("Non ci sono spese da analizzare nelle categorie con i filtri attuali.")
        return

    summary = build_category_summary(dataframe)
    if summary.empty:
        st.info("Non ci sono categorie da mostrare.")
        return

    search_term = st.text_input(
        "Cerca categoria",
        placeholder="Scrivi una categoria, ad esempio Casa o Spesa",
        help="Filtra le categorie visibili e apri il dettaglio cliccando sulla card.",
    ).strip()

    filtered_summary = summary.copy()
    if search_term:
        filtered_summary = filtered_summary[
            filtered_summary["category"].str.contains(search_term, case=False, na=False)
        ]

    if filtered_summary.empty:
        st.info("Nessuna categoria trovata con questa ricerca.")
        return

    with st.expander("Panoramica categorie", expanded=False):
        columns = st.columns(3, gap="medium")
        for index, (_, row) in enumerate(filtered_summary.iterrows()):
            category_name = str(row["category"])
            icon = CATEGORY_ICONS.get(category_name, "●")
            label = (
                f"{icon}\n"
                f"{category_name}\n"
                f"{format_currency(float(row['totale']))}"
            )
            with columns[index % 3]:
                if st.button(
                    label,
                    key=f"open_category_{category_name}",
                    use_container_width=True,
                    type="secondary",
                ):
                    st.session_state.selected_category = category_name
                    st.session_state.current_view = "category_detail"
                    st.rerun()

    render_recent_expenses_expander(dataframe)


def render_recent_expenses_expander(dataframe: pd.DataFrame) -> None:
    if dataframe.empty:
        return

    cutoff_date = pd.Timestamp(date.today()) - pd.Timedelta(days=9)
    recent_expenses = dataframe[dataframe["expense_date"] >= cutoff_date].copy()
    recent_expenses = recent_expenses.sort_values(by=["expense_date", "id"], ascending=[False, False]).head(10)

    with st.expander("Spese recenti", expanded=False):
        if recent_expenses.empty:
            st.info("Nessuna spesa negli ultimi 10 giorni con i filtri attivi.")
            return

        for _, row in recent_expenses.iterrows():
            title = str(row.get("name") or row.get("description") or "Spesa")
            details = (
                f"{row['expense_date'].strftime('%Y-%m-%d')}  |  "
                f"{row['category']}  |  "
                f"{format_currency(float(row['amount']))}"
            )
            extra = f"{row['paid_by']}  |  {row['expense_type']}"

            content_col, action_col = st.columns([0.92, 0.08], vertical_alignment="center")
            with content_col:
                st.markdown(f"**{title}**")
                st.caption(details)
                st.caption(extra)
            with action_col:
                if st.button("✎", key=f"edit_recent_{int(row['id'])}", help="Modifica spesa"):
                    st.session_state.preselected_expense_id = int(row["id"])
                    st.session_state.show_edit_expense_modal = True
                    st.rerun()
            st.divider()




def render_summary_workspace(filtered_expenses: pd.DataFrame, filtered_incomes: pd.DataFrame) -> None:
    controls_col, action_col = st.columns([0.82, 0.18], vertical_alignment="center")
    with controls_col:
        show_analysis = st.toggle(
            "Mostra analisi",
            value=bool(st.session_state.get("summary_show_analysis", False)),
            key="summary_show_analysis_toggle",
        )
        st.session_state.summary_show_analysis = show_analysis
    with action_col:
        if st.button("Aggiungi categoria", key="summary_add_category_toggle", use_container_width=True, type="secondary"):
            st.session_state.summary_show_add_category = not bool(st.session_state.get("summary_show_add_category", False))
            st.rerun()

    if st.session_state.get("summary_show_add_category", False):
        open_section("Aggiungi categoria", "Una nuova categoria sara disponibile nei form delle spese.")
        render_add_category_form()
        close_section()
        st.write("")

    open_section("Riepilogo", "Elenco completo delle spese con i filtri attivi.")
    render_expense_list(filtered_expenses)
    st.write("")
    render_export_section(filtered_expenses)
    close_section()

    if st.session_state.get("summary_show_analysis", False):
        st.write("")
        open_section("Analisi", "Grafici e confronto tra entrate e uscite del periodo filtrato.")
        render_charts(filtered_expenses)
        st.write("")
        render_income_expense_analysis(filtered_incomes, filtered_expenses)
        close_section()


def render_operation_detail_page(filtered_expenses: pd.DataFrame, filtered_incomes: pd.DataFrame) -> None:
    current_view = st.session_state.get("current_view", "home")
    view_config = {
        "summary": (
            "Riepilogo",
            "Tutte le spese visibili con i filtri attivi, con esportazione e strumenti utili.",
        ),
    }

    if current_view not in view_config:
        st.session_state.current_view = "summary"
        current_view = "summary"

    title, subtitle = view_config[current_view]
    st.markdown(
        f"""
        <div class="hero-card">
            <h1 style="margin:0; font-size:2rem;">{title}</h1>
            <p style="margin:0.8rem 0 0 0; max-width:780px; opacity:0.92; font-size:1rem;">
                {subtitle}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    back_col, info_col = st.columns([0.08, 0.92])
    with back_col:
        back_clicked = render_back_circle_button("back_to_operations")
    if back_clicked:
        st.session_state.current_view = "home"
        st.session_state.current_section = "Home"
        st.session_state.pending_section_navigation_sync = True
        st.rerun()
    info_col.caption("Usa la sidebar per mantenere i filtri attivi anche nelle schermate operative.")

    if current_view == "summary":
        render_summary_workspace(filtered_expenses, filtered_incomes)


def render_add_category_form() -> None:
    with st.form("add_category_form", clear_on_submit=True):
        category_name = st.text_input("Nome nuova categoria")
        submitted = st.form_submit_button("Salva categoria", use_container_width=True)
        if submitted:
            success, message = add_category(category_name)
            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    existing_categories = get_categories()
    st.caption("Categorie disponibili")
    if not existing_categories:
        st.info("Non ci sono categorie disponibili.")
        return

    for category_name in existing_categories:
        name_col, action_col = st.columns([0.9, 0.1], vertical_alignment="center")
        with name_col:
            st.write(category_name)
        with action_col:
            if st.button("✕", key=f"delete_category_{category_name}", help="Elimina categoria"):
                success, message = delete_category(category_name)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)


def render_create_income_form() -> None:
    with st.form("create_income_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        income_date = col1.date_input("Data entrata", value=date.today(), format="YYYY-MM-DD")
        amount = col2.number_input("Importo entrata", min_value=0.0, step=50.0, format="%.2f")

        source = st.text_input("Fonte entrata", placeholder="Stipendio, freelance, rimborso...")
        description = st.text_input("Descrizione entrata")
        submitted = st.form_submit_button("Salva entrata", use_container_width=True)
        if submitted:
            payload = {"amount": amount, "source": source, "description": description}
            errors = validate_income_data(payload)
            if errors:
                for error in errors:
                    st.error(error)
            else:
                create_income(
                    income_date=income_date,
                    amount=amount,
                    source=source,
                    description=description,
                    owner=st.session_state.current_user["username"],
                )
                st.session_state.show_new_income_modal = False
                st.success("Entrata salvata con successo.")
                st.rerun()


def render_income_tools() -> None:
    with st.container(key="income_toolbar_shell"):
        back_col, edit_col, sort_col, search_col, _ = st.columns([0.08, 0.22, 0.08, 0.08, 0.54], vertical_alignment="center")
        with back_col:
            with st.container(key="income_toolbar_back_item"):
                is_confirmed_search = bool(
                    st.session_state.get("income_search_confirmed", False)
                    and st.session_state.get("income_search_query", "")
                )
                if st.button(
                    "",
                    key="income_search_reset_button",
                    use_container_width=False,
                    type="secondary",
                    icon=":material/arrow_back:",
                    disabled=not is_confirmed_search,
                ):
                    st.session_state.income_search_query = ""
                    st.session_state.income_search_confirmed = False
                    st.rerun()
        with edit_col:
            with st.container(key="income_toolbar_edit_item"):
                is_edit_mode = st.session_state.get("income_edit_mode", False)
                edit_button_type = "primary" if is_edit_mode else "secondary"
                if st.button("Modifica entrata", key="income_edit_mode_toggle", use_container_width=False, type=edit_button_type):
                    st.session_state.income_edit_mode = not is_edit_mode
                    st.rerun()
        with sort_col:
            with st.container(key="income_toolbar_sort_item"):
                with st.container(key="income_sort_toggle"):
                    with st.popover("", use_container_width=False, icon=":material/tune:"):
                        with st.container(key="income_sort_menu"):
                            sort_options = [
                                "Data piu recente",
                                "Importo maggiore",
                                "Importo minore",
                            ]
                            current_sort = st.session_state.get("income_sort_mode", sort_options[0])
                            selected_sort = st.radio(
                                "Ordina entrate",
                                sort_options,
                                index=sort_options.index(current_sort) if current_sort in sort_options else 0,
                                label_visibility="collapsed",
                                key="income_sort_mode",
                            )
                            if selected_sort != current_sort:
                                st.session_state.income_sort_mode = selected_sort
                                st.rerun()
        with search_col:
            with st.container(key="income_toolbar_search_item"):
                with st.container(key="income_search_toggle"):
                    with st.popover("", use_container_width=False, icon=":material/search:"):
                        with st.container(key="income_search_menu"):
                            live_value = render_live_search(
                                st.session_state.get("income_search_query", ""),
                                key="income_search_query_live",
                                placeholder="Cerca per nome",
                            )
                            if live_value == EXPENSE_SEARCH_RESET_SIGNAL:
                                if st.session_state.get("income_search_query", "") or st.session_state.get("income_search_confirmed", False):
                                    st.session_state.income_search_query = ""
                                    st.session_state.income_search_confirmed = False
                                    st.rerun()
                            elif isinstance(live_value, str) and live_value.startswith(EXPENSE_SEARCH_CONFIRM_PREFIX):
                                confirmed_value = live_value.removeprefix(EXPENSE_SEARCH_CONFIRM_PREFIX)
                                st.session_state.income_search_query = confirmed_value
                                st.session_state.income_search_confirmed = bool(confirmed_value.strip())
                                st.rerun()
                            elif live_value != st.session_state.get("income_search_query", ""):
                                st.session_state.income_search_query = live_value
                                if not str(live_value).strip():
                                    st.session_state.income_search_confirmed = False
                                st.rerun()


def render_income_info_block(top_source: str, latest_date: str) -> None:
    with st.container(key="income_header_info"):
        active_focus = st.session_state.get("income_info_focus", "source")
        with st.container(key="income_info_tabs_row"):
            source_col, latest_col = st.columns(2, vertical_alignment="center")
            with source_col:
                with st.container(key="income_info_source_tab"):
                    if st.button(
                        "Fonte principale",
                        key="income_info_source_button",
                        use_container_width=True,
                        type="primary" if active_focus == "source" else "secondary",
                    ):
                        st.session_state.income_info_focus = "source"
                        st.rerun()
            with latest_col:
                with st.container(key="income_info_latest_tab"):
                    if st.button(
                        "Ultima entrata",
                        key="income_info_latest_button",
                        use_container_width=True,
                        type="primary" if active_focus == "latest" else "secondary",
                    ):
                        st.session_state.income_info_focus = "latest"
                        st.rerun()

        active_focus = st.session_state.get("income_info_focus", "source")
        with st.container(key="income_info_value_row"):
            source_value = f'<div class="income-info-active-value">{escape(str(top_source))}</div>' if active_focus == "source" else ""
            latest_value = f'<div class="income-info-active-value">{escape(str(latest_date))}</div>' if active_focus == "latest" else ""
            st.markdown(
                f"""
                <div class="income-info-value-grid">
                    <div class="income-info-value-cell">{source_value}</div>
                    <div class="income-info-value-cell">{latest_value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_income_header_block(top_source: str, latest_date: str) -> None:
    with st.container(key="income_header_content"):
        render_income_info_block(str(top_source), latest_date)


def render_edit_income_section(dataframe: pd.DataFrame) -> None:
    if dataframe.empty:
        st.info("Seleziona un filtro diverso o aggiungi un'entrata per modificarla.")
        return

    options = {
        f"{row['income_date'].strftime('%d/%m')} · {row['source']} · {format_currency(float(row['amount']))}": int(row["id"])
        for _, row in dataframe.iterrows()
    }
    option_labels = list(options.keys())
    preselected_income_id = st.session_state.pop("preselected_income_id", None)
    default_index = 0
    if preselected_income_id is not None:
        for index, label in enumerate(option_labels):
            if options[label] == preselected_income_id:
                default_index = index
                break

    selected_label = st.selectbox("Scegli un'entrata", option_labels, index=default_index)
    selected_income_id = options[selected_label]
    income = get_income_by_id(selected_income_id, current_username)

    if income is None:
        st.warning("L'entrata selezionata non esiste piu.")
        return

    with st.form("edit_income_form"):
        income_date = st.date_input("Data entrata", value=income["income_date"], format="YYYY-MM-DD")
        amount = st.number_input("Importo entrata", min_value=0.0, value=float(income["amount"]), step=50.0, format="%.2f")
        source = st.text_input("Fonte entrata", value=income["source"])
        description = st.text_input("Descrizione entrata", value=income.get("description", ""))

        save_col, delete_col = st.columns(2)
        save_clicked = save_col.form_submit_button("Aggiorna entrata", use_container_width=True)
        delete_clicked = delete_col.form_submit_button("Elimina entrata", use_container_width=True)

        if save_clicked:
            payload = {"amount": amount, "source": source, "description": description}
            errors = validate_income_data(payload)
            if errors:
                for error in errors:
                    st.error(error)
            else:
                updated = update_income(
                    income_id=selected_income_id,
                    current_username=current_username,
                    income_date=income_date,
                    amount=amount,
                    source=source,
                    description=description,
                )
                if updated:
                    st.session_state.show_edit_income_modal = False
                    st.success("Entrata aggiornata con successo.")
                    st.rerun()
                else:
                    st.error("Non sei autorizzato a modificare questa entrata.")

        if delete_clicked:
            if delete_income(selected_income_id, current_username):
                st.session_state.show_edit_income_modal = False
                st.success("Entrata eliminata con successo.")
                st.rerun()
            else:
                st.error("Non sei autorizzato a eliminare questa entrata.")


def build_rendered_income_dataset(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty:
        return dataframe.copy()

    rendered_incomes = dataframe.copy()
    search_query = str(st.session_state.get("income_search_query", "") or "").strip().lower()
    if search_query:
        rendered_incomes = rendered_incomes[
            rendered_incomes["source"].fillna("").astype(str).str.lower().str.contains(search_query, na=False)
        ].copy()

    sort_mode = st.session_state.get("income_sort_mode", "Data piu recente")
    if rendered_incomes.empty:
        return rendered_incomes

    if sort_mode == "Importo maggiore":
        return rendered_incomes.sort_values(["amount", "income_date", "id"], ascending=[False, False, False]).copy()
    if sort_mode == "Importo minore":
        return rendered_incomes.sort_values(["amount", "income_date", "id"], ascending=[True, False, False]).copy()
    return rendered_incomes.sort_values(["income_date", "id"], ascending=[False, False]).copy()


def render_incomes_section(dataframe: pd.DataFrame, selected_month: str | None = None) -> None:
    if dataframe.empty:
        st.info("Nessuna entrata trovata per il periodo selezionato.")
        return

    sorted_frame = build_rendered_income_dataset(dataframe)
    if sorted_frame.empty:
        if str(st.session_state.get("income_search_query", "") or "").strip():
            st.info("Nessuna entrata trovata con questa ricerca.")
        else:
            st.info("Nessuna entrata trovata per il periodo selezionato.")
        return

    total_amount = float(sorted_frame["amount"].sum())
    latest_date = sorted_frame.iloc[0]["income_date"].strftime("%d/%m")
    top_source = (
        sorted_frame.groupby("source", dropna=False)["amount"].sum().sort_values(ascending=False).index[0]
        if not sorted_frame.empty else "-"
    )
    edit_mode = st.session_state.get("income_edit_mode", False)

    def render_income_feed_block() -> None:
        st.markdown('<div class="income-list">', unsafe_allow_html=True)
        for _, row in sorted_frame.iterrows():
            description = str(row.get("description") or "").strip()
            date_label = row["income_date"].strftime("%d/%m")
            with st.container(key=f"income_row_{int(row['id'])}"):
                row_cols = st.columns([0.16, 0.28, 0.38, 0.18], vertical_alignment="center")
                with row_cols[0]:
                    st.markdown(f'<div class="income-cell income-cell-secondary">{date_label}</div>', unsafe_allow_html=True)
                with row_cols[1]:
                    if edit_mode:
                        if st.button(str(row["source"]), key=f"income_name_pick_{int(row['id'])}", use_container_width=True, type="tertiary"):
                            st.session_state.preselected_income_id = int(row["id"])
                            st.session_state.show_edit_income_modal = True
                            st.rerun()
                    else:
                        st.markdown(f'<div class="income-cell income-cell-source">{row["source"]}</div>', unsafe_allow_html=True)
                with row_cols[2]:
                    st.markdown(f'<div class="income-cell income-cell-secondary">{description or "Entrata"}</div>', unsafe_allow_html=True)
                with row_cols[3]:
                    st.markdown(f'<div class="income-cell income-cell-amount">{format_currency(float(row["amount"]))}</div>', unsafe_allow_html=True)
                st.markdown('<div class="income-card"></div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    render_income_section_layout(
        month_label=selected_month,
        render_main_block=lambda: render_income_header_block(str(top_source), latest_date),
        render_lower_block=lambda: render_income_lower_layout(
            render_tools_block=render_income_tools,
            render_total_block=lambda: render_total_sticky_amount(total_amount),
            render_feed_block=render_income_feed_block,
            edit_mode=edit_mode,
        ),
        edit_mode=edit_mode,
    )


def render_income_expense_analysis(all_incomes: pd.DataFrame, all_expenses: pd.DataFrame) -> None:
    st.caption("Confronto mensile tra entrate e uscite")
    summary = build_income_vs_expense_summary(all_incomes, all_expenses)
    if summary.empty:
        st.info("Non ci sono abbastanza dati per confrontare entrate e uscite.")
        return

    latest = summary.iloc[-1]
    col1, col2, col3 = st.columns(3)
    col1.metric("Entrate ultimo mese", format_currency(float(latest["Entrate"])))
    col2.metric("Uscite ultimo mese", format_currency(float(latest["Uscite"])))
    col3.metric("Saldo ultimo mese", format_currency(float(latest["Saldo"])))

    chart_data = summary.rename(columns={"month_label": "Mese"}).set_index("Mese")
    st.line_chart(chart_data[["Entrate", "Uscite", "Saldo"]])


def render_dashboard_detail_page(all_expenses: pd.DataFrame, all_incomes: pd.DataFrame, selected_month: str) -> None:
    metric_key = st.session_state.get("dashboard_metric")
    current_user = st.session_state.current_user or {}
    current_username = current_user.get("username", "")
    month_data = all_expenses if selected_month == "Tutti" else all_expenses[all_expenses["month_label"] == selected_month]
    month_incomes = all_incomes if selected_month == "Tutti" else all_incomes[all_incomes["month_label"] == selected_month]

    view_map = {
        "total_incomes": (
            "Entrate",
            "Tutte le entrate del periodo selezionato.",
            month_incomes,
            "income",
        ),
        "total_month": (
            "Uscite",
            "Tutte le spese del periodo selezionato.",
            month_data,
            "expense",
        ),
        "my_personal": (
            "Personali",
            "Solo le spese personali pagate da me.",
            month_data[(month_data["expense_type"] == "Personale") & (month_data["owner"] == current_username)],
            "expense",
        ),
        "shared_total": (
            "Condivise",
            "Tutte le spese condivise del periodo selezionato.",
            month_data[month_data["expense_type"] == "Condivisa"],
            "expense",
        ),
        "net_month": (
            "Saldo",
            "Differenza tra entrate e uscite del periodo selezionato.",
            pd.DataFrame(),
            "net",
        ),
        "balance": (
            "Saldo coppia",
            "Dettaglio delle spese condivise che compongono il saldo tra voi due.",
            month_data[month_data["expense_type"] == "Condivisa"],
            "expense",
        ),
    }

    if metric_key not in view_map:
        st.session_state.current_view = "home"
        st.rerun()

    title, subtitle, detail_frame, detail_type = view_map[metric_key]
    st.markdown(
        f"""
        <div class="hero-card">
            <div style="letter-spacing:0.08em; text-transform:uppercase; font-size:0.82rem; opacity:0.78; margin-bottom:0.45rem;">
                Dashboard
            </div>
            <h1 style="margin:0; font-size:2rem;">{title}</h1>
            <p style="margin:0.8rem 0 0 0; max-width:780px; opacity:0.92; font-size:1rem;">
                {subtitle}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    back_col, info_col = st.columns([0.08, 0.92])
    with back_col:
        back_clicked = render_back_circle_button("back_to_dashboard")
    if back_clicked:
        st.session_state.current_view = "home"
        st.rerun()
    info_col.caption(f"Mese attivo nella dashboard: {selected_month}")

    open_section(title, "Elenco delle spese che compongono la voce selezionata.")
    if detail_frame.empty:
        if detail_type == "net":
            total_incomes = float(month_incomes["amount"].sum()) if not month_incomes.empty else 0.0
            total_expenses = float(month_data["amount"].sum()) if not month_data.empty else 0.0
            st.write(f"Entrate: {format_currency(total_incomes)}")
            st.write(f"Uscite: {format_currency(total_expenses)}")
            st.write(f"Saldo del periodo: {format_currency(total_incomes - total_expenses)}")
        else:
            st.info("Nessuna spesa trovata per questa voce della dashboard.")
    else:
        if detail_type == "income":
            render_incomes_section(detail_frame)
        else:
            render_expense_list(detail_frame)
    close_section()


def render_profile_page() -> None:
    current_user = st.session_state.get("current_user") or {}
    user_id = current_user.get("id")
    user = get_user_by_id(user_id) if user_id else None

    if user is None:
        st.session_state.current_view = "home"
        st.rerun()

    st.markdown(
        """
        <div class="hero-card">
            <div style="letter-spacing:0.08em; text-transform:uppercase; font-size:0.82rem; opacity:0.78; margin-bottom:0.45rem;">
                Profilo
            </div>
            <h1 style="margin:0; font-size:2rem;">Dati utente</h1>
            <p style="margin:0.8rem 0 0 0; max-width:780px; opacity:0.92; font-size:1rem;">
                Qui puoi modificare i dati personali salvati per il tuo accesso.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    back_col, info_col = st.columns([0.08, 0.92])
    with back_col:
        back_clicked = render_back_circle_button("back_to_home_from_profile")
    if back_clicked:
        st.session_state.current_view = "home"
        st.rerun()
    info_col.caption("I dati salvati qui vengono riutilizzati per il login e per il profilo.")

    open_section("Profilo utente", "Aggiorna i dati salvati per questo account.")
    with st.form("profile_form"):
        full_name = st.text_input("Nome completo", value=user.get("full_name", ""))
        username = st.text_input("Username", value=user.get("username", ""))
        email = st.text_input("Email", value=user.get("email", ""))
        new_password = st.text_input("Nuova password", type="password", help="Lascia vuoto per non cambiarla.")
        submitted = st.form_submit_button("Salva modifiche", use_container_width=True)

        if submitted:
            success, message, updated_user = update_user_profile(
                user_id=user["id"],
                full_name=full_name,
                username=username,
                email=email,
                new_password=new_password,
            )
            if success and updated_user is not None:
                st.session_state.current_user = updated_user
                st.success(message)
                st.rerun()
            else:
                st.error(message)
    close_section()


def render_category_detail_page(filtered_expenses: pd.DataFrame) -> None:
    selected_category = st.session_state.get("selected_category")
    if not selected_category:
        st.session_state.current_view = "home"
        st.session_state.current_section = "Uscite"
        st.session_state.pending_section_navigation_sync = True
        st.rerun()

    category_expenses = filtered_expenses[filtered_expenses["category"] == selected_category].copy()

    st.markdown(
        f"""
        <div class="hero-card">
            <div style="letter-spacing:0.08em; text-transform:uppercase; font-size:0.82rem; opacity:0.78; margin-bottom:0.45rem;">
                Dettaglio categoria
            </div>
            <h1 style="margin:0; font-size:2rem;">{selected_category}</h1>
            <p style="margin:0.8rem 0 0 0; max-width:780px; opacity:0.92; font-size:1rem;">
                Vista dedicata della categoria selezionata. Qui trovi solo le spese di questa categoria
                con i filtri attivi della sidebar gia applicati.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    back_col, info_col = st.columns([0.08, 0.92])
    with back_col:
        back_clicked = render_back_circle_button("back_to_categories")
    if back_clicked:
        st.session_state.current_view = "home"
        st.session_state.current_section = "Uscite"
        st.session_state.pending_section_navigation_sync = True
        st.rerun()
    info_col.caption("La sidebar continua a controllare mese, persona e tipo spesa.")

    if category_expenses.empty:
        st.info("Nessuna spesa trovata per questa categoria con i filtri correnti.")
        return

    summary = build_category_summary(category_expenses)
    category_row = summary.iloc[0]

    stat1, stat2, stat3 = st.columns(3)
    stat1.metric("Totale categoria", format_currency(float(category_row["totale"])))
    stat2.metric("Numero spese", int(category_row["numero_spese"]))
    stat3.metric(
        "Spese condivise",
        int((category_expenses["expense_type"] == "Condivisa").sum()),
    )

    open_section("Spese della categoria", "Elenco dettagliato dei movimenti appartenenti a questa categoria.")
    for _, row in category_expenses.iterrows():
        expense_name = str(row.get("name") or row.get("description") or "Spesa")
        description = str(row.get("description") or "").strip()
        split_type = str(row.get("split_type") or "equal")
        split_ratio = float(row.get("split_ratio") or 0.5)
        split_label = "50/50" if split_type == "equal" else f"Personalizzata {int(split_ratio * 100)}% / {int((1 - split_ratio) * 100)}%"
        with st.container(border=True):
            st.markdown(f"**{expense_name}**")
            meta_line = (
                f"Data: {row['expense_date'].strftime('%Y-%m-%d')}  |  "
                f"Importo: {format_currency(float(row['amount']))}  |  "
                f"Pagato da: {row['paid_by']}"
            )
            st.caption(meta_line)
            details_line = (
                f"Tipo: {row['expense_type']}  |  "
                f"Proprietario: {row.get('owner') or '-'}  |  "
                f"Divisione: {split_label}"
            )
            st.caption(details_line)
            if description:
                st.caption(f"Note: {description}")
    close_section()


def build_expense_option_label(row: pd.Series) -> str:
    date_label = row["expense_date"].strftime("%Y-%m-%d")
    name_label = row.get("name", row["description"])
    return f"#{int(row['id'])} | {date_label} | {name_label} | {format_currency(float(row['amount']))}"


def build_balance_label(balance: float) -> str:
    return build_couple_balance_label(balance)


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


if __name__ == "__main__":
    main()
