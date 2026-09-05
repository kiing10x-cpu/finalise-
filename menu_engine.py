from helpers import *


def build_keyboard_from_buttons(buttons, menu_id):
    if not buttons:
        return None
    rows = {}
    for b in buttons:
        rows.setdefault(b.get("row", 1), []).append(b)
    kb_rows = []
    for row_num in sorted(rows.keys()):
        row_widgets = []
        for b in rows[row_num]:
            style = b.get("style")
            btype = b.get("type")
            if btype == "url":
                row_widgets.append(styled_button(b["label"], url=b["value"], style=style or "primary"))
            elif btype == "menu":
                row_widgets.append(styled_button(b["label"], callback_data=f"nav:{b['value']}", style=style or "primary"))
            elif btype == "toggle":
                current = bool(BOT_DATA["settings"].get(b["value"], False))
                st = "success" if current else "danger"
                row_widgets.append(
                    styled_button(toggle_label(b["label"], current), callback_data=f"tgl:{b['value']}:{menu_id}", style=st)
                )
            elif btype == "callback":
                row_widgets.append(styled_button(b["label"], callback_data=b["value"], style=style or "primary"))
            else:
                continue
        if row_widgets:
            kb_rows.append(row_widgets)
    return InlineKeyboardMarkup(kb_rows) if kb_rows else None


_me_cache = {"me": None, "at": 0.0}


async def _cached_get_me(context: ContextTypes.DEFAULT_TYPE):
    """get_me() never changes mid-run, but render_menu() used to call it on
    every single welcome-screen render — an avoidable network round-trip on
    the hottest path in the bot, and one more place a transient network
    hiccup could make the bot's name/link silently fail to show. Cached for
    10 minutes; refreshed automatically after that or if it's never been
    fetched yet."""
    now = time.monotonic()
    if _me_cache["me"] is None or (now - _me_cache["at"]) > 600:
        _me_cache["me"] = await context.bot.get_me()
        _me_cache["at"] = now
    return _me_cache["me"]


