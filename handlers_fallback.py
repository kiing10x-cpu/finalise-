from export_backup import *


async def cmd_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Friendly fallback for every unregistered /unknown command."""
    user = update.effective_user
    if user and is_blocked(user.id) and not is_admin(user.id):
        return
    if user and BOT_DATA["settings"].get("maintenance") and not is_admin(user.id):
        await send_maintenance_notice(context, update.effective_chat.id)
        return
    text = (
        "⚠️ <b>" + to_small_caps("unknown command") + "</b>\n\n"
        "<blockquote>"
        + to_small_caps("that command doesn't exist or isn't formatted correctly.") + "\n\n"
        + to_small_caps("tap the button below (or send /start) to go back to the main menu.")
        + "</blockquote>"
    )
    kb = InlineKeyboardMarkup([[styled_button("🚀 /start", callback_data="go_start")]])
    sent = await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
    # Self-cleaning: this is just noise once the user has moved on, so it
    # always disappears shortly after — independent of the global
    # auto-delete setting (which may be 0 / off for real menu content).
    await schedule_delete(context, sent.chat_id, sent.message_id, 15)


async def cb_go_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """One-tap '🚀 /start' button attached to the unknown-command fallback,
    so a confused user doesn't have to type the command themselves."""
    query = update.callback_query
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        pass
    chat_id = update.effective_chat.id
    uid = str(update.effective_user.id)
    if not BOT_DATA["users"].get(uid, {}).get("lang_prompted"):
        BOT_DATA["users"].setdefault(uid, {})["lang_prompted"] = True
        save_data()
        await _send_language_picker(context, chat_id)
        return
    sent = await show_post_onboarding(context, chat_id, uid)
    await track_and_refresh_panel(context, chat_id, "start", sent)


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command equivalent of the Broadcast Centre's New Broadcast button."""
    if not is_admin(update.effective_user.id):
        return
    context.user_data["awaiting"] = "broadcast_content"
    await update.message.reply_text(
        to_small_caps("📢 send your broadcast now") + "\n"
        + to_small_caps("text, photo or video — one single message") + "\n\n"
        + to_small_caps("it will be delivered to every registered user and this admin chat, respecting your forward-lock setting")
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """#13 — escape hatch out of any stuck admin/user text-input flow."""
    for key in (
        "awaiting", "btn_flow", "style_source_text", "style_target",
        "message_target", "report_link_draft", "owner_contact_label_draft",
        "autoreply_key_draft",
    ):
        context.user_data.pop(key, None)
    await update.message.reply_text("✅ Cancelled. Any pending flow has been cleared.")


async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """#13 — catch-all so one bad update can't silently kill processing, and
    every failure is visible from the admin 'Recent Errors' screen / logger channel."""
    log.exception("Unhandled error", exc_info=context.error)
    update_type = type(update).__name__ if update else "unknown"
    err_text = str(context.error)
    # A duplicate-instance getUpdates conflict is common and has a very
    # different (and non-code) fix from a generic bug, so it gets its own
    # Activity Log category instead of being lumped under "unhandled".
    kind = "conflict" if "Conflict" in err_text and "getUpdates" in err_text else "unhandled"
    log_error(kind, f"[{update_type}] {err_text}")
    save_data()
    try:
        await log_event(context, f"🐞 Error: {str(context.error)[:300]}")
    except Exception:
        pass

    # Urgent/critical errors go straight to every admin's DM, unconditionally
    # — this does NOT check the Logger Channel toggle (log_event above does),
    # so an admin who never bothered configuring a logger channel still finds
    # out immediately when something actually breaks, instead of it only
    # showing up next time they happen to open Activity Log.
    if kind == "unhandled":
        try:
            await dm_all_admins(
                context,
                "🚨 " + to_title_small_caps("Urgent Alert") + "\n\n"
                + f"{to_title_small_caps('Type')} : {html.escape(update_type)}\n"
                + f"{to_title_small_caps('Error')} : {html.escape(err_text[:300])}",
                parse_mode="HTML",
            )
        except Exception:
            pass


SCREEN_RENDERERS.update(
    {
        "adm_home": _render_adm_home,
        "adm_stats": _render_adm_stats,
        "adm_users": _render_adm_users,
        "adm_live": _render_adm_live,
        "adm_broadcast": _render_adm_broadcast,
        "adm_bc_delmenu": _render_adm_bc_delmenu,
        "adm_menu_ui": _render_adm_menu_ui,
        "adm_settings": _render_adm_settings,
        "adm_maintenance": _render_adm_maintenance,
        "adm_danger": _render_adm_danger,
        "adm_owner_contact": _render_adm_owner_contact,
        "adm_logger_channel": _render_adm_logger_channel,
        "adm_activity_channel": _render_adm_activity_channel,
        "adm_force_join": _render_adm_force_join,
        "adm_premium": _render_adm_premium,
        "adm_upi": _render_adm_upi,
        "adm_devsettings": _render_adm_devsettings,
        "adm_support_settings": _render_adm_support_settings,
        "adm_tickets": _render_adm_tickets,
        "adm_leaderboard": _render_adm_leaderboard,
        "adm_share": _render_adm_share,
        "adm_cmdtest": _render_adm_cmdtest,
        "adm_activity": _render_adm_activity,
        "adm_selftest": _render_adm_selftest,
        "adm_notifications": _render_adm_notifications,
        "ai_check": _render_ai_check,
    }
)


# ----------------------------------------------------------------------------
# 🧩 Feature Plugins — drop a .py file into plugins/ and its features load
# straight into the bot, without editing bot.py at all.
#
# HOW TO WRITE A PLUGIN (share this with whoever is building the feature):
#   1. Create a new file, e.g. plugins/my_feature.py
#   2. It must define one function: `def register(app):`
#   3. Inside register(), add handlers exactly like in bot.py, e.g.:
#
#        from __main__ import (
#            styled_button, is_premium_active, is_admin, to_small_caps,
#            require_premium, BOT_DATA, log_error,
#        )
#        from telegram.ext import CommandHandler
#
#        async def my_cool_feature(update, context):
#            await update.message.reply_text("Hello from a plugin!")
#
#        def register(app):
#            app.add_handler(CommandHandler("mycommand", my_cool_feature))
#
#   4. To make a feature Premium-only, wrap the handler with the
#      require_premium() decorator (see below) — it automatically blocks
#      non-premium users and shows them the upgrade menu, same as every
#      built-in premium feature.
#   5. Save the file into the bot's plugins/ folder and RESTART the bot —
#      plugin files are only scanned once, at startup, so a running bot
#      won't pick up a newly uploaded file until it's restarted.
#
# A broken plugin (syntax error, missing register(), exception while
# loading) is skipped and logged to the Activity Log — it can never crash
# the rest of the bot or stop other plugins from loading.
# ----------------------------------------------------------------------------


__all__ = [_n for _n in dir() if not _n.startswith("__")]
