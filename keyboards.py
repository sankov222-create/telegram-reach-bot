from datetime import datetime, timedelta
from telegram import InlineKeyboardButton

MONTHS_RU = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
]

WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def build_calendar(year, month, prefix):
    """Build inline calendar keyboard"""
    keyboard = []

    # Month/Year header
    month_name = MONTHS_RU[month - 1]
    keyboard.append([
        InlineKeyboardButton(f"< {month-1 if month > 1 else 12}", callback_data=f"{prefix}:{datetime(year if month > 1 else year-1, month-1 if month > 1 else 12, 1).strftime('%Y-%m')}"),
        InlineKeyboardButton(f"{month_name} {year}", callback_data=f"{prefix}:none"),
        InlineKeyboardButton(f"{month+1 if month < 12 else 1} >", callback_data=f"{prefix}:{datetime(year if month < 12 else year+1, month+1 if month < 12 else 1, 1).strftime('%Y-%m')}")
    ])

    # Weekday headers
    weekday_row = [InlineKeyboardButton(day, callback_data=f"{prefix}:none") for day in WEEKDAYS_RU]
    keyboard.append(weekday_row)

    # Days
    first_day = datetime(year, month, 1)
    start_weekday = first_day.weekday()
    days_in_month = (datetime(year, month + 1, 1) - timedelta(days=1)).day if month < 12 else 31

    day_row = [InlineKeyboardButton(" ", callback_data=f"{prefix}:none") for _ in range(start_weekday)]

    for day in range(1, days_in_month + 1):
        date_str = f"{year}-{month:02d}-{day:02d}"
        day_row.append(InlineKeyboardButton(str(day), callback_data=f"{prefix}:{date_str}"))

        if len(day_row) == 7:
            keyboard.append(day_row)
            day_row = []

    if day_row:
        keyboard.append(day_row)

    return keyboard
