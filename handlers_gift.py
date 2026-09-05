from handlers_support import *


async def show_usage_screen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """📊 Stats screen. Premium status/expiry are hidden unless a Premium
    plan has actually been assigned to this user from the Admin Panel."""
    await _clear_ephemeral(context, update.effective_chat.id)
    user = update.effective_user
    uid = str(user.id)
    u = BOT_DATA["users"].setdefault(uid, {})
    today = datetime.utcnow().strftime("%Y-%m-%d")
    used = u.get("downloads_today", 0) if u.get("downloads_today_date") == today else 0
    assigned_premium = u.get("plan", "Free") != "Free"
    active = is_premium_active(uid)
    limit = BOT_DATA["settings"].get("daily_limit", 20)
    username = f"@{user.username}" if user.username else "Not set"
    limit_text = "Unlimited" if assigned_premium else str(limit)
    remaining = "Unlimited" if assigned_premium else str(max(0, limit - used))

    lines = [
        "<u>" + to_title_small_caps("My Usage") + "</u>", "",
        f"Nᴀᴍᴇ : {html.escape(user.full_name)}",
        f"Uꜱᴇʀɴᴀᴍᴇ : {html.escape(username)}",
        f"Uꜱᴇʀ Iᴅ : {user.id}",
        f"Rᴇᴇʟs Dᴏᴡɴʟᴏᴀᴅᴇᴅ : {u.get('reels_count', 0)}",
        f"Aᴜᴅɪᴏs Gᴇᴛ : {u.get('audio_count', 0)}",
        f"Cᴀᴘᴛɪᴏɴs Gᴇᴛ : {u.get('caption_count', 0)}",
        f"Lɪᴍɪᴛ : {limit_text}",
        f"Uꜱᴇᴅ : {used}",
        f"Rᴇᴍᴀɪɴɪɴɢ : {remaining}",
    ]
    if assigned_premium:
        expiry = u.get("plan_expires_at")
        if expiry:
            try:
                expiry_text = to_ist(datetime.fromisoformat(expiry)).strftime("%d %b %Y, %I:%M %p") + " IST"
            except Exception:
                expiry_text = expiry
        else:
            expiry_text = "No expiry"
        lines += ["", f"💎 Pʀᴇᴍɪᴜᴍ Sᴛᴀᴛᴜꜱ : {'Active' if active else 'Expired'}", f"Eхᴘɪʀʏ : {html.escape(expiry_text)}"]

    text = "<blockquote>" + "\n".join(lines) + "</blockquote>"
    kb = None
    if BOT_DATA["settings"].get("share_enabled", True):
        share_url = await resolve_share_url(context)
        kb = InlineKeyboardMarkup([[styled_button("📤 " + to_small_caps("Share Bot"), url=share_url, style="primary")]])
    await _replace_rkb_screen(context, update.effective_chat.id, "usage", text, reply_markup=kb, parse_mode="HTML")


# ----------------------------------------------------------------------------
# Developer button
# ----------------------------------------------------------------------------

def _normalize_username_link(value: str) -> str:
    value = value.strip()
    if value.startswith("http://") or value.startswith("https://") or value.startswith("tg://"):
        return value
    return f"https://t.me/{value.lstrip('@')}"


async def resolve_share_url(context: ContextTypes.DEFAULT_TYPE) -> str:
    """v11 — the My Usage Share button now opens Telegram's real share
    composer instead of simply opening the bot profile. The configured
    share_url remains the content being shared; when unset, the live bot
    username is resolved automatically."""
    target = BOT_DATA["settings"].get("share_url")
    try:
        if not target:
            me = await context.bot.get_me()
            target = f"https://t.me/{me.username}" if me.username else "https://t.me/"
    except Exception:
        target = "https://t.me/"
    text = BOT_DATA["settings"].get("share_text") or "Try this Instagram Reel Downloader bot."
    return "https://t.me/share/url?url=" + quote(target, safe="") + "&text=" + quote(text, safe="")


