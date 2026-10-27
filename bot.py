
import os
import logging
import sqlite3

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters,
)

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

TOKEN = os.environ["BOT_TOKEN"]

ADMIN_IDS = {
    int(os.environ["ADMIN_ID"]),
    8273813142,
}

CHANNELS = [
    ("@ujas_kino_tarjima", "https://t.me/ujas_kino_tarjima"),
    ("@myslitishina", "https://t.me/myslitishina"),
]

DB_FILE = "movies.db"
PROMPT = "🍿 Qidirmoqchi bo‘lgan kinoyingiz kodini yozing."


def is_admin(user_id):
    return user_id in ADMIN_IDS


def db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            file_id TEXT NOT NULL
        )
    """)
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(movies)")
    }
    if "code" not in columns:
        conn.execute("ALTER TABLE movies ADD COLUMN code TEXT")
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_movies_code
        ON movies(code) WHERE code IS NOT NULL
    """)
    return conn


def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Kino qo‘shish", callback_data="add")],
        [InlineKeyboardButton("🗑️ Kino o‘chirish", callback_data="delete")],
        [InlineKeyboardButton("📋 Kino ro‘yxati", callback_data="list")],
    ])


def subscription_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Ujas Kino Tarjima", url=CHANNELS[0][1])],
        [InlineKeyboardButton("📢 Myslitishina", url=CHANNELS[1][1])],
        [InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_sub")],
    ])


async def is_subscribed(user_id, context):
    if is_admin(user_id):
        return True

    for channel_id, _ in CHANNELS:
        try:
            member = await context.bot.get_chat_member(
                chat_id=channel_id,
                user_id=user_id,
            )
            if member.status not in ("member", "administrator", "creator"):
                return False
        except Exception:
            logging.exception("Obuna tekshirish xatosi: %s", channel_id)
            return False

    return True


