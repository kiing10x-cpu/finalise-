from handlers_misc import *


async def create_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE) -> dict:
    uid = str(update.effective_user.id)
    tid = BOT_DATA["next_ticket_id"]
    BOT_DATA["next_ticket_id"] += 1
    ticket = {
        "id": tid, "user_id": update.effective_user.id, "status": "open",
        "created_at": datetime.utcnow().isoformat(), "closed_at": None,
    }
    BOT_DATA["tickets"][str(tid)] = ticket
    BOT_DATA["users"].setdefault(uid, {})["open_ticket_id"] = tid
    save_data()
    return ticket


async def post_ticket_card(context: ContextTypes.DEFAULT_TYPE, ticket: dict, user_obj):
    group_id = BOT_DATA["settings"].get("admin_group_id")
    targets = [group_id] if group_id else BOT_DATA.get("admins", [])
    card_text = f"👤 {user_obj.full_name} | 🆔 {user_obj.id} | 🎫 #{ticket['id']} | Status: 🟢 Open"
    kb = InlineKeyboardMarkup([[
        styled_button("✅ Close Ticket", callback_data=f"tk_close:{ticket['id']}"),
        styled_button("🔁 Reopen", callback_data=f"tk_reopen:{ticket['id']}"),
    ]])
    for target in targets:
        if not target:
            continue
        try:
            sent = await context.bot.send_message(chat_id=target, text=card_text, reply_markup=kb)
            BOT_DATA["ticket_msg_map"][str(sent.message_id)] = str(ticket["id"])
        except Exception:
            pass
    save_data()


async def forward_to_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id: int):
    group_id = BOT_DATA["settings"].get("admin_group_id")
    targets = [group_id] if group_id else BOT_DATA.get("admins", [])
    for target in targets:
        if not target:
            continue
        try:
            copied = await context.bot.copy_message(
                chat_id=target, from_chat_id=update.effective_chat.id, message_id=update.message.message_id
            )
            BOT_DATA["ticket_msg_map"][str(copied.message_id)] = str(ticket_id)
        except Exception:
            pass
    save_data()


async def handle_admin_ticket_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, tid: str):
    ticket = BOT_DATA["tickets"].get(tid)
    if not ticket or ticket["status"] != "open":
        return
    # v10 — same confirmation-to-admin fix as the one-shot support flow above.
    try:
        await context.bot.copy_message(
            chat_id=ticket["user_id"], from_chat_id=update.effective_chat.id, message_id=update.message.message_id
        )
        await update.message.reply_text("✅ " + to_title_small_caps("Reply sent to user."))
    except Exception:
        await update.message.reply_text(
            "⚠️ " + to_title_small_caps("Couldn't deliver reply — the user may have blocked the bot.")
        )


def get_support_prompt_text(uid: str = None) -> str:
    """v10 — sourced from BOT_DATA['menus']['support'] so the admin can edit
    this from Menu & UI, falling back to the original default copy.
    v11 — now also respects the user's saved language, same lookup
    render_menu() uses, so Support shows the translated text instead of
    always falling back to the base/English copy."""
    menu = BOT_DATA["menus"].get("support", {})
    lang = BOT_DATA["users"].get(str(uid), {}).get("lang") if uid else None
    translation = menu.get("translations", {}).get(lang) if (lang and lang != "en") else None  # "en" is the bot.py default, never a translation override
    return (translation or {}).get("text") or menu.get("text") or DEFAULT_MENUS["support"]["text"]


async def support_button_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """One-shot support flow: user gets exactly one message to submit.
    The admin receives a mention and can reply directly to that single support
    message; there is no lingering open-ticket state.

    NOTE — this prompt is intentionally the ONLY thing sent through
    _replace_rkb_screen (the shared "rkb_latest" panel slot). The
    confirmation sent after submission is sent separately (see
    handle_user_awaiting_input) and is never tracked under that slot, so
    switching to another bottom-keyboard button later can never delete the
    user's submission confirmation. The prompt itself IS explicitly deleted
    the moment the user submits their message — see the "support_message"
    branch of handle_user_awaiting_input."""
    chat_id = update.effective_chat.id
    context.user_data["awaiting"] = "support_message"
    await _replace_rkb_screen(context, chat_id, "support", get_support_prompt_text(uid=chat_id), parse_mode="HTML")


async def cb_ticket_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    tid = query.data.split(":", 1)[1]
    ticket = BOT_DATA["tickets"].get(tid)
    if not ticket:
        return
    ticket["status"] = "closed"
    ticket["closed_at"] = datetime.utcnow().isoformat()
    uid = str(ticket["user_id"])
    if BOT_DATA["users"].get(uid, {}).get("open_ticket_id") == int(tid):
        BOT_DATA["users"][uid]["open_ticket_id"] = None
    save_data()
    try:
        await context.bot.send_message(chat_id=ticket["user_id"], text=STR["ticket_closed"](tid))
    except Exception:
        pass
    try:
        await query.edit_message_reply_markup(
            InlineKeyboardMarkup([[styled_button("🔁 Reopen", callback_data=f"tk_reopen:{tid}")]])
        )
    except Exception:
        pass
    await log_event(context, f"🎫 Ticket #{tid} closed by {update.effective_user.id}")