async def resolve_developer_url(context: ContextTypes.DEFAULT_TYPE) -> str | None:
    link = BOT_DATA["settings"].get("developer_link")
    if link:
        return _normalize_username_link(link)
    dev_id = BOT_DATA["settings"].get("developer_id")
    if not dev_id:
        return None
    # tg://user?id=... only opens if the tapping user's Telegram client already
    # has that account cached (shared group, contact, etc.) — it silently does
    # nothing otherwise, which is the "click nahi khulta" bug. Resolving the
    # real @username via getChat and linking to t.me/username always works.
    try:
        chat = await context.bot.get_chat(dev_id)
        if chat.username:
            return f"https://t.me/{chat.username}"
    except Exception:
        pass
    return f"tg://user?id={dev_id}"


async def show_developer_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = await resolve_developer_url(context)
    if not url:
        await context.bot.send_message(update.effective_chat.id, to_small_caps("developer contact not set up yet."))
        return
    kb = InlineKeyboardMarkup([[styled_button("👨‍💻 " + to_small_caps("message developer"), url=url, style="primary")]])
    menu = BOT_DATA["menus"].get("developer", {})
    lang = BOT_DATA["users"].get(str(update.effective_chat.id), {}).get("lang")
    translation = menu.get("translations", {}).get(lang) if (lang and lang != "en") else None  # "en" is the bot.py default, never a translation override
    banner = (translation or {}).get("text") or menu.get("text") or DEFAULT_MENUS["developer"]["text"]
    await _replace_rkb_screen(
        context, update.effective_chat.id, "developer",
        banner, reply_markup=kb, parse_mode=menu.get("parse_mode"),
    )


# ----------------------------------------------------------------------------
# Gift flow (Telegram Stars + UPI)
# ----------------------------------------------------------------------------

async def show_gift_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """v4 — pure voluntary support/tip flow. This is separate from Premium
    Plans (those live under Usage now) — this is just 'send a gift to
    support the bot', any amount, no plan attached.
    v5 — the top-donor leaderboard now lives right inside this screen
    (not a separate top-level menu button), and only when the admin has
    turned it on in the Admin Panel.
    v6 — redesigned copy/buttons for a cleaner, more premium feel. Amount
    selection logic (Stars fixed buttons, UPI free-text entry) is left
    exactly as it already works — only the wording/labels changed here."""
    await _clear_ephemeral(context, update.effective_chat.id)
    kb_rows = [[styled_button("⭐ Support With Stars", callback_data="gift_stars", style="success")]]
    if BOT_DATA["settings"].get("upi_id"):
        kb_rows.append([styled_button("💳 Support Via UPI", callback_data="gift_upi", style="primary")])

    # v10 — banner text now comes from BOT_DATA["menus"]["gift"] so the
    # admin can edit it from Menu & UI like any other menu, instead of it
    # being hardcoded here. The Stars/UPI buttons above stay code-driven
    # since they carry real payment logic.
    # v11 — also respects the user's saved language (same lookup
    # render_menu() uses), so Send A Gift shows the translated text
    # instead of always falling back to the base/English copy.
    menu = BOT_DATA["menus"].get("gift", {})
    lang = BOT_DATA["users"].get(str(update.effective_chat.id), {}).get("lang")
    translation = menu.get("translations", {}).get(lang) if (lang and lang != "en") else None  # "en" is the bot.py default, never a translation override
    text = (translation or {}).get("text") or menu.get("text") or DEFAULT_MENUS["gift"]["text"]

    if BOT_DATA["settings"].get("leaderboard_enabled"):
        text += "\n\n" + build_leaderboard_text(limit=3)
        kb_rows.append([styled_button("🏆 Full Leaderboard", callback_data="view_leaderboard", style="primary")])
    await _replace_rkb_screen(
        context, update.effective_chat.id, "gift", text, reply_markup=InlineKeyboardMarkup(kb_rows),
        parse_mode=menu.get("parse_mode") or "HTML",
    )


async def cb_gift_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_gift_menu(update, context)


async def cb_view_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not BOT_DATA["settings"].get("leaderboard_enabled"):
        return
    await query.message.reply_text(build_leaderboard_text())


async def cb_gift_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup([
        [
            styled_button("⭐ 50", callback_data="gift_stars_amt:50", style="success"),
            styled_button("⭐ 100", callback_data="gift_stars_amt:100", style="success"),
            styled_button("⭐ 500", callback_data="gift_stars_amt:500", style="success"),
        ],
        [
            styled_button("➕ Another Amount", callback_data="gift_stars_custom", style="primary"),
            styled_button("🗑 Dismiss", callback_data="gift_dismiss", style="danger"),
        ],
    ])
    msg = await query.message.reply_text("⭐ " + to_title_small_caps("Choose an amount:"), reply_markup=kb)
    _track_ephemeral(context, msg)


