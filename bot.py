"""Telegram-бот: охват постов Instagram/TikTok/YouTube за выбранный период.

Сценарий:
1. /start — бот просит прислать ссылку на профиль (можно несколько, разных площадок).
2. Пользователь жмёт «Готово» — бот показывает календарь для выбора начальной и конечной даты.
3. Бот парсит данные через Apify и присылает охват по каждой площадке + топ-4 поста по охвату.
"""
import asyncio
import logging
import os
from datetime import date

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

from keyboards import build_calendar  # noqa: E402
from scrapers import FETCHERS, PLATFORM_NAMES, detect_platform  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("reach-bot")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

DONE_BUTTON = InlineKeyboardMarkup([[InlineKeyboardButton("Готово ✅", callback_data="links_done")]])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["links"] = {}
    context.user_data["step"] = "links"
    await update.message.reply_text(
        "Привет! Пришлите ссылку на профиль Instagram, TikTok или YouTube.\n\n"
        "Можно прислать несколько ссылок по очереди (разные площадки одного аккаунта) — "
        "когда закончите, нажмите «Готово».",
        reply_markup=DONE_BUTTON,
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("step")
    text = (update.message.text or "").strip()

    if step != "links":
        await update.message.reply_text("Сначала выберите даты на календаре выше 🙂 Если нужно начать заново — /start")
        return

    platform = detect_platform(text)
    if not platform:
        await update.message.reply_text("Не распознал ссылку. Пришлите ссылку на Instagram, TikTok или YouTube.")
        return

    context.user_data["links"][platform] = text
    await update.message.reply_text(
        "Добавлено: %s ✅\nПришлите ещё ссылку или нажмите «Готово»." % PLATFORM_NAMES[platform],
        reply_markup=DONE_BUTTON,
    )


async def links_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    links = context.user_data.get("links", {})
    if not links:
        await query.message.reply_text("Вы не прислали ни одной ссылки. Пришлите ссылку на профиль.")
        return

    context.user_data["step"] = "start_date"
    today = date.today()
    await query.message.reply_text(
        "Выберите НАЧАЛЬНУЮ дату периода:",
        reply_markup=build_calendar(today.year, today.month, "start"),
    )


async def calendar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()
    if data == "ignore":
        return

    prefix, kind, value = data.split(":", 2)

    if kind == "nav":
        year, month = map(int, value.split("-"))
        await query.edit_message_reply_markup(reply_markup=build_calendar(year, month, prefix))
        return

    if kind != "day":
        return

    picked = date.fromisoformat(value)

    if prefix == "start":
        context.user_data["start_date"] = picked
        context.user_data["step"] = "end_date"
        await query.edit_message_text("Начальная дата: %s" % picked.strftime("%d.%m.%Y"))
        await query.message.reply_text(
            "Теперь выберите КОНЕЧНУЮ дату периода:",
            reply_markup=build_calendar(picked.year, picked.month, "end"),
        )
        return

    # prefix == "end"
    start = context.user_data.get("start_date")
    if not start:
        await query.message.reply_text("Сначала выберите начальную дату — начните заново: /start")
        return
    if picked < start:
        await query.message.reply_text(
            "Конечная дата раньше начальной. Выберите ещё раз:",
            reply_markup=build_calendar(picked.year, picked.month, "end"),
        )
        return

    context.user_data["end_date"] = picked
    await query.edit_message_text("Конечная дата: %s" % picked.strftime("%d.%m.%Y"))
    await run_analysis(query.message, context)


async def run_analysis(message, context: ContextTypes.DEFAULT_TYPE):
    links = dict(context.user_data["links"])
    start = context.user_data["start_date"]
    end = context.user_data["end_date"]
    context.user_data["step"] = "processing"

    await message.reply_text(
        "Собираю данные с %s по %s для %d площадок(и)... Это может занять пару минут ⏳"
        % (start.strftime("%d.%m.%Y"), end.strftime("%d.%m.%Y"), len(links))
    )

    for platform, url in links.items():
        try:
            fetcher = FETCHERS[platform]
            posts = await asyncio.to_thread(fetcher, url, start, end)
        except Exception:
            logger.exception("fetch failed for %s", platform)
            await message.reply_text("⚠️ Не удалось собрать данные %s. Попробуйте позже." % PLATFORM_NAMES[platform])
            continue
        await message.reply_text(format_report(platform, posts), disable_web_page_preview=True)

    context.user_data["step"] = None
    await message.reply_text("Готово! Чтобы посчитать ещё раз — /start")


def _fmt_num(n) -> str:
    return "{:,}".format(int(n)).replace(",", " ")


def format_report(platform: str, posts: list) -> str:
    name = PLATFORM_NAMES[platform]
    if not posts:
        return "%s\nЗа выбранный период публикаций не найдено." % name

    total_views = sum(p["views"] for p in posts)
    avg_views = total_views / len(posts)

    lines = [
        name,
        "Постов: %d" % len(posts),
        "Суммарный охват: %s" % _fmt_num(total_views),
        "Средний охват: %s" % _fmt_num(avg_views),
        "",
        "Топ-4 по охвату:",
    ]
    top4 = sorted(posts, key=lambda p: p["views"], reverse=True)[:4]
    for i, p in enumerate(top4, 1):
        lines.append("%d. %s — %s просмотров\n%s" % (i, p["date"], _fmt_num(p["views"]), p["url"]))

    return "\n".join(lines)


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(links_done, pattern="^links_done$"))
    app.add_handler(CallbackQueryHandler(calendar_callback, pattern="^(start|end):"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
