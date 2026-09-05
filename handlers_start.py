from onboarding import *


LANG_NAMES = {
    "en": "English",
    "hi": "हिन्दी",
}


async def _send_language_picker(context: ContextTypes.DEFAULT_TYPE, chat_id: int, existing_message=None):
    """Shared 'choose your language' screen — shown at the very start of
    onboarding, before the disclaimer. Edits existing_message in place when
    given (so a button tap replaces the same message), otherwise sends a
    fresh one (e.g. the very first prompt during /start)."""
    text = (
        "🌐 <b>" + to_small_caps("Language Selection") + "</b>\n\n"
        "<blockquote>"
        "<u>➤ " + to_small_caps("Welcome!") + "</u>\n\n"
        + to_small_caps("Please select your preferred language to continue.") + "\n\n"
        "<u>➤ " + to_small_caps("Select Language") + "</u>\n"
        + to_small_caps("Choose one of the languages below.") +
        "</blockquote>"
    )
    current_lang = BOT_DATA["users"].get(str(chat_id), {}).get("lang") or "en"
    kb = build_language_keyboard(current_lang)
    if existing_message is not None:
        try:
            return await existing_message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            pass
    return await context.bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)


def build_language_keyboard(current_lang: str = None) -> InlineKeyboardMarkup:
    """Dynamic language picker — shows every language enabled in
    Settings > Languages (which is pre-filled from language_pack.json),
    not just English/Hindi. English is always included first since it's
    the bot's built-in/default language.

    FIX (list not being enabled): this used to be hardcoded to only
    हिन्दी + English, so even though language_pack.json ships 10 languages
    and Settings > Languages was pre-populated with all of them, the
    actual picker shown to users never reflected that. Now it reads
    BOT_DATA["settings"]["languages"] (admin-editable) and looks up each
    code's display name from language_pack.json's "languages" map — with
    flag emojis — falling back to LANG_NAMES/the bare code if a name
    isn't found.

    FIX (wrong highlight): the picker used to always render English in
    green ('success') no matter what the user actually had selected. Now
    it highlights whichever language is passed in as `current_lang` (the
    user's own saved preference, or "en" if they haven't picked yet), and
    marks it with a ✅ too so it's unambiguous even without colour.

    Layout: 2 languages per row (grid), as requested.
    """
    pack_names = _load_language_pack().get("languages", {})
    enabled = list(BOT_DATA.get("settings", {}).get("languages", []) or [])
    codes = ["en"] + [c for c in enabled if c != "en"]
    cur = current_lang or "en"

    def _label(code: str) -> str:
        return pack_names.get(code) or LANG_NAMES.get(code) or code.upper()

    buttons = []
    for code in codes:
        is_selected = (code == cur)
        label = ("✅ " if is_selected else "") + _label(code)
        buttons.append(styled_button(
            label, callback_data=f"setlang:{code}",
            style="success" if is_selected else "primary",
        ))
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(rows)