async def cb_gift_dismiss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        pass


async def cb_gift_stars_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["awaiting"] = "gift_stars_custom_amount"
    msg = await query.message.reply_text("✏️ " + to_small_caps("enter a numeric star amount (e.g. 150)."))
    _track_ephemeral(context, msg)


def record_donation(uid: str, name: str, amount: float, kind: str):
    """v5 — leaderboard bookkeeping. kind is 'stars' or 'inr'. Both
    currencies are combined into one 'score' for ranking purposes (1 star
    == 1 rupee of ranking weight — simple and good enough for a fun
    leaderboard; admin can adjust the weighting later if it ever matters)."""
    if amount <= 0:
        return
    entry = BOT_DATA["donations"].setdefault(uid, {"name": name, "stars": 0, "inr": 0, "score": 0})
    entry["name"] = name or entry.get("name") or f"User {uid}"
    if kind == "stars":
        entry["stars"] = entry.get("stars", 0) + amount
    else:
        entry["inr"] = entry.get("inr", 0) + amount
    entry["score"] = entry.get("stars", 0) + entry.get("inr", 0)
    save_data()


def build_leaderboard_text(limit: int = 10) -> str:
    """Ranked list of top supporters, medal-styled for the top 3, with a
    warm note at the bottom so donating actually feels good to see — not
    just a bare list of numbers."""
    donors = [d for d in BOT_DATA.get("donations", {}).values() if d.get("score", 0) > 0]
    donors.sort(key=lambda d: d.get("score", 0), reverse=True)
    donors = donors[:limit]
    if not donors:
        return (
            "🏆 " + to_small_caps("top supporters") + "\n\n"
            + to_small_caps("no donations yet — be the first to make the list!")
        )
    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 " + to_small_caps("top supporters"), to_small_caps("our amazing community, ranked"), ""]
    for i, d in enumerate(donors):
        rank = medals[i] if i < 3 else f"{i + 1}."
        bits = []
        if d.get("stars"):
            bits.append(f"{int(d['stars'])}⭐")
        if d.get("inr"):
            bits.append(f"₹{int(d['inr'])}")
        lines.append(f"{rank} {d.get('name', 'Anonymous')} — {' + '.join(bits)}")
    lines.append("")
    lines.append(to_small_caps("every gift helps keep this bot alive — thank you for the love! 💛"))
    return "\n".join(lines)


def find_premium_plan(pid: str):
    for p in BOT_DATA["settings"].get("premium_plans", []):
        if p["id"] == pid:
            return p
    return None


