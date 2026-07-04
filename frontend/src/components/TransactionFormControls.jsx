import { useEffect, useRef, useState } from "react";

export function AmountInput({ value, onChange }) {
  const [displayValue, setDisplayValue] = useState(formatAmountDisplay(value));
  const [isDecimalEditing, setIsDecimalEditing] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const inputRef = useRef(null);
  const amountVisualParts = getAmountVisualParts(displayValue, isDecimalEditing, isFocused);

  useEffect(() => {
    const currentNumericValue = parseDisplayAmount(displayValue);
    const nextNumericValue = Number(value || 0);
    if (currentNumericValue !== nextNumericValue) {
      setDisplayValue(formatAmountDisplay(value));
      setIsDecimalEditing(false);
    }
  }, [value, displayValue]);

  function commitDisplay(nextDisplay, decimalEditing = isDecimalEditing) {
    setDisplayValue(nextDisplay);
    setIsDecimalEditing(decimalEditing);
    onChange(parseDisplayAmount(nextDisplay) ? String(parseDisplayAmount(nextDisplay)) : "");
  }

  function handleKeyDown(event) {
    if (["Tab", "ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
      return;
    }

    if (/^\d$/.test(event.key)) {
      event.preventDefault();
      const { integerPart, decimalPart } = splitAmountDisplay(displayValue);
      if (isDecimalEditing) {
        if (decimalPart.length >= 2) return;
        commitDisplay(`${integerPart || "0"},${decimalPart}${event.key}`, true);
        return;
      }
      const nextInteger = normalizeIntegerPart(`${integerPart}${event.key}`);
      commitDisplay(`${nextInteger},00`, false);
      window.requestAnimationFrame(() => {
        inputRef.current?.setSelectionRange(nextInteger.length, nextInteger.length);
      });
      return;
    }

    if (event.key === "," || event.key === ".") {
      event.preventDefault();
      const { integerPart } = splitAmountDisplay(displayValue);
      commitDisplay(`${integerPart || "0"},`, true);
      return;
    }

    if (event.key === "Backspace") {
      event.preventDefault();
      const cursorPosition = event.currentTarget.selectionStart ?? displayValue.length;
      const commaIndex = displayValue.indexOf(",");
      const { integerPart, decimalPart } = splitAmountDisplay(displayValue);
      if (isDecimalEditing) {
        const decimalCursor = Math.max(0, cursorPosition - commaIndex - 1);
        if (decimalCursor > 0) {
          const nextDecimal = `${decimalPart.slice(0, decimalCursor - 1)}${decimalPart.slice(decimalCursor)}`;
          commitDisplay(`${integerPart || "0"},${nextDecimal}`, true);
          return;
        }
        commitDisplay(`${integerPart || "0"},00`, false);
        return;
      }

      const safeIntegerCursor = commaIndex === -1 ? cursorPosition : Math.min(cursorPosition, commaIndex);
      if (safeIntegerCursor <= 0) return;
      const nextInteger = `${integerPart.slice(0, safeIntegerCursor - 1)}${integerPart.slice(safeIntegerCursor)}`;
      commitDisplay(nextInteger ? `${nextInteger},00` : "", false);
      window.requestAnimationFrame(() => {
        inputRef.current?.setSelectionRange(nextInteger.length, nextInteger.length);
      });
      return;
    }

    if (event.key === "Delete") {
      event.preventDefault();
      commitDisplay("", false);
      return;
    }

    event.preventDefault();
  }

  function handlePaste(event) {
    event.preventDefault();
    const pastedText = event.clipboardData.getData("text");
    const nextDisplay = formatPastedAmount(pastedText);
    commitDisplay(nextDisplay, nextDisplay.includes(",") && !nextDisplay.endsWith(",00"));
  }

  function handleBlur() {
    setIsFocused(false);
    if (!displayValue) return;
    const { integerPart, decimalPart } = splitAmountDisplay(displayValue);
    if (!integerPart && !decimalPart) {
      setDisplayValue("");
      setIsDecimalEditing(false);
      onChange("");
      return;
    }
    if (Number(`${integerPart || "0"}.${decimalPart || "0"}`) === 0) {
      setDisplayValue("");
      setIsDecimalEditing(false);
      onChange("");
      return;
    }
    const paddedDecimals = decimalPart.padEnd(2, "0").slice(0, 2);
    commitDisplay(`${integerPart || "0"},${paddedDecimals}`, false);
  }

  function handleFocus() {
    setIsFocused(true);
    if (displayValue) return;
    setDisplayValue("0,");
    setIsDecimalEditing(false);
    window.requestAnimationFrame(() => {
      inputRef.current?.setSelectionRange(1, 1);
    });
  }

  function handleClick(event) {
    const input = event.currentTarget;
    if (!displayValue) {
      setIsFocused(true);
      setDisplayValue("0,");
      setIsDecimalEditing(false);
      window.requestAnimationFrame(() => {
        inputRef.current?.setSelectionRange(1, 1);
      });
      return;
    }
    const commaIndex = displayValue.indexOf(",");
    if (commaIndex === -1 || input.selectionStart <= commaIndex) {
      setIsDecimalEditing(false);
      return;
    }

    const { integerPart } = splitAmountDisplay(displayValue);
    commitDisplay(`${integerPart || "0"},`, true);
    window.requestAnimationFrame(() => {
      inputRef.current?.setSelectionRange(inputRef.current.value.length, inputRef.current.value.length);
    });
  }

  return (
    <label className="expense-amount-field">
      <span className="expense-currency-symbol" aria-hidden="true">€</span>
      <div className="expense-amount-visual" aria-hidden="true">
        <span className="ghost">{amountVisualParts.prefixGhost}</span>
        <span className="typed">{amountVisualParts.typed}</span>
        {amountVisualParts.caret ? <span className="amount-visual-caret" /> : null}
        <span className="typed">{amountVisualParts.typedSuffix}</span>
        <span className="ghost">{amountVisualParts.ghost}</span>
      </div>
      <input
        ref={inputRef}
        type="text"
        inputMode="decimal"
        aria-label="Importo"
        style={{ "--amount-chars": Math.max(displayValue.length, 4) }}
        value={displayValue}
        onFocus={handleFocus}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        onBlur={handleBlur}
        onChange={() => {}}
      />
    </label>
  );
}

export function DateChoice({ value, onChange, ariaLabel = "Data spesa" }) {
  const [isOpen, setIsOpen] = useState(false);
  const [viewDate, setViewDate] = useState(parseISODate(value) || new Date());
  const menuRef = useRef(null);
  const selectedValue = value || getTodayDateString();
  const calendarDays = buildCalendarDays(viewDate);
  const monthLabel = new Intl.DateTimeFormat("it-IT", { month: "long", year: "numeric" }).format(viewDate);

  useEffect(() => {
    if (isOpen) {
      setViewDate(parseISODate(selectedValue) || new Date());
    }
  }, [isOpen, selectedValue]);

  useEffect(() => {
    if (!isOpen) return undefined;

    function closeMenu(event) {
      if (!menuRef.current?.contains(event.target)) {
        setIsOpen(false);
      }
    }

    function closeOnEscape(event) {
      if (event.key === "Escape") setIsOpen(false);
    }

    function closeOnResize() {
      setIsOpen(false);
    }

    document.addEventListener("pointerdown", closeMenu);
    window.addEventListener("resize", closeOnResize);
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeMenu);
      window.removeEventListener("resize", closeOnResize);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [isOpen]);

  return (
    <div ref={menuRef} className="expense-date-choice">
      <button
        type="button"
        className="expense-icon-field"
        aria-label={ariaLabel}
        aria-expanded={isOpen}
        onClick={() => setIsOpen((current) => !current)}
      >
        <svg aria-hidden="true" viewBox="0 0 24 24" className="expense-calendar-icon">
          <path d="M8 4.5v2.7M16 4.5v2.7" />
          <rect x="5.25" y="6" width="13.5" height="13" rx="3.4" />
          <path d="M8.5 11h7M8.5 14.5h4.5" />
        </svg>
      </button>
      {isOpen ? (
        <div className="expense-date-popover">
          <div className="expense-calendar-head">
            <button type="button" onClick={() => setViewDate(shiftMonth(viewDate, -1))} aria-label="Mese precedente">‹</button>
            <strong>{monthLabel}</strong>
            <button type="button" onClick={() => setViewDate(shiftMonth(viewDate, 1))} aria-label="Mese successivo">›</button>
          </div>
          <div className="expense-calendar-weekdays" aria-hidden="true">
            {["L", "M", "M", "G", "V", "S", "D"].map((day, index) => (
              <span key={`${day}-${index}`}>{day}</span>
            ))}
          </div>
          <div className="expense-calendar-grid">
            {calendarDays.map((day) => (
              <button
                key={day.iso}
                type="button"
                className={`expense-calendar-day${day.isCurrentMonth ? "" : " muted"}${day.iso === selectedValue ? " selected" : ""}${day.iso === getTodayDateString() ? " today" : ""}`}
                onClick={() => {
                  onChange(day.iso);
                  setIsOpen(false);
                }}
              >
                {day.date.getDate()}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function formatAmountDisplay(value) {
  if (value === "" || value === null || value === undefined) return "";
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue) || numericValue <= 0) return "";
  const [integerPart, decimalPart = "00"] = numericValue.toFixed(2).split(".");
  return `${integerPart},${decimalPart}`;
}

function splitAmountDisplay(displayValue) {
  const normalized = String(displayValue || "").replace(".", ",");
  const [rawInteger = "", rawDecimal = ""] = normalized.split(",");
  return {
    integerPart: normalizeIntegerPart(rawInteger),
    decimalPart: rawDecimal.replace(/\D/g, "").slice(0, 2),
  };
}

function parseDisplayAmount(displayValue) {
  const { integerPart, decimalPart } = splitAmountDisplay(displayValue);
  if (!integerPart && !decimalPart) return 0;
  return Number(`${integerPart || "0"}.${decimalPart}`);
}

function normalizeIntegerPart(value) {
  const digits = String(value || "").replace(/\D/g, "");
  return digits.replace(/^0+(?=\d)/, "");
}

function formatPastedAmount(value) {
  const normalized = String(value || "").replace(/[^\d,.]/g, "").replace(".", ",");
  const [rawInteger = "", rawDecimal = ""] = normalized.split(",");
  const integerPart = normalizeIntegerPart(rawInteger);
  const decimalPart = rawDecimal.replace(/\D/g, "").slice(0, 2);
  if (!integerPart && !decimalPart) return "";
  return `${integerPart || "0"},${decimalPart.padEnd(2, "0")}`;
}

function getAmountVisualParts(displayValue, isDecimalEditing, isFocused) {
  if (!displayValue) {
    return { prefixGhost: "", typed: "", typedSuffix: "", ghost: "0,00", caret: false };
  }
  if (isFocused && displayValue === "0,") {
    return { prefixGhost: "0", typed: "", typedSuffix: ",00", ghost: "", caret: true };
  }
  const normalizedDisplay = displayValue.includes(",") ? displayValue : `${displayValue},00`;
  if (!isDecimalEditing) {
    const integerPart = normalizedDisplay.split(",")[0] || "0";
    const hasTypedAmount = Number(parseDisplayAmount(normalizedDisplay)) > 0;
    if (hasTypedAmount) {
      return { prefixGhost: "", typed: integerPart, typedSuffix: ",00", ghost: "", caret: isFocused };
    }
    return {
      prefixGhost: "",
      typed: integerPart,
      typedSuffix: isFocused ? ",00" : "",
      ghost: isFocused ? "" : ",00",
      caret: isFocused,
    };
  }
  const { integerPart, decimalPart } = splitAmountDisplay(normalizedDisplay);
  if (!decimalPart) {
    if (isFocused && (integerPart || "0") === "0") {
      return { prefixGhost: "0", typed: "", typedSuffix: ",00", ghost: "", caret: true };
    }
    return { prefixGhost: "", typed: isFocused ? `${integerPart || "0"},` : "", typedSuffix: "", ghost: isFocused ? "00" : "0,00", caret: isFocused };
  }
  return {
    prefixGhost: "",
    typed: `${integerPart || "0"},${decimalPart}`,
    typedSuffix: "",
    ghost: "".padEnd(Math.max(0, 2 - decimalPart.length), "0"),
    caret: isFocused && decimalPart.length < 2,
  };
}

function buildCalendarDays(viewDate) {
  const year = viewDate.getFullYear();
  const month = viewDate.getMonth();
  const firstDay = new Date(year, month, 1);
  const startOffset = (firstDay.getDay() + 6) % 7;
  const startDate = new Date(year, month, 1 - startOffset);

  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(startDate);
    date.setDate(startDate.getDate() + index);
    return {
      date,
      iso: toISODate(date),
      isCurrentMonth: date.getMonth() === month,
    };
  });
}

function shiftMonth(date, delta) {
  return new Date(date.getFullYear(), date.getMonth() + delta, 1);
}

function parseISODate(value) {
  if (!value) return null;
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function toISODate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function getTodayDateString() {
  return toISODate(new Date());
}