async def show_post_onboarding(context: ContextTypes.DEFAULT_TYPE, chat_id: int, uid: str):
    """Lands the user on the start menu once both onboarding gates
    (language selection, then disclaimer — see require_disclaimer()) are
    already satisfied. The language-prompt branch that used to live here
    was moved earlier in the flow, ahead of the disclaimer, so language
    selection always happens first. This is kept as a safety fallback: if
    some caller ever reaches here with lang_prompted still unset, it shows
    the picker instead of skipping straight to start."""
    user = BOT_DATA["users"].get(uid, {})
    if not user.get("lang_prompted"):
        user["lang_prompted"] = True
        save_data()
        return await _send_language_picker(context, chat_id)
    sent = await render_menu(context, chat_id, "start")
    if not BOT_DATA["users"].get(uid, {}).get("reply_kb_sent"):
        try:
            await context.bot.send_message(chat_id, "⠀", reply_markup=main_reply_keyboard(is_admin(int(uid)), BOT_DATA["users"].get(uid, {}).get("lang")))
        except Exception:
            pass
        BOT_DATA["users"].setdefault(uid, {})["reply_kb_sent"] = True
        save_data()
    return sent


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_obj = update.effective_user
    if is_blocked(user_obj.id) and not is_admin(user_obj.id):
        return  # blocked users get silence, not an error
    is_new = touch_user(update)

    # Group-specific /start: don't show the private onboarding/gate flow in
    # a group. Show a clean card with the group name as a link and who
    # started the bot, matching the bot's house typography.
    if not _is_private_chat(update):
        chat = update.effective_chat
        title = html.escape(chat.title or "This Group")
        if getattr(chat, "username", None):
            group_link = f"https://t.me/{chat.username}"
        elif str(chat.id).startswith("-100") and update.message:
            group_link = f"https://t.me/c/{str(chat.id)[4:]}/{update.message.message_id}"
        else:
            group_link = None
        group_name = f'<a href="{group_link}">{title}</a>' if group_link else title
        starter = update.effective_user
        starter_name = html.escape(starter.full_name or "User")
        starter_link = f'<a href="tg://user?id={starter.id}">{starter_name}</a>'
        body = (
            "<blockquote>🚀 " + to_title_small_caps("Bot Started In") + "\n\n"
            + "👥 " + group_name + "\n"
            + "👤 " + to_title_small_caps("Started By") + " : " + starter_link + "\n\n"
            + to_title_small_caps("Send An Instagram Reel Link To Download It.")
            + "</blockquote>"
        )
        await update.message.reply_text(body, parse_mode="HTML", disable_web_page_preview=True)
        await notify_admins_new_start(context, update, is_new)
        await delete_incoming(update)
        return

    # Notify admins here, before any gate check (rate-limit, maintenance,
    # disclaimer/force-join) gets a chance to return early — touch_user()
    # already flipped is_new to False for any later /start from this user,
    # so this is the only point where a genuinely new user can be reported.
    await notify_admins_new_start(context, update, is_new)
    if not check_rate_limit(user_obj.id):
        await update.message.reply_text("⏳ " + to_small_caps("slow down, too many requests too fast."))
        await delete_incoming(update)
        return
    if BOT_DATA["settings"].get("maintenance") and not is_admin(user_obj.id):
        await send_maintenance_notice(context, update.effective_chat.id)
        await delete_incoming(update)
        return

    if not await require_gate(update, context):
        await delete_incoming(update)
        return

    BOT_DATA["metrics"]["start_count"] = BOT_DATA["metrics"].get("start_count", 0) + 1
    save_data()

    await send_premium_emoji_greeting(context.bot, update.effective_chat.id)
    sent = await show_post_onboarding(context, update.effective_chat.id, str(user_obj.id))
    await track_and_refresh_panel(context, update.effective_chat.id, "start", sent)
    await delete_incoming(update)


async def cb_maint_notify_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The 🔔 Notify Me button under the maintenance message. Tapping it:
    1) confirms the chat_id is on the notify list (it already is, but this
       makes the user's intent explicit), 2) turns the button itself from
       red → a blue, checked "Notified" state so it's visually obvious the
       tap registered, and 3) explains in plain words what happens next."""
    query = update.callback_query
    chat_id = update.effective_chat.id
    notified = BOT_DATA.setdefault("maintenance_notified", [])
    if chat_id not in notified:
        notified.append(chat_id)
        save_data()
    try:
        await query.answer(
            "🔔 " + to_small_caps("notifications on!") + "\n"
            + to_small_caps("we'll message you here the instant the bot is back — no need to check manually."),
            show_alert=True,
        )
    except Exception:
        pass
    try:
        confirmed_kb = InlineKeyboardMarkup(
            [[styled_button("✅ " + to_small_caps("you'll be notified"), callback_data="maint_notify_me_done", style="primary")]]
        )
        # Beyond the popup alert (which disappears in a couple seconds),
        # leave a permanent line inside the message itself so the
        # confirmation stays visible in the chat, not just flashed once.
        confirm_line = "\n\n🔔 " + to_small_caps("notification set — we'll message you the moment the bot is back online.")
        base_text = query.message.caption if query.message.photo else query.message.text
        base_text = base_text or ""
        new_text = base_text if confirm_line.strip() in base_text else base_text + confirm_line
        if query.message.photo:
            await query.edit_message_caption(caption=new_text, reply_markup=confirmed_kb)
        else:
            await query.edit_message_text(new_text, reply_markup=confirmed_kb)
    except Exception:
        pass


async def cb_maint_notify_me_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Button already shows the confirmed (blue ✅) state — a second tap
    just reassures the user, it doesn't need to do anything further."""
    try:
        await update.callback_query.answer(
            "✅ " + to_small_caps("you're all set — you'll be notified automatically."),
            show_alert=False,
        )
    except Exception:
        pass


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_obj = update.effective_user
    if is_blocked(user_obj.id) and not is_admin(user_obj.id):
        return
    touch_user(update)
    if not await require_gate(update, context):
        await delete_incoming(update)
        return
    menu_id = "help_admin" if is_admin(user_obj.id) else "help_user"
    await render_menu(context, update.effective_chat.id, menu_id)
    await delete_incoming(update)