async def ask_to_subscribe(message):
    await message.reply_text(
        "🍿 Botdan foydalanish uchun quyidagi ikkala kanalga "
        "obuna bo‘ling, so‘ng tekshirish tugmasini bosing.",
        reply_markup=subscription_keyboard(),
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if not await is_subscribed(update.effective_user.id, context):
        await ask_to_subscribe(update.effective_message)
        return
    await update.effective_message.reply_text(PROMPT)


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text("⛔ Bu buyruq faqat adminlar uchun.")
        return
    context.user_data.clear()
    await update.effective_message.reply_text(
        "⚙️ Admin panel", reply_markup=admin_menu()
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if is_admin(update.effective_user.id):
        await update.effective_message.reply_text(
            "❌ Amal bekor qilindi.", reply_markup=admin_menu()
        )
    else:
        await update.effective_message.reply_text(PROMPT)


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "check_sub":
        if await is_subscribed(user_id, context):
            await query.edit_message_text(PROMPT)
        else:
            await query.answer(
                "Ikkala kanalga ham obuna bo‘ling!", show_alert=True
            )
        return

    if not is_admin(user_id):
        await query.answer("Bu amal adminlar uchun!", show_alert=True)
        return

    if data == "add":
        context.user_data.clear()
        context.user_data["state"] = "waiting_title"
        await query.edit_message_text(
            "🎬 Kino nomini yuboring.\nBekor qilish: /cancel"
        )
        return

    if data == "list":
        with db() as conn:
            movies = conn.execute(
                "SELECT code, title FROM movies ORDER BY id DESC"
            ).fetchall()
        text = (
            "📋 Kinolar:\n\n" + "\n".join(
                f"🔢 {code or 'Kod belgilanmagan'} — {title}"
                for code, title in movies
            )
            if movies else "Hozircha kino yo‘q."
        )
        await query.edit_message_text(text, reply_markup=admin_menu())
        return

    if data == "delete":
        with db() as conn:
            movies = conn.execute(
                "SELECT id, code, title FROM movies ORDER BY id DESC"
            ).fetchall()
        if not movies:
            await query.edit_message_text(
                "O‘chirish uchun kino yo‘q.", reply_markup=admin_menu()
            )
            return

        keyboard = [
            [InlineKeyboardButton(
                f"🗑️ {code or 'Kodsiz'} — {title}",
                callback_data=f"del:{movie_id}",
            )]
            for movie_id, code, title in movies
        ]
        keyboard.append([
            InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_home")
        ])
        await query.edit_message_text(
            "O‘chirmoqchi bo‘lgan kinoni tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data == "admin_home":
        await query.edit_message_text("⚙️ Admin panel", reply_markup=admin_menu())
        return

    if data.startswith("del:"):
        try:
            movie_id = int(data.split(":", 1)[1])
        except ValueError:
            await query.edit_message_text(
                "❌ Noto‘g‘ri kino raqami.", reply_markup=admin_menu()
            )
            return

        with db() as conn:
            conn.execute("DELETE FROM movies WHERE id = ?", (movie_id,))
        await query.edit_message_text(
            "✅ Kino o‘chirildi.", reply_markup=admin_menu()
        )


async def receive_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message:
        return

    user_id = update.effective_user.id
    state = context.user_data.get("state")

    if is_admin(user_id) and state == "waiting_title":
        if not message.text or not message.text.strip():
            await message.reply_text("Kino nomini matn qilib yuboring.")
            return
        context.user_data["movie_title"] = message.text.strip()
        context.user_data["state"] = "waiting_code"
        await message.reply_text(
            "🔢 Kino kodini yuboring. Masalan: 777 yoki 2026.\n"
            "Bekor qilish: /cancel"
        )
        return

    if is_admin(user_id) and state == "waiting_code":
        if not message.text or not message.text.strip():
            await message.reply_text("Kino kodini matn qilib yuboring.")
            return
        code = message.text.strip()
        with db() as conn:
            exists = conn.execute(
                "SELECT 1 FROM movies WHERE code = ?", (code,)
            ).fetchone()
        if exists:
            await message.reply_text("❌ Bu kod band. Boshqa kod tanlang.")
            return
        context.user_data["movie_code"] = code
        context.user_data["state"] = "waiting_video"
        await message.reply_text(
            f"✅ Kod: {code}\nEndi kinoning videosini yuboring."
        )
        return

    if is_admin(user_id) and state == "waiting_video":
        if not message.video:
            await message.reply_text("Kinoni Telegram videosi sifatida yuboring.")
            return

        title = context.user_data["movie_title"]
        code = context.user_data["movie_code"]
        try:
            with db() as conn:
                conn.execute(
                    "INSERT INTO movies (title, file_id, code) VALUES (?, ?, ?)",
                    (title, message.video.file_id, code),
                )
        except sqlite3.IntegrityError:
            await message.reply_text("Bu kod band. /cancel yozib qaytadan boshlang.")
            context.user_data.clear()
            return

        context.user_data.clear()
        await message.reply_text(
            f"✅ Kino saqlandi!\n🎬 {title}\n🔢 Kod: {code}\n\n"
            "Yana kino qo‘shish uchun /admin yozing."
        )
        return

    if not await is_subscribed(user_id, context):
        await ask_to_subscribe(message)
        return

    if not message.text:
        await message.reply_text(PROMPT)
        return

    code = message.text.strip()
    with db() as conn:
        movie = conn.execute(
            "SELECT title, file_id FROM movies WHERE code = ?", (code,)
        ).fetchone()

    if not movie:
        await message.reply_text(
            "❌ Bunday koddagi kino topilmadi. Kodni tekshirib qayta yuboring."
        )
        return

    title, file_id = movie
    await context.bot.send_video(
        chat_id=user_id,
        video=file_id,
        caption=f"🎬 {title}",
        protect_content=True,
    )


def main():
    conn = db()
    conn.close()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(
        filters.ALL & ~filters.COMMAND, receive_message
    ))
    logging.info("Bot ishga tushmoqda. Adminlar: %s", ADMIN_IDS)
    app.run_polling()


if __name__ == "__main__":
    main()
