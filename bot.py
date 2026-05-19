import logging
import sqlite3
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes

TOKEN = "8740908913:AAEZkbe7NNLdSz-6QZqp9TMEE0UhW0f3cD4"

logging.basicConfig(level=logging.INFO)

conn = sqlite3.connect("dict.db", check_same_thread=False)
conn.executescript("""
    CREATE TABLE IF NOT EXISTS words (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, word TEXT, translation TEXT,
        UNIQUE(user_id, word)
    );
""")
conn.commit()

ADDING = 1


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я Dictionary Bot.\n\n"
        "/add — добавить слово\n"
        "/list — список слов\n"
        "/quiz — тест\n"
        "/delete <слово> — удалить"
    )

async def add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введи: слово перевод\nНапример: cat кот\n/cancel — отмена")
    return ADDING

async def add_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    parts = update.message.text.split(" ", 1)
    if len(parts) < 2:
        await update.message.reply_text("Введи слово и перевод через пробел, например: cat кот")
        return ADDING
    word, translation = parts[0].strip(), parts[1].strip()
    try:
        conn.execute("INSERT INTO words(user_id,word,translation) VALUES(?,?,?)",
                     (update.effective_user.id, word, translation))
        conn.commit()
        await update.message.reply_text(f"✅ {word} — {translation}")
    except sqlite3.IntegrityError:
        await update.message.reply_text(f"⚠️ Слово «{word}» уже есть")
    return ConversationHandler.END

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END

async def list_words(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = conn.execute("SELECT word, translation FROM words WHERE user_id=? ORDER BY word",
                        (update.effective_user.id,)).fetchall()
    if not rows:
        await update.message.reply_text("Словарь пуст. Добавь слово через /add")
        return
    text = "\n".join(f"• {w} — {t}" for w, t in rows)
    await update.message.reply_text(f"📚 Твои слова:\n\n{text}")

async def delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Использование: /delete <слово>")
        return
    word = " ".join(ctx.args)
    cur = conn.execute("DELETE FROM words WHERE user_id=? AND word=?",
                       (update.effective_user.id, word))
    conn.commit()
    if cur.rowcount:
        await update.message.reply_text(f"🗑 «{word}» удалено")
    else:
        await update.message.reply_text(f"❌ Слово «{word}» не найдено")

async def quiz(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    rows = conn.execute("SELECT id, word, translation FROM words WHERE user_id=?", (uid,)).fetchall()
    if len(rows) < 2:
        await update.message.reply_text("Нужно минимум 2 слова для квиза. Добавь через /add")
        return
    correct = random.choice(rows)
    wrong_options = random.sample([r for r in rows if r[0] != correct[0]], min(3, len(rows)-1))
    options = [r[2] for r in wrong_options] + [correct[2]]
    random.shuffle(options)
    keyboard = [[InlineKeyboardButton(o, callback_data=f"quiz_{correct[0]}_{o == correct[2]}")] for o in options]
    await update.message.reply_text(
        f"❓ Как переводится *{correct[1]}*?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def quiz_answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, word_id, is_correct = query.data.split("_")
    row = conn.execute("SELECT word, translation FROM words WHERE id=?", (word_id,)).fetchone()
    if is_correct == "True":
        await query.edit_message_text(f"✅ Правильно! {row[0]} — {row[1]}")
    else:
        await query.edit_message_text(f"❌ Неверно. {row[0]} — {row[1]}")

# ── Запуск ──
app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("list", list_words))
app.add_handler(CommandHandler("delete", delete))
app.add_handler(CommandHandler("quiz", quiz))
app.add_handler(ConversationHandler(
    entry_points=[CommandHandler("add", add)],
    states={ADDING: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_input)]},
    fallbacks=[CommandHandler("cancel", cancel)],
))
app.add_handler(CallbackQueryHandler(quiz_answer, pattern="^quiz_"))
app.run_polling()