async def cb_gift_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User tapped a specific admin-defined plan in the gift menu — show only
    the payment methods the admin actually priced for this plan."""
    query = update.callback_query
    await query.answer()
    pid = query.data.split(":", 1)[1]
    plan = find_premium_plan(pid)
    if not plan or not plan.get("enabled"):
        await query.message.reply_text("⚠️ " + to_small_caps("this plan is no longer available."))
        return
    kb_rows = []
    if plan.get("price_stars"):
        kb_rows.append([styled_button(f"⭐ Pay {plan['price_stars']} Stars", callback_data=f"gift_plan_stars:{pid}", style="success")])
    if plan.get("price_inr") and BOT_DATA["settings"].get("upi_id"):
        kb_rows.append([styled_button(f"💳 Pay ₹{plan['price_inr']} via UPI", callback_data=f"gift_plan_upi:{pid}", style="primary")])
    if not kb_rows:
        await query.message.reply_text("⚠️ " + to_small_caps("no payment method available for this plan right now."))
        return
    await query.message.reply_text(
        f"💎 {plan['name']} — {plan.get('days', 30)} days\nChoose how to pay:",
        reply_markup=InlineKeyboardMarkup(kb_rows),
    )


async def cb_gift_plan_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = query.data.split(":", 1)[1]
    plan = find_premium_plan(pid)
    if not plan or not plan.get("enabled") or not plan.get("price_stars"):
        await query.message.reply_text("⚠️ " + to_small_caps("this plan is no longer available."))
        return
    await send_stars_invoice(context, query.message.chat_id, plan["price_stars"], plan_id=pid, plan_name=plan["name"])


async def cb_gift_plan_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = query.data.split(":", 1)[1]
    plan = find_premium_plan(pid)
    if not plan or not plan.get("enabled") or not plan.get("price_inr"):
        await query.message.reply_text("⚠️ " + to_small_caps("this plan is no longer available."))
        return
    await start_upi_order(update, context, plan["price_inr"], plan_id=pid)


async def send_stars_invoice(context: ContextTypes.DEFAULT_TYPE, chat_id: int, amount: int, plan_id: str = None, plan_name: str = None):
    title = to_title_small_caps(f"{plan_name} — Premium ⭐") if plan_name else to_title_small_caps("Gift The Developer ⭐")
    desc = to_title_small_caps(f"Unlock {plan_name}.") if plan_name else to_title_small_caps(f"Send {amount} Telegram Stars as a gift.")
    return await context.bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=desc,
        payload=f"stars_gift:{amount}:{chat_id}:{int(time.time())}:{plan_id or ''}",
        provider_token="",  # not used for XTR
        currency="XTR",
        prices=[LabeledPrice(label=f"{amount} Stars", amount=amount)],
    )


async def cb_gift_stars_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    amount = int(query.data.split(":", 1)[1])
    # Free-form tip invoice (no plan attached) — tracked as ephemeral so it
    # gets swept away the moment another menu is opened.
    msg = await send_stars_invoice(context, query.message.chat_id, amount)
    _track_ephemeral(context, msg)


async def cmd_precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)


async def cmd_successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sp = update.message.successful_payment
    uid = str(update.effective_user.id)
    # A star payment tied to an admin-defined plan grants that plan's day
    # count; a generic/free-amount gift doesn't unlock anything.
    plan_id = None
    parts = (sp.invoice_payload or "").split(":")
    if len(parts) >= 5 and parts[4]:
        plan_id = parts[4]
    plan = find_premium_plan(plan_id) if plan_id else None
    if plan:
        days = plan.get("days", 30)
        grant_premium(uid, days)
        text = (
            "✅ " + to_small_caps("payment successful!") + "\n\n"
            f"💎 {to_small_caps('plan')}: {plan['name']}\n"
            f"⭐ {to_small_caps('paid')}: {sp.total_amount} {to_small_caps('stars')}\n"
            f"⏳ {to_small_caps('premium unlocked for')} {days} {to_small_caps('days')}"
        )
        log_line = f"⭐ Plan purchased — {sp.total_amount} stars from {update.effective_user.id} ({plan['name']}), premium granted"
    else:
        # A voluntary tip (no plan attached) is a pure thank-you — nothing
        # is unlocked, and only real gifts count toward the leaderboard.
        record_donation(uid, update.effective_user.full_name, sp.total_amount, "stars")
        text = (
            "🎉 " + to_small_caps("thank you so much for the support!") + "\n\n"
            f"💫 {to_small_caps('you sent')}: {sp.total_amount} ⭐\n\n"
            + to_small_caps("it really means a lot — thank you! ❤️")
        )
        log_line = f"⭐ Gift received — {sp.total_amount} stars from {update.effective_user.id}"
    await update.message.reply_text(text)
    await log_event(context, log_line)
    # Stars payments settle instantly with no manual admin verification, so
    # every admin also gets a direct DM regardless of logger-channel setup.
    await dm_all_admins(context, "💰 " + log_line)


async def cb_gift_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not BOT_DATA["settings"].get("upi_id"):
        await query.message.reply_text("⚠️ " + to_small_caps("upi is not configured yet."))
        return
    context.user_data["awaiting"] = "gift_upi_amount"
    await query.message.reply_text("💳 " + to_small_caps("enter amount (₹):"))


async def start_upi_order(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int, plan_id: str = None):
    upi_id = BOT_DATA["settings"].get("upi_id")
    oid = str(BOT_DATA["next_gift_id"])
    BOT_DATA["next_gift_id"] += 1
    expires_at = time.time() + 600  # 10 minutes
    order = {
        "id": oid, "user_id": update.effective_user.id, "amount": amount,
        "expires_at": expires_at, "status": "pending", "plan_id": plan_id,
    }
    BOT_DATA["gift_orders"][oid] = order
    save_data()
    upi_uri = f"upi://pay?pa={upi_id}&am={amount}&cu=INR&tn=Gift%20Order%20{oid}"
    # Locally-generated branded QR (gradient card, amount/caption baked in,
    # payer's own Telegram avatar as center logo). Falls back to the remote
    # api.qrserver.com URL if qrcode/Pillow aren't installed.
    avatar_bytes = await fetch_user_avatar_bytes(context, update.effective_user.id)
    qr_photo = generate_branded_qr(
        upi_uri, amount=amount, caption=to_small_caps("scan with any upi app"),
        logo_bytes=avatar_bytes,
    )
    if qr_photo is None:
        qr_photo = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={quote(upi_uri)}"
    kb = InlineKeyboardMarkup([[styled_button("✅ Done", callback_data=f"gift_upi_paid:{oid}", style="success")]])
    msg = await context.bot.send_photo(
        chat_id=update.effective_chat.id, photo=qr_photo,
        caption=f"💳 ₹{amount} — {to_small_caps('scan to pay via upi')}\n⏳ expires in 10:00",
        reply_markup=kb,
    )
    context.job_queue.run_repeating(
        upi_countdown_job, interval=20, first=20,
        data={"oid": oid, "chat_id": msg.chat_id, "message_id": msg.message_id},
        name=f"upi_countdown_{oid}",
    )


async def upi_countdown_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    oid, chat_id, message_id = job.data["oid"], job.data["chat_id"], job.data["message_id"]
    order = BOT_DATA["gift_orders"].get(oid)
    if not order or order["status"] != "pending":
        job.schedule_removal()
        return
    remaining = int(order["expires_at"] - time.time())
    if remaining <= 0:
        order["status"] = "expired"
        save_data()
        # Auto-delete the QR photo from the chat on expiry (10 min), rather
        # than leaving a dead/expired QR sitting there. A small follow-up
        # notice replaces it so the user still has a way to retry.
        deleted = False
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            deleted = True
        except Exception:
            log.exception("Could not delete expired QR message %s/%s, falling back to caption edit", chat_id, message_id)
        kb = InlineKeyboardMarkup([[styled_button("🔁 Generate New QR", callback_data="gift_upi", style="primary")]])
        if deleted:
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ " + to_small_caps("qr expired and was removed. generate a new one:"),
                    reply_markup=kb,
                )
            except Exception:
                pass
        else:
            try:
                await context.bot.edit_message_caption(chat_id=chat_id, message_id=message_id, caption="❌ QR expired, generate new one", reply_markup=kb)
            except Exception:
                pass
        job.schedule_removal()
        return
    mm, ss = remaining // 60, remaining % 60
    try:
        await context.bot.edit_message_caption(
            chat_id=chat_id, message_id=message_id,
            caption=f"💳 ₹{order['amount']} — {to_small_caps('scan to pay via upi')}\n⏳ expires in {mm:02d}:{ss:02d}",
            reply_markup=InlineKeyboardMarkup([[styled_button("✅ Done", callback_data=f"gift_upi_paid:{oid}", style="success")]]),
        )
    except Exception:
        pass


async def cb_gift_upi_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    oid = query.data.split(":", 1)[1]
    order = BOT_DATA["gift_orders"].get(oid)
    if not order:
        return
    if order["expires_at"] < time.time():
        await query.message.reply_text("❌ " + to_small_caps("qr expired, generate a new one via 🎁 send a gift."))
        return
    order["status"] = "claimed_pending_verify"
    save_data()
    plan = find_premium_plan(order.get("plan_id")) if order.get("plan_id") else None
    # Delete the QR photo immediately on tap rather than leaving it sitting
    # there with a "marked as paid" note stacked below it.
    try:
        await query.message.delete()
    except Exception:
        try:
            await query.edit_message_reply_markup(None)
        except Exception:
            pass
    user_text = (
        "✅ " + to_small_caps("your payment has been sent to admin.") + "\n"
        + to_small_caps("admin will verify and notify you shortly.")
    )
    await context.bot.send_message(chat_id=query.message.chat_id, text=user_text)
    targets = BOT_DATA.get("admins", [])
    kind = f"Plan purchase ({plan['name']})" if plan else "Support gift"
    # Approve/Decline for a plan purchase, Received/Not Received for a
    # free-amount gift.
    approve_label = "✅ Approve Payment" if plan else "✅ Received"
    decline_label = "❌ Decline Payment" if plan else "❌ Not Received"
    admin_kb = InlineKeyboardMarkup([[
        styled_button(approve_label, callback_data=f"gift_upi_confirm:{oid}", style="success"),
        styled_button(decline_label, callback_data=f"gift_upi_decline:{oid}", style="danger"),
    ]])
    for target in targets:
        try:
            await context.bot.send_message(
                target,
                f"💳 UPI order #{oid} — {kind} — ₹{order['amount']} — user {order['user_id']} claims paid.",
                reply_markup=admin_kb,
            )
        except Exception:
            pass


async def cb_gift_upi_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin taps Approve (plan order) or Received (free-amount gift)."""
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    oid = query.data.split(":", 1)[1]
    order = BOT_DATA["gift_orders"].get(oid)
    if not order or order["status"] == "paid":
        await query.answer("Already handled or not found.", show_alert=True)
        return
    order["status"] = "paid"
    save_data()
    uid = str(order["user_id"])
    donor_name = BOT_DATA["users"].get(uid, {}).get("name") or f"User {uid}"
    plan = find_premium_plan(order.get("plan_id")) if order.get("plan_id") else None
    if plan:
        days = plan.get("days", 30)
        grant_premium(uid, days)
        user_text = (
            "✅ " + to_small_caps("payment approved!") + "\n\n"
            f"💎 {to_small_caps('plan')}: {plan['name']}\n"
            f"💳 {to_small_caps('paid')}: ₹{order['amount']}\n"
            f"⏳ {to_small_caps('premium unlocked for')} {days} {to_small_caps('days')}"
        )
        log_line = f"💳 UPI order #{oid} approved by admin {update.effective_user.id} ({plan['name']}), premium granted"
        admin_ack = f"✅ Order #{oid} approved, plan unlocked for the user."
    else:
        # A free-amount payment doesn't unlock premium on its own —
        # "Received" just confirms the money arrived and says thanks.
        record_donation(uid, donor_name, order["amount"], "inr")
        user_text = (
            "🎉 " + to_small_caps("thank you so much for the support!") + "\n\n"
            f"💫 {to_small_caps('you sent')}: ₹{order['amount']}\n\n"
            + to_small_caps("it really means a lot — thank you! ❤️")
        )
        log_line = f"💳 UPI gift #{oid} marked received by admin {update.effective_user.id}"
        admin_ack = f"✅ Order #{oid} marked received."
    try:
        await context.bot.send_message(order["user_id"], user_text)
    except Exception:
        pass
    try:
        await query.edit_message_reply_markup(None)
        await query.message.reply_text(admin_ack)
    except Exception:
        pass
    await log_event(context, log_line)


