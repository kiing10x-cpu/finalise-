from menu_engine import *


def _track_ephemeral(context: ContextTypes.DEFAULT_TYPE, message) -> None:
    if message is None:
        return
    ids = context.user_data.setdefault("ephemeral_msg_ids", [])
    ids.append((message.chat_id, message.message_id))


async def _clear_ephemeral(context: ContextTypes.DEFAULT_TYPE, chat_id: int = None) -> None:
    ids = context.user_data.pop("ephemeral_msg_ids", [])
    for cid, mid in ids:
        if chat_id is not None and cid != chat_id:
            continue
        try:
            await context.bot.delete_message(chat_id=cid, message_id=mid)
        except Exception:
            pass


async def require_disclaimer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """PDF #1 — gate behind LANGUAGE SELECTION FIRST, then the
    disclaimer/agree flow (no force-join check here). Kept as a standalone
    building block for require_gate() below; most call sites should use
    require_gate() instead, which also enforces force-join. Language is
    asked before the disclaimer so the disclaimer that follows can be shown
    immediately in the language the user just picked. Returns True if the
    user may proceed; otherwise shows whichever screen is still pending and
    returns False. Admins are exempt."""
    user_obj = update.effective_user
    if not user_obj:
        return True
    if is_admin(user_obj.id):
        return True
    uid = str(user_obj.id)
    user = BOT_DATA["users"].get(uid, {})
    if not user.get("lang_prompted"):
        user["lang_prompted"] = True
        save_data()
        await _send_language_picker(context, update.effective_chat.id)
        return False
    if not user.get("accepted_terms"):
        await render_menu(context, update.effective_chat.id, "disclaimer", lang=user.get("lang"))
        return False
    return True


async def show_force_join_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show one full-width-looking join button per required channel."""
    links = await get_force_join_links(context)
    kb_rows = []
    for i, link in enumerate(links, 1):
        label = "📢 Join Channel" if len(links) == 1 else f"📢 Join Channel {i}"
        kb_rows.append([styled_button(label, url=link, style="primary")])
    kb_rows.append([styled_button("✅ I'VE JOINED / SENT REQUEST", callback_data="check_force_join", style="success")])
    text = "🔒 " + to_small_caps("please join all required channels to use this bot.")
    if not links:
        text += "\n⚠️ " + to_small_caps("no usable join link found — contact an admin.")
    chat_id = update.effective_chat.id
    if update.callback_query:
        try:
            await update.callback_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb_rows))
            return
        except Exception:
            pass
    await context.bot.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(kb_rows))


# NOTE: the maintenance notice and the "bot is live again" message are both
# fully admin-customisable — edit them anytime via 🎨 Menu & UI → maintenance
# / bot_live, or directly from Settings → 🔒 Maintenance → ✏️ Set New Message.
# The constant below only exists as a last-resort fallback if the "bot_live"
# menu entry is ever missing from storage.
_BOT_LIVE_FALLBACK = (
    "✅ 𝐁𝐎𝐓 𝐈𝐒 𝐋𝐈𝐕𝐄\n\n"
    "ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ɪꜱ ᴄᴏᴍᴘʟᴇᴛᴇ — ᴛʜᴇ ʙᴏᴛ ɪꜱ ʙᴀᴄᴋ ᴜᴘ ᴀɴᴅ ʀᴜɴɴɪɴɢ ɴᴏʀᴍᴀʟʟʏ."
)


async def _send_typewriter(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str,
    reply_markup=None, parse_mode=None, delay: float = 0.25,
):
    """Reveals the message progressively, word by word, instead of dumping
    the full block instantly — a light animation just enough for a premium
    'someone is actually typing this' feel without dragging the user's wait
    time out. The button (if any) only appears on the final, complete
    message.

    parse_mode is applied ONLY on the final, complete frame — every
    intermediate reveal is sent as plain text. This matters when `text`
    contains HTML (e.g. a <blockquote> wrapper): parsing a half-revealed
    string as HTML would leave an unclosed tag and Telegram would reject
    the edit, so intermediate frames are deliberately unparsed and only the
    finished message renders styled.

    `delay` controls the pause between reveal steps — bump it slightly
    (e.g. for the Support confirmation) for a more deliberate, human-typed
    feel; the default stays snappy for shorter, lower-stakes messages."""
    words = text.split(" ")
    if len(words) <= 4:
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            await asyncio.sleep(max(delay, 0.5))
        except Exception:
            pass
        return await context.bot.send_message(
            chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode
        )

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    except Exception:
        pass

    steps = 5  # short and deliberate — just enough to feel alive, not slow
    chunk = max(1, -(-len(words) // steps))  # ceil division
    msg = None
    for i in range(chunk, len(words) + chunk, chunk):
        shown = " ".join(words[:i])
        is_last = i >= len(words)
        cursor = "" if is_last else " ▌"
        try:
            if msg is None:
                msg = await context.bot.send_message(chat_id=chat_id, text=shown + cursor)
            else:
                await msg.edit_text(
                    shown + cursor,
                    reply_markup=reply_markup if is_last else None,
                    parse_mode=parse_mode if is_last else None,
                )
        except Exception:
            pass
        if not is_last:
            try:
                await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            except Exception:
                pass
            await asyncio.sleep(delay)
    if msg is None:
        msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
    return msg


async def send_maintenance_notice(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Show the maintenance message — typed out live, with the 🔔 Notify Me
    button attached. Deletes that chat's previous notice first (if any) so
    at most one maintenance message ever sits in the chat at a time."""
    notice_map = BOT_DATA.setdefault("maintenance_notice_msg", {})
    chat_key = str(chat_id)
    prev_msg_id = notice_map.get(chat_key)
    if prev_msg_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=prev_msg_id)
        except Exception:
            pass  # already gone / too old to delete — fine, we just move on
        notice_map.pop(chat_key, None)

    try:
        menu = BOT_DATA["menus"].get("maintenance", {})
        if menu.get("image_file_id"):
            # admin has attached an image via the generic Menu & UI editor —
            # animation doesn't apply there, send normally.
            first = await render_menu(context, chat_id, "maintenance")
        else:
            text = menu.get("text") or to_small_caps("maintenance is currently active.")
            buttons = menu.get("buttons") or []
            kb = build_keyboard_from_buttons(buttons, "maintenance") if buttons else None
            first = await _send_typewriter(context, chat_id, text, reply_markup=kb)

        # Remember every chat_id shown the notice, so that when maintenance
        # is switched off we know exactly who to notify (instead of nobody
        # finding out except by tapping something again) — and remember
        # THIS message's id specifically, so it can be auto-deleted the
        # moment maintenance goes off, or replaced next time this fires.
        notified = BOT_DATA.setdefault("maintenance_notified", [])
        if chat_id not in notified:
            notified.append(chat_id)
        if first is not None:
            notice_map[chat_key] = first.message_id
        save_data()
        return first
    except Exception:
        return None


