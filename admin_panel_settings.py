from admin_panel_menu import *


# ---- Settings & Admins --------------------------------------------------------

async def _render_adm_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    s = BOT_DATA["settings"]
    # v6 — same 2-per-row grid treatment as the top-level Admin Panel, so
    # deep submenus stay just as easy to scan and control.
    rows = [
        [styled_button("🔒 Maintenance", callback_data="adm_maintenance")],
        [styled_button(f"⏱ Global Auto-Delete: {s.get('global_auto_delete_seconds', 0)}s", callback_data="adm_set_autodelete"),
         styled_button("💬 Auto-Replies", callback_data="adm_autoreply_list")],
    ]
    # 👤 Manage Admins can hand out access to everything, so — like the
    # whole 🍭 Update Backup section / ☠️ Danger Zone — it stays owner-only
    # even though "settings" itself is a grantable permission.
    # 📥 Restore Backup lives on the consolidated 🍭 Update Backup screen
    # along with every other backup/database action (Mongo Plugin, full DB
    # export, etc.), not here.
    if is_owner(update.effective_user.id):
        rows.append([styled_button("👤 Manage Admins", callback_data="adm_manage_admins")])
    rows += [
        [styled_button(
             toggle_label("🔐 Lock All Forwarding", s.get('lock_all_content')),
             callback_data="stgl:lock_all_content:adm_settings",
         ),
         styled_button("👑 Owner/Developer Contact", callback_data="adm_owner_contact")],
        [styled_button("📋 Logger Channel", callback_data="adm_logger_channel"),
         styled_button("📣 Activity Channel", callback_data="adm_activity_channel")],
        [styled_button(f"📢 Force-Join: {s.get('force_join_channel') or 'OFF'}", callback_data="adm_force_join")],
        [styled_button(
            toggle_label("📄 Send As Document", s.get('send_as_document')),
            callback_data="stgl:send_as_document:adm_settings",
        )],
        [styled_button(
             toggle_label("🌟 Premium Emoji Greeting", s.get('premium_emoji_enabled')),
             callback_data="stgl:premium_emoji_enabled:adm_settings",
         ),
         styled_button("✏️ Set Premium Emoji", callback_data="adm_set_premium_emoji")],
        back_row(),
        home_row(),
    ]
    kb = InlineKeyboardMarkup(rows)
    await query.edit_message_text(
        "⚙️ " + to_small_caps("settings") + "\n"
        + to_small_caps("configure core bot behaviour below."),
        reply_markup=kb,
    )


async def cb_adm_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _render_adm_settings(update, context)


async def cb_adm_set_premium_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["awaiting"] = "premium_emoji_capture"
    await query.message.reply_text(
        to_small_caps("🌟 send (or forward) a message that contains ONE premium custom emoji.") + "\n"
        + to_small_caps("i'll grab that emoji's id and use it in the start greeting when premium emoji is turned on.") + "\n\n"
        + to_small_caps("note: this only works if the sender actually has telegram premium — that's a telegram limit, not this bot's.")
    )