async def cmd_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_obj = update.effective_user
    if is_blocked(user_obj.id) and not is_admin(user_obj.id):
        return
    touch_user(update)
    if not await require_gate(update, context):
        await delete_incoming(update)
        return
    menu = BOT_DATA["menus"].get("language", {})
    lang = BOT_DATA["users"].get(str(user_obj.id), {}).get("lang")
    translation = menu.get("translations", {}).get(lang) if (lang and lang != "en") else None  # "en" is the bot.py default, never a translation override
    banner = (translation or {}).get("text") or menu.get("text") or DEFAULT_MENUS["language"]["text"]
    # build_language_keyboard() always includes at least English + Default
    # (Hinglish), whether or not the owner has added any extra languages in
    # Settings > Languages — so the picker should always be shown, never
    # blocked behind an "extra languages" check.
    await _replace_rkb_screen(
        context, update.effective_chat.id, "language",
        banner, reply_markup=build_language_keyboard(lang or "en"), parse_mode=menu.get("parse_mode"),
    )


async def cb_setlang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    code = query.data.split(":", 1)[1]
    uid = str(update.effective_user.id)
    # Accept any language the admin has actually enabled, not just "hi".
    enabled_langs = set(BOT_DATA.get("settings", {}).get("languages", []) or [])
    lang_value = code if (code == "en" or code in enabled_langs) else "en"
    if uid in BOT_DATA["users"]:
        BOT_DATA["users"][uid]["lang"] = lang_value
        # Belt-and-suspenders: a selection from any source means the picker
        # has now been shown/handled for this user.
        BOT_DATA["users"][uid]["lang_prompted"] = True
        save_data()
    # Onboarding order: language is picked BEFORE the disclaimer. So if this
    # user hasn't agreed to the terms yet, the next screen is the disclaimer
    # — now shown in whichever language they just picked — not the start
    # menu. Returning users who change their language later (already past
    # the disclaimer) still land straight on start, same as before.
    if not BOT_DATA["users"].get(uid, {}).get("accepted_terms"):
        await render_menu(context, query.message.chat_id, "disclaimer", existing_message=query.message, lang=lang_value)
        return
    await render_menu(context, query.message.chat_id, "start", existing_message=query.message)
    # Refresh the persistent keyboard too, so a returning user who changes
    # language immediately sees the new labels instead of the old language.
    try:
        await context.bot.send_message(
            query.message.chat_id,
            "⠀",
            reply_markup=main_reply_keyboard(is_admin(int(uid)), lang_value),
        )
        BOT_DATA["users"].setdefault(uid, {})["reply_kb_sent"] = True
        save_data()
    except Exception as e:
        log_error("language_keyboard_refresh", f"could not refresh reply keyboard: {e}")


