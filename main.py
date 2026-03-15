import os
import asyncio
import logging
import random

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)
from telegram.constants import ParseMode

import storage
import forum
import crypto
import video
import ai
import tts

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_TOKEN", "8567578486:AAFVxpzrIDXIGf8K5eD7x5uGbyDM9Fnd00c")
DATA_FILE = "bot/data.json"
KEEP_ALIVE_PORT = 5000


# ─── helpers ────────────────────────────────────────────────────────────────

def get_name(chat_id) -> str:
    return storage.get_bot_name(storage.load(DATA_FILE), chat_id)


def build_menu(data: dict, chat_id) -> InlineKeyboardMarkup:
    chat = storage.get_chat(data, chat_id)
    voice_on  = chat.get("voice", False)
    focus_on  = chat.get("focus", False)
    active    = chat.get("active", False)
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"{'🔔 Уведомления ВКЛ' if active else '🔕 Уведомления ВЫКЛ'}",
                callback_data="do:toggle_active"
            ),
        ],
        [
            InlineKeyboardButton(
                f"🎯 Фокус: {'🟢' if focus_on else '🔴'}",
                callback_data="do:focus"
            ),
            InlineKeyboardButton(
                f"🎙 Голос: {'🟢' if voice_on else '🔴'}",
                callback_data="do:voice"
            ),
        ],
        [
            InlineKeyboardButton("👁 Слежка — помощь",  callback_data="info:watch"),
            InlineKeyboardButton("📋 Список наблюдения", callback_data="do:list"),
        ],
        [
            InlineKeyboardButton("💰 Курсы крипты",  callback_data="do:crypto"),
            InlineKeyboardButton("💱 Конвертер",     callback_data="info:convert"),
        ],
        [
            InlineKeyboardButton("✏️ Имя бота — помощь", callback_data="info:name"),
            InlineKeyboardButton("🔄 Сброс ИИ",          callback_data="do:reset"),
        ],
        [
            InlineKeyboardButton("❓ Все команды", callback_data="do:help"),
        ],
    ])


async def send_reply(update: Update, text: str, voice_on: bool,
                     parse_mode=None):
    """Send voice + caption if voice is on, otherwise plain text."""
    if voice_on:
        path = await asyncio.get_event_loop().run_in_executor(
            None, tts.text_to_voice, text
        )
        if path:
            try:
                with open(path, "rb") as f:
                    caption = tts.clean_html(text)[:1024]
                    await update.message.reply_voice(voice=f, caption=caption)
                tts.remove_voice_file(path)
                return
            except Exception as e:
                logger.error(f"Voice send error: {e}")
                tts.remove_voice_file(path)
    await update.message.reply_text(text, parse_mode=parse_mode)


# ─── commands ────────────────────────────────────────────────────────────────

async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data = storage.load(DATA_FILE)
    name = storage.get_bot_name(data, chat_id)
    await update.message.reply_text(
        f"📱 <b>Главное меню — {name}</b>\n\nВыбери нужную функцию:",
        reply_markup=build_menu(data, chat_id),
        parse_mode=ParseMode.HTML
    )