async def render_menu(context: ContextTypes.DEFAULT_TYPE, chat_id: int, menu_id: str, existing_message=None, lang: str = None):
    await _clear_ephemeral(context, chat_id)
    menu = BOT_DATA["menus"].get(menu_id)
    if not menu:
        await context.bot.send_message(chat_id, to_small_caps(f"⚠️ menu '{menu_id}' not found."))
        return

    # Resolve language: explicit arg > saved user preference > base (default) text.
    if lang is None:
        lang = BOT_DATA["users"].get(str(chat_id), {}).get("lang")
    translation = menu.get("translations", {}).get(lang) if (lang and lang != "en") else None  # "en" is the bot.py default, never a translation override

    buttons = (translation or {}).get("buttons") or menu.get("buttons", [])
    text = (translation or {}).get("text") or menu.get("text", "")
    kb = build_keyboard_from_buttons(buttons, menu_id)
    parse_mode = menu.get("parse_mode") or None
    image = menu.get("image_file_id")

    # Welcome-screen personalization — supports {username}/{bot_name} and
    # legacy {first_name}/{bot_link} placeholders for the start menu.
    if menu_id == "start":
        if "{username}" in text or "{first_name}" in text:
            stored_name = BOT_DATA["users"].get(str(chat_id), {}).get("name") or ""
            first_name = stored_name.split(" ")[0] if stored_name else "there"
            user_display = html.escape(first_name)
            # Make the user's displayed name open their Telegram profile.
            username_link = f'<a href="tg://user?id={int(chat_id)}">{user_display}</a>'
            text = text.replace("{username}", username_link)
            text = text.replace("{first_name}", user_display)
        if "{bot_name}" in text or "{bot_link}" in text:
            bot_name = "our bot"
            bot_link = "our bot"
            try:
                me = await _cached_get_me(context)
                display_name = html.escape(me.first_name or "our bot")
                bot_name = display_name
                # tg://user?id=<id> (not an https://t.me/<username> link) —
                # same trick already used above for {username}. A t.me/
                # link jumps straight into the chat; this ID-based deep
                # link opens the bot's profile card first instead.
                bot_link = f'<a href="tg://user?id={me.id}">{display_name}</a>'
            except Exception as e:
                log_error("bot_link_resolve", f"render_menu couldn't resolve bot name/link: {e}")
            text = text.replace("{bot_name}", bot_name)
            text = text.replace("{bot_link}", bot_link)

    # #10 — owner/developer credit button, injected at render time (not part
    # of the admin-editable button list) so it can't be accidentally deleted
    # by editing menu buttons.
    if menu_id in ("start", "help_user"):
        owner_id = BOT_DATA["settings"].get("owner_display_user_id")
        if owner_id:
            label = BOT_DATA["settings"].get("owner_display_label") or "👑 Developer"
            owner_id_str = str(owner_id)
            if owner_id_str.isdigit():
                # Same tg://user?id= reliability issue as the developer
                # button — resolve the real @username via getChat when we can.
                url = f"tg://user?id={owner_id_str}"
                try:
                    chat = await context.bot.get_chat(int(owner_id_str))
                    if chat.username:
                        url = f"https://t.me/{chat.username}"
                except Exception:
                    pass
            else:
                url = f"https://t.me/{owner_id_str.lstrip('@')}"
            owner_row = [styled_button(label, url=url, style="primary")]
            kb = InlineKeyboardMarkup((kb.inline_keyboard if kb else []) + [owner_row])

    # #4 — global forwarding/sharing lock applies to every menu the bot sends.
    protect = bool(BOT_DATA["settings"].get("lock_all_content", False))

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    except Exception:
        pass

    sent_message = None
    try:
        if existing_message is not None:
            has_photo = bool(existing_message.photo)
            if image and has_photo:
                await existing_message.edit_media(
                    media=InputMediaPhoto(media=image, caption=text, parse_mode=parse_mode), reply_markup=kb
                )
                sent_message = existing_message
            elif image and not has_photo:
                await existing_message.delete()
                sent_message = await context.bot.send_photo(
                    chat_id, photo=image, caption=text, parse_mode=parse_mode, reply_markup=kb, protect_content=protect
                )
            elif not image and has_photo:
                await existing_message.delete()
                sent_message = await context.bot.send_message(
                    chat_id, text=text, parse_mode=parse_mode, reply_markup=kb, protect_content=protect
                )
            else:
                await existing_message.edit_text(text=text, parse_mode=parse_mode, reply_markup=kb)
                sent_message = existing_message
        else:
            if image:
                sent_message = await context.bot.send_photo(
                    chat_id, photo=image, caption=text, parse_mode=parse_mode, reply_markup=kb, protect_content=protect
                )
            else:
                sent_message = await context.bot.send_message(
                    chat_id, text=text, parse_mode=parse_mode, reply_markup=kb, protect_content=protect
                )
    except Exception:
        log.exception("render_menu failed for %s, sending fresh", menu_id)
        try:
            if image:
                sent_message = await context.bot.send_photo(
                    chat_id, photo=image, caption=text, parse_mode=parse_mode, reply_markup=kb, protect_content=protect
                )
            else:
                sent_message = await context.bot.send_message(
                    chat_id, text=text, parse_mode=parse_mode, reply_markup=kb, protect_content=protect
                )
        except Exception:
            log.exception("render_menu completely failed for %s", menu_id)
            return

    seconds = menu.get("auto_delete_seconds")
    if seconds is None:
        seconds = BOT_DATA["settings"].get("global_auto_delete_seconds", 0)
    if sent_message:
        track_sent_message(chat_id, sent_message.message_id)
        await schedule_delete(context, chat_id, sent_message.message_id, seconds)
    return sent_message


async def track_and_refresh_panel(context: ContextTypes.DEFAULT_TYPE, chat_id: int, key: str, sent_message):
    """The first panel message stays forever; every later /start or /admin
    deletes the previous panel message and leaves only the fresh one."""
    if not sent_message:
        return
    key = f"{key}:{chat_id}"
    prev = BOT_DATA["panel_msg"].get(key)
    if prev and prev != sent_message.message_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=prev)
        except Exception:
            pass
    BOT_DATA["panel_msg"][key] = sent_message.message_id
    save_data()


def remember_panel_message(context: ContextTypes.DEFAULT_TYPE, query, screen_key: str):
    """Remembers which panel message triggered a text-input flow, so once
    the value is saved that same message can be edited in place instead of
    leaving it stale with just a small confirmation line further down."""
    context.user_data["panel_refresh"] = {
        "chat_id": query.message.chat_id,
        "message_id": query.message.message_id,
        "screen": screen_key,
    }


async def refresh_panel_after_save(context: ContextTypes.DEFAULT_TYPE, screen_key: str, build_fn, parse_mode=None) -> bool:
    """Edits the original admin-panel screen (remembered via
    remember_panel_message) in place to reflect a just-saved value.
    Returns True if it succeeded, so callers can still send a plain
    confirmation as a fallback if the panel message is gone."""
    info = context.user_data.get("panel_refresh")
    if not info or info.get("screen") != screen_key:
        return False
    context.user_data.pop("panel_refresh", None)
    text, kb = build_fn()
    try:
        await context.bot.edit_message_text(
            chat_id=info["chat_id"], message_id=info["message_id"], text=text, reply_markup=kb, parse_mode=parse_mode,
        )
        return True
    except Exception:
        return False


async def cb_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, menu_id = query.data.split(":", 1)
    await render_menu(context, query.message.chat_id, menu_id, existing_message=query.message)