async def cb_agree_terms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """PDF #1 — 'I Agree & Continue' button on the disclaimer screen."""
    query = update.callback_query
    await query.answer()
    uid = str(update.effective_user.id)
    if uid in BOT_DATA["users"]:
        BOT_DATA["users"][uid]["accepted_terms"] = True
        BOT_DATA["users"][uid]["accepted_terms_at"] = datetime.utcnow().isoformat()
        save_data()
    try:
        await query.message.delete()
    except Exception:
        pass
    # Disclaimer accepted — now check the OTHER half of the gate before
    # letting the user any further in. If a force-join channel is set, they
    # see the join prompt right here instead of skipping straight to the
    # start menu.
    if not await is_force_join_ok(context, update.effective_user.id):
        await show_force_join_prompt(update, context)
        return
    await show_post_onboarding(context, query.message.chat_id, uid)


# ----------------------------------------------------------------------------
# Reel download
# ----------------------------------------------------------------------------

def build_reel_delivered_card(user_name: str, user_id, reel_number, original_reel_url: str, username: str = None) -> str:
    """HTML card used for both the Activity Channel AND the admin-DM Live
    Activity feed — same layout in both places so admins never see two
    different formats for the same event.

    Layout:
        Rᴇᴇʟ Nᴏ : #2      <- underlined (label + value)
        Sᴛᴀᴛᴜs : Dᴇʟɪᴠᴇʀᴇᴅ <- underlined (label + value)

        Uꜱᴇʀ : <clickable name>
        Uꜱᴇʀɴᴀᴍᴇ : Not Set / @username
        Uꜱᴇʀ ID : 123456

        Click Here To View Reel   (bare link, no visible URL)

    All dynamic values are HTML-escaped before insertion, including the
    URL used in the href attribute. The user's name is a clickable link
    straight to their Telegram profile (via @username if set, otherwise
    tg://user?id), same pattern as clickable_user() elsewhere in the bot.
    """
    safe_name = html.escape(str(user_name or "—"))
    safe_uid = html.escape(str(user_id))
    safe_no = html.escape(str(reel_number))
    safe_url = html.escape(original_reel_url or "", quote=True)
    username_display = f"@{username}" if username else "Not Set"

    if username:
        name_html = f'<a href="https://t.me/{html.escape(username, quote=True)}">{safe_name}</a>'
    else:
        name_html = f'<a href="tg://user?id={safe_uid}">{safe_name}</a>'

    reel_no_line = f"<u>{to_title_small_caps('Reel No')} : #{safe_no}</u>"
    status_line = f"<u>{to_title_small_caps('Status')} : {to_title_small_caps('Delivered')}</u>"

    return (
        f"{reel_no_line}\n"
        f"{status_line}\n\n"
        f"{to_title_small_caps('User')} : {name_html}\n"
        f"{to_title_small_caps('Username')} : {html.escape(username_display)}\n"
        f"{to_title_small_caps('User Id')} : {safe_uid}\n\n"
        f'<a href="{safe_url}">{to_title_small_caps("Click Here To View Reel")}</a>'
    )


async def send_reel_delivered_card(context, user_name: str, user_id, reel_number, original_reel_url: str, username: str = None):
    """Posts the reel-delivered card to admin-facing destinations, per the
    admin-configurable "📡 Notify Route" (Settings & Admins > Live Feed):
      - "logger"   -> Logger Channel only
      - "activity" -> Activity Channel only
      - "dm"       -> Admin DM only
      - "all"      -> all three (default)
    Same card/format everywhere, so admins never see two different-looking
    messages for the same event."""
    card = build_reel_delivered_card(user_name, user_id, reel_number, original_reel_url, username=username)
    s = BOT_DATA["settings"]
    route = s.get("notify_route", "all")

    if route in ("activity", "all") and s.get("activity_channel_enabled") and s.get("activity_channel_id"):
        try:
            await context.bot.send_message(
                chat_id=s["activity_channel_id"],
                text=card,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception:
            log.warning("Activity Channel reel-delivered post failed", exc_info=True)

    if route in ("dm", "all") and s.get("user_activity_dm", True):
        await dm_all_admins(context, card, parse_mode="HTML")

    if route in ("logger", "all"):
        await log_event(context, card, parse_mode="HTML")


__all__ = [_n for _n in dir() if not _n.startswith("__")]