async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    data = storage.load(DATA_FILE)
    chat = storage.get_chat(data, chat_id)
    name = storage.get_bot_name(data, chat_id)
    action = query.data

    if action == "do:toggle_active":
        chat["active"] = not chat.get("active", False)
        storage.save(data, DATA_FILE)
        state = "🔔 включены" if chat["active"] else "🔕 выключены"
        await query.answer(f"Уведомления {state}", show_alert=True)

    elif action == "do:focus":
        chat["focus"] = not chat.get("focus", False)
        storage.save(data, DATA_FILE)
        state = "🟢 ВКЛЮЧЁН" if chat["focus"] else "🔴 ВЫКЛЮЧЕН"
        await query.answer(f"Режим фокуса: {state}", show_alert=True)

    elif action == "do:voice":
        chat["voice"] = not chat.get("voice", False)
        storage.save(data, DATA_FILE)
        state = "🟢 ВКЛЮЧЁН" if chat["voice"] else "🔴 ВЫКЛЮЧЕН"
        await query.answer(f"Голосовые ответы: {state}", show_alert=True)

    elif action == "do:list":
        watch = chat.get("watch", {})
        muted = chat.get("muted", [])
        focus = chat.get("focus", False)
        if not watch:
            await query.answer("Список наблюдения пуст", show_alert=True)
        else:
            mode_map = {"both": "обе стороны", "author": "автор", "target": "цель"}
            lines = [f"Фокус: {'вкл' if focus else 'выкл'}\n"]
            for nick, mode in watch.items():
                m = " (заглушен)" if nick in muted else ""
                lines.append(f"• {nick} — {mode_map.get(mode, mode)}{m}")
            await query.answer("\n".join(lines), show_alert=True)

    elif action == "do:crypto":
        await query.message.reply_text("⏳ Загружаю курсы...")
        result = crypto.get_top_prices()
        await query.message.reply_text(result, parse_mode=ParseMode.HTML)

    elif action == "do:reset":
        ai.clear_history(chat_id)
        await query.answer("🔄 История ИИ сброшена!", show_alert=True)

    elif action == "do:help":
        text = (
            "📋 <b>Команды:</b>\n\n"
            "/start — подключить чат\n/stop — отключить\n/menu — это меню\n\n"
            "/watch &lt;ник&gt; — следить\n/watchauthor /watchtarget\n"
            "/unwatch /mute /unmute /list\n/focus — режим фокуса\n\n"
            "/crypto — курсы\n/convert 1 BTC USD\n\n"
            "/voice — голосовые ответы\n\n"
            "/setname &lt;пароль&gt; &lt;имя&gt;\n"
            "/setpassword &lt;старый&gt; &lt;новый&gt;\n"
            "/myname — текущее имя\n\n"
            "/reset — сброс ИИ\n\n"
            "📹 Ссылка YouTube/Instagram → скачает видео"
        )
        await query.message.reply_text(text, parse_mode=ParseMode.HTML)

    elif action == "info:watch":
        await query.answer(
            "👁 Команды слежки:\n"
            "/watch <ник> — обе стороны\n"
            "/watchauthor <ник> — если он пишет жалобу\n"
            "/watchtarget <ник> — если жалуются на него\n"
            "/unwatch <ник> — убрать\n"
            "/mute <ник> — заглушить\n"
            "/focus — только наблюдаемые",
            show_alert=True
        )

    elif action == "info:convert":
        await query.answer(
            "💱 Конвертер:\n/convert 1 BTC USD\n/convert 100 USD ETH\n/convert 0.5 ETH BNB",
            show_alert=True
        )

    elif action == "info:name":
        await query.answer(
            "✏️ Имя бота:\n"
            "/setname <пароль> <имя>\n"
            "Пароль по умолчанию: maks2024\n\n"
            "/setpassword <старый> <новый>\n"
            "/myname — узнать текущее имя",
            show_alert=True
        )

    data = storage.load(DATA_FILE)
    try:
        await query.edit_message_reply_markup(
            reply_markup=build_menu(data, chat_id)
        )
    except Exception:
        pass


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data = storage.load(DATA_FILE)
    chat = storage.get_chat(data, chat_id)
    chat["active"] = True
    storage.save(data, DATA_FILE)
    name = storage.get_bot_name(data, chat_id)
    await update.message.reply_text(
        f"✅ <b>Чат подключён!</b>\n\n"
        f"Привет, я <b>{name}</b> — пиши мне что угодно 👋\n\n"
        f"Используй /menu для удобного доступа ко всем функциям.",
        parse_mode=ParseMode.HTML
    )


async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = storage.load(DATA_FILE)
    chat = storage.get_chat(data, update.effective_chat.id)
    chat["active"] = False
    storage.save(data, DATA_FILE)
    await update.message.reply_text("🔴 Уведомления отключены. /start чтобы включить снова.")


