from handlers_gift import *


async def handle_user_awaiting_input(update: Update, context: ContextTypes.DEFAULT_TYPE, awaiting: str):
    text = (update.message.text or "").strip()
    user_obj = update.effective_user

    if awaiting == "support_message":
        # NOTE — pop "awaiting" first thing, unconditionally, so a support
        # request can never accidentally re-trigger on a later message even
        # if something below raises.
        context.user_data.pop("awaiting", None)

        # The "please type your message below" prompt is only ever needed
        # up until this exact moment — the user just submitted it. Delete
        # it now so the chat doesn't keep showing a now-stale instruction
        # sitting above the confirmation. It's the same "rkb_latest" panel
        # message _replace_rkb_screen tracked when the prompt was shown.
        _prompt_key = f"rkb_latest:{update.effective_chat.id}"
        _prompt_msg_id = BOT_DATA.get("panel_msg", {}).pop(_prompt_key, None)
        if _prompt_msg_id:
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=_prompt_msg_id)
            except Exception:
                pass
            save_data()

        rid = str(BOT_DATA["next_support_id"])
        BOT_DATA["next_support_id"] += 1
        created_at = datetime.utcnow().isoformat()
        req = {
            "user_id": user_obj.id,
            "user_mention": clickable_user(user_obj),
            "username_display": f"@{user_obj.username}" if user_obj.username else "No Username",
            "text": text,
            "status": "pending",
            "created_at": created_at,
            "resolved_at": None,
            "resolved_by": None,
            "confirm_chat_id": update.effective_chat.id,
            "confirm_message_id": None,
            "admin_message_ids": [],
        }
        BOT_DATA["support_requests"][rid] = req

        # Notify admins / the configured support chat with the live card.
        card_text, card_kb = _build_support_admin_card(rid)
        support_chat_id = BOT_DATA["settings"].get("support_chat_id")
        targets = [support_chat_id] if support_chat_id else BOT_DATA.get("admins", [])
        for target in targets:
            if not target:
                continue
            try:
                sent = await context.bot.send_message(
                    chat_id=target, text=card_text, parse_mode="HTML", reply_markup=card_kb
                )
                # Replying to this message still routes an admin's reply
                # straight to the user (unchanged), AND it's linked back to
                # this request for the live-status "Mark Resolved" button.
                BOT_DATA.setdefault("support_msg_map", {})[str(sent.message_id)] = str(user_obj.id)
                BOT_DATA.setdefault("support_admin_msg_map", {})[str(sent.message_id)] = rid
                req["admin_message_ids"].append(sent.message_id)
            except Exception:
                pass
        save_data()
        await log_event(context, f"🆘 Support request #{rid} from {user_obj.id}")

        # Sent instantly, fully HTML-parsed — no typewriter animation here,
        # since intermediate frames would show raw <blockquote> markup on
        # some clients mid-reveal.
        confirm_msg = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=_build_support_user_confirmation(rid),
            parse_mode="HTML",
        )
        if confirm_msg:
            req["confirm_message_id"] = confirm_msg.message_id
            req["confirm_chat_id"] = confirm_msg.chat_id
            save_data()

    elif awaiting == "ticket_new":
        context.user_data.pop("awaiting", None)
        ticket = await create_ticket(update, context)
        await update.message.reply_text(STR["ticket_created"](ticket["id"]))
        await post_ticket_card(context, ticket, user_obj)
        await forward_to_ticket(update, context, ticket["id"])
        await log_event(context, f"🎫 Ticket #{ticket['id']} opened by {user_obj.id}")

    elif awaiting == "gift_stars_custom_amount":
        context.user_data.pop("awaiting", None)
        if not text.isdigit() or int(text) <= 0:
            await update.message.reply_text("⚠️ " + to_small_caps("please send a valid star number."))
            return
        msg = await send_stars_invoice(context, update.effective_chat.id, int(text))
        _track_ephemeral(context, msg)

    elif awaiting == "gift_upi_amount":
        context.user_data.pop("awaiting", None)
        if not text.isdigit() or int(text) <= 0:
            await update.message.reply_text("⚠️ " + to_small_caps("please send a valid ₹ amount."))
            return
        await start_upi_order(update, context, int(text))

    elif awaiting == "copyright_report_link":
        context.user_data["report_link_draft"] = text
        context.user_data["awaiting"] = "copyright_report_details"
        await update.message.reply_text(
            "Thanks. Now briefly describe your ownership / proof of rights (or paste a link to proof)."
        )

    elif awaiting == "copyright_report_details":
        context.user_data.pop("awaiting", None)
        link = context.user_data.pop("report_link_draft", "")
        report = {
            "id": len(BOT_DATA["copyright_reports"]) + 1,
            "reporter_id": user_obj.id,
            "reporter_username": user_obj.username,
            "link": link,
            "details": text,
            "at": datetime.utcnow().isoformat(),
            "status": "open",
        }
        BOT_DATA["copyright_reports"].append(report)
        save_data()
        await update.message.reply_text(
            "✅ Thanks — your report has been received and will be reviewed and acted upon promptly."
        )

        domain = None
        try:
            from urllib.parse import urlparse
            domain = urlparse(link).netloc or None
        except Exception:
            domain = None

        alert_lines = [
            f"🚫 New copyright report #{report['id']}",
            f"From: {user_obj.id} (@{user_obj.username or 'no username'})",
            f"Link: {link or '(none given)'}",
            f"Details: {text[:500]}",
        ]
        kb_rows = []
        if link:
            kb_rows.append([styled_button("🚫 Block This Link", callback_data=f"adm_block_link:{report['id']}")])
        if domain:
            kb_rows.append([styled_button(f"🚫 Block Domain ({domain})", callback_data=f"adm_block_domain:{report['id']}")])
        kb = InlineKeyboardMarkup(kb_rows) if kb_rows else None

        support_chat_id = BOT_DATA["settings"].get("support_chat_id")
        targets = [support_chat_id] if support_chat_id else BOT_DATA.get("admins", [])
        for target in targets:
            if not target:
                continue
            try:
                await context.bot.send_message(chat_id=target, text="\n".join(alert_lines), reply_markup=kb)
            except Exception:
                pass
        await log_event(context, f"🚫 Copyright report #{report['id']} filed against {link or '(no link)'}")


