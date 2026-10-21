
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

logging.basicConfig(level=logging.INFO)

TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎬 Kinolar", callback_data="movies")],
    ]

    if update.effective_user.id == ADMIN_ID:
        keyboard.append([
            InlineKeyboardButton("⚙️ Admin panel", callback_data="admin")
        ])

    await update.message.reply_text(
        "🍿 Kino botimizga xush kelibsiz!\n\n"
        "Davom etish uchun menyudan tanlang.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "admin":
        if query.from_user.id != ADMIN_ID:
            await query.answer("Ruxsat yo‘q!", show_alert=True)
            return

        await query.edit_message_text(
            "⚙️ Admin panel\n\n"
            "Keyingi bosqichda bu yerga kino qo‘shish "
            "va boshqarish tugmalarini ulaymiz."
        )

    elif query.data == "movies":
        await query.edit_message_text(
            "🎬 Hozircha kinolar qo‘shilmagan.\n"
            "Admin panel orqali kino qo‘shish funksiyasini keyin ulaymiz."
        )


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.run_polling()


if __name__ == "__main__":
    main()