async def cb_gift_upi_decline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Decline Payment (plan order) or Not Received (free-amount gift) —
    nothing is granted, no donation is recorded, and the user is told."""
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    oid = query.data.split(":", 1)[1]
    order = BOT_DATA["gift_orders"].get(oid)
    if not order or order["status"] in ("paid", "declined"):
        await query.answer("Already handled or not found.", show_alert=True)
        return
    order["status"] = "declined"
    save_data()
    plan = find_premium_plan(order.get("plan_id")) if order.get("plan_id") else None
    user_text = (
        "❌ " + to_small_caps("your payment could not be verified.") + "\n"
        + to_small_caps("if you believe this is a mistake, please contact support.")
    )
    log_line = (
        f"💳 UPI order #{oid} declined by admin {update.effective_user.id}"
        + (f" ({plan['name']})" if plan else " (gift)")
    )
    try:
        await context.bot.send_message(order["user_id"], user_text)
    except Exception:
        pass
    try:
        await query.edit_message_reply_markup(None)
        await query.message.reply_text(f"❌ Order #{oid} declined.")
    except Exception:
        pass
    await log_event(context, log_line)


# ----------------------------------------------------------------------------
# PDF #3 / #11 — Copyright report + Support flows (user-facing, not admin-only)
# ----------------------------------------------------------------------------

async def cb_report_copyright(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["awaiting"] = "copyright_report_link"
    await query.message.reply_text(
        "🚫 Report Copyright Issue\n\nPlease paste the link to the content you believe infringes your copyright."
    )


async def cb_support_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["awaiting"] = "support_message"
    await query.message.reply_text(get_support_prompt_text(uid=update.effective_user.id), parse_mode="HTML")


__all__ = [_n for _n in dir() if not _n.startswith("__")]
