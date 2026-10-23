
import os
import logging
import threading
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("BOT_TOKEN")
ADMINS = [8468706982, 8893604839]

web = Flask(__name__)

@web.get("/")
def home():
    return "KEY HOUSE bot is running!", 200

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web.run(host="0.0.0.0", port=port)

MENU = [
    ["🏠 Купить", "🔑 Снять"],
    ["💰 Продать", "📢 Сдать"],
    ["📩 Отправить предложение риэлтору"],
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = ReplyKeyboardMarkup(MENU, resize_keyboard=True)
    await update.message.reply_text(
        "🏡 Добро пожаловать в KEY HOUSE!\n\n"
        "Недвижимость, которую хочется назвать домом.\n\n"
        "Выберите, что вас интересует:",
        reply_markup=keyboard,
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text

    if text in ["🏠 Купить", "🔑 Снять", "💰 Продать", "📢 Сдать"]:
        context.user_data["request_type"] = text
        await update.message.reply_text(
            f"Вы выбрали: {text}\n\n"
            "Опишите вашу заявку: район, бюджет, количество комнат "
            "или другие пожелания."
        )
        return

    if text == "📩 Отправить предложение риэлтору":
        context.user_data["request_type"] = "Предложение риэлтору"
        await update.message.reply_text(
            "Напишите ваше предложение или описание недвижимости."
        )
        return

    request_type = context.user_data.get("request_type")
    if not request_type:
        await update.message.reply_text("Нажмите /start и выберите раздел.")
        return

    username = f"@{user.username}" if user.username else "нет username"
    message = (
        "📩 НОВАЯ ЗАЯВКА — KEY HOUSE\n\n"
        f"Тип: {request_type}\n"
        f"Имя: {user.full_name}\n"
        f"Username: {username}\n"
        f"ID клиента: {user.id}\n\n"
        f"Заявка:\n{text}"
    )

    delivered = 0
    for admin_id in ADMINS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=message)
            delivered += 1
        except Exception:
            logging.exception("Не удалось отправить заявку администратору %s", admin_id)

    if delivered:
        await update.message.reply_text(
            "✅ Спасибо! Ваша заявка отправлена риэлтору KEY HOUSE."
        )
        context.user_data.pop("request_type", None)
    else:
        await update.message.reply_text(
            "Не удалось доставить заявку. Попробуйте позже."
        )

def main():
    if not TOKEN:
        raise RuntimeError("Не задан BOT_TOKEN в Render")

    threading.Thread(target=run_web, daemon=True).start()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    app.run_polling()

if __name__ == "__main__":
    main()