async def broadcast_bot_live(context: ContextTypes.DEFAULT_TYPE):
    """Ping everyone who saw the maintenance notice that the bot is back up,
    deleting their old notice first so the "bot is live" message replaces
    it instead of sitting underneath a stale card."""
    live_menu = BOT_DATA["menus"].get("bot_live", {})
    live_text = live_menu.get("text") or _BOT_LIVE_FALLBACK
    chat_ids = BOT_DATA.get("maintenance_notified", [])
    notice_map = BOT_DATA.setdefault("maintenance_notice_msg", {})
    for chat_id in chat_ids:
        prev_msg_id = notice_map.pop(str(chat_id), None)
        if prev_msg_id:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=prev_msg_id)
            except Exception:
                pass
        try:
            await context.bot.send_message(chat_id=chat_id, text=live_text, parse_mode=live_menu.get("parse_mode"))
        except Exception:
            pass
    BOT_DATA["maintenance_notified"] = []
    notice_map.clear()
    save_data()


async def require_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """The single source of truth for 'is this user allowed to do anything
    yet'. Combines the disclaimer-acceptance gate AND the force-join gate —
    until BOTH are satisfied, nothing else in the bot should run: no
    command, no inline button, no reply-keyboard button. Admins are exempt
    from both. Returns True if the user may proceed; otherwise shows
    whichever screen is still pending (disclaimer takes priority over
    force-join, since there's no point sending someone to join a channel
    before they've even agreed to use the bot) and returns False."""
    user_obj = update.effective_user
    if not user_obj:
        return True
    if is_admin(user_obj.id):
        return True
    if not await require_disclaimer(update, context):
        return False
    if not await is_force_join_ok(context, user_obj.id):
        await show_force_join_prompt(update, context)
        return False
    return True


async def cb_global_button_gate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Registered in handler group -1, ahead of EVERY other handler — this
    is what makes 'no button works until agree + join' actually true,
    instead of each of 100+ individual callback handlers needing its own
    check (which is exactly how it stayed half-enforced before: some
    screens checked, most didn't). is_admin() inside require_gate() exempts
    admins as usual. The callbacks that ARE the gate itself — agree_terms,
    check_force_join, and setlang:* (language is now picked BEFORE the
    disclaimer, so it must work even though the user hasn't agreed to
    terms yet) — must fall through untouched, or the user would have no
    way to ever pass the gate."""
    query = update.callback_query
    if not query:
        return
    data = query.data or ""
    if data in ("maint_notify_me", "maint_notify_me_done"):
        # This IS the maintenance screen's own button — it must always work
        # while maintenance is on, or tapping it would just re-trigger the
        # maintenance notice instead of confirming the opt-in.
        return
    if BOT_DATA["settings"].get("maintenance") and not is_admin(update.effective_user.id):
        await send_maintenance_notice(context, update.effective_chat.id)
        try:
            await query.answer()
        except Exception:
            pass
        raise ApplicationHandlerStop
    if data in ("agree_terms", "check_force_join") or data.startswith("setlang:"):
        return
    if not await require_gate(update, context):
        try:
            await query.answer()
        except Exception:
            pass
        raise ApplicationHandlerStop


__all__ = [_n for _n in dir() if not _n.startswith("__")]