async def cb_adm_block_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    report_id = int(query.data.split(":", 1)[1])
    report = next((r for r in BOT_DATA["copyright_reports"] if r["id"] == report_id), None)
    if not report or not report.get("link"):
        await query.message.reply_text("⚠️ Report/link not found.")
        return
    link = report["link"]
    if link not in BOT_DATA["blocked_links"]:
        BOT_DATA["blocked_links"].append(link)
    report["status"] = "link_blocked"
    save_data()
    await query.message.reply_text(f"✅ Blocked link: {link}")
    await log_event(context, f"🚫 Admin blocked link: {link}")


async def cb_adm_block_domain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    report_id = int(query.data.split(":", 1)[1])
    report = next((r for r in BOT_DATA["copyright_reports"] if r["id"] == report_id), None)
    if not report or not report.get("link"):
        await query.message.reply_text("⚠️ Report/link not found.")
        return
    try:
        from urllib.parse import urlparse
        domain = urlparse(report["link"]).netloc
    except Exception:
        domain = None
    if not domain:
        await query.message.reply_text("⚠️ Couldn't parse a domain from that link.")
        return
    if domain not in BOT_DATA["blocked_domains"]:
        BOT_DATA["blocked_domains"].append(domain)
    report["status"] = "domain_blocked"
    save_data()
    await query.message.reply_text(f"✅ Blocked domain: {domain}")
    await log_event(context, f"🚫 Admin blocked domain: {domain}")


# ----------------------------------------------------------------------------
# Admin panel — top level (#9 categorized, functional dispatcher — not a
# content menu, since these are actions, not editable copy)
# ----------------------------------------------------------------------------


__all__ = [_n for _n in dir() if not _n.startswith("__")]
