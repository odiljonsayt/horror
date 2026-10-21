
import os
import logging
import sqlite3

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)

TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
CHANNEL_ID = os.environ.get("CHANNEL_ID", "").strip()
CHANNEL_URL = os.environ.get("CHANNEL_URL", "").strip()
DB_FILE = "movies.db"


def db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            file_id TEXT NOT NULL
        )
    """)
    return conn


def get_movies():
    with db() as conn:
        return conn.execute(
            "SELECT id, title FROM movies ORDER BY id DESC"
        ).fetchall()


def main_menu(user_id):
    rows = [[
        InlineKeyboardButton("🎬 Kinolar", callback_data="movies")
    ]]
    if user_id == ADMIN_ID:
        rows.append([
            InlineKeyboardButton("⚙️ Admin panel", callback_data="admin")
        ])
    return InlineKeyboardMarkup(rows)


def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Kino qo‘shish", callback_data="add")],
        [InlineKeyboardButton("🗑️ Kino o‘chirish", callback_data="delete")],
        [InlineKeyboardButton("📋 Kino ro‘yxati", callback_data="list")],
        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="home")],
    ])


async def is_subscribed(user_id, context):
    if not CHANNEL_ID:
        return True

    try:
        member = await context.bot.get_chat_member(
            chat_id=CHANNEL_ID,
            user_id=user_id,
        )
        return member.status in ("member", "administrator", "creator")
    except Exception:
        logging.exception("Obunani tekshirishda xato")
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    if CHANNEL_ID and not await is_subscribed(
        update.effective_user.id, context
    ):
        keyboard = []
        if CHANNEL_URL:
            keyboard.append([
                InlineKeyboardButton(
                    "📢 Kanalga obuna bo‘lish",
                    url=CHANNEL_URL,
                )
            ])
        keyboard.append([
            InlineKeyboardButton(
                "✅ Obunani tekshirish",
                callback_data="check_sub",
            )
        ])
        await update.message.reply_text(
            "🍿 Kino botiga xush kelibsiz!\n\n"
            "Davom etish uchun kanalimizga obuna bo‘ling.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    await update.message.reply_text(
        "🍿 Kino botimizga xush kelibsiz!\n\n"
        "Menyudan tanlang:",
        reply_markup=main_menu(update.effective_user.id),
    )


async def show_movies(query):
    movies = get_movies()

    if not movies:
        await query.edit_message_text(
            "🎬 Hozircha kinolar qo‘shilmagan.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 Bosh menyu", callback_data="home")
            ]]),
        )
        return

    keyboard = [
        [InlineKeyboardButton(
            f"🎬 {title}", callback_data=f"movie:{movie_id}"
        )]
        for movie_id, title in movies
    ]
    keyboard.append([
        InlineKeyboardButton("🏠 Bosh menyu", callback_data="home")
    ])

    await query.edit_message_text(
        "🎬 Kerakli kinoni tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "check_sub":
        if not CHANNEL_ID:
            await query.edit_message_text(
                "Kanal sozlanmagan. Admin bilan bog‘laning."
            )
        elif await is_subscribed(user_id, context):
            await query.edit_message_text(
                "✅ Obuna tasdiqlandi! Botga /start yuboring."
            )
        else:
            await query.answer(
                "Avval kanalga obuna bo‘ling!", show_alert=True
            )
        return

    if CHANNEL_ID and not await is_subscribed(user_id, context):
        await query.answer(
            "Avval kanalga obuna bo‘ling!", show_alert=True
        )
        return

    if data == "home":
        context.user_data.clear()
        await query.edit_message_text(
            "🏠 Bosh menyu:",
            reply_markup=main_menu(user_id),
        )
        return

    if data == "movies":
        await show_movies(query)
        return

    if data == "admin":
        if user_id != ADMIN_ID:
            await query.answer("Ruxsat yo‘q!", show_alert=True)
            return
        context.user_data.clear()
        await query.edit_message_text(
            "⚙️ Admin panel",
            reply_markup=admin_menu(),
        )
        return

    if data == "add":
        if user_id != ADMIN_ID:
            return
        context.user_data.clear()
        context.user_data["state"] = "waiting_title"
        await query.edit_message_text(
            "➕ Kino nomini yuboring.\n\n"
            "Bekor qilish uchun /cancel yozing."
        )
        return

    if data == "list":
        if user_id != ADMIN_ID:
            return
        movies = get_movies()
        text = "📋 Kinolar ro‘yxati:\n\n"
        text += "\n".join(
            f"{i}. {title}" for i, (_, title) in enumerate(movies, 1)
        ) if movies else "Hozircha kino yo‘q."
        await query.edit_message_text(
            text,
            reply_markup=admin_menu(),
        )
        return

    if data == "delete":
        if user_id != ADMIN_ID:
            return
        movies = get_movies()
        if not movies:
            await query.edit_message_text(
                "O‘chirish uchun kino yo‘q.",
                reply_markup=admin_menu(),
            )
            return
        keyboard = [
            [InlineKeyboardButton(
                f"🗑️ {title}", callback_data=f"del:{movie_id}"
            )]
            for movie_id, title in movies
        ]
        keyboard.append([
            InlineKeyboardButton("⬅️ Orqaga", callback_data="admin")
        ])
        await query.edit_message_text(
            "O‘chirmoqchi bo‘lgan kinoni tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data.startswith("del:"):
        if user_id != ADMIN_ID:
            return
        movie_id = int(data.split(":")[1])
        with db() as conn:
            conn.execute("DELETE FROM movies WHERE id = ?", (movie_id,))
        await query.edit_message_text(
            "✅ Kino o‘chirildi.",
            reply_markup=admin_menu(),
        )
        return

    if data.startswith("movie:"):
        movie_id = int(data.split(":")[1])
        with db() as conn:
            movie = conn.execute(
                "SELECT title, file_id FROM movies WHERE id = ?",
                (movie_id,),
            ).fetchone()

        if not movie:
            await query.message.reply_text("Bu kino topilmadi.")
            return

        title, file_id = movie
        await context.bot.send_video(
            chat_id=user_id,
            video=file_id,
            caption=f"🎬 {title}",
            protect_content=True,
        )


async def receive_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    if update.effective_user.id != ADMIN_ID:
        return

    state = context.user_data.get("state")

    if state == "waiting_title":
        if not update.message.text:
            await update.message.reply_text("Kino nomini matn qilib yuboring.")
            return

        context.user_data["movie_title"] = update.message.text.strip()
        context.user_data["state"] = "waiting_video"
        await update.message.reply_text(
            "✅ Nom saqlandi.\n\n"
            "Endi kinoning videosini Telegram orqali yuboring."
        )
        return

    if state == "waiting_video":
        video = update.message.video
        if not video:
            await update.message.reply_text(
                "Iltimos, kino faylini Telegram videosi sifatida yuboring."
            )
            return

        title = context.user_data.get("movie_title", "Nomsiz kino")
        with db() as conn:
            conn.execute(
                "INSERT INTO movies (title, file_id) VALUES (?, ?)",
                (title, video.file_id),
            )

        context.user_data.clear()
        await update.message.reply_text(
            f"✅ «{title}» muvaffaqiyatli qo‘shildi!",
            reply_markup=admin_menu(),
        )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Bekor qilindi.",
        reply_markup=main_menu(update.effective_user.id),
    )


def main():
    db().close()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(
        filters.ALL & ~filters.COMMAND,
        receive_message,
    ))

    app.run_polling()


if __name__ == "__main__":
    main()