async def cmd_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = storage.load(DATA_FILE)
    chat = storage.get_chat(data, update.effective_chat.id)
    chat["voice"] = not chat.get("voice", False)
    storage.save(data, DATA_FILE)
    on = chat["voice"]
    if on:
        await update.message.reply_text(
            "🎙 Голосовые ответы <b>ВКЛЮЧЕНЫ</b>!\n"
            "Теперь я буду отвечать голосом 🔊\n\n"
            "Голос: женский (русский)\n"
            "/voice — выключить",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text("🔇 Голосовые ответы выключены. /voice чтобы включить.")


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = get_name(update.effective_chat.id)
    text = (
        f"📋 <b>Доступные команды:</b>\n\n"
        "🔌 <b>Подключение:</b>\n"
        "/start — подключить чат/группу\n"
        "/stop — отключить уведомления\n"
        "/menu — главное меню 📱\n\n"
        "🔍 <b>Наблюдение:</b>\n"
        "/watch &lt;ник&gt; — следить в обе стороны\n"
        "/watchauthor &lt;ник&gt; — если он пишет жалобу\n"
        "/watchtarget &lt;ник&gt; — если жалуются на него\n"
        "/unwatch &lt;ник&gt; — удалить\n"
        "/mute /unmute &lt;ник&gt; — заглушить/включить\n"
        "/list — список наблюдения\n"
        "/focus — режим фокуса\n\n"
        "💰 <b>Крипта:</b>\n"
        "/crypto — курсы\n"
        "/convert 1 BTC USD — конвертер\n\n"
        f"🤖 <b>ИИ {name}:</b>\n"
        "/reset — сбросить историю\n\n"
        "🎙 <b>Голос:</b>\n"
        "/voice — вкл/выкл голосовые ответы\n\n"
        "✏️ <b>Имя бота:</b>\n"
        "/setname &lt;пароль&gt; &lt;имя&gt;\n"
        "/setpassword &lt;старый&gt; &lt;новый&gt;\n"
        "/myname — текущее имя\n\n"
        "📹 Ссылка YouTube/Instagram → скачает видео\n\n"
        "💬 В группах: упомяни @бот или ответь на сообщение"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_setname(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text(
            "✏️ Использование: /setname &lt;пароль&gt; &lt;новое_имя&gt;\n"
            "Пример: /setname maks2024 Алекс",
            parse_mode=ParseMode.HTML
        )
        return
    password = ctx.args[0]
    new_name = " ".join(ctx.args[1:]).strip()
    data = storage.load(DATA_FILE)
    if password != data.get("bot_name_password", "maks2024"):
        await update.message.reply_text("❌ Неверный пароль.")
        return
    chat = storage.get_chat(data, update.effective_chat.id)
    chat["bot_name"] = new_name
    storage.save(data, DATA_FILE)
    await update.message.reply_text(
        f"✅ Имя бота изменено на <b>{new_name}</b>!",
        parse_mode=ParseMode.HTML
    )


async def cmd_setpassword(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text(
            "🔑 /setpassword &lt;текущий_пароль&gt; &lt;новый_пароль&gt;",
            parse_mode=ParseMode.HTML
        )
        return
    old_pass, new_pass = ctx.args[0], ctx.args[1]
    data = storage.load(DATA_FILE)
    if old_pass != data.get("bot_name_password", "maks2024"):
        await update.message.reply_text("❌ Неверный пароль.")
        return
    data["bot_name_password"] = new_pass
    storage.save(data, DATA_FILE)
    await update.message.reply_text("✅ Пароль обновлён!")


async def cmd_myname(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = storage.load(DATA_FILE)
    chat_name = storage.get_chat(data, update.effective_chat.id).get("bot_name", "")
    global_name = data.get("bot_name", "МАКС")
    current = chat_name or global_name
    suffix = f"\n(Глобальное: <b>{global_name}</b>)" if chat_name else "\n(Глобальное имя)"
    await update.message.reply_text(
        f"Меня зовут <b>{current}</b> 😊{suffix}",
        parse_mode=ParseMode.HTML
    )


async def cmd_watch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Использование: /watch <ник>")
        return
    nick = " ".join(ctx.args).strip()
    data = storage.load(DATA_FILE)
    storage.get_chat(data, update.effective_chat.id)["watch"][nick] = "both"
    storage.save(data, DATA_FILE)
    await update.message.reply_text(f"👁 Слежу за <b>{nick}</b> в обе стороны.", parse_mode=ParseMode.HTML)


async def cmd_watchauthor(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Использование: /watchauthor <ник>")
        return
    nick = " ".join(ctx.args).strip()
    data = storage.load(DATA_FILE)
    storage.get_chat(data, update.effective_chat.id)["watch"][nick] = "author"
    storage.save(data, DATA_FILE)
    await update.message.reply_text(f"👁 Слежу за <b>{nick}</b> — только если пишет жалобу.", parse_mode=ParseMode.HTML)


async def cmd_watchtarget(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Использование: /watchtarget <ник>")
        return
    nick = " ".join(ctx.args).strip()
    data = storage.load(DATA_FILE)
    storage.get_chat(data, update.effective_chat.id)["watch"][nick] = "target"
    storage.save(data, DATA_FILE)
    await update.message.reply_text(f"👁 Слежу за <b>{nick}</b> — только если жалуются на него.", parse_mode=ParseMode.HTML)


async def cmd_unwatch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Использование: /unwatch <ник>")
        return
    nick = " ".join(ctx.args).strip()
    data = storage.load(DATA_FILE)
    chat = storage.get_chat(data, update.effective_chat.id)
    removed = chat["watch"].pop(nick, None)
    storage.save(data, DATA_FILE)
    if removed:
        await update.message.reply_text(f"🗑 <b>{nick}</b> удалён.", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(f"❌ <b>{nick}</b> не был в списке.", parse_mode=ParseMode.HTML)


async def cmd_mute(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Использование: /mute <ник>")
        return
    nick = " ".join(ctx.args).strip()
    data = storage.load(DATA_FILE)
    chat = storage.get_chat(data, update.effective_chat.id)
    if nick not in chat["muted"]:
        chat["muted"].append(nick)
    storage.save(data, DATA_FILE)
    await update.message.reply_text(f"🔕 <b>{nick}</b> заглушён.", parse_mode=ParseMode.HTML)


async def cmd_unmute(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Использование: /unmute <ник>")
        return
    nick = " ".join(ctx.args).strip()
    data = storage.load(DATA_FILE)
    chat = storage.get_chat(data, update.effective_chat.id)
    if nick in chat["muted"]:
        chat["muted"].remove(nick)
    storage.save(data, DATA_FILE)
    await update.message.reply_text(f"🔔 Уведомления по <b>{nick}</b> включены.", parse_mode=ParseMode.HTML)


async def cmd_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = storage.load(DATA_FILE)
    chat = storage.get_chat(data, update.effective_chat.id)
    watch = chat.get("watch", {})
    muted = chat.get("muted", [])
    focus = chat.get("focus", False)
    if not watch:
        await update.message.reply_text("📋 Список наблюдения пуст.\n\n/watch <ник> — добавить")
        return
    lines = [f"👁 <b>Список наблюдения</b> (фокус: {'🟢' if focus else '🔴'}):\n"]
    mode_map = {"both": "обе стороны", "author": "только автор", "target": "только цель"}
    for nick, mode in watch.items():
        m = " 🔕" if nick in muted else ""
        lines.append(f"• <b>{nick}</b> — {mode_map.get(mode, mode)}{m}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_focus(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = storage.load(DATA_FILE)
    chat = storage.get_chat(data, update.effective_chat.id)
    chat["focus"] = not chat.get("focus", False)
    storage.save(data, DATA_FILE)
    state = "🟢 ВКЛЮЧЁН" if chat["focus"] else "🔴 ВЫКЛЮЧЕН"
    await update.message.reply_text(
        f"🎯 Режим фокуса: <b>{state}</b>\n"
        f"{'Только наблюдаемые игроки' if chat['focus'] else 'Все жалобы'}",
        parse_mode=ParseMode.HTML
    )


async def cmd_crypto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Загружаю курсы...")
    result = crypto.get_top_prices()
    await update.message.reply_text(result, parse_mode=ParseMode.HTML)


async def cmd_convert(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if len(args) < 3:
        await update.message.reply_text(
            "💱 <b>Конвертер крипты</b>\n\n"
            "Использование: /convert &lt;сумма&gt; &lt;откуда&gt; &lt;куда&gt;\n\n"
            "Примеры:\n/convert 1 BTC USD\n/convert 100 USD ETH",
            parse_mode=ParseMode.HTML
        )
        return
    try:
        amount = float(args[0].replace(",", "."))
        from_sym, to_sym = args[1], args[2]
        await update.message.reply_text("⏳ Конвертирую...")
        result = crypto.convert(amount, from_sym, to_sym)
        await update.message.reply_text(result)
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Пример: /convert 1 BTC USD")


async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ai.clear_history(update.effective_chat.id)
    await update.message.reply_text("🔄 История разговора сброшена!")


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    user = update.effective_user
    username = user.username or user.first_name or ""
    text = update.message.text.strip()

    is_group = chat_type in ("group", "supergroup")
    if is_group:
        bot_username = ctx.bot.username
        replied_to_bot = (
            update.message.reply_to_message is not None
            and update.message.reply_to_message.from_user is not None
            and update.message.reply_to_message.from_user.id == ctx.bot.id
        )
        mentioned = (f"@{bot_username}" in text) if bot_username else False
        if not replied_to_bot and not mentioned:
            return
        if bot_username:
            text = text.replace(f"@{bot_username}", "").strip()

    data = storage.load(DATA_FILE)
    name = storage.get_bot_name(data, chat_id)
    chat = storage.get_chat(data, chat_id)
    voice_on = chat.get("voice", False)

    url = video.extract_url(text)
    if url:
        msg = await update.message.reply_text("⏳ Скачиваю видео... подожди немного")
        try:
            fpath, title_or_err = await asyncio.get_event_loop().run_in_executor(
                None, video.download_video, url
            )
            if fpath and os.path.exists(fpath):
                await msg.delete()
                with open(fpath, "rb") as f:
                    await update.message.reply_video(
                        video=f,
                        caption=f"📹 {title_or_err or 'Видео'}",
                        supports_streaming=True
                    )
                import shutil
                shutil.rmtree(os.path.dirname(fpath), ignore_errors=True)
            else:
                await msg.edit_text(f"❌ {title_or_err or 'Не удалось скачать видео.'}")
        except Exception as e:
            logger.error(f"Video error: {e}")
            await msg.edit_text("❌ Ошибка при скачивании видео.")
        return

    try:
        reply = await asyncio.get_event_loop().run_in_executor(
            None, ai.get_response, chat_id, text, username, name
        )
        await send_reply(update, reply, voice_on)
    except Exception as e:
        logger.error(f"AI error: {e}")
        await update.message.reply_text("Хм, что-то пошло не так 🤷")


# ─── background tasks ────────────────────────────────────────────────────────

async def forum_monitor_task(app: Application):
    while True:
        try:
            data = storage.load(DATA_FILE)
            new_threads = forum.get_all_new_threads(data["seen_threads"])
            for thread in new_threads:
                storage.add_seen(data, thread["id"])
                if thread.get("_skip_notify"):
                    continue
                message = forum.format_thread_message(thread)
                for cid, chat_cfg in data["chats"].items():
                    if not chat_cfg.get("active"):
                        continue
                    if forum.should_notify(thread, chat_cfg):
                        try:
                            await app.bot.send_message(
                                chat_id=int(cid),
                                text=message,
                                parse_mode=ParseMode.HTML,
                                disable_web_page_preview=True
                            )
                            if chat_cfg.get("voice"):
                                path = await asyncio.get_event_loop().run_in_executor(
                                    None, tts.text_to_voice, message
                                )
                                if path:
                                    with open(path, "rb") as f:
                                        await app.bot.send_voice(chat_id=int(cid), voice=f)
                                    tts.remove_voice_file(path)
                        except Exception as e:
                            logger.warning(f"Notify error {cid}: {e}")
            storage.save(data, DATA_FILE)
        except Exception as e:
            logger.error(f"Forum monitor error: {e}")
        await asyncio.sleep(60)


async def random_greeting_task(app: Application):
    while True:
        wait_hours = random.uniform(4, 12)
        await asyncio.sleep(wait_hours * 3600)
        try:
            data = storage.load(DATA_FILE)
            for cid, chat_cfg in data["chats"].items():
                if chat_cfg.get("active"):
                    try:
                        name = storage.get_bot_name(data, int(cid))
                        greeting = ai.get_greeting(name)
                        voice_on = chat_cfg.get("voice", False)
                        if voice_on:
                            path = await asyncio.get_event_loop().run_in_executor(
                                None, tts.text_to_voice, greeting
                            )
                            if path:
                                with open(path, "rb") as f:
                                    await app.bot.send_voice(
                                        chat_id=int(cid), voice=f,
                                        caption=greeting
                                    )
                                tts.remove_voice_file(path)
                                continue
                        await app.bot.send_message(chat_id=int(cid), text=greeting)
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Greeting task error: {e}")


async def post_init(app: Application):
    commands = [
        BotCommand("start",       "Подключить чат/группу"),
        BotCommand("stop",        "Отключить уведомления"),
        BotCommand("menu",        "Главное меню 📱"),
        BotCommand("watch",       "Следить за игроком"),
        BotCommand("watchauthor", "Следить — только автор жалобы"),
        BotCommand("watchtarget", "Следить — только цель жалобы"),
        BotCommand("unwatch",     "Убрать из наблюдения"),
        BotCommand("mute",        "Заглушить игрока"),
        BotCommand("unmute",      "Включить уведомления по игроку"),
        BotCommand("list",        "Список наблюдения"),
        BotCommand("focus",       "Режим фокуса"),
        BotCommand("crypto",      "Курсы крипты"),
        BotCommand("convert",     "Конвертер крипты"),
        BotCommand("voice",       "Голосовые ответы вкл/выкл"),
        BotCommand("setname",     "Сменить имя бота (с паролем)"),
        BotCommand("setpassword", "Сменить пароль"),
        BotCommand("myname",      "Текущее имя бота"),
        BotCommand("reset",       "Сбросить историю ИИ"),
        BotCommand("help",        "Список всех команд"),
    ]
    await app.bot.set_my_commands(commands)
    asyncio.create_task(forum_monitor_task(app))
    asyncio.create_task(random_greeting_task(app))


def main():
    from keep_alive import start_keep_alive
    start_keep_alive(KEEP_ALIVE_PORT)

    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start",       cmd_start))
    app.add_handler(CommandHandler("stop",        cmd_stop))
    app.add_handler(CommandHandler("menu",        cmd_menu))
    app.add_handler(CommandHandler("help",        cmd_help))
    app.add_handler(CommandHandler("watch",       cmd_watch))
    app.add_handler(CommandHandler("watchauthor", cmd_watchauthor))
    app.add_handler(CommandHandler("watchtarget", cmd_watchtarget))
    app.add_handler(CommandHandler("unwatch",     cmd_unwatch))
    app.add_handler(CommandHandler("mute",        cmd_mute))
    app.add_handler(CommandHandler("unmute",      cmd_unmute))
    app.add_handler(CommandHandler("list",        cmd_list))
    app.add_handler(CommandHandler("focus",       cmd_focus))
    app.add_handler(CommandHandler("crypto",      cmd_crypto))
    app.add_handler(CommandHandler("convert",     cmd_convert))
    app.add_handler(CommandHandler("voice",       cmd_voice))
    app.add_handler(CommandHandler("setname",     cmd_setname))
    app.add_handler(CommandHandler("setpassword", cmd_setpassword))
    app.add_handler(CommandHandler("myname",      cmd_myname))
    app.add_handler(CommandHandler("reset",       cmd_reset))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info(f"МАКС бот запускается (порт {KEEP_ALIVE_PORT})...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
