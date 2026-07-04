from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = ""
    password: str = ""


class ProfileUpdateRequest(BaseModel):
    full_name: str
    username: str
    email: str = ""
    new_password: str = ""


class IncomePayload(BaseModel):
    income_date: date
    amount: float = Field(gt=0)
    source: str
    description: str


class ExpensePayload(BaseModel):
    expense_date: date
    amount: float = Field(gt=0)
    name: str
    category: str
    description: str
    paid_by: str
    expense_type: str
    split_type: str = "equal"
    split_ratio: float = 0.5


class SettledPayload(BaseModel):
    is_settled: bool


class CategoryPayload(BaseModel):
    name: str


class BulkDeletePayload(BaseModel):
    ids: list[int]


class CalendarEvent(BaseModel):
    id: int
    type: Literal["income", "expense"]
    title: str
    amount: float
    category: str = ""
    source: str = ""
    owner: str | None = None
    paid_by: str = ""
    date: date
    is_shared: bool = False
    settled: bool | None = None
    display_label: str


class CalendarDay(BaseModel):
    date: date
    day_number: int
    is_current_month: bool
    is_today: bool
    total_expenses: float
    total_incomes: float
    net_total: float
    events: list[CalendarEvent]
    event_count: int
    preview_events: list[CalendarEvent]
    remaining_count: int


class CalendarWeek(BaseModel):
    days: list[CalendarDay]


class CalendarMonthMeta(BaseModel):
    label: str
    year: int
    month: int
    title: str
    prev_month_label: str
    next_month_label: str


class CalendarSummary(BaseModel):
    total_expenses: float
    total_incomes: float
    net_total: float
    expense_count: int
    income_count: int
    event_count: int


class CalendarResponse(BaseModel):
    month: CalendarMonthMeta
    content_filter: Literal["all", "incomes", "expenses"]
    weekdays: list[str]
    weeks: list[CalendarWeek]
    summary: CalendarSummary


class CalendarDayDetailResponse(BaseModel):
    date: date
    content_filter: Literal["all", "incomes", "expenses"]
    day: CalendarDay | None


class CoupleBalancePeriod(BaseModel):
    label: str
    title: str
    year: int | None = None
    month: int | None = None
    is_all_time: bool
    prev_month_label: str
    next_month_label: str


class CoupleBalanceItem(BaseModel):
    id: int
    date: date
    expense_date: date
    name: str
    description: str = ""
    category: str
    amount: float
    paid_by: str
    owner: str | None = None
    counterpart: str
    is_shared: bool
    is_settled: bool
    settled: bool
    split_type: str
    split_ratio: float
    payer_share: float
    partner_share: float
    status_label: str
    action_label: str
    balance_impact: float
    month_label: str | None = None


class CoupleBalanceSummary(BaseModel):
    balance: float
    balance_value: float
    balance_label: str
    shared_total: float
    total_shared: float
    unsettled_total: float
    total_unsettled: float
    open_items: int
    settled_items: int
    total_items: int
    filtered_items: int


class CoupleBalanceStatusOption(BaseModel):
    value: Literal["open", "settled", "all"]
    label: str


class CoupleBalanceFilters(BaseModel):
    status_options: list[CoupleBalanceStatusOption]
    category_options: list[str]


class CoupleBalanceResponse(BaseModel):
    period: CoupleBalancePeriod
    status_filter: Literal["open", "settled", "all"]
    category: str
    summary: CoupleBalanceSummary
    items: list[CoupleBalanceItem]
    filters: CoupleBalanceFilters
    month_options: list[str]