async def handle_premium_emoji_capture(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reads MessageEntity(type='custom_emoji') off the admin's sample
    message. Registered as its own MessageHandler (entities aren't plain
    text) rather than folded into handle_admin_text_input."""
    if context.user_data.get("awaiting") != "premium_emoji_capture":
        return
    if not is_admin(update.effective_user.id):
        return
    context.user_data["awaiting"] = None
    msg = update.message
    entities = msg.entities or msg.caption_entities or []
    ce = next((e for e in entities if e.type == MessageEntity.CUSTOM_EMOJI), None)
    if not ce:
        await msg.reply_text(
            to_small_caps("❌ no custom emoji found in that message — make sure it's an actual premium animated emoji, not a regular unicode emoji.")
        )
        return
    text_src = msg.text or msg.caption or ""
    # offset/length are UTF-16 code units per the Bot API spec.
    utf16 = text_src.encode("utf-16-le")
    glyph_bytes = utf16[ce.offset * 2: (ce.offset + ce.length) * 2]
    glyph = glyph_bytes.decode("utf-16-le", errors="ignore") or "🌟"
    BOT_DATA["settings"]["premium_emoji_id"] = ce.custom_emoji_id
    BOT_DATA["settings"]["premium_emoji_char"] = glyph
    save_data()
    await msg.reply_text(
        to_small_caps("✅ premium emoji saved.") + "\n"
        + to_small_caps("turn on '🌟 premium emoji greeting' in settings to use it on /start.")
    )


async def send_premium_emoji_greeting(bot, chat_id: int):
    """Sends a short standalone greeting line with the admin-configured
    Premium custom emoji, right before the normal /start menu. Kept as its
    own message (entities-based, no HTML) so it never conflicts with the
    HTML parse_mode used everywhere else. Non-Premium viewers automatically
    see the fallback glyph — that's Telegram's own behaviour, not ours."""
    s = BOT_DATA["settings"]
    if not s.get("premium_emoji_enabled") or not s.get("premium_emoji_id"):
        return
    glyph = s.get("premium_emoji_char") or "🌟"
    caption = to_small_caps(" welcome!")
    text = glyph + caption
    glyph_len = len(glyph.encode("utf-16-le")) // 2
    entities = [MessageEntity(type=MessageEntity.CUSTOM_EMOJI, offset=0, length=glyph_len, custom_emoji_id=s["premium_emoji_id"])]
    try:
        await bot.send_message(chat_id, text, entities=entities)
    except Exception:
        log.warning("Premium emoji greeting failed (id may be stale/invalid)", exc_info=True)


# ---- Maintenance (single combined screen: status + toggle + set message) ---

def _maintenance_kb(is_on: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [styled_button(toggle_label("Maintenance", is_on), callback_data="stgl:maintenance:adm_maintenance")],
            [styled_button("✏️ Set New Message", callback_data="adm_maint_setmsg")],
            back_row("adm_settings"),
            home_row(),
        ]
    )


async def _render_adm_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    is_on = bool(BOT_DATA["settings"].get("maintenance"))
    current_text = BOT_DATA["menus"].get("maintenance", {}).get("text", "")
    preview = (current_text[:250] + "…") if len(current_text) > 250 else current_text
    status_line = (
        "🔴 " + to_small_caps("active — only admins can use the bot right now")
        if is_on else
        "🟢 " + to_small_caps("off — bot is live and working normally")
    )
    body = (
        "🔒 " + to_small_caps("maintenance") + "\n\n"
        + status_line + "\n\n"
        + to_small_caps("current message shown to users") + ":\n"
        + preview
    )
    await query.edit_message_text(body, reply_markup=_maintenance_kb(is_on))


async def cb_adm_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _render_adm_maintenance(update, context)


async def cb_adm_maint_setmsg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["awaiting"] = "maintenance_set_msg"
    await query.message.reply_text(
        "✏️ " + to_small_caps("send the new maintenance message now") + "\n"
        + to_small_caps("this is exactly what users will see while maintenance is on.")
    )


# ---- Owner/Developer credit button (#10) --------------------------------------

def _build_adm_owner_contact_view():
    s = BOT_DATA["settings"]
    current = s.get("owner_display_user_id")
    label = s.get("owner_display_label") or "👑 Developer"
    text = (
        "👑 Owner/Developer Contact\n\n"
        f"Current target: {current or '(not set)'}\n"
        f"Button label: {label}\n\n"
        "This shows a display/credit button on Start & Help — it does NOT "
        "grant that user any bot-admin permissions."
    )
    kb = InlineKeyboardMarkup(
        [
            [styled_button("✏️ Set Contact", callback_data="adm_owner_contact_set")],
            [styled_button("❌ Clear", callback_data="adm_owner_contact_clear")],
            back_row(),
        ]
    )
    return text, kb


async def _render_adm_owner_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    text, kb = _build_adm_owner_contact_view()
    await query.edit_message_text(text, reply_markup=kb)


async def cb_adm_owner_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _render_adm_owner_contact(update, context)


async def cb_adm_owner_contact_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    remember_panel_message(context, query, "owner_contact")
    context.user_data["awaiting"] = "owner_contact_label"
    await query.message.reply_text(to_small_caps("send the button label (e.g. '👑 developer' or '💬 contact us')."))


async def cb_adm_owner_contact_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    BOT_DATA["settings"]["owner_display_user_id"] = None
    BOT_DATA["settings"]["owner_display_label"] = None
    save_data()
    await query.edit_message_text("✅ Owner/Developer contact button cleared.", reply_markup=InlineKeyboardMarkup([back_row()]))


# ---- Logger channel (#14) ------------------------------------------------------

def _build_adm_logger_channel_view():
    s = BOT_DATA["settings"]
    text = (
        "📋 Logger Channel\n\n"
        f"Channel ID: {s.get('logger_channel_id') or '(not set)'}\n"
        f"Enabled: {'✅ ON' if s.get('logger_enabled') else '❌ OFF'}\n\n"
        "Logs new users, downloads, broadcasts, admin changes, copyright "
        "reports, and errors here."
    )
    kb = InlineKeyboardMarkup(
        [
            [styled_button("✏️ Set Channel", callback_data="adm_logger_channel_set")],
            [styled_button(
                toggle_label("🔀 Enabled", s.get('logger_enabled')),
                callback_data="stgl:logger_enabled:adm_logger_channel",
            )],
            back_row(),
        ]
    )
    return text, kb


async def _render_adm_logger_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    text, kb = _build_adm_logger_channel_view()
    await query.edit_message_text(text, reply_markup=kb)


async def cb_adm_logger_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _render_adm_logger_channel(update, context)


async def cb_adm_logger_channel_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    remember_panel_message(context, query, "logger_channel")
    context.user_data["awaiting"] = "logger_channel_id"
    await query.message.reply_text(
        "Forward any message from the target channel here (bot must be an "
        "admin there), or just type its numeric ID (looks like -100xxxxxxxxxx)."
    )


# ---- #18 — Activity Channel (dedicated home for the Reel Delivered card) ------

def _build_adm_activity_channel_view():
    s = BOT_DATA["settings"]
    text = (
        "📣 Activity Channel\n\n"
        f"Channel ID: {s.get('activity_channel_id') or '(not set)'}\n"
        f"Enabled: {'✅ ON' if s.get('activity_channel_enabled') else '❌ OFF'}\n\n"
        "Every delivered reel posts a clean 'Reel Delivered' card here — "
        "separate from the general Logger Channel, so this stays a pure "
        "delivery feed with no error/debug noise mixed in."
    )
    kb = InlineKeyboardMarkup(
        [
            [styled_button("✏️ Set Channel", callback_data="adm_activity_channel_set")],
            [styled_button(
                toggle_label("🔀 Enabled", s.get('activity_channel_enabled')),
                callback_data="stgl:activity_channel_enabled:adm_activity_channel",
            )],
            back_row(),
        ]
    )
    return text, kb


async def _render_adm_activity_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    text, kb = _build_adm_activity_channel_view()
    await query.edit_message_text(text, reply_markup=kb)


async def cb_adm_activity_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _render_adm_activity_channel(update, context)


async def cb_adm_activity_channel_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    remember_panel_message(context, query, "activity_channel")
    context.user_data["awaiting"] = "activity_channel_id"
    await query.message.reply_text(
        "Forward any message from the target channel here (bot must be an "
        "admin there), or just type its numeric ID (looks like -100xxxxxxxxxx)."
    )


# ---- Force-join channel ------------------------------------------------

def _build_adm_force_join_view():
    targets = _force_join_targets()
    lines = []
    for i, t in enumerate(targets, 1):
        lines.append(f"{i}. {t.get('chat_id') or '(link-only)'}\n   🔗 {t.get('link') or 'auto-resolve'}")
    text = (
        "📢 " + to_title_small_caps("Multiple Force-Join") + "\n\n"
        + ("\n\n".join(lines) if lines else to_small_caps("no channels set — force-join disabled."))
        + "\n\n<blockquote>"
        + to_title_small_caps(
            "Users Must Satisfy All Listed Channels. Public @Usernames, Numeric "
            "Channel IDs And t.me/Invite Links Are Supported. Join Requests Are Also "
            "Accepted When Telegram Delivers The Request Update To This Bot."
        )
        + "</blockquote>"
    )
    kb_rows = [
        [styled_button("➕ Add Channel / Link", callback_data="adm_force_join_set")],
        [styled_button("🗑 Remove Last", callback_data="adm_force_join_remove")] if targets else [],
        [styled_button("❌ Disable All", callback_data="adm_force_join_clear")],
        back_row(),
    ]
    kb_rows = [r for r in kb_rows if r]
    return text, InlineKeyboardMarkup(kb_rows)


async def _render_adm_force_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    text, kb = _build_adm_force_join_view()
    await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")


async def cb_adm_force_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _render_adm_force_join(update, context)


async def cb_adm_force_join_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    remember_panel_message(context, query, "force_join")
    context.user_data["awaiting"] = "force_join_channel"
    msg = await query.message.reply_text(
        "<blockquote>"
        + to_title_small_caps("Send A Public") + " @ChannelUsername, "
        + to_title_small_caps("Numeric Channel") + " ID (-100xxxxxxxxxx), "
        + to_title_small_caps("Or A Full") + " https://t.me/... "
        + to_title_small_caps("Invite/Join Link. You Can Add Multiple Channels One By One. "
                               "For Reliable Membership Checking, The Bot Should Be An Admin "
                               "In Each Channel.")
        + "</blockquote>",
        parse_mode="HTML",
    )
    _track_ephemeral(context, msg)


async def cb_adm_force_join_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    BOT_DATA["settings"]["force_join_channel"] = None
    BOT_DATA["settings"]["force_join_channels"] = []
    save_data()
    await _render_adm_force_join(update, context)


async def cb_adm_force_join_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    targets = _force_join_targets()
    if targets:
        targets.pop()
        BOT_DATA["settings"]["force_join_channels"] = targets
        BOT_DATA["settings"]["force_join_channel"] = targets[0].get("chat_id") if targets else None
        save_data()
    await _render_adm_force_join(update, context)


async def cb_adm_force_join_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Live diagnostic — actually calls the Bot API right now and shows the
    exact result/error, instead of the admin having to guess why nobody is
    getting blocked. This is the #1 real-world cause of 'force-join doesn't
    work': the bot silently isn't an admin in the target channel, or the
    channel string is wrong — and that used to only get logged, never shown."""
    query = update.callback_query
    await query.answer()
    channel = BOT_DATA["settings"].get("force_join_channel")
    if not channel:
        await query.message.reply_text("⚠️ No force-join channel is set.")
        return
    lines = [f"🧪 Testing force-join channel: {channel}\n"]
    try:
        me = await context.bot.get_me()
        chat = await context.bot.get_chat(channel)
        lines.append(f"✅ Bot can see the channel: {chat.title or chat.id}")
        member = await context.bot.get_chat_member(chat_id=channel, user_id=me.id)
        if member.status in ("administrator", "creator"):
            lines.append("✅ Bot IS an admin there — membership checks will work.")
        else:
            lines.append(
                "❌ Bot is a MEMBER but NOT an admin there — get_chat_member calls for "
                "other users will fail and force-join will silently fail OPEN "
                "(let everyone through). Make the bot an admin in this channel."
            )
    except Exception as e:
        lines.append(
            f"❌ Bot could NOT access this channel at all ({e}).\n"
            "This is almost always the reason force-join 'doesn't work' — the bot "
            "must be added to the channel as an ADMIN first. Double-check the "
            "username/ID too."
        )
    await query.message.reply_text("\n".join(lines))


def _build_adm_leaderboard_view():
    # Leaderboard-only screen; share settings live in _build_adm_share_view.
    s = BOT_DATA["settings"]
    lb_on = s.get("leaderboard_enabled", False)
    donor_count = len([d for d in BOT_DATA.get("donations", {}).values() if d.get("score", 0) > 0])
    text = (
        "🏆 Leaderboard\n\n"
        f"Status: {'✅ ON' if lb_on else '❌ OFF'} — shown inside 🎁 Send Gift, "
        f"{donor_count} donor(s) ranked so far.\n\n"
        "Only voluntary 🎁 Send Gift donations count here — Premium Plan "
        "purchases are subscriptions, not gifts, so they're never counted.\n\n"
        + build_leaderboard_text()
    )
    kb_rows = [
        [styled_button(
            f"{'✅' if lb_on else '❌'} Leaderboard",
            callback_data="stgl:leaderboard_enabled:adm_leaderboard",
        )],
        [styled_button("📢 Post Leaderboard to All Users", callback_data="adm_post_leaderboard")],
        back_row(),
    ]
    return text, InlineKeyboardMarkup(kb_rows)


async def _render_adm_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    text, kb = _build_adm_leaderboard_view()
    await query.edit_message_text(text, reply_markup=kb)


async def cb_adm_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _render_adm_leaderboard(update, context)


async def cb_adm_post_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcasts the leaderboard to every known user (same delivery path
    as /broadcast) and cross-posts to the logger channel if one is set."""
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    text = build_leaderboard_text()
    sent, failed = 0, 0
    for uid in list(BOT_DATA["users"].keys()):
        try:
            m = await context.bot.send_message(int(uid), text)
            track_sent_message(int(uid), m.message_id)
            await schedule_delete(context, int(uid), m.message_id, BOT_DATA["settings"].get("global_auto_delete_seconds", 0))
            sent += 1
        except Exception:
            failed += 1
    channel = BOT_DATA["settings"].get("logger_channel_id") if BOT_DATA["settings"].get("logger_enabled") else None
    if channel:
        try:
            await context.bot.send_message(channel, text)
        except Exception:
            pass
    await query.message.reply_text(f"✅ {to_small_caps('leaderboard posted to all users')}\nSent: {sent} | Failed: {failed}")
    await log_event(context, f"🏆 Leaderboard posted to users by {update.effective_user.id} — {sent} recipients")


def _build_adm_share_view():
    s = BOT_DATA["settings"]
    share_on = s.get("share_enabled", True)
    share_url = s.get("share_url") or to_small_caps("(default — bot's own link)")
    text = (
        "📤 Share Settings\n\n"
        f"Share button (under My Usage): {'✅ ON' if share_on else '❌ OFF'}\n"
        f"Share URL: {share_url}"
    )
    kb_rows = [
        [styled_button(
            f"{'✅' if share_on else '❌'} Share Button",
            callback_data="stgl:share_enabled:adm_share",
        )],
        [styled_button("✏️ Set Share URL", callback_data="adm_share_url_set")],
    ]
    if s.get("share_url"):
        kb_rows.append([styled_button("🗑️ Reset Share URL", callback_data="adm_share_url_clear")])
    kb_rows.append(back_row())
    return text, InlineKeyboardMarkup(kb_rows)


async def _render_adm_share(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    text, kb = _build_adm_share_view()
    await query.edit_message_text(text, reply_markup=kb)


async def cb_adm_share(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _render_adm_share(update, context)


async def cb_adm_share_url_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    remember_panel_message(context, query, "share")
    context.user_data["awaiting"] = "share_url"
    await query.message.reply_text(
        "Type the URL the '📤 Share' button (under My Usage) should open — "
        "e.g. your channel link or a landing page. Send /cancel to leave it as-is."
    )


async def cb_adm_share_url_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    BOT_DATA["settings"]["share_url"] = None
    save_data()
    await _render_adm_share(update, context)


async def cb_settings_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Looks up the target screen via SCREEN_RENDERERS so any toggle button,
    on any admin screen, re-renders after flipping its setting."""
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    _, key, return_to = query.data.split(":", 2)
    was_on = bool(BOT_DATA["settings"].get(key, False))
    BOT_DATA["settings"][key] = not was_on
    save_data()

    if key == "maintenance":
        # Single combined screen now (status + toggle + set-message all in
        # one place) — toggling just re-renders that same screen instead of
        # showing a separate bulky "MAINTENANCE ON" / "BOT IS LIVE" card.
        if BOT_DATA["settings"]["maintenance"]:
            await query.answer("🔒 " + to_small_caps("maintenance enabled."), show_alert=False)
        else:
            await query.answer("🟢 " + to_small_caps("bot is live again."), show_alert=False)
            # Tell every user who actually hit the maintenance wall — not
            # just the admin looking at this panel — that the bot is back.
            await broadcast_bot_live(context)
        await _render_adm_maintenance(update, context)
        return

    renderer = SCREEN_RENDERERS.get(return_to)
    if renderer is not None:
        await renderer(update, context)
    else:
        await query.answer(to_small_caps("✅ updated."), show_alert=False)


async def cb_adm_lang_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    langs = BOT_DATA["settings"].get("languages", [])
    pack_names = _load_language_pack().get("languages", {})
    text = "🌐 Enabled Languages\n\n" + ("\n".join(f"• {pack_names.get(c) or LANG_NAMES.get(c, c)}" for c in langs) if langs else to_small_caps("none — default language only."))
    kb = InlineKeyboardMarkup(
        [
            [styled_button("➕ Add Language", callback_data="adm_lang_add")],
            [styled_button("➖ Remove Language", callback_data="adm_lang_remove")],
            [styled_button("🔙 Back", callback_data="adm_settings")],
        ]
    )
    await query.edit_message_text(text, reply_markup=kb)


async def cb_adm_lang_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pack_names = _load_language_pack().get("languages", {})
    all_known = {**LANG_NAMES, **pack_names}
    available = [c for c in all_known if c not in BOT_DATA["settings"].get("languages", []) and c != "en"]
    if not available:
        await query.message.reply_text(to_small_caps("all available languages are already added."))
        return
    rows = [[styled_button(all_known[c], callback_data=f"adm_lang_add_do:{c}")] for c in available]
    await query.message.reply_text(to_small_caps("which language would you like to add?"), reply_markup=InlineKeyboardMarkup(rows))


async def cb_adm_lang_add_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    code = query.data.split(":", 1)[1]
    pack_names = _load_language_pack().get("languages", {})
    if code not in BOT_DATA["settings"]["languages"]:
        BOT_DATA["settings"]["languages"].append(code)
        save_data()
    await query.edit_message_text(to_small_caps(f"✅ {pack_names.get(code) or LANG_NAMES.get(code, code)} added. you can now add text for it via 🌐 translations in any menu."))


async def cb_adm_lang_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    langs = BOT_DATA["settings"].get("languages", [])
    if not langs:
        await query.message.reply_text(to_small_caps("no languages have been added yet."))
        return
    pack_names = _load_language_pack().get("languages", {})
    rows = [[styled_button(pack_names.get(c) or LANG_NAMES.get(c, c), callback_data=f"adm_lang_remove_do:{c}")] for c in langs]
    await query.message.reply_text(to_small_caps("which language would you like to remove?"), reply_markup=InlineKeyboardMarkup(rows))


async def cb_adm_lang_remove_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    code = query.data.split(":", 1)[1]
    if code in BOT_DATA["settings"]["languages"]:
        BOT_DATA["settings"]["languages"].remove(code)
        save_data()
    await query.edit_message_text(to_small_caps(f"✅ {LANG_NAMES.get(code, code)} removed."))


async def cb_adm_set_autodelete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["awaiting"] = "global_autodelete"
    await query.message.reply_text("Global auto-delete kitne seconds ka ho (0 = disable)?")


async def cb_adm_autoreply_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    replies = BOT_DATA["settings"].get("auto_replies", {})
    lines = ["💬 Auto-Replies\n"] + (
        [f"• `{k}` → {v[:30]}" for k, v in replies.items()] or [to_small_caps("no auto-reply has been set.")]
    )
    kb = InlineKeyboardMarkup(
        [
            [styled_button("➕ Add", callback_data="adm_autoreply_add")],
            [styled_button("❌ Remove", callback_data="adm_autoreply_del")],
            [styled_button("🔙 Back", callback_data="adm_settings")],
        ]
    )
    await query.edit_message_text("\n".join(lines), reply_markup=kb)


async def cb_adm_autoreply_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["awaiting"] = "autoreply_key"
    await query.message.reply_text(to_small_caps("send the trigger keyword or phrase — it will auto-reply whenever a message contains it."))


async def cb_adm_autoreply_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["awaiting"] = "autoreply_delkey"
    await query.message.reply_text(to_small_caps("send the keyword you want to remove."))


def _perm_summary_text(selected: set) -> str:
    if not selected:
        return to_small_caps("no sections selected — this admin won't see anything in the panel yet.")
    lines = [f"• {ADMIN_PERMISSION_LABELS[k]}" for k in ADMIN_PERMISSION_KEYS if k in selected]
    return to_small_caps("access granted") + ":\n" + "\n".join(lines)


def _perm_picker_keyboard(selected: set, confirm_cb: str, cancel_cb: str, toggle_prefix: str) -> InlineKeyboardMarkup:
    """Shared toggle-grid used both when adding a new admin and when
    editing an existing one's access. ✅/⬜ next to each grantable section
    (see ADMIN_PERMISSIONS) — 📦 Update Backup, ☠️ Danger Zone, and 👤
    Manage Admins are deliberately absent: they're owner-only forever."""
    rows, row = [], []
    for key, label in ADMIN_PERMISSIONS:
        mark = "✅" if key in selected else "⬜"
        row.append(styled_button(f"{mark} {label}", callback_data=f"{toggle_prefix}:{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([styled_button("✅ Select All", callback_data=f"{toggle_prefix}_all"),
                 styled_button("⬜ Clear All", callback_data=f"{toggle_prefix}_none")])
    rows.append([styled_button("💾 Save", callback_data=confirm_cb),
                 styled_button("🚫 Cancel", callback_data=cancel_cb)])
    return InlineKeyboardMarkup(rows)


async def cb_adm_manage_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_owner(update.effective_user.id):
        await query.answer("🔒 " + to_small_caps("only the owner can access this."), show_alert=True)
        return
    admins = BOT_DATA.get("admins", [])
    lines = ["👤 " + to_small_caps("current admins") + "\n"]
    rows = []
    for a in admins:
        n_perms = len(get_admin_perms(a))
        lines.append(f"• {a} — {n_perms}/{len(ADMIN_PERMISSION_KEYS)} " + to_small_caps("sections"))
        rows.append([styled_button(f"✏️ {to_small_caps('edit access')} — {a}", callback_data=f"admperm_edit:{a}")])
    rows.append([styled_button("➕ Add Admin", callback_data="adm_add_admin")])
    rows.append([styled_button("➖ Remove Admin", callback_data="adm_remove_admin")])
    rows.append([styled_button("🔙 Back", callback_data="adm_settings")])
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))


async def cb_adm_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_owner(update.effective_user.id):
        await query.message.reply_text(to_small_caps("only the owner can add a new admin."))
        return
    context.user_data["awaiting"] = "add_admin_id"
    await query.message.reply_text(to_small_caps("send the new admin's user id."))


async def cb_adm_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_owner(update.effective_user.id):
        await query.message.reply_text(to_small_caps("only the owner can remove an admin."))
        return
    context.user_data["awaiting"] = "remove_admin_id"
    await query.message.reply_text(to_small_caps("send the user id of the admin to remove."))


__all__ = [_n for _n in dir() if not _n.startswith("__")]