async def cb_toggle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle button embedded inside a dynamic menu (#4 toggle-type button)."""
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    _, key, menu_id = query.data.split(":", 2)
    BOT_DATA["settings"][key] = not bool(BOT_DATA["settings"].get(key, False))
    save_data()
    await render_menu(context, query.message.chat_id, menu_id, existing_message=query.message)


# ----------------------------------------------------------------------------
# Style Text picker (#1) — reusable for menu body text AND button labels
# ----------------------------------------------------------------------------

# The welcome screen's live placeholders — {first_name} and {bot_link} (the
# bot's own clickable name/username in the welcome text). BUG FIX: every
# STYLE_OPTIONS function remaps plain a-z/A-Z letters (small caps, bold,
# fullwidth, ...), so styling text that contains these tokens used to
# mangle the literal word "bot_link" inside the braces into unicode
# look-alike letters. render_menu()'s exact `text.replace("{bot_link}", ...)`
# could then never find the token again, so the bot's name/link in the
# welcome message silently stopped being clickable the moment an admin
# styled the welcome text even once. Fixed by shielding these tokens with
# private-use sentinel characters (untouched by every style function) before
# styling, then restoring the real placeholder text afterwards.
_WELCOME_PLACEHOLDERS = ["{first_name}", "{bot_link}", "{username}", "{bot_name}"]


def apply_style_preserving_placeholders(func, text: str) -> str:
    protected = text
    markers = {}
    for i, token in enumerate(_WELCOME_PLACEHOLDERS):
        if token in protected:
            marker = f"\ue000{i}\ue001"
            markers[marker] = token
            protected = protected.replace(token, marker)
    styled = func(protected)
    for marker, token in markers.items():
        styled = styled.replace(marker, token)
    return styled


async def send_style_preview(context, chat_id, source_text):
    rows = []
    for i, (label, func) in enumerate(STYLE_OPTIONS):
        preview = apply_style_preserving_placeholders(func, source_text)
        display = preview if len(preview) <= 30 else preview[:27] + "..."
        rows.append([styled_button(display, callback_data=f"styleset:{i}")])
    await context.bot.send_message(chat_id, to_small_caps("🅰️ choose a style:"), reply_markup=InlineKeyboardMarkup(rows))


async def _replace_rkb_screen(context: ContextTypes.DEFAULT_TYPE, chat_id: int, key: str, text: str, reply_markup=None, parse_mode=None):
    """Delete the previous message shown for this reply-keyboard screen (if
    any) before sending the new one — for EVERY persistent bottom button
    (📊 My Usage, 🎁 Send A Gift, 👨‍💻 Developer, 📘 How To Use, 🎧 Support,
    ⬇️ Download Reel, 🌐 Language), not just one of them. Without this,
    tapping the same button over and over just stacked a fresh bot reply
    under the last one every time, click after click. Uses the same
    persisted panel_msg store as /start and /admin, so it survives a bot
    restart, not just context.user_data."""
    msg = await context.bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
    # All persistent reply-keyboard actions share one panel slot. This means
    # the user's own button message remains in chat, while only the latest
    # bot-side screen is replaced on every button tap.
    await track_and_refresh_panel(context, chat_id, "rkb_latest", msg)
    return msg



async def cb_styleset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    idx = int(query.data.split(":", 1)[1])
    src = context.user_data.pop("style_source_text", None)
    target = context.user_data.pop("style_target", None)
    if src is None or target is None:
        await query.edit_message_text(to_small_caps("session expired — please try again."))
        return
    label, func = STYLE_OPTIONS[idx]
    styled_text = apply_style_preserving_placeholders(func, src)

    if target.startswith("menu_text:"):
        menu_id = target.split(":", 1)[1]
        BOT_DATA["menus"][menu_id]["text"] = styled_text
        BOT_DATA["menus"][menu_id]["updated_by"] = update.effective_user.id
        BOT_DATA["menus"][menu_id]["updated_at"] = datetime.utcnow().isoformat()
        save_data()
        await query.edit_message_text(f"✅ Menu text updated ({label} style).")
    elif target.startswith("button_label:"):
        _, menu_id, idx_str = target.split(":", 2)
        BOT_DATA["menus"][menu_id]["buttons"][int(idx_str)]["label"] = styled_text
        save_data()
        await query.edit_message_text(f"✅ Button label updated ({label} style).")


# ----------------------------------------------------------------------------
# Basic user-facing commands
# ----------------------------------------------------------------------------

async def delete_incoming(update: Update):
    """#6 — best-effort cleanup of the user's own command message."""
    try:
        await update.message.delete()
    except Exception:
        pass


# The Send-Gift/Stars flow's "choose an amount" / invoice messages are
# tracked per-user and swept away the moment another menu is opened —
# no bot restart or persistent duplicate messages needed.


__all__ = [_n for _n in dir() if not _n.startswith("__")]
