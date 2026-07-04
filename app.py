from __future__ import annotations

import base64
import calendar
from datetime import date
from pathlib import Path
import pandas as pd
import streamlit as st

from database import initialize_database
from services import (
    EXPENSE_TYPE_OPTIONS,
    SHARED_SPLIT_OPTIONS,
    add_category,
    apply_filters,
    apply_income_filters,
    authenticate_user,
    build_category_summary,
    build_dashboard_metrics,
    build_income_vs_expense_summary,
    create_expense,
    create_income,
    delete_income,
    delete_category,
    delete_expense,
    export_expenses_to_csv,
    export_expenses_to_pdf,
    format_currency,
    compute_balance,
    get_categories,
    get_expense_by_id,
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
    update_income,
    update_user_profile,
    validate_expense_data,
    validate_income_data,
    REPORTLAB_AVAILABLE,
)
from ui_helpers import close_section, open_section, render_topbar, require_authentication


st.set_page_config(page_title="Monitor Spese", page_icon="€", layout="wide")


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
            .block-container {
                padding-top: 0.85rem;
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
                position: sticky;
                top: 0.55rem;
                z-index: 20;
                display: flex;
                justify-content: flex-end;
                margin: 0.25rem 0 0.45rem 0;
                pointer-events: none;
            }
            .expense-total-pill {
                display: inline-flex;
                align-items: center;
                gap: 0.55rem;
                padding: 0.46rem 0.78rem;
                border-radius: 999px;
                background: rgba(255, 253, 250, 0.94);
                border: 1px solid var(--border);
                box-shadow: 0 10px 24px rgba(70, 43, 22, 0.08);
                backdrop-filter: blur(10px);
                pointer-events: none;
            }
            .expense-total-label {
                color: var(--muted);
                font-size: 0.76rem;
                text-transform: uppercase;
                letter-spacing: 0.06em;
                line-height: 1;
            }
            .expense-total-value {
                color: var(--text);
                font-size: 0.98rem;
                font-weight: 700;
                line-height: 1;
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
            div.st-key-expense_fixed_stack {
                position: sticky;
                top: 4.9rem;
                z-index: 30;
                padding: 0.1rem 0 0.45rem 0;
                background: transparent !important;
                backdrop-filter: none !important;
            }
            div.st-key-expense_fixed_stack > div,
            div.st-key-expense_fixed_stack div[data-testid="stVerticalBlock"],
            div.st-key-expense_fixed_stack div[data-testid="stElementContainer"] {
                background: transparent !important;
                box-shadow: none !important;
            }
            div.st-key-expense_feed_scroll {
                height: calc(100vh - 350px);
                max-height: calc(100vh - 350px);
                overflow-y: auto;
                overflow-x: hidden;
                padding-right: 0.18rem;
                scrollbar-width: thin;
            }
            div.st-key-expense_feed_scroll > div {
                padding-top: 0.1rem;
            }
            .home-counter-wrap {
                display: flex;
                align-items: center;
                justify-content: flex-end;
                gap: 1rem;
                margin: 0.15rem 0 0.6rem 0;
                padding: 0;
            }
            .home-counter-grid {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 1.3rem;
                width: 100%;
            }
            .home-counter-item {
                min-width: 0;
                text-align: right;
            }
            .home-counter-label {
                color: var(--muted);
                font-size: 0.72rem;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                margin-bottom: 0.12rem;
            }
            .home-counter-value {
                color: var(--text);
                font-size: 1.02rem;
                font-weight: 700;
                line-height: 1.05;
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
                padding-top: 0.15rem;
            }
            .topbar-row {
                padding-top: 0.45rem;
                margin-bottom: 0.2rem;
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
            .income-header {
                display: flex;
                align-items: center;
                justify-content: flex-start;
                gap: 1rem;
                margin-bottom: 1rem;
            }
            .income-meta {
                display: flex;
                align-items: center;
                justify-content: flex-start;
                gap: 1rem;
                color: var(--muted);
                font-size: 0.88rem;
                font-weight: 500;
                line-height: 1;
                flex-wrap: wrap;
                text-align: left;
            }
            .income-meta strong {
                color: var(--text);
                font-weight: 600;
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
                margin-top: 0.15rem;
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
            .hero-layout {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 1.2rem;
                flex-wrap: wrap;
            }
            .hero-visual {
                flex: 1 1 260px;
                min-width: 220px;
                display: flex;
                justify-content: flex-end;
                align-items: center;
            }
            .hero-visual-frame {
                position: relative;
                width: min(100%, 320px);
                display: flex;
                justify-content: center;
                align-items: center;
            }
            .hero-visual-frame::before {
                content: "";
                position: absolute;
                inset: 14% 12% 16% 12%;
                border-radius: 999px;
                background: radial-gradient(circle, rgba(96, 229, 255, 0.26) 0%, rgba(96, 229, 255, 0.08) 42%, transparent 72%);
                filter: blur(18px);
            }
            .hero-image {
                position: relative;
                z-index: 1;
                width: 100%;
                max-width: 300px;
                object-fit: contain;
                filter: drop-shadow(0 20px 28px rgba(18, 13, 9, 0.22));
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
                .hero-layout {
                    align-items: flex-start;
                }
                .hero-visual {
                    width: 100%;
                    justify-content: center;
                }
                .hero-meta {
                    max-width: 100%;
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
            }
            div.st-key-expense_category_filter div[data-testid="stRadio"] label[data-baseweb="radio"] {
                min-width: auto;
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
                font-weight: 500;
                color: rgba(44, 33, 23, 0.72);
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
            div.st-key-expense_tools_row {
                margin: 0.22rem 0 0.22rem 0;
            }
            div.st-key-expense_tools_row div[data-testid="stHorizontalBlock"] {
                justify-content: flex-start;
                align-items: center;
                gap: 0.38rem;
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
                min-width: 40px !important;
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
            div.st-key-expense_edit_mode_toggle > button:hover,
            div.st-key-expense_edit_mode_toggle div.stButton > button:hover {
                background: transparent !important;
                color: var(--accent-dark) !important;
                transform: none !important;
            }
            div.st-key-expense_sort_toggle button {
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
            div.st-key-expense_sort_toggle button:hover {
                background: transparent !important;
                color: var(--accent-dark) !important;
                transform: none !important;
            }
            div.st-key-expense_sort_toggle > button,
            div.st-key-expense_sort_toggle div.stButton > button {
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
            div.st-key-expense_sort_toggle > button:hover,
            div.st-key-expense_sort_toggle div.stButton > button:hover {
                background: transparent !important;
                color: var(--accent-dark) !important;
                transform: none !important;
            }
            div.st-key-expense_search_toggle button,
            div.st-key-expense_search_toggle div.stButton > button,
            div.st-key-income_search_toggle button,
            div.st-key-income_search_toggle div.stButton > button {
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
                font-size: 1.1rem !important;
                line-height: 1 !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
            }
            div.st-key-expense_search_toggle button p,
            div.st-key-income_search_toggle button p {
                font-size: 1.18rem !important;
                line-height: 1 !important;
                font-weight: 500 !important;
                margin: 0 !important;
            }
            div.st-key-expense_search_toggle button:hover,
            div.st-key-expense_search_toggle div.stButton > button:hover,
            div.st-key-income_search_toggle button:hover,
            div.st-key-income_search_toggle div.stButton > button:hover {
                background: transparent !important;
                color: var(--accent-dark) !important;
                transform: none !important;
            }
            div.st-key-expense_sort_menu,
            div.st-key-expense_search_menu,
            div.st-key-income_sort_menu,
            div.st-key-income_search_menu {
                margin-top: 0.18rem;
                padding: 0.6rem 0.72rem;
                background: rgba(255, 251, 246, 0.98);
                border: 1px solid var(--border);
                border-radius: 16px;
                box-shadow: 0 14px 28px rgba(70, 43, 22, 0.08);
            }
            div.st-key-expense_search_menu input,
            div.st-key-income_search_menu input {
                font-size: 0.86rem !important;
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

    render_topbar()
    if st.session_state.get("current_view") == "new_expense":
        st.session_state.current_view = "home"
        st.session_state.show_new_expense_modal = True
    if st.session_state.get("current_view") == "new_income":
        st.session_state.current_view = "home"
        st.session_state.show_new_income_modal = True
    if st.session_state.get("current_view") == "edit_expense":
        st.session_state.current_view = "home"
        st.session_state.show_edit_expense_modal = True
    filtered_expenses, selected_month = render_sidebar_filters(all_expenses)
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
        render_home_counter(all_expenses, all_incomes, selected_month)
        render_hero(all_expenses)
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
    if "show_income_sort_menu" not in st.session_state:
        st.session_state.show_income_sort_menu = False
    if "show_income_search_menu" not in st.session_state:
        st.session_state.show_income_search_menu = False
    if "is_authenticated" not in st.session_state:
        st.session_state.is_authenticated = False
    if "current_user" not in st.session_state:
        st.session_state.current_user = None


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


def render_topbar() -> None:
    user = st.session_state.current_user or {}
    st.markdown('<div class="topbar-row">', unsafe_allow_html=True)
    left, right = st.columns([1, 0.08])
    with left:
        st.markdown(
            f'<div class="topbar-text">Connesso come: {user.get("full_name", "Utente")} ({user.get("username", "-")})</div>',
            unsafe_allow_html=True,
        )
    with right:
        if st.button("Logout", key="logout_small", use_container_width=False, type="tertiary"):
            st.session_state.is_authenticated = False
            st.session_state.current_user = None
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_hero(dataframe: pd.DataFrame) -> None:
    image_path = Path(__file__).with_name("hero-robot-cutout.png")
    hero_image_html = ""
    if image_path.exists():
        encoded_image = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        hero_image_html = (
            '<div class="hero-visual">'
            '<div class="hero-visual-frame">'
            f'<img src="data:image/png;base64,{encoded_image}" alt="Robot con salvadanaio" class="hero-image">'
            "</div>"
            "</div>"
        )

    st.markdown(
        f"""
        <div class="hero-container" id="hero-container">
            <div class="hero-card">
                <div class="hero-layout">
                    <div class="hero-meta">
                        <h1 class="hero-title">Monitor spese personali e di coppia</h1>
                        <p class="hero-copy">
                            Uno spazio semplice per registrare le spese, vedere cosa hai speso e capire subito il saldo di coppia.
                        </p>
                        <div class="legend-row">
                            <span class="legend-badge">Chi siamo</span>
                            <span class="legend-badge">I tuoi risparmi</span>
                            <span class="legend-badge">I tuoi movimenti</span>
                        </div>
                    </div>
                    {hero_image_html}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_main_content(
    section: str,
    filtered_expenses: pd.DataFrame,
    filtered_incomes: pd.DataFrame,
    all_expenses: pd.DataFrame,
    all_incomes: pd.DataFrame,
    selected_month: str,
) -> None:
    if section == "Home":
        st.caption("Scegli una card per entrare nella schermata dedicata all'operazione che vuoi eseguire.")
        render_operation_cards(filtered_expenses)

    elif section == "Entrate":
        render_month_navigation_bar(selected_month, "income_month")
        render_incomes_section(filtered_incomes)

    elif section == "Uscite":
        with st.container(key="expense_fixed_stack"):
            render_month_navigation_bar(selected_month, "expense_month")
            selected_type_view = render_expense_type_filter_bar()
            selected_category = render_expense_category_filter_bar(filtered_expenses)
            visible_expenses = filtered_expenses.copy()
            if selected_type_view == "Personali":
                visible_expenses = visible_expenses[visible_expenses["expense_type"] == "Personale"].copy()
            elif selected_type_view == "Condivise":
                visible_expenses = visible_expenses[visible_expenses["expense_type"] == "Condivisa"].copy()
            if selected_category != "Tutte":
                visible_expenses = visible_expenses[visible_expenses["category"] == selected_category].copy()
            render_expense_total_sticky(visible_expenses)
            render_expense_tools(visible_expenses)
        if st.session_state.get("expense_edit_mode", False):
            st.markdown('<div class="expense-edit-backdrop"></div>', unsafe_allow_html=True)
        with st.container(key="expense_feed_scroll"):
            if st.session_state.get("expense_edit_mode", False):
                st.markdown('<div class="expense-edit-focus">', unsafe_allow_html=True)
            render_expense_feed(visible_expenses)
            if st.session_state.get("expense_edit_mode", False):
                st.markdown("</div>", unsafe_allow_html=True)

    elif section == "Riepilogo":
        render_month_navigation_bar(selected_month, "summary_month")
        st.caption("Tutte le spese visibili con i filtri attivi, con esportazione CSV.")
        render_expense_list(filtered_expenses)
        st.write("")
        render_export_section(filtered_expenses)

    elif section == "Calendario":
        render_calendar_section(filtered_expenses, filtered_incomes)

    else:
        st.caption("Promemoria e spese programmate, con una notifica per cio che richiede attenzione.")
        st.info("Programma spese in arrivo. Qui vedrai promemoria, ricorrenze e spese da tenere d'occhio.")


def render_section_navigation() -> str:
    current_section = st.session_state.get("current_section", "Home")
    action_label = "Nuova entrata" if current_section == "Entrate" else "Nuova spesa"
    nav_col, action_col = st.columns([1, 0.22], vertical_alignment="center")
    with nav_col:
        section = st.radio(
            "Sezioni",
            ["Home", "Entrate", "Uscite", "Riepilogo", "Calendario", "Programma spese •"],
            horizontal=True,
            label_visibility="collapsed",
            key="current_section",
        )
    with action_col:
        if st.button(action_label, key="top_new_expense", use_container_width=True, type="primary"):
            if current_section == "Entrate":
                st.session_state.show_new_income_modal = True
            else:
                st.session_state.show_new_expense_modal = True
            st.rerun()
    return "Programma spese" if section == "Programma spese •" else section


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
    year, month_text = active_month_label.split("-")
    year = int(year)
    month = int(month_text)

    month_expenses = expenses[expenses["month_label"] == active_month_label].copy() if not expenses.empty else expenses
    month_incomes = incomes[incomes["month_label"] == active_month_label].copy() if not incomes.empty else incomes

    if calendar_filter == "Entrate":
        month_expenses = month_expenses.iloc[0:0].copy()
    elif calendar_filter == "Uscite":
        month_incomes = month_incomes.iloc[0:0].copy()

    expense_day_totals = {}
    if not month_expenses.empty:
        expense_day_totals = (
            month_expenses.groupby(month_expenses["expense_date"].dt.day)["amount"].sum().to_dict()
        )

    income_day_totals = {}
    if not month_incomes.empty:
        income_day_totals = (
            month_incomes.groupby(month_incomes["income_date"].dt.day)["amount"].sum().to_dict()
        )

    expense_events: dict[int, list[str]] = {}
    if not month_expenses.empty:
        for _, row in month_expenses.sort_values("expense_date").iterrows():
            day = int(row["expense_date"].day)
            title = str(row.get("name") or row.get("description") or row.get("category") or "Spesa")
            expense_events.setdefault(day, []).append(f"expense|{title}")

    income_events: dict[int, list[str]] = {}
    if not month_incomes.empty:
        for _, row in month_incomes.sort_values("income_date").iterrows():
            day = int(row["income_date"].day)
            title = str(row.get("source") or row.get("description") or "Entrata")
            income_events.setdefault(day, []).append(f"income|{title}")

    weekdays = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
    calendar_rows = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
    today = date.today()

    html_parts = [
        '<div class="calendar-shell">',
        '<div class="calendar-grid">',
    ]

    for weekday in weekdays:
        html_parts.append(f'<div class="calendar-weekday">{weekday}</div>')

    for week in calendar_rows:
        for day in week:
            classes = ["calendar-day"]
            if day.month != month:
                classes.append("is-other-month")
            if day == today:
                classes.append("is-today")

            day_events: list[str] = []
            if day.month == month:
                day_events.extend(expense_events.get(day.day, []))
                day_events.extend(income_events.get(day.day, []))

            event_markup = []
            for event in day_events[:3]:
                event_type, label = event.split("|", 1)
                event_markup.append(
                    f'<div class="calendar-event"><span class="calendar-event-dot {event_type}"></span><span class="calendar-event-text">{label}</span></div>'
                )
            if len(day_events) > 3:
                event_markup.append(
                    f'<div class="calendar-event"><span class="calendar-event-text">+{len(day_events) - 3} altri</span></div>'
                )

            total_text = ""
            if day.month == month:
                expense_total = float(expense_day_totals.get(day.day, 0.0))
                income_total = float(income_day_totals.get(day.day, 0.0))
                if expense_total > 0 or income_total > 0:
                    total_text = f'<div class="calendar-day-total">Uscite {format_currency(expense_total)} · Entrate {format_currency(income_total)}</div>'

            today_dot = '<span class="calendar-today-dot"></span>' if day == today else ""
            html_parts.append(
                f'<div class="{" ".join(classes)}">'
                f'<div class="calendar-day-top"><div class="calendar-day-number">{day.day}</div>{today_dot}</div>'
                f"{total_text}"
                f'<div class="calendar-event-list">{"".join(event_markup)}</div>'
                "</div>"
            )

    html_parts.extend(["</div>", "</div>"])
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def render_home_counter(all_expenses: pd.DataFrame, all_incomes: pd.DataFrame, selected_month: str) -> None:
    filters = st.session_state.get("filters", {})
    selected_year = filters.get("year_label")
    active_month_label = resolve_month_label(selected_month)
    active_year = selected_year or active_month_label.split("-")[0]

    scope_col, metrics_col = st.columns([0.24, 0.76], vertical_alignment="center")
    with scope_col:
        scope = st.segmented_control(
            "Periodo home",
            ["Mensile", "Annuale"],
            default=st.session_state.get("home_counter_scope", "Mensile"),
            key="home_counter_scope",
            label_visibility="collapsed",
        )

    if scope == "Annuale":
        scoped_expenses = all_expenses[all_expenses["month_label"].str.startswith(active_year)] if not all_expenses.empty else all_expenses
        scoped_incomes = all_incomes[all_incomes["month_label"].str.startswith(active_year)] if not all_incomes.empty else all_incomes
    else:
        scoped_expenses = all_expenses[all_expenses["month_label"] == active_month_label] if not all_expenses.empty else all_expenses
        scoped_incomes = all_incomes[all_incomes["month_label"] == active_month_label] if not all_incomes.empty else all_incomes

    total_expenses = float(scoped_expenses["amount"].sum()) if not scoped_expenses.empty else 0.0
    total_incomes = float(scoped_incomes["amount"].sum()) if not scoped_incomes.empty else 0.0
    savings = total_incomes - total_expenses

    with metrics_col:
        st.markdown(
            f"""
            <div class="home-counter-wrap">
                <div class="home-counter-grid">
                    <div class="home-counter-item">
                        <div class="home-counter-label">Spese</div>
                        <div class="home-counter-value">{format_currency(total_expenses)}</div>
                    </div>
                    <div class="home-counter-item">
                        <div class="home-counter-label">Entrate</div>
                        <div class="home-counter-value">{format_currency(total_incomes)}</div>
                    </div>
                    <div class="home-counter-item">
                        <div class="home-counter-label">Saldo</div>
                        <div class="home-counter-value">{format_currency(savings)}</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


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
        build_balance_label(metrics["balance"]),
        "balance",
    )

    st.caption(
        "Saldo coppia: valore positivo = l'altra persona deve soldi a me; valore negativo = io devo soldi all'altra persona."
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
    st.markdown(
        f"""
        <div class="expense-total-sticky">
            <div class="expense-total-pill">
                <span class="expense-total-label">Totale</span>
                <span class="expense-total-value">{format_currency(total_amount)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_expense_tools(dataframe: pd.DataFrame) -> None:
    tools_col, _ = st.columns([0.32, 0.68], vertical_alignment="center")
    with tools_col:
        with st.container(key="expense_tools_row"):
            edit_col, sort_col, search_col = st.columns([0.58, 0.21, 0.21], vertical_alignment="center")
            with edit_col:
                is_edit_mode = st.session_state.get("expense_edit_mode", False)
                edit_label = "✓" if is_edit_mode else "Modifica spesa"
                if st.button(edit_label, key="expense_edit_mode_toggle", use_container_width=False, type="secondary"):
                    st.session_state.expense_edit_mode = not is_edit_mode
                    st.rerun()
            with sort_col:
                with st.container(key="expense_sort_toggle"):
                    if st.button("≡", key="expense_sort_toggle_button", use_container_width=False, type="secondary"):
                        is_open = st.session_state.get("show_expense_sort_menu", False)
                        st.session_state.show_expense_sort_menu = not is_open
                        st.session_state.show_expense_search_menu = False
                        st.rerun()
                if st.session_state.get("show_expense_sort_menu", False):
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
                with st.container(key="expense_search_toggle"):
                    if st.button("⌕", key="expense_search_toggle_button", use_container_width=False, type="secondary"):
                        is_open = st.session_state.get("show_expense_search_menu", False)
                        st.session_state.show_expense_search_menu = not is_open
                        st.session_state.show_expense_sort_menu = False
                        st.rerun()
                if st.session_state.get("show_expense_search_menu", False):
                    with st.container(key="expense_search_menu"):
                        st.text_input(
                            "Cerca spesa",
                            value=st.session_state.get("expense_search_query", ""),
                            key="expense_search_query",
                            placeholder="Cerca per nome",
                            label_visibility="collapsed",
                        )

def render_expense_feed(dataframe: pd.DataFrame) -> None:
    if dataframe.empty:
        st.info("Nessuna spesa trovata con i filtri selezionati.")
        return

    search_query = str(st.session_state.get("expense_search_query", "") or "").strip().lower()
    if search_query:
        dataframe = dataframe[
            dataframe["name"].fillna("").astype(str).str.lower().str.contains(search_query, na=False)
        ].copy()
        if dataframe.empty:
            st.info("Nessuna spesa trovata con questa ricerca.")
            return

    sort_mode = st.session_state.get("expense_sort_mode", "Data piu recente")
    if sort_mode == "Importo maggiore":
        ordered_expenses = dataframe.sort_values(by=["amount", "expense_date", "id"], ascending=[False, False, False]).copy()
    elif sort_mode == "Importo minore":
        ordered_expenses = dataframe.sort_values(by=["amount", "expense_date", "id"], ascending=[True, False, False]).copy()
    else:
        ordered_expenses = dataframe.sort_values(by=["expense_date", "id"], ascending=[False, False]).copy()
    edit_mode = st.session_state.get("expense_edit_mode", False)
    st.markdown('<div class="expense-list">', unsafe_allow_html=True)
    for _, row in ordered_expenses.iterrows():
        expense_name = str(row.get("name") or row.get("description") or "Spesa")
        date_label = row["expense_date"].strftime("%d/%m")
        with st.container(key=f"expense_row_{int(row['id'])}"):
            row_cols = st.columns([0.14, 0.28, 0.2, 0.16, 0.14, 0.18], vertical_alignment="center")
            with row_cols[0]:
                st.markdown(f'<div class="expense-cell expense-cell-secondary">{date_label}</div>', unsafe_allow_html=True)
            with row_cols[1]:
                if edit_mode:
                    if st.button(expense_name, key=f"expense_name_pick_{int(row['id'])}", use_container_width=True, type="tertiary"):
                        st.session_state.preselected_expense_id = int(row["id"])
                        st.session_state.show_edit_expense_modal = True
                        st.rerun()
                else:
                    st.markdown(f'<div class="expense-cell expense-cell-name">{expense_name}</div>', unsafe_allow_html=True)
            with row_cols[2]:
                st.markdown(f'<div class="expense-cell expense-cell-secondary">{row["category"]}</div>', unsafe_allow_html=True)
            with row_cols[3]:
                st.markdown(f'<div class="expense-cell expense-cell-user">{row["paid_by"]}</div>', unsafe_allow_html=True)
            with row_cols[4]:
                st.markdown(f'<div class="expense-cell expense-cell-secondary">{row["expense_type"]}</div>', unsafe_allow_html=True)
            with row_cols[5]:
                st.markdown(f'<div class="expense-cell expense-cell-amount">{format_currency(float(row["amount"]))}</div>', unsafe_allow_html=True)
            st.markdown('<div class="expense-card"></div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


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
    expense = get_expense_by_id(selected_expense_id)

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
                update_expense(
                    expense_id=selected_expense_id,
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
                st.session_state.show_edit_expense_modal = False
                st.success("Spesa aggiornata con successo.")
                st.rerun()

        if delete_clicked:
            delete_expense(selected_expense_id)
            st.session_state.show_edit_expense_modal = False
            st.success("Spesa eliminata con successo.")
            st.rerun()


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




def render_operation_cards(dataframe: pd.DataFrame) -> None:
    cards = [
        {
            "title": "Nuova spesa",
            "subtitle": "Inserisci una nuova spesa personale o condivisa.",
            "view": "new_expense",
        },
        {
            "title": "Nuova entrata",
            "subtitle": "Registra una nuova entrata mensile.",
            "view": "new_income",
        },
        {
            "title": "Modifica spesa",
            "subtitle": "Apri la schermata per aggiornare o eliminare un movimento.",
            "view": "edit_expense",
        },
        {
            "title": "Aggiungi categoria",
            "subtitle": "Crea una nuova categoria da usare nei prossimi inserimenti.",
            "view": "add_category",
        },
        {
            "title": "Analisi",
            "subtitle": "Guarda grafici e andamento mensile in una schermata dedicata.",
            "view": "analysis",
        },
    ]

    columns = st.columns(2, gap="large")
    for index, card in enumerate(cards):
        with columns[index % 2]:
            st.markdown(
                """
                <style>
                    div.stButton > button[kind="secondary"] {
                        min-height: 116px !important;
                        padding-top: 0.95rem !important;
                        padding-bottom: 0.95rem !important;
                    }
                </style>
                """,
                unsafe_allow_html=True,
            )
            label = card["title"]
            if st.button(
                label.upper(),
                key=f"operation_card_{card['view']}",
                use_container_width=True,
                type="secondary",
            ):
                if card["view"] == "new_expense":
                    st.session_state.show_new_expense_modal = True
                elif card["view"] == "new_income":
                    st.session_state.show_new_income_modal = True
                elif card["view"] == "edit_expense":
                    st.session_state.show_edit_expense_modal = True
                else:
                    st.session_state.current_view = card["view"]
                st.rerun()


def render_operation_detail_page(filtered_expenses: pd.DataFrame, filtered_incomes: pd.DataFrame) -> None:
    current_view = st.session_state.get("current_view", "home")
    view_config = {
        "new_expense": (
            "Nuova spesa",
            "Compila il form qui sotto per registrare una nuova spesa.",
        ),
        "new_income": (
            "Nuova entrata",
            "Compila il form qui sotto per registrare una nuova entrata.",
        ),
        "edit_expense": (
            "Modifica spesa",
            "Seleziona una spesa esistente e aggiorna i campi necessari.",
        ),
        "add_category": (
            "Aggiungi categoria",
            "Crea una nuova categoria personalizzata per organizzare meglio le spese.",
        ),
        "analysis": (
            "Analisi",
            "Una vista piu calma per capire come stai spendendo nel tempo.",
        ),
    }

    if current_view not in view_config:
        st.session_state.current_view = "home"
        st.session_state.current_section = "Home"
        st.rerun()

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
        st.rerun()
    info_col.caption("Usa la sidebar per mantenere i filtri attivi anche nelle schermate operative.")

    if current_view == "new_expense":
        render_create_form()
    elif current_view == "new_income":
        open_section("Nuova entrata", "Inserimento rapido di una nuova entrata.")
        render_create_income_form()
        close_section()
    elif current_view == "edit_expense":
        open_section("Modifica spesa", "Aggiorna o elimina una spesa esistente.")
        render_edit_section(filtered_expenses)
        close_section()
    elif current_view == "add_category":
        open_section("Aggiungi categoria", "Una nuova categoria sara disponibile nei form delle spese.")
        render_add_category_form()
        close_section()
    elif current_view == "analysis":
        open_section("Analisi", "Grafici e confronto tra entrate e uscite del periodo filtrato.")
        render_charts(filtered_expenses)
        st.write("")
        render_income_expense_analysis(filtered_incomes, filtered_expenses)
        close_section()


def render_add_category_form() -> None:
    with st.form("add_category_form", clear_on_submit=True):
        category_name = st.text_input("Nome nuova categoria")
        submitted = st.form_submit_button("Salva categoria", use_container_width=True)
        if submitted:
            success, message, *_ = add_category(category_name)
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
    tools_col, _ = st.columns([0.36, 0.64], vertical_alignment="center")
    with tools_col:
        edit_col, sort_col, search_col = st.columns([0.58, 0.21, 0.21], vertical_alignment="center")
        with edit_col:
            is_edit_mode = st.session_state.get("income_edit_mode", False)
            edit_label = "✓" if is_edit_mode else "Modifica entrata"
            if st.button(edit_label, key="income_edit_mode_toggle", use_container_width=False, type="secondary"):
                st.session_state.income_edit_mode = not is_edit_mode
                st.rerun()
        with sort_col:
            with st.container(key="income_sort_toggle"):
                if st.button("≡", key="income_sort_toggle_button", use_container_width=False, type="secondary"):
                    is_open = st.session_state.get("show_income_sort_menu", False)
                    st.session_state.show_income_sort_menu = not is_open
                    st.session_state.show_income_search_menu = False
                    st.rerun()
            if st.session_state.get("show_income_sort_menu", False):
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
            with st.container(key="income_search_toggle"):
                if st.button("⌕", key="income_search_toggle_button", use_container_width=False, type="secondary"):
                    is_open = st.session_state.get("show_income_search_menu", False)
                    st.session_state.show_income_search_menu = not is_open
                    st.session_state.show_income_sort_menu = False
                    st.rerun()
            if st.session_state.get("show_income_search_menu", False):
                with st.container(key="income_search_menu"):
                    st.text_input(
                        "Cerca entrata",
                        value=st.session_state.get("income_search_query", ""),
                        key="income_search_query",
                        placeholder="Cerca per nome",
                        label_visibility="collapsed",
                    )
h

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
    income = get_income_by_id(selected_income_id)

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
                update_income(
                    income_id=selected_income_id,
                    income_date=income_date,
                    amount=amount,
                    source=source,
                    description=description,
                )
                st.session_state.show_edit_income_modal = False
                st.success("Entrata aggiornata con successo.")
                st.rerun()

        if delete_clicked:
            delete_income(selected_income_id)
            st.session_state.show_edit_income_modal = False
            st.success("Entrata eliminata con successo.")
            st.rerun()


def render_incomes_section(dataframe: pd.DataFrame) -> None:
    if dataframe.empty:
        st.info("Nessuna entrata trovata per il periodo selezionato.")
        return

    search_query = str(st.session_state.get("income_search_query", "") or "").strip().lower()
    if search_query:
        dataframe = dataframe[
            dataframe["source"].fillna("").astype(str).str.lower().str.contains(search_query, na=False)
        ].copy()
        if dataframe.empty:
            st.info("Nessuna entrata trovata con questa ricerca.")
            return

    sort_mode = st.session_state.get("income_sort_mode", "Data piu recente")
    if sort_mode == "Importo maggiore":
        sorted_frame = dataframe.sort_values(["amount", "income_date", "id"], ascending=[False, False, False]).copy()
    elif sort_mode == "Importo minore":
        sorted_frame = dataframe.sort_values(["amount", "income_date", "id"], ascending=[True, False, False]).copy()
    else:
        sorted_frame = dataframe.sort_values(["income_date", "id"], ascending=[False, False]).copy()

    total_amount = float(sorted_frame["amount"].sum())
    latest_date = sorted_frame.iloc[0]["income_date"].strftime("%d/%m")
    top_source = (
        sorted_frame.groupby("source", dropna=False)["amount"].sum().sort_values(ascending=False).index[0]
        if not sorted_frame.empty else "-"
    )

    st.markdown(
        f"""
        <div class="income-header">
            <div class="income-meta">
                <span>Fonte principale <strong>{top_source}</strong></span>
                <span>Ultima entrata <strong>{latest_date}</strong></span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="expense-total-sticky">
            <div class="expense-total-pill">
                <span class="expense-total-label">Totale</span>
                <span class="expense-total-value">{format_currency(total_amount)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_income_tools()

    edit_mode = st.session_state.get("income_edit_mode", False)
    if edit_mode:
        st.markdown('<div class="income-edit-backdrop"></div>', unsafe_allow_html=True)
        st.markdown('<div class="income-edit-focus">', unsafe_allow_html=True)

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
    if edit_mode:
        st.markdown("</div>", unsafe_allow_html=True)


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
    if balance > 0:
        return f"L'altra persona deve {format_currency(balance)}"
    if balance < 0:
        return f"Io devo {format_currency(abs(balance))}"
    return "In pari"


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
