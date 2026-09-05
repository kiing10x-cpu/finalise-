from admin_panel_settings import *


# ---- New-admin access picker: shown right after /add_admin_id is entered ----

async def _render_newadmin_picker(query, context):
    draft = context.user_data.setdefault("newadmin_perms_draft", set())
    new_id = context.user_data.get("newadmin_id_draft")
    text = (
        "➕ " + to_small_caps(f"choose access for admin {new_id}") + "\n\n"
        + to_small_caps("tap a section to toggle it, then save. only what you tick here is what they'll be able to open.") + "\n\n"
        + _perm_summary_text(draft)
    )
    await query.edit_message_text(text, reply_markup=_perm_picker_keyboard(draft, "newadmin_confirm", "newadmin_cancel", "newadmin_perm"))


async def cb_newadmin_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_owner(update.effective_user.id):
        return
    key = query.data.split(":", 1)[1]
    draft = context.user_data.setdefault("newadmin_perms_draft", set())
    draft.symmetric_difference_update({key})
    await _render_newadmin_picker(query, context)


async def cb_newadmin_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_owner(update.effective_user.id):
        return
    context.user_data["newadmin_perms_draft"] = set(ADMIN_PERMISSION_KEYS)
    await _render_newadmin_picker(query, context)


async def cb_newadmin_none(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_owner(update.effective_user.id):
        return
    context.user_data["newadmin_perms_draft"] = set()
    await _render_newadmin_picker(query, context)


async def cb_newadmin_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_owner(update.effective_user.id):
        return
    new_id = context.user_data.pop("newadmin_id_draft", None)
    draft = context.user_data.pop("newadmin_perms_draft", set())
    if new_id is None:
        await query.edit_message_text(to_small_caps("this expired — please try adding the admin again."))
        return
    if new_id not in BOT_DATA["admins"]:
        BOT_DATA["admins"].append(new_id)
    BOT_DATA.setdefault("admin_permissions", {})[str(new_id)] = sorted(draft)
    save_data()
    await query.edit_message_text("✅ " + to_small_caps(f"{new_id} is now an admin.") + "\n\n" + _perm_summary_text(draft))
    await log_event(context, f"👤 Admin added: {new_id} — {len(draft)}/{len(ADMIN_PERMISSION_KEYS)} section(s) (by {update.effective_user.id})")


async def cb_newadmin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("newadmin_id_draft", None)
    context.user_data.pop("newadmin_perms_draft", None)
    await query.edit_message_text(to_small_caps("cancelled — no admin was added."))


# ---- Edit-existing-admin access picker (from Manage Admins ✏️) -------------

async def _render_editperm_picker(query, context):
    draft = context.user_data.setdefault("editperm_draft", set())
    target_id = context.user_data.get("editperm_target_id")
    text = (
        "✏️ " + to_small_caps(f"editing access for admin {target_id}") + "\n\n"
        + to_small_caps("tap a section to toggle it, then save.") + "\n\n"
        + _perm_summary_text(draft)
    )
    await query.edit_message_text(text, reply_markup=_perm_picker_keyboard(draft, "editperm_confirm", "editperm_cancel", "editperm_perm"))


async def cb_admperm_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_owner(update.effective_user.id):
        return
    target_id = int(query.data.split(":", 1)[1])
    context.user_data["editperm_target_id"] = target_id
    context.user_data["editperm_draft"] = get_admin_perms(target_id)
    await _render_editperm_picker(query, context)


async def cb_editperm_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_owner(update.effective_user.id):
        return
    key = query.data.split(":", 1)[1]
    draft = context.user_data.setdefault("editperm_draft", set())
    draft.symmetric_difference_update({key})
    await _render_editperm_picker(query, context)


async def cb_editperm_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_owner(update.effective_user.id):
        return
    context.user_data["editperm_draft"] = set(ADMIN_PERMISSION_KEYS)
    await _render_editperm_picker(query, context)


async def cb_editperm_none(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_owner(update.effective_user.id):
        return
    context.user_data["editperm_draft"] = set()
    await _render_editperm_picker(query, context)


async def cb_editperm_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_owner(update.effective_user.id):
        return
    target_id = context.user_data.pop("editperm_target_id", None)
    draft = context.user_data.pop("editperm_draft", set())
    if target_id is None:
        await query.edit_message_text(to_small_caps("this expired — please try again."))
        return
    BOT_DATA.setdefault("admin_permissions", {})[str(target_id)] = sorted(draft)
    save_data()
    await query.edit_message_text("✅ " + to_small_caps(f"access updated for {target_id}.") + "\n\n" + _perm_summary_text(draft))
    await log_event(context, f"🔧 Admin access updated: {target_id} -> {len(draft)}/{len(ADMIN_PERMISSION_KEYS)} section(s) (by {update.effective_user.id})")


async def cb_editperm_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("editperm_target_id", None)
    context.user_data.pop("editperm_draft", None)
    await query.edit_message_text(to_small_caps("cancelled — no changes made."))


async def cb_help_update_backup_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    is_own = is_owner(update.effective_user.id)
    text = (
        "<blockquote expandable>"
        "<u>📦 " + to_small_caps("update backup — how it works") + "</u>\n\n"
        + to_small_caps("normally, pushing a new bot.py to github wipes the live data — every setting, every menu edit, every saved user — because most free hosts start from a clean, empty disk on every deploy.") + "\n\n"
        "<u>➤ " + to_small_caps("step 1 — export") + "</u>\n"
        + to_small_caps("before you push a code update, run 📦 update backup from the admin panel (or /updatebackup). the bot sends you 2 files:") + "\n"
        "  • <code>" + SEED_SETTINGS_FILE + "</code> — " + to_small_caps("every setting, menu, admin, group, ticket etc. (no users)") + "\n"
        "  • <code>" + SEED_USERS_FILE + "</code> — " + to_small_caps("the full user list") + "\n\n"
        "<u>➤ " + to_small_caps("step 2 — commit") + "</u>\n"
        + to_small_caps("add both files into your github repo, in the same folder as bot.py, using those exact names, then push your updated code.") + "\n\n"
        "<u>➤ " + to_small_caps("step 3 — auto-restore") + "</u>\n"
        + to_small_caps("on the next startup, if the host has no existing data (fresh/wiped disk), the bot automatically reads both files and restores everything by itself — no restore command, no manual upload.") + "\n\n"
        "<u>➤ " + to_small_caps("safety") + "</u>\n"
        + to_small_caps("if the bot already has live data (a host with persistent storage), the seed files are ignored — your current live data is never overwritten automatically.")
        + ("\n\n🔒 " + to_small_caps("only the owner can actually run the export (📦 update backup / /updatebackup) — this help screen is visible to every admin.") if not is_own else "")
        + "</blockquote>"
    )
    kb = InlineKeyboardMarkup(
        [[styled_button("🔙 Back", callback_data="nav:help_admin")]]
        if not is_own else
        [[styled_button("📦 Run Update Backup Now", callback_data="adm_update_backup_run")],
         [styled_button("🔙 Back", callback_data="nav:help_admin")]]
    )
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)


async def cb_adm_restore_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_owner(update.effective_user.id):
        await query.answer("🔒 " + to_small_caps("only the owner can restore a backup."), show_alert=True)
        return
    await query.message.reply_text(
        to_small_caps("📥 restore backup") + "\n\n"
        + to_small_caps("send me the .json or .json.enc backup file directly in this dm (the one exported via /database). ")
        + to_small_caps("an automatic backup of the current data will be taken first, then a confirmation screen will be shown.") + "\n\n"
        + (to_small_caps("🔒 encrypted (.json.enc) backups only restore on this same bot instance, unless you copied backup.key over first.") if BACKUP_ENCRYPTION_AVAILABLE else "")
    )


# ---- Danger Zone --------------------------------------------------------------

async def _render_adm_danger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    kb = InlineKeyboardMarkup(
        [
            [styled_button("🧹 Clear Broadcast Log", callback_data="adm_clear_bclog")],
            [styled_button("🧹 Delete All Bot Messages In This Chat", callback_data="adm_delete_chat_msgs")],
            [styled_button("🔄 Reset Menus to Default", callback_data="adm_reset_menus_confirm")],
            [styled_button("❌ Reset ALL Bot Data", callback_data="adm_reset_confirm")],
            back_row(),
            home_row(),
        ]
    )
    await query.edit_message_text("🛑 Danger Zone\n(Ye actions destructive hain.)", reply_markup=kb)


# ---- Premium / UPI / Developer / Support / Tickets --

def _build_adm_premium_view():
    s = BOT_DATA["settings"]
    plans = s.get("premium_plans", [])
    premium_count = sum(1 for uid in BOT_DATA["users"] if is_premium_active(uid))
    lines = [
        f"💎 Premium\n\nMaster switch: {'✅ ON' if s.get('premium_enabled') else '❌ OFF'}",
        f"Daily free limit: {s.get('daily_limit', 20)}",
        f"👥 Active premium users: {premium_count}",
        "",
    ]
    # Main controls stay at the top; every ➕ Add action is grouped at the
    # bottom so the management flow is cleaner on mobile.
    kb_rows = [
        [styled_button(toggle_label("🔀 Master Switch", s.get('premium_enabled')),
                        callback_data="stgl:premium_enabled:adm_premium")],
        [styled_button("✏️ Set Daily Limit", callback_data="adm_set_dailylimit")],
        [styled_button("👥 See Premium Users", callback_data="adm_premium_users")],
        [styled_button("💳 UPI Settings", callback_data="adm_upi")],
    ]
    if not plans:
        lines.append("No plans yet — tap ➕ Add Plan below.")
    else:
        lines.append("Your plans (tap a plan's row buttons to toggle/delete):")
        for p in plans:
            state = "🟢 ON" if p.get("enabled") else "🔴 OFF"
            price_bits = []
            if p.get("price_inr"):
                price_bits.append(f"₹{p['price_inr']}")
            if p.get("price_stars"):
                price_bits.append(f"{p['price_stars']}⭐")
            price_str = " / ".join(price_bits) if price_bits else "(no price set)"
            lines.append(f"• {p['name']} — {price_str} — {p.get('days', 30)}d — {state}")
            kb_rows.append([
                styled_button(f"{'🔴 Turn Off' if p.get('enabled') else '🟢 Turn On'} · {p['name']}",
                              callback_data=f"adm_plan_toggle:{p['id']}",
                              style="success" if p.get("enabled") else "danger"),
                styled_button("🗑", callback_data=f"adm_plan_del:{p['id']}", style="danger"),
            ])
    # Keep all Add actions together at the bottom.
    kb_rows.append([styled_button("➕ Add Premium User (By ID)", callback_data="adm_premium_grant")])
    kb_rows.append([styled_button("➕ Add Plan", callback_data="adm_plan_add")])
    kb_rows.append(back_row())
    kb_rows.append(home_row())
    text = "\n".join(lines) + (
        "\n\nWhen master switch is ON and a plan is toggled ON, that plan shows up "
        "immediately to every user in the 🎁 gift/upgrade menu."
    )
    return text, InlineKeyboardMarkup(kb_rows)


async def _render_adm_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    text, kb = _build_adm_premium_view()
    await query.edit_message_text(text, reply_markup=kb)


async def cb_adm_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _render_adm_premium(update, context)


# ---- See Premium Users / manually grant premium by user ID --------------

async def cb_adm_premium_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """👥 See Premium Users — lists every user currently marked premium,
    with days remaining (or 'no expiry' for lifetime grants)."""
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    rows = []
    now = datetime.utcnow()
    for uid, u in BOT_DATA["users"].items():
        if not is_premium_active(uid):
            continue
        name = u.get("name") or f"User {uid}"
        exp = u.get("plan_expires_at")
        if exp:
            try:
                remaining = (datetime.fromisoformat(exp) - now).days
                when = f"{remaining}d left" if remaining >= 0 else "expiring"
            except Exception:
                when = "unknown expiry"
        else:
            when = "no expiry"
        rows.append(f"• {name} (`{uid}`) — {when}")
    if rows:
        text = "👥 " + to_small_caps("premium users") + f" ({len(rows)})\n\n" + "\n".join(rows[:60])
        if len(rows) > 60:
            text += f"\n… and {len(rows) - 60} more"
    else:
        text = "👥 " + to_small_caps("no premium users right now.")
    kb = InlineKeyboardMarkup([back_row("adm_premium")])
    await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")


async def cb_adm_premium_grant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """➕ Add Premium User (by ID) — admin types a Telegram user ID (and
    optionally how many days) and premium unlocks automatically, no
    payment/plan flow needed. Same manual-override tool admins expect for
    comps, testers, or fixing a missed payment."""
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    remember_panel_message(context, query, "premium")
    context.user_data["awaiting"] = "premium_grant_userid"
    await query.message.reply_text(
        "👤 Send the user's Telegram ID to unlock Premium for.\n"
        "Optionally add days after a space (default 30) — e.g. `123456789 90`.",
        parse_mode="Markdown",
    )


# ---- Premium plan CRUD (add / toggle / delete) ---------------------------------

async def cb_adm_plan_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    remember_panel_message(context, query, "premium")
    context.user_data["new_plan"] = {}
    context.user_data["awaiting"] = "plan_step_name"
    await query.message.reply_text(
        to_small_caps("➕ new plan — step 1/4") + "\n" + to_small_caps("send the plan name (e.g. 'monthly', 'weekly pro').")
    )


async def cb_adm_plan_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = query.data.split(":", 1)[1]
    for p in BOT_DATA["settings"].get("premium_plans", []):
        if p["id"] == pid:
            p["enabled"] = not p.get("enabled")
            save_data()
            await log_event(context, f"💎 Plan '{p['name']}' toggled {'✅ ON' if p['enabled'] else '❌ OFF'} by {update.effective_user.id}")
            break
    await _render_adm_premium(update, context)


async def cb_adm_plan_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = query.data.split(":", 1)[1]
    plans = BOT_DATA["settings"].get("premium_plans", [])
    BOT_DATA["settings"]["premium_plans"] = [p for p in plans if p["id"] != pid]
    save_data()
    await _render_adm_premium(update, context)


async def cb_adm_set_dailylimit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    remember_panel_message(context, query, "premium")
    context.user_data["awaiting"] = "daily_limit"
    await query.message.reply_text(to_small_caps("send the new daily free-download limit (a number)."))


def _build_adm_upi_view():
    upi = BOT_DATA["settings"].get("upi_id")
    kb = InlineKeyboardMarkup([
        [styled_button("✏️ Set UPI ID", callback_data="adm_upi_set")],
        [styled_button("❌ Clear", callback_data="adm_upi_clear")],
        back_row("adm_premium"), home_row(),
    ])
    return f"💳 UPI Settings\n\nCurrent: {upi or '(not set)'}", kb


async def _render_adm_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    text, kb = _build_adm_upi_view()
    await query.edit_message_text(text, reply_markup=kb)


async def cb_adm_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _render_adm_upi(update, context)


async def cb_adm_upi_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    remember_panel_message(context, query, "upi")
    context.user_data["awaiting"] = "upi_id"
    await query.message.reply_text(to_small_caps("send the upi id (e.g. name@bank)."))


async def cb_adm_upi_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    BOT_DATA["settings"]["upi_id"] = None
    save_data()
    await query.edit_message_text("✅ UPI ID cleared.", reply_markup=InlineKeyboardMarkup([back_row()]))


def _build_adm_devsettings_view():
    s = BOT_DATA["settings"]
    dev_id = s.get("developer_id")
    dev_link = s.get("developer_link")
    current = f"@{dev_link.rstrip('/').rsplit('/', 1)[-1]}" if dev_link else (str(dev_id) if dev_id else "(not set)")
    text = (
        "👨‍💻 Developer Settings\n\n"
        f"Current: {current}\n\n"
        "Set by numeric user ID or by @username — either works."
    )
    kb = InlineKeyboardMarkup([
        [styled_button("✏️ Set Developer (ID or @username)", callback_data="adm_dev_id")],
        [styled_button("🔗 Set Custom Link (advanced)", callback_data="adm_dev_link")],
        back_row(), home_row(),
    ])
    return text, kb


async def _render_adm_devsettings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    text, kb = _build_adm_devsettings_view()
    await query.edit_message_text(text, reply_markup=kb)


async def cb_adm_devsettings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _render_adm_devsettings(update, context)


async def cb_adm_dev_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    remember_panel_message(context, query, "devsettings")
    context.user_data["awaiting"] = "developer_id"
    await query.message.reply_text(
        to_small_caps("send the developer's numeric user id, OR their @username — either works.")
    )


async def cb_adm_dev_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    remember_panel_message(context, query, "devsettings")
    context.user_data["awaiting"] = "developer_link"
    await query.message.reply_text(to_small_caps("send the t.me/username link (or type 'clear' to remove it)."))


def _build_adm_support_settings_view():
    gid = BOT_DATA["settings"].get("admin_group_id")
    kb = InlineKeyboardMarkup([
        [styled_button("✏️ Set Ticket Group", callback_data="adm_group_set")],
        back_row(), home_row(),
    ])
    return f"🎧 Support Settings\n\nTicket group: {gid or '(not set — falls back to admin DMs)'}", kb


async def _render_adm_support_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    text, kb = _build_adm_support_settings_view()
    await query.edit_message_text(text, reply_markup=kb)


async def cb_adm_support_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _render_adm_support_settings(update, context)


async def cb_adm_group_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    remember_panel_message(context, query, "support_settings")
    context.user_data["awaiting"] = "admin_group_id"
    await query.message.reply_text(
        "Forward any message from the ticket group here (bot must be admin there), "
        "or type its numeric ID (-100...)."
    )


async def _render_adm_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    tickets = list(BOT_DATA["tickets"].values())
    open_n = sum(1 for t in tickets if t["status"] == "open")
    lines = [f"🎫 Tickets — {open_n} open / {len(tickets)} total\n"]
    for t in tickets[-15:]:
        icon = "🟢" if t["status"] == "open" else "🔴"
        lines.append(f"#{t['id']} — user {t['user_id']} — {icon} {t['status']}")
    kb = InlineKeyboardMarkup([back_row(), home_row()])
    await query.edit_message_text("\n".join(lines), reply_markup=kb)


async def cb_adm_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _render_adm_tickets(update, context)


async def cb_adm_danger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _render_adm_danger(update, context)


async def cb_adm_delete_chat_msgs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """#5 — wipes only the chat the admin runs this from (Telegram allows
    deleting messages up to 48h old; older ones fail silently)."""
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    ids = BOT_DATA.get("sent_messages", {}).pop(str(chat_id), [])
    save_data()
    deleted = 0
    for mid in ids:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=mid)
            deleted += 1
        except Exception:
            pass
    try:
        await query.message.delete()
    except Exception:
        pass
    await context.bot.send_message(chat_id, f"✅ Deleted {deleted}/{len(ids)} tracked bot messages in this chat.")


