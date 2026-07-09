"""Инлайн-календарь для выбора даты в Telegram."""
import calendar

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

MONTHS_RU = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]
WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def build_calendar(year: int, month: int, prefix: str) -> InlineKeyboardMarkup:
    """prefix — "start" или "end", чтобы отличать календарь начальной/конечной даты."""
    rows = []
    rows.append([InlineKeyboardButton("%s %d" % (MONTHS_RU[month - 1], year), callback_data="ignore")])
    rows.append([InlineKeyboardButton(d, callback_data="ignore") for d in WEEKDAYS_RU])

    for week in calendar.monthcalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                row.append(InlineKeyboardButton(
                    str(day),
                    callback_data="%s:day:%04d-%02d-%02d" % (prefix, year, month, day),
                ))
        rows.append(row)

    prev_month, prev_year = (month - 1, year) if month > 1 else (12, year - 1)
    next_month, next_year = (month + 1, year) if month < 12 else (1, year + 1)
    rows.append([
        InlineKeyboardButton("<", callback_data="%s:nav:%04d-%02d" % (prefix, prev_year, prev_month)),
        InlineKeyboardButton(">", callback_data="%s:nav:%04d-%02d" % (prefix, next_year, next_month)),
    ])
    return InlineKeyboardMarkup(rows)