async def cb_ticket_reopen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    tid = query.data.split(":", 1)[1]
    ticket = BOT_DATA["tickets"].get(tid)
    if not ticket:
        return
    ticket["status"] = "open"
    ticket["closed_at"] = None
    uid = str(ticket["user_id"])
    BOT_DATA["users"].setdefault(uid, {})["open_ticket_id"] = int(tid)
    save_data()
    try:
        await query.edit_message_reply_markup(
            InlineKeyboardMarkup([[styled_button("✅ Close Ticket", callback_data=f"tk_close:{tid}")]])
        )
    except Exception:
        pass
    await log_event(context, f"🎫 Ticket #{tid} reopened by {update.effective_user.id}")


_CARD_SEP = "──────────────────"


def _build_support_admin_card(rid: str) -> tuple:
    """Admin-facing 'New Support Request' card — sectioned layout, message
    quoted in « », live Pending/Resolved status, name is a clickable link
    to the user's profile. Reused both when the request first comes in and
    when an admin marks it resolved, so the card always reflects the live
    status."""
    req = BOT_DATA["support_requests"][rid]
    lbl = to_title_small_caps
    is_open = req["status"] == "pending"
    status_word = lbl("Pending") if is_open else lbl("Resolved")
    received = iso_to_ist_str(req["created_at"], "%d %B %Y") + " • " + iso_to_ist_str(req["created_at"], "%H:%M:%S") + " IST"
    payload = (
        "📩 " + lbl("New Support Request") + "\n\n"
        f"{_CARD_SEP}\n\n"
        "👤 " + lbl("User Information") + "\n\n"
        f"{lbl('Name')} : {req['user_mention']}\n"
        f"{lbl('Username')} : {html.escape(req['username_display'])}\n"
        f"{lbl('User Id')} : {req['user_id']}\n\n"
        "💬 " + lbl("Support Message") + "\n\n"
        f"«{html.escape(req['text'])}»\n\n"
        "🕒 " + lbl("Received At") + "\n\n"
        f"{received}\n\n"
        f"{_CARD_SEP}\n\n"
        "📌 " + f"{lbl('Status')} : {status_word}"
    )
    kb = None
    if is_open:
        kb = InlineKeyboardMarkup([[
            styled_button("✅ Mark Resolved", callback_data=f"sup_resolve:{rid}"),
        ]])
    return payload, kb


def _build_support_user_confirmation(rid: str) -> str:
    """User-facing confirmation — the exact requested copy, with the live
    status swapped between the just-submitted card and the resolved card."""
    req = BOT_DATA["support_requests"][rid]
    lbl = to_title_small_caps
    if req["status"] == "pending":
        body = (
            "✅ " + lbl("Message Submitted") + "\n\n"
            + lbl("Thank you for contacting support.") + "\n\n"
            + "📩 " + lbl("Your message has been sent to our support team.") + "\n\n"
            + lbl("We'll review it and get back to you as soon as possible.") + "\n\n"
            + "❤️ " + lbl("Thank you for your patience.")
        )
    else:
        body = (
            "✅ " + lbl("Support Request Resolved") + "\n\n"
            + lbl("Thank you for contacting support.") + "\n\n"
            + "📩 " + lbl("Your issue has been reviewed and marked as resolved.") + "\n\n"
            + lbl("Need anything else? Just send us a new message anytime.") + "\n\n"
            + "❤️ " + lbl("Thank you for your patience.")
        )
    return "<blockquote>" + body + "</blockquote>"


async def cb_support_resolve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin taps '✅ Mark Resolved' on a support card. This is what makes
    the user-facing status live instead of frozen on PENDING forever — we
    edit the SAME confirmation message in the user's chat in place, and
    edit this same admin card too, rather than sending fresh clutter."""
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer()
        return
    rid = query.data.split(":", 1)[1]
    req = BOT_DATA["support_requests"].get(rid)
    if not req:
        await query.answer("Request not found.", show_alert=True)
        return
    if req["status"] != "pending":
        await query.answer("Already resolved.")
        return

    req["status"] = "resolved"
    req["resolved_at"] = datetime.utcnow().isoformat()
    req["resolved_by"] = update.effective_user.id
    save_data()

    # Live-update the user's own confirmation message: PENDING -> SOLVED.
    try:
        await context.bot.edit_message_text(
            chat_id=req["confirm_chat_id"],
            message_id=req["confirm_message_id"],
            text=_build_support_user_confirmation(rid),
            parse_mode="HTML",
        )
    except Exception:
        # Message may have been deleted by the user / too old to edit —
        # fall back to a fresh "resolved" message in the same style.
        try:
            msg = await context.bot.send_message(
                chat_id=req["confirm_chat_id"], text=_build_support_user_confirmation(rid), parse_mode="HTML"
            )
            req["confirm_chat_id"] = msg.chat_id
            req["confirm_message_id"] = msg.message_id
            save_data()
        except Exception:
            pass

    # Live-update this admin card too (Pending -> Resolved, button removed).
    card_text, card_kb = _build_support_admin_card(rid)
    try:
        await query.edit_message_text(card_text, parse_mode="HTML", reply_markup=card_kb)
    except Exception:
        pass

    await query.answer("✅ Marked resolved.")
    await log_event(context, f"🎧 Support request #{rid} resolved by {update.effective_user.id}")


# ----------------------------------------------------------------------------
# My usage
# ----------------------------------------------------------------------------


__all__ = [_n for _n in dir() if not _n.startswith("__")]