async def cb_adm_clear_bclog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    BOT_DATA["broadcast_log"] = []
    save_data()
    await query.message.reply_text(to_small_caps("✅ broadcast log cleared."))


async def cb_adm_reset_menus_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup(
        [[styled_button(to_small_caps("⚠️ yes, reset"), callback_data="adm_reset_menus_do"),
          styled_button("Cancel", callback_data="adm_danger")]]
    )
    await query.edit_message_text("⚠️ Sab menus (text/image/buttons) default pe reset ho jayenge. Pakka?", reply_markup=kb)


async def cb_adm_reset_menus_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    make_backup_snapshot(reason="pre_menu_reset")
    BOT_DATA["menus"] = json.loads(json.dumps(DEFAULT_MENUS))
    save_data()
    await query.edit_message_text("✅ Menus default pe reset ho gaye.")


async def cb_adm_reset_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup(
        [[styled_button(to_small_caps("⚠️ yes, reset everything"), callback_data="adm_reset_do"),
          styled_button("Cancel", callback_data="adm_danger")]]
    )
    await query.edit_message_text(
        to_small_caps("⚠️ are you sure? this will delete ALL bot data — users, settings, menus, everything.") + "\n" + to_small_caps("an auto-backup will be taken first."),
        reply_markup=kb,
    )


RESET_ALL_PASSCODE = "03"


async def cb_adm_reset_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """A destructive, irreversible action gets one extra layer beyond the
    button confirm — a short passcode the admin has to type, so a stray or
    mis-tapped click can never wipe the bot on its own."""
    query = update.callback_query
    await query.answer()
    context.user_data["awaiting"] = "reset_all_passcode"
    await query.message.reply_text(
        "🔐 " + to_small_caps("last step — send the reset passcode to confirm.")
    )


async def _do_reset_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_DATA
    make_backup_snapshot(reason="pre_reset")
    BOT_DATA = json.loads(json.dumps(DEFAULT_DATA))
    save_data()
    await update.message.reply_text(to_small_caps("✅ reset complete. the previous data is safely stored in a backup."))


# ----------------------------------------------------------------------------


__all__ = [_n for _n in dir() if not _n.startswith("__")]
