import logging
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from dotenv import load_dotenv

from scrapers import detect_platform, FETCHERS, PLATFORM_NAMES
from keyboards import build_calendar

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
APIFY_TOKEN = os.getenv("APIFY_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - ask user for social media links"""
    context.user_data['links'] = {}
    context.user_data['current_platform'] = None

    message = (
        "Привет! 👋\n\n"
        "Я помогу тебе анализировать охват постов в соцсетях.\n"
        "Отправь мне ссылки на профили:\n"
        "• Instagram\n"
        "• TikTok\n"
        "• YouTube\n\n"
        "Отправляй по одной ссылке, потом напиши 'готово'"
    )
    await update.message.reply_text(message)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle profile links"""
    text = update.message.text.strip()

    if text.lower() == 'готово':
        if not context.user_data.get('links'):
            await update.message.reply_text("Ты не отправил ни одну ссылку!")
            return

        await show_date_selector(update, context, 'start')
        return

    platform = detect_platform(text)
    if platform:
        context.user_data['links'][platform] = text
        await update.message.reply_text(f"✅ {PLATFORM_NAMES[platform]} добавлен!")
    else:
        await update.message.reply_text("❌ Я не распознал ссылку. Попробуй ещё раз.")


async def show_date_selector(update: Update, context: ContextTypes.DEFAULT_TYPE, selector_type):
    """Show calendar for date selection"""
    context.user_data['selector_type'] = selector_type
    today = datetime.now()
    keyboard = build_calendar(today.year, today.month, f"{selector_type}:nav")

    reply_markup = InlineKeyboardMarkup(keyboard)
    if selector_type == 'start':
        await update.message.reply_text("Выбери начальную дату:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Выбери конечную дату:", reply_markup=reply_markup)


async def calendar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle calendar navigation and date selection"""
    query = update.callback_query
    await query.answer()

    data = query.data
    selector_type = context.user_data.get('selector_type', 'start')

    if ':nav:' in data:
        # Navigation between months
        _, _, date_str = data.split(':')
        year, month = int(date_str[:4]), int(date_str[5:7])
        keyboard = build_calendar(year, month, f"{selector_type}:nav")
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_reply_markup(reply_markup=reply_markup)

    elif ':' in data:
        # Date selection
        parts = data.split(':')
        if len(parts) >= 3:
            date_str = parts[2]

            if selector_type == 'start':
                context.user_data['start_date'] = datetime.strptime(date_str, "%Y-%m-%d").date()
                await query.edit_message_text("✅ Начальная дата выбрана!\n\nТеперь выбери конечную дату:")
                await show_date_selector(query, context, 'end')
            else:
                context.user_data['end_date'] = datetime.strptime(date_str, "%Y-%m-%d").date()
                await query.edit_message_text("✅ Спасибо! Анализирую данные... ⏳")
                await run_analysis(query, context)


async def run_analysis(query, context):
    """Fetch data from Apify and generate report"""
    links = context.user_data.get('links', {})
    start_date = context.user_data.get('start_date')
    end_date = context.user_data.get('end_date')

    if not start_date or not end_date:
        await query.edit_message_text("❌ Ошибка при выборе дат")
        return

    report = await format_report(links, start_date, end_date)

    # Split report if too long (Telegram limit 4096 chars)
    if len(report) > 4000:
        chunks = [report[i:i+4000] for i in range(0, len(report), 4000)]
        for chunk in chunks:
            await query.message.reply_text(chunk)
    else:
        await query.edit_message_text(report)


async def format_report(links, start_date, end_date):
    """Generate analysis report"""
    report = f"📊 Анализ охвата ({start_date} — {end_date})\n\n"

    for platform, url in links.items():
        fetcher = FETCHERS.get(platform)
        if not fetcher:
            continue

        try:
            posts = await fetcher(url, start_date, end_date)
            if not posts:
                report += f"\n❌ {PLATFORM_NAMES[platform]}: нет данных\n"
                continue

            total_reach = sum(p.get('reach', 0) for p in posts)
            avg_reach = total_reach / len(posts) if posts else 0

            report += f"\n📱 {PLATFORM_NAMES[platform]}\n"
            report += f"Постов: {len(posts)}\n"
            report += f"Общий охват: {_fmt_num(total_reach)}\n"
            report += f"Средний: {_fmt_num(int(avg_reach))}\n\n"
            report += "Топ-4 по охватам:\n"

            top_posts = sorted(posts, key=lambda p: p.get('reach', 0), reverse=True)[:4]
            for i, post in enumerate(top_posts, 1):
                title = post.get('title', 'Пост без названия')[:30]
                reach = _fmt_num(post.get('reach', 0))
                report += f"{i}. {title}... — {reach}\n"

        except Exception as e:
            report += f"\n❌ {PLATFORM_NAMES[platform]}: {str(e)[:50]}\n"

    return report


def _fmt_num(n):
    """Format number with spaces"""
    return f"{n:,}".replace(",", " ")


if __name__ == "__main__":
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(calendar_callback))

    logger.info("Bot started")
    app.run_polling()
