from handlers_input import *


def get_admin_panel_title() -> str:
    """v10 — sourced from BOT_DATA['menus']['admin'] so the admin can edit
    this banner from Menu & UI too, falling back to the original default."""
    menu = BOT_DATA["menus"].get("admin", {})
    return menu.get("text") or DEFAULT_MENUS["admin"]["text"]


def admin_panel_keyboard(user_id: int = None):
    """Buttons are filtered per-caller: the owner sees everything; an admin
    only sees the sections they've actually been granted (see
    ADMIN_PERMISSIONS / get_admin_perms). 📦 Update Backup and ☠️ Danger
    Zone are owner-only and are never shown to admins at all, no matter
    what permissions they hold. Passing user_id=None shows every button
    (kept for any legacy caller that hasn't been updated to pass it)."""
    perms = get_admin_perms(user_id) if user_id is not None else set(ADMIN_PERMISSION_KEYS)

    def allowed(perm_key):
        return user_id is None or perm_key in perms

    all_buttons = [
        ("premium", styled_button("💎 Premium", callback_data="adm_premium")),
        ("leaderboard", styled_button("🏆 Leaderboard", callback_data="adm_leaderboard")),
        ("share", styled_button("🎚 Share Settings", callback_data="adm_share")),
        ("broadcast", styled_button("📢 Broadcast", callback_data="adm_broadcast")),
        ("devsettings", styled_button("😎 Developer Settings", callback_data="adm_devsettings")),
        ("support_settings", styled_button("🛠 Support Settings", callback_data="adm_support_settings")),
        ("tickets", styled_button("📬 Tickets", callback_data="adm_tickets")),
        ("stats", styled_button("📊 Statistics", callback_data="adm_stats")),
        ("users", styled_button("👥 Users & Groups", callback_data="adm_users")),
        ("live", styled_button("🍃 Live User Feed", callback_data="adm_live")),
        ("menu_ui", styled_button("🪄 Menu & UI", callback_data="adm_menu_ui")),
        ("cmdtest", styled_button("📟 Test Commands", callback_data="adm_cmdtest")),
        ("ai_check", styled_button("🤖 AI Check", callback_data="ai_check")),
        ("notifications", styled_button("🔔 Notifications", callback_data="adm_notifications")),
        ("activity", styled_button("📜 Activity Log", callback_data="adm_activity")),
        ("selftest", styled_button("🗽 Self-Test", callback_data="adm_selftest")),
        ("plugins", styled_button("🧩 Feature Plugins", callback_data="adm_plugins")),
        ("settings", styled_button("⚙️ Settings", callback_data="adm_settings")),
    ]

    rows, row = [], []
    for perm_key, btn in all_buttons:
        if not allowed(perm_key):
            continue
        row.append(btn)
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    # Owner-only, always — never granted to admins via permissions.
    if user_id is None or is_owner(user_id):
        rows.append([styled_button("🍭 Update Backup", callback_data="adm_update_backup"),
                     styled_button("🚧 Danger Zone", callback_data="adm_danger")])

    if not rows:
        rows = [[styled_button("ℹ️ No Sections Granted Yet", callback_data="adm_home")]]

    return InlineKeyboardMarkup(rows)


def back_row(cb="adm_back", label="🔙 Back"):
    # v10 — colorless, same as every other Admin Panel button.
    return [styled_button(label, callback_data=cb)]


def home_row():
    """#3 — extra row shown only on top-level category screens, alongside
    the regular (stack-aware) 🔙 Back row.
    v10 — colorless, same as every other Admin Panel button."""
    return [styled_button("🏠 Admin Home", callback_data="adm_home")]


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await _clear_ephemeral(context, update.effective_chat.id)
    context.user_data["adm_nav_stack"] = ["adm_home"]
    sent = await update.message.reply_text(get_admin_panel_title(), reply_markup=admin_panel_keyboard(update.effective_user.id))
    await track_and_refresh_panel(context, update.effective_chat.id, "admin", sent)
    await delete_incoming(update)


async def _render_adm_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text(get_admin_panel_title(), reply_markup=admin_panel_keyboard(update.effective_user.id))


async def cb_adm_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _clear_ephemeral(context, update.effective_chat.id)
    context.user_data.pop("awaiting", None)
    context.user_data["adm_nav_stack"] = ["adm_home"]
    await _render_adm_home(update, context)


# ---- Activity log + self-test ---------------------------------------

async def _render_adm_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    entries = BOT_DATA.get("error_log", [])[-10:][::-1]
    if not entries:
        body = "✅ " + to_small_caps("activity log") + "\n\n" + to_small_caps("all clear — nothing to report.")
    else:
        # Group consecutive display by kind so repeats of the same issue
        # (e.g. force-join misconfigured) don't push everything else off
        # screen, and each entry explains what happened, why, and how to
        # fix it — not just a raw exception string.
        blocks = []
        fix_rows = []
        for n, e in enumerate(entries, 1):
            kind = e.get("kind", "unhandled")
            label, why, fix = ERROR_KIND_INFO.get(kind, ERROR_KIND_INFO["unhandled"])
            when = iso_to_ist_str(e.get("time"), "%Y-%m-%d %H:%M")
            detail = e.get("detail") or e.get("error") or ""
            blocks.append(
                f"{n}. {label}  •  {when} IST\n"
                f"What: {why}\n"
                f"Fix: {fix}\n"
                f"Detail: {detail[:180]}"
            )
            if e.get("id") is not None:
                fix_rows.append([styled_button(
                    f"🛠 Fix Now #{n} — {label}", callback_data=f"adm_fix:{e['id']}"
                )])
        body = (
            "📋 " + to_small_caps("activity log") + f" — {to_small_caps('last')} {len(entries)}\n\n"
            + "\n\n".join(blocks)
        )
    kb_rows = list(fix_rows) if entries else []
    kb_rows.append([styled_button("🗑 Clear Log", callback_data="adm_clear_activity")])
    kb_rows.append(back_row())
    kb_rows.append(home_row())
    kb = InlineKeyboardMarkup(kb_rows)
    await query.edit_message_text(body, reply_markup=kb)


async def cb_adm_fix_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🛠 Fix Now — attempts a real, automatic remediation for the error
    kinds that actually have one (re-checks force-join channels live,
    forces a fresh MongoDB reconnect attempt). For kinds that have no code-
    level fix (a duplicate instance, a one-off download failure, a bug that
    needs a real code change), it explains exactly why and what a human
    needs to do instead — it never just claims success."""
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer()
        return
    try:
        err_id = int(query.data.split(":", 1)[1])
    except (IndexError, ValueError):
        await query.answer("⚠️ " + to_small_caps("bad fix reference."), show_alert=True)
        return
    entry = next((e for e in BOT_DATA.get("error_log", []) if e.get("id") == err_id), None)
    if entry is None:
        await query.answer("⚠️ " + to_small_caps("that log entry is gone — log was cleared."), show_alert=True)
        return
    kind = entry.get("kind", "unhandled")
    await query.answer("🛠 " + to_small_caps("running fix..."))

    if kind == "force_join":
        targets = _force_join_targets()
        if not targets:
            result = "ℹ️ " + to_small_caps("no force-join channel is configured — nothing to check.")
        else:
            lines = ["🔎 " + to_small_caps("re-checking force-join channel(s) now:")]
            for t in targets:
                chat_id = t.get("chat_id")
                if not chat_id:
                    lines.append(f"• {t.get('link')} — " + to_small_caps("link-only target, can't be auto-verified."))
                    continue
                try:
                    me = await context.bot.get_me()
                    member = await context.bot.get_chat_member(chat_id=chat_id, user_id=me.id)
                    if member.status in ("administrator", "creator"):
                        lines.append(f"• {chat_id} — ✅ " + to_small_caps("bot is admin here, looks correctly configured."))
                    else:
                        lines.append(f"• {chat_id} — ⚠️ " + to_small_caps(f"bot can see this chat but is only '{member.status}' — make it admin."))
                except Exception as e:
                    lines.append(f"• {chat_id} — ❌ " + to_small_caps(f"still failing: {e}"))
            result = "\n".join(lines)

    elif kind == "mongo":
        col = get_mongo_collection(force=True)  # force a fresh connection attempt
        if col is not None:
            result = "✅ " + to_small_caps("reconnected to mongodb successfully.")
        else:
            result = "❌ " + to_small_caps(f"still can't connect — {_mongo_last_error or 'unknown error'}")

    elif kind == "conflict":
        result = (
            "ℹ️ " + to_small_caps("this can't be fixed from inside this process.") + "\n"
            + to_small_caps("make sure no other copy of this bot (old deploy, second terminal, another server) is running with the same bot token, then stop it.")
        )

    else:
        result = "ℹ️ " + to_small_caps(f"'{kind}' has no automatic fix — see the fix hint above for the manual step.")

    try:
        await query.message.reply_text(result)
    except Exception:
        pass


async def cb_adm_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    await _render_adm_activity(update, context)


async def cb_adm_clear_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    BOT_DATA["error_log"] = []
    save_data()
    await _render_adm_activity(update, context)


async def _render_adm_selftest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.edit_message_text("🧪 " + to_small_caps("running self-test..."))
    results = []
    results.append(("Bot token", "✅ OK" if BOT_TOKEN else "❌ missing"))
    try:
        me = await context.bot.get_me()
        results.append(("Telegram API", f"✅ OK (@{me.username})"))
    except Exception as e:
        results.append(("Telegram API", f"❌ {e}"))
    results.append(("ffmpeg", "✅ found" if FFMPEG_AVAILABLE else "⚠️ not found (merge downloads may fail)"))
    results.append(("ffprobe", "✅ found" if FFPROBE_AVAILABLE else "ℹ️ not found (not needed — audio uses direct ffmpeg)"))
    try:
        import yt_dlp as _yd
        results.append(("yt-dlp", f"✅ v{_yd.version.__version__}"))
    except Exception as e:
        results.append(("yt-dlp", f"❌ {e}"))
    results.append(("Download dir", "✅ writable" if os.access(DOWNLOAD_DIR, os.W_OK) else "❌ not writable"))
    body = "🧪 " + to_small_caps("self-test results") + "\n\n" + "\n".join(f"{k}: {v}" for k, v in results)
    await query.edit_message_text(body, reply_markup=InlineKeyboardMarkup([back_row(), home_row()]))


async def cb_adm_selftest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    await _render_adm_selftest(update, context)


# ---- 🧪 Test Commands — run/check every bot command straight from the panel --
# One small screen, one button per command the bot supports. Tapping a
# button runs that command's real, safe logic and drops the actual result
# right into this chat — no need to leave the admin panel or type anything
# to verify a command still works. Commands that need an argument (like
# /block <id>) show their usage instead of guessing one; owner-only
# commands only actually run for the owner.
COMMAND_TEST_LIST = [
    ("start", "🚀 /start"),
    ("help", "❓ /help"),
    ("language", "🌐 /language"),
    ("admin", "🛠 /admin"),
    ("ping", "🏓 /ping"),
    ("health", "🩺 /health"),
    ("dbstatus", "🗄 /dbstatus"),
    ("database", "💾 /database"),
    ("exportusers", "📤 /exportusers"),
    ("exportpdf", "📊 /exportpdf"),
    ("export", "📦 /export"),
    ("block", "🚫 /block"),
    ("unblock", "✅ /unblock"),
    ("cancel", "🧹 /cancel"),
]


def _cmdtest_kb() -> InlineKeyboardMarkup:
    rows, row = [], []
    for key, label in COMMAND_TEST_LIST:
        row.append(styled_button(label, callback_data=f"run_cmd:{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(back_row())
    rows.append(home_row())
    return InlineKeyboardMarkup(rows)


async def _render_adm_cmdtest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    body = (
        "🧪 " + to_small_caps("test commands") + "\n\n"
        + to_small_caps("tap any command below to run/check it right now — the real result is sent here, exactly like typing it.") + "\n\n"
        + to_small_caps("owner-only commands only actually run for the owner; /block and /unblock need an argument, so they just show their usage.")
    )
    await query.edit_message_text(body, reply_markup=_cmdtest_kb())


async def cb_adm_cmdtest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    await _render_adm_cmdtest(update, context)


async def cb_run_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    admin_id = update.effective_user.id
    if not is_admin(admin_id):
        await query.answer()
        return
    key = query.data.split(":", 1)[1]
    chat_id = update.effective_chat.id

    # Auto-clean the Test Commands screen: delete whatever result the last
    # tap here left behind before running a new one, so repeatedly tapping
    # through commands doesn't fill the chat with old test output.
    for old_mid in context.user_data.get("last_test_msg_ids", []):
        try:
            await context.bot.delete_message(chat_id, old_mid)
        except Exception:
            pass
    context.user_data["last_test_msg_ids"] = []

    async def send(text, **kwargs):
        sent = await context.bot.send_message(chat_id, text, **kwargs)
        context.user_data.setdefault("last_test_msg_ids", []).append(sent.message_id)
        return sent

    async def track(sent_msg):
        """For calls that send via context.bot directly (documents, etc.)
        instead of the send() helper above — still gets cleaned up next run."""
        if sent_msg is not None:
            context.user_data.setdefault("last_test_msg_ids", []).append(sent_msg.message_id)
        return sent_msg

    try:
        if key == "start":
            await query.answer("✅ " + to_small_caps("running /start..."))
            await track(await render_menu(context, chat_id, "start"))

        elif key == "help":
            await query.answer("✅ " + to_small_caps("running /help..."))
            await track(await render_menu(context, chat_id, "help_admin" if is_admin(admin_id) else "help_user"))

        elif key == "language":
            await query.answer("✅ " + to_small_caps("running /language..."))
            cur_lang = BOT_DATA["users"].get(str(admin_id), {}).get("lang") or "en"
            await send("🌐 " + to_small_caps("choose a language:"), reply_markup=build_language_keyboard(cur_lang))

        elif key == "admin":
            await query.answer("✅ " + to_small_caps("running /admin..."))
            await send(get_admin_panel_title(), reply_markup=admin_panel_keyboard(admin_id))

        elif key == "ping":
            # Same live status data/format as the real /ping command.
            await query.answer()
            t0 = time.monotonic()
            msg = await context.bot.send_message(chat_id, "🏓 " + to_title_small_caps("Pong!"))
            await track(msg)
            ms = int((time.monotonic() - t0) * 1000)
            backend = "MongoDB" if get_mongo_collection() is not None else "Local JSON File"
            lines = [
                f"↬ {to_title_small_caps('Uptime')} : {human_uptime_full()}",
                f"↬ {to_title_small_caps('Storage')} : {to_title_small_caps(backend)}",
                f"↬ {to_title_small_caps('Server Time')} : {now_ist_str('%d %b %Y, %H:%M:%S')} IST",
            ]
            await msg.edit_text(
                f"🏓 <b>{to_title_small_caps('Pong!')}</b> {ms}ms\n\n<blockquote>{html.escape(chr(10).join(lines))}</blockquote>",
                parse_mode="HTML",
            )

        elif key == "health":
            await query.answer()
            await send(build_health_text())

        elif key == "dbstatus":
            if not is_owner(admin_id):
                await query.answer("🔒 " + to_small_caps("owner only."), show_alert=True)
            else:
                await query.answer()
                col = get_mongo_collection()
                if col is not None:
                    text = "✅ MongoDB: connected"
                elif MONGO_URI:
                    text = f"❌ MongoDB: not connected\nReason: {_mongo_last_error}"
                else:
                    text = "ℹ️ MongoDB not configured — using local JSON file."
                text += f"\n\nUsers: {len(BOT_DATA['users'])} | Groups: {len(BOT_DATA['groups'])} | Admins: {len(BOT_DATA['admins'])}"
                await send(text)

        elif key == "database":
            if not is_owner(admin_id):
                await query.answer("🔒 " + to_small_caps("owner only."), show_alert=True)
            else:
                await query.answer("✅ " + to_small_caps("building backup..."))
                raw = json.dumps(BOT_DATA, ensure_ascii=False, indent=2).encode("utf-8")
                payload, encrypted = encrypt_backup_bytes(raw)
                filename = "bot_data_backup.json.enc" if encrypted else "bot_data_backup.json"
                path = os.path.join(tempfile.gettempdir(), f"bot_data_export_{int(time.time())}_{filename}")
                with open(path, "wb") as f:
                    f.write(payload)
                with open(path, "rb") as f:
                    doc = await context.bot.send_document(chat_id, document=f, filename=filename)
                await track(doc)
                os.remove(path)

        elif key == "exportusers":
            if not is_owner(admin_id):
                await query.answer("🔒 " + to_small_caps("owner only."), show_alert=True)
            else:
                await query.answer("✅ " + to_small_caps("building csv..."))
                path = os.path.join(tempfile.gettempdir(), f"users_export_{int(time.time())}.csv")
                with open(path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["user_id", "name", "username", "joined", "last_active"])
                    for uid, info in BOT_DATA["users"].items():
                        writer.writerow([uid, info.get("name"), info.get("username"), info.get("joined"), info.get("last_active")])
                with open(path, "rb") as f:
                    doc = await context.bot.send_document(chat_id, document=f, filename="users_export.csv")
                await track(doc)
                os.remove(path)

        elif key == "exportpdf":
            if not is_owner(admin_id):
                await query.answer("🔒 " + to_small_caps("owner only."), show_alert=True)
            elif not PDF_REPORT_AVAILABLE:
                await query.answer()
                await send(to_small_caps("❌ pdf report needs matplotlib + reportlab — run `pip install matplotlib reportlab`."))
            else:
                await query.answer("✅ " + to_small_caps("building pdf report..."))
                pdf_path = await asyncio.to_thread(build_pdf_report)
                with open(pdf_path, "rb") as f:
                    doc = await context.bot.send_document(chat_id, document=f, filename="bot_report.pdf")
                await track(doc)
                os.remove(pdf_path)

        elif key == "export":
            if not is_owner(admin_id):
                await query.answer("🔒 " + to_small_caps("owner only."), show_alert=True)
            else:
                await query.answer()
                src_dir = os.path.dirname(os.path.abspath(__file__))
                zip_path = None
                try:
                    zip_path = _build_export_zip(src_dir)
                    size = os.path.getsize(zip_path)
                    if size > EXPORT_MAX_BYTES:
                        await send(
                            "⚠️ " + to_small_caps(
                                f"export would be {size / 1024 / 1024:.1f}mb — too large for telegram's ~50mb limit."
                            )
                        )
                    else:
                        await send(
                            "✅ " + to_small_caps(
                                f"export check passed — source zip builds fine at {size / 1024:.0f}kb."
                            ) + "\n" + to_small_caps("run the real /export command to actually receive the file.")
                        )
                finally:
                    if zip_path and os.path.exists(zip_path):
                        os.remove(zip_path)

        elif key == "block":
            await query.answer()
            await send(
                "ℹ️ " + to_small_caps("/block needs an argument, so it can't be run blindly from here.")
                + "\nUsage: /block <user_id | link | domain>"
            )

        elif key == "unblock":
            await query.answer()
            await send(
                "ℹ️ " + to_small_caps("/unblock needs an argument, so it can't be run blindly from here.")
                + "\nUsage: /unblock <user_id | link | domain>"
            )

        elif key == "cancel":
            await query.answer("✅ " + to_small_caps("running /cancel..."))
            for k in (
                "awaiting", "btn_flow", "style_source_text", "style_target",
                "message_target", "report_link_draft", "owner_contact_label_draft",
                "autoreply_key_draft",
            ):
                context.user_data.pop(k, None)
            await send("✅ " + to_small_caps("cancelled — any pending flow (for you) has been cleared."))

        else:
            await query.answer(to_small_caps("unknown command."), show_alert=True)
    except Exception as e:
        log.exception("cb_run_cmd failed for %s", key)
        try:
            await send("❌ " + to_small_caps(f"'{key}' check failed: {e}"))
        except Exception:
            pass


# ---- Live User Feed (anti-misuse monitoring) ---------------------------------

async def _render_adm_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    col = get_mongo_collection()
    backend = "MongoDB ✅ (synced)" if col is not None else "Local (in-memory/JSON, no Mongo connected)"
    entries = BOT_DATA.get("activity_log", [])[-15:][::-1]
    lines = [f"🕵️ Live User Feed\n🗄 Backend: {backend}\n👥 Total tracked users: {len(BOT_DATA['users'])}\n"]
    if not entries:
        lines.append(to_small_caps("no activity has been recorded yet."))
    else:
        for e in entries:
            uname = f"@{e['username']}" if e.get("username") else "(no username)"
            when = iso_to_ist_str(e.get("time"), "%H:%M:%S")
            lines.append(f"• {when} IST — {e.get('name')} {uname} [{e.get('user_id')}]\n  ↳ {e.get('url')}")
    body = "\n".join(lines)
    s = BOT_DATA["settings"]
    route = s.get("notify_route", "all")
    route_labels = {"logger": "📋 Logger", "activity": "📢 Activity", "dm": "📩 Admin Dm", "all": "🌐 All"}
    kb = InlineKeyboardMarkup(
        [
            [styled_button("🚫 Ban / Unban User (by ID)", callback_data="adm_quickban")],
            [styled_button(
                f"📡 Notify Route: {route_labels.get(route, 'All')}",
                callback_data="adm_notify_route_cycle",
            )],
            [styled_button(
                toggle_label("📡 Feed To Admin DM", s.get('user_activity_dm', True)),
                callback_data="stgl:user_activity_dm:adm_live",
            )],
            [styled_button(
                toggle_label("🆕 Detailed Join Alerts", s.get('detailed_join_alerts', True)),
                callback_data="stgl:detailed_join_alerts:adm_live",
            )],
            back_row("adm_home"),
        ]
    )
    await query.edit_message_text(body, reply_markup=kb)


async def cb_adm_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    await _render_adm_live(update, context)


async def cb_adm_notify_route_cycle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cycles the Reel-Delivered notification destination: Logger ->
    Activity -> Admin DM -> All -> Logger ... one tap, no sub-menu needed."""
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    order = ["all", "logger", "activity", "dm"]
    current = BOT_DATA["settings"].get("notify_route", "all")
    nxt = order[(order.index(current) + 1) % len(order)] if current in order else "all"
    BOT_DATA["settings"]["notify_route"] = nxt
    save_data()
    await _render_adm_live(update, context)


async def cb_adm_quickban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban/Unban a user by ID, entered from the admin panel — this is the
    only place a ban actually happens; the Live Feed is view-only."""
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    context.user_data["awaiting"] = "adm_ban_unban_userid"
    await query.message.reply_text(
        to_small_caps("🚫 send the user's numeric id — if already banned they will be unbanned, otherwise they will be banned.")
    )


# ---- #3 — generic back-stack navigation --------------------------------------
# Screens registered here can be reached via the stack-aware "adm_back"
# button regardless of how deep the user has drilled in. Leaf actions (add /
# remove / toggle / confirm) intentionally aren't part of this table — they
# fall back to a hardcoded parent, same as before.
SCREEN_RENDERERS = {}  # populated just above build_app, once every screen fn exists


def nav_tracked(screen_key):
    """Wraps a screen's callback handler so entering it gets pushed onto the
    per-admin nav stack, so 'Back' can unwind through however many screens
    were visited, not just to a single hardcoded parent.

    Also doubles as the enforcement point for granular admin permissions:
    if screen_key maps to a key in ADMIN_PERMISSIONS, the caller must have
    that permission (owner always does). Nested/utility screens that
    aren't in the catalog (e.g. a broadcast sub-step) are left ungated
    here since reaching them already required passing the gated top-level
    screen first."""
    def deco(fn):
        async def wrapped(update, context):
            perm_key = _perm_key_for_screen(screen_key)
            if perm_key in ADMIN_PERMISSION_KEYS and not has_admin_perm(update.effective_user.id, perm_key):
                await update.callback_query.answer(
                    "🔒 " + to_small_caps("you don't have access to this section."), show_alert=True,
                )
                return
            stack = context.user_data.setdefault("adm_nav_stack", ["adm_home"])
            if not stack or stack[-1] != screen_key:
                stack.append(screen_key)
                if len(stack) > 15:
                    del stack[0]
            return await fn(update, context)
        return wrapped
    return deco


async def cb_adm_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Sweep away any leftover "send a value..." prompt / "✅ saved" confirmation
    # messages from whatever setup flow the admin is leaving — those should
    # not keep sitting in the chat once the admin navigates away.
    await _clear_ephemeral(context, update.effective_chat.id)
    context.user_data.pop("awaiting", None)
    stack = context.user_data.setdefault("adm_nav_stack", ["adm_home"])
    if len(stack) > 1:
        stack.pop()  # drop the screen we're currently on
    target = stack[-1] if stack else "adm_home"
    renderer = SCREEN_RENDERERS.get(target)
    if renderer is None:
        stack[:] = ["adm_home"]
        renderer = SCREEN_RENDERERS["adm_home"]
    await renderer(update, context)


# ---- Stats & Activity -------------------------------------------------------

async def _render_adm_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    mem = get_memory_usage_mb()
    backend = "MongoDB" if get_mongo_collection() is not None else "Local JSON File"
    uptime = human_uptime()
    text = (
        "📊 " + to_title_small_caps("Stats & Activity") + "\n\n"
        + f"{to_title_small_caps('Users')} : {len(BOT_DATA['users'])}\n"
        + f"{to_title_small_caps('Groups')} : {len(BOT_DATA['groups'])}\n"
        + f"{to_title_small_caps('Blocked')} : {len(BOT_DATA.get('blocked_users', []))}\n"
        + f"{to_title_small_caps('Broadcasts Sent')} : {BOT_DATA['metrics'].get('broadcasts_sent', 0)}\n"
        + f"{to_title_small_caps('Reels Downloaded')} : {BOT_DATA['metrics'].get('reels_downloaded', 0)}\n"
        + f"{to_title_small_caps('/Start Count')} : {BOT_DATA['metrics'].get('start_count', 0)}\n"
        + f"{to_title_small_caps('Copyright Reports')} : {len(BOT_DATA['copyright_reports'])}\n\n"
        + f"{to_title_small_caps('Uptime')} : {uptime}\n"
        + f"{to_title_small_caps('Memory')} : {mem if mem is not None else 'N/A'} MB\n"
        + f"{to_title_small_caps('Storage')} : {to_title_small_caps(backend)}"
    )
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([back_row(), home_row()]))


async def cb_adm_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _render_adm_stats(update, context)


# ---- 🔔 Notification Center ---------------------------------------------------
# A single live "what's going on" dashboard so the admin doesn't have to open
# Tickets, Activity Log, Users & Groups, and Settings separately just to see
# whether anything needs attention right now.

async def _render_adm_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    now = datetime.utcnow()
    day_ago = now - timedelta(hours=24)

    def _parse(ts):
        try:
            return datetime.fromisoformat(ts)
        except Exception:
            return None

    # New users / groups in the last 24h.
    new_users_24h = sum(
        1 for u in BOT_DATA["users"].values()
        if (dt := _parse(u.get("joined"))) and dt >= day_ago
    )
    new_groups_24h = sum(
        1 for g in BOT_DATA["groups"].values()
        if (dt := _parse(g.get("added_at"))) and dt >= day_ago
    )
    reel_activity_24h = sum(
        1 for e in BOT_DATA.get("activity_log", [])
        if (dt := _parse(e.get("time"))) and dt >= day_ago
    )

    # Tickets / support requests still waiting on a reply.
    open_tickets = sum(1 for t in BOT_DATA.get("tickets", {}).values() if t.get("status") == "open")
    pending_support = sum(
        1 for r in BOT_DATA.get("support_requests", {}).values() if r.get("status") != "resolved"
    )

    # Errors logged in the last 24h, most recent first.
    recent_errors = [
        e for e in BOT_DATA.get("error_log", [])
        if (dt := _parse(e.get("time"))) and dt >= day_ago
    ]
    recent_errors.sort(key=lambda e: e.get("time") or "", reverse=True)
    last_error = recent_errors[0] if recent_errors else None

    maintenance_on = bool(BOT_DATA["settings"].get("maintenance"))
    blocked_count = len(BOT_DATA.get("blocked", []))

    lines = ["🔔 " + to_title_small_caps("Notification Center"), ""]

    # Needs-attention section first, so the admin sees anything urgent
    # without scrolling.
    alerts = []
    if maintenance_on:
        alerts.append("🔒 " + to_small_caps("maintenance mode is currently ON — users can't use the bot."))
    if open_tickets:
        alerts.append(f"🎫 {open_tickets} " + to_small_caps("open ticket(s) waiting for a reply."))
    if pending_support:
        alerts.append(f"🆘 {pending_support} " + to_small_caps("support request(s) still pending."))
    if recent_errors:
        alerts.append(f"⚠️ {len(recent_errors)} " + to_small_caps("error(s) logged in the last 24h."))
    if not alerts:
        alerts.append("✅ " + to_small_caps("all clear — nothing needs attention right now."))
    lines.extend(alerts)
    lines.append("")

    # Live activity snapshot.
    lines.append("📈 " + to_small_caps("last 24 hours"))
    lines.append(f"👤 " + to_small_caps("new users: ") + str(new_users_24h))
    lines.append(f"👨‍👩‍👧 " + to_small_caps("new groups: ") + str(new_groups_24h))
    lines.append(f"🎬 " + to_small_caps("reel activity: ") + str(reel_activity_24h))
    lines.append("")

    if last_error:
        kind = last_error.get("kind", "unhandled")
        label, _why, _fix = ERROR_KIND_INFO.get(kind, ERROR_KIND_INFO["unhandled"])
        when = iso_to_ist_str(last_error.get("time"), "%Y-%m-%d %H:%M")
        lines.append("🐞 " + to_small_caps("most recent error"))
        lines.append(f"{label} — {when} IST")
        lines.append("")

    lines.append("📊 " + to_small_caps("current totals"))
    lines.append(f"👥 " + to_small_caps("users: ") + str(len(BOT_DATA["users"])))
    lines.append(f"🚫 " + to_small_caps("blocked: ") + str(blocked_count))
    lines.append(f"🎬 " + to_small_caps("reels delivered: ") + str(BOT_DATA["metrics"].get("reels_downloaded", 0)))
    lines.append(f"⏱ " + to_small_caps("uptime: ") + human_uptime())

    text = "\n".join(lines)
    kb = InlineKeyboardMarkup(
        [
            [styled_button("🎫 Tickets", callback_data="adm_tickets"),
             styled_button("📜 Activity Log", callback_data="adm_activity")],
            [styled_button("🔄 Refresh", callback_data="adm_notifications")],
            back_row(),
            home_row(),
        ]
    )
    await query.edit_message_text(text, reply_markup=kb)


async def cb_adm_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _render_adm_notifications(update, context)


# ---- Users & Groups ----------------------------------------------------------

async def _render_adm_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    kb = InlineKeyboardMarkup(
        [
            [styled_button("📋 List Users (last 20)", callback_data="adm_users_list")],
            [styled_button("👨‍👩‍👧 List Groups", callback_data="adm_groups_list")],
            [styled_button("🔍 Check User", callback_data="adm_check_user")],
            [styled_button("✉️ Message a User", callback_data="adm_users_msg")],
            back_row(),
            home_row(),
        ]
    )
    await query.edit_message_text("👥 Users & Groups", reply_markup=kb)


async def cb_adm_groups_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    groups = list(BOT_DATA["groups"].items())
    if not groups:
        text = to_small_caps("the bot is not in any group yet.")
    else:
        lines = [f"👨‍👩‍👧 Groups ({len(groups)})\n"]
        for gid, info in groups:
            lines.append(f"• {info.get('title', '(no title)')} — {gid}")
        text = "\n".join(lines)
    kb = InlineKeyboardMarkup([[styled_button("🔙 Back", callback_data="adm_users")]])
    await query.edit_message_text(text, reply_markup=kb)


async def cb_adm_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _render_adm_users(update, context)


async def cb_adm_users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    users = list(BOT_DATA["users"].items())[-20:]
    if not users:
        text = to_small_caps("no user records found yet.")
    else:
        lines = ["📋 Last 20 Users\n"]
        for uid, info in users:
            uname = f"@{info.get('username')}" if info.get("username") else "(no username)"
            lines.append(f"• {uid} — {info.get('name')} {uname}")
        text = "\n".join(lines)
    kb = InlineKeyboardMarkup([[styled_button("🔙 Back", callback_data="adm_users")]])
    await query.edit_message_text(text, reply_markup=kb)


async def cb_adm_users_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["awaiting"] = "message_user_id"
    await query.message.reply_text(to_small_caps("send the id of the user you want to message."))


async def cb_adm_check_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["awaiting"] = "check_user_id"
    await query.message.reply_text(to_small_caps("send the user id you want to check."))


async def build_user_details_card(context: ContextTypes.DEFAULT_TYPE, target_id: int) -> str:
    """Full live detail card for one user, shown to an admin from
    '🔍 Check User' — same sectioned house style as the New User Started
    alert / Stats screen, but pulled fresh from stored data + a live
    getChat call, and with a clickable Name."""
    lbl = to_title_small_caps
    uid = str(target_id)
    u = BOT_DATA["users"].get(uid, {})

    # Prefer a live getChat so name/username/premium reflect the user's
    # CURRENT profile, not whatever was cached at their last /start. Falls
    # back to stored data if the chat can't be fetched (user blocked the
    # bot, invalid id, never started it, etc.).
    chat_obj = None
    try:
        chat_obj = await context.bot.get_chat(target_id)
    except Exception:
        pass

    if chat_obj is not None:
        name = chat_obj.full_name if hasattr(chat_obj, "full_name") else (
            " ".join(filter(None, [getattr(chat_obj, "first_name", None), getattr(chat_obj, "last_name", None)]))
        )
        name = name or u.get("name") or str(target_id)
        username = getattr(chat_obj, "username", None) or u.get("username")
        is_premium = getattr(chat_obj, "is_premium", None)
        name_link = f'<a href="https://t.me/{username}">{html.escape(name)}</a>' if username else f'<a href="tg://user?id={target_id}">{html.escape(name)}</a>'
    else:
        name = u.get("name") or str(target_id)
        username = u.get("username")
        is_premium = None
        name_link = f'<a href="tg://user?id={target_id}">{html.escape(name)}</a>'

    if not u and chat_obj is None:
        return None  # unknown to the bot AND not resolvable live — caller shows "not found"

    username_display = f"@{username}" if username else "Not Set"
    today = datetime.utcnow().strftime("%Y-%m-%d")
    used_today = u.get("downloads_today", 0) if u.get("downloads_today_date") == today else 0
    plan = u.get("plan", "Free")
    active_premium = is_premium_active(uid)
    joined = u.get("joined_at") or u.get("started_at")
    joined_display = iso_to_ist_str(joined, "%d %B %Y • %H:%M:%S") + " IST" if joined else "Unknown"
    banned = target_id in BOT_DATA.get("blocked", [])

    lines = [
        "🔍 " + lbl("User Details"),
        "",
        _CARD_SEP,
        "",
        "👤 " + lbl("User Information"),
        "",
        f"{lbl('Name')} : {name_link}",
        f"{lbl('Username')} : {html.escape(username_display)}",
        f"{lbl('User Id')} : {target_id}",
        "",
        "📊 " + lbl("Activity"),
        "",
        f"{lbl('Reels Downloaded')} : {u.get('reels_count', 0)}",
        f"{lbl('Audios Get')} : {u.get('audio_count', 0)}",
        f"{lbl('Captions Get')} : {u.get('caption_count', 0)}",
        f"{lbl('Used Today')} : {used_today}",
        "",
        "💎 " + lbl("Premium"),
        "",
        f"{lbl('Plan')} : {lbl(plan)}",
        f"{lbl('Status')} : {lbl('Active') if active_premium else lbl('Not Active')}",
        "",
        "⚙️ " + lbl("Account"),
        "",
        f"{lbl('Joined At')} : {joined_display}",
        f"{lbl('Banned')} : {lbl('Yes') if banned else lbl('No')}",
    ]
    if is_premium is not None:
        lines.append(f"{lbl('Telegram Premium')} : {lbl('Yes') if is_premium else lbl('No')}")
    lines += ["", _CARD_SEP]

    return "<blockquote>" + "\n".join(lines) + "</blockquote>"


# ---- Broadcast (reliable delivery, admin copy, /broadcast command, and month-wise delete) ----
#
# What changed and why:
#  1. do_broadcast() used to fire every send back-to-back with zero pacing.
#     Telegram enforces a hard ~30 messages/second global rate limit; blast
#     past it and the API replies with 429 "Too Many Requests" (RetryAfter),
#     which the old code caught with a bare `except Exception` and simply
#     logged as a permanent failure. That's the "bar bar failed ho jata hai"
#     — most of those "failures" were really just flood-control hits that a
#     short pause and one retry would have delivered fine. Fixed by pacing
#     every send and giving a RetryAfter exactly one honoured retry.
#  2. Failures are now categorized (blocked the bot, invalid/deleted chat,
#     rate-limited-then-recovered, other) instead of one flat "failed"
#     number, so the admin can actually see *why* delivery didn't land.
#  3. Every successfully delivered message ID is now recorded per user
#     against the broadcast, so a broadcast can be pulled back out of every
#     recipient's chat later (see Delete Broadcast below).
BROADCAST_SEND_DELAY = 0.05  # ~20 msg/sec — safely under Telegram's cap


def _broadcast_report_text(entry: dict) -> str:
    """Build the normal broadcast completion report."""
    total = entry.get("total_targeted", 0)
    sent = entry.get("recipients", 0)
    blocked = entry.get("blocked", 0)
    invalid_chat = entry.get("invalid_chat", 0)
    other_failed = entry.get("other_failed", 0)
    recovered = entry.get("recovered", 0)
    failed_total = blocked + invalid_chat + other_failed
    return (
        "✅ " + to_small_caps("broadcast complete") + "\n\n"
        + to_small_caps("total targeted") + f": {total}\n"
        + to_small_caps("delivered successfully") + f": {sent}\n"
        + to_small_caps("not delivered") + f": {failed_total}\n\n"
        + to_small_caps("breakdown — why some were not delivered") + "\n"
        + "🚫 " + to_small_caps("blocked the bot / account deactivated") + f": {blocked}\n"
        + "⚠️ " + to_small_caps("chat unavailable / never started the bot") + f": {invalid_chat}\n"
        + "❓ " + to_small_caps("other delivery error") + f": {other_failed}\n"
        + ("🔁 " + to_small_caps("recovered after a brief rate-limit pause") + f": {recovered}\n" if recovered else "")
        + "\n🔐 " + to_small_caps("forward-lock") + f": {'✅ ON' if entry.get('protect') else '❌ OFF'}"
    )


async def cb_adm_start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show confirmation before sending the bot's normal /start experience to everyone."""
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    kb = InlineKeyboardMarkup([
        [styled_button("✅ Confirm /start Broadcast", callback_data="adm_start_broadcast_confirm")],
        [styled_button("❌ Cancel", callback_data="adm_broadcast")]
    ])
    await query.edit_message_text(
        "⚠️ " + to_small_caps("confirm /start broadcast") + "\n\n"
        + to_small_caps("this will send the bot's normal /start welcome message to every registered user, plus this admin chat.") + "\n"
        + to_small_caps("no custom broadcast content will be used."),
        reply_markup=kb,
    )


async def cb_adm_start_broadcast_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send the normal /start experience as a simple alive/working notification."""
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return

    status = await query.message.reply_text("🚀 " + to_small_caps("/start broadcast in progress..."))
    targets = set(BOT_DATA["users"].keys())
    targets.add(str(update.effective_user.id))
    sent = 0
    failed = 0

    for uid in targets:
        try:
            # Render the exact same start destination/menu users get from /start,
            # without pretending Telegram received a command from the bot.
            await context.bot.send_message(chat_id=int(uid), text="/start")
            sent += 1
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
            try:
                await context.bot.send_message(chat_id=int(uid), text="/start")
                sent += 1
            except Exception:
                failed += 1
        except Exception:
            failed += 1
        await asyncio.sleep(BROADCAST_SEND_DELAY)

    try:
        await status.edit_text(
            "✅ " + to_small_caps("/start broadcast complete") + "\n\n"
            + to_small_caps("delivered") + f": {sent}\n"
            + to_small_caps("failed") + f": {failed}"
        )
    except Exception:
        pass
    await log_event(context, f"🚀 /start broadcast by {update.effective_user.id} — {sent} delivered, {failed} failed")


async def _render_adm_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    s = BOT_DATA["settings"]
    protect = s.get("protect_broadcasts", True)
    kb = InlineKeyboardMarkup(
        [
            [styled_button("📢 New Broadcast", callback_data="adm_bc_new"),
             styled_button("📜 Broadcast Log", callback_data="adm_bc_log")],
            [styled_button(
                toggle_label("🔐 Forward-Lock", protect),
                callback_data="stgl:protect_broadcasts:adm_broadcast",
            ),
             styled_button("🚀 /start Broadcast", callback_data="adm_start_broadcast")],
            [styled_button("🗑 Delete Broadcast", callback_data="adm_bc_delmenu")],
            back_row(),
            home_row(),
        ]
    )
    total_users = len(BOT_DATA["users"])
    body = (
        to_small_caps("📢 broadcast centre") + "\n"
        + to_small_caps("send an announcement to every registered user") + "\n\n"
        + to_small_caps("total reachable users") + f": {total_users}\n\n"
        + to_small_caps("/start broadcast sends the normal bot welcome message as an alive/working notification")
    )
    await query.edit_message_text(body, reply_markup=kb)


async def cb_adm_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _render_adm_broadcast(update, context)


async def cb_adm_bc_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["awaiting"] = "broadcast_content"
    await query.message.reply_text(
        to_small_caps("📢 send your broadcast now") + "\n"
        + to_small_caps("text, photo or video — one single message") + "\n\n"
        + to_small_caps("it will be delivered to every registered user and this admin chat, respecting your forward-lock setting")
    )


async def cb_adm_bc_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    entries = BOT_DATA["broadcast_log"][-10:][::-1]
    if not entries:
        text = to_small_caps("📜 broadcast log") + "\n\n" + to_small_caps("no broadcasts have been sent yet.")
    else:
        lines = [to_small_caps("📜 last 10 broadcasts") + "\n"]
        for e in entries:
            when = iso_to_ist_str(e.get("at"), "%Y-%m-%d %H:%M") + " IST"
            line = (
                f"• {when} — "
                + to_small_caps("delivered") + f" {e.get('recipients', 0)} • "
                + to_small_caps("blocked") + f" {e.get('blocked', 0)} • "
                + to_small_caps("failed") + f" {e.get('other_failed', 0)}"
            )
            lines.append(line)
        text = "\n".join(lines)
    kb = InlineKeyboardMarkup([back_row("adm_broadcast")])
    await query.edit_message_text(text, reply_markup=kb)


async def do_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    # #4 — the master "lock everything" switch ORs together with the
    # broadcast-specific forward-lock toggle.
    s = BOT_DATA["settings"]
    protect = s.get("protect_broadcasts", True) or s.get("lock_all_content", False)
    broadcast_id = BOT_DATA.get("broadcast_next_id", 1)
    BOT_DATA["broadcast_next_id"] = broadcast_id + 1

    status_msg = await update.message.reply_text(
        "📢 " + to_small_caps("broadcast in progress...") + " 0%"
    )

    delivered_ids = {}
    sent = 0
    blocked = 0          # user blocked the bot / kicked it / deactivated account
    invalid_chat = 0     # chat no longer exists / never started the bot
    other_failed = 0     # anything else (unexpected)
    recovered = 0        # succeeded only after a flood-control retry

    user_ids = list(BOT_DATA["users"].keys())
    # The sending admin also receives a copy, so the broadcast is visible in
    # the admin chat exactly like it is for users.
    admin_uid = str(update.effective_user.id)
    if admin_uid not in user_ids:
        user_ids.append(admin_uid)
    total = len(user_ids)
    for i, uid in enumerate(user_ids):
        try:
            copied = await context.bot.copy_message(
                chat_id=int(uid), from_chat_id=msg.chat_id, message_id=msg.message_id,
                protect_content=protect,
            )
        except RetryAfter as e:
            # Flood control — Telegram itself tells us exactly how long to
            # wait. Honour it once, then retry this one user before giving
            # up, instead of silently counting a recoverable hit as failed.
            await asyncio.sleep(e.retry_after + 0.5)
            try:
                copied = await context.bot.copy_message(
                    chat_id=int(uid), from_chat_id=msg.chat_id, message_id=msg.message_id,
                    protect_content=protect,
                )
                recovered += 1
            except Exception:
                other_failed += 1
                copied = None
        except Forbidden:
            # User blocked the bot, deleted their account, or kicked it
            # from a group — permanent, not worth retrying.
            blocked += 1
            copied = None
        except BadRequest:
            # Chat not found / user never actually opened a DM with the
            # bot — also permanent.
            invalid_chat += 1
            copied = None
        except TelegramError:
            other_failed += 1
            copied = None
        except Exception:
            other_failed += 1
            copied = None

        if copied:
            track_sent_message(int(uid), copied.message_id)
            # Broadcasts are exempt from the global auto-delete timer — they
            # only go away via an explicit 🗑 Delete Broadcast action.
            delivered_ids[uid] = copied.message_id
            sent += 1

        await asyncio.sleep(BROADCAST_SEND_DELAY)

        if total and (i + 1) % 25 == 0:
            pct = int(((i + 1) / total) * 100)
            try:
                await status_msg.edit_text("📢 " + to_small_caps("broadcast in progress...") + f" {pct}%")
            except Exception:
                pass

    failed_total = blocked + invalid_chat + other_failed
    at = datetime.utcnow().isoformat()
    entry = {
        "id": broadcast_id,
        "by": update.effective_user.id,
        "at": at,
        "recipients": sent,
        "blocked": blocked,
        "invalid_chat": invalid_chat,
        "other_failed": other_failed,
        "recovered": recovered,
        "total_targeted": total,
        "messages": delivered_ids,  # {user_id: message_id} — used by Delete Broadcast
        "protect": protect,
        "report_chat_id": None,
        "report_message_id": None,
    }
    BOT_DATA["broadcast_log"].append(entry)
    BOT_DATA["metrics"]["broadcasts_sent"] = BOT_DATA["metrics"].get("broadcasts_sent", 0) + 1
    save_data()

    report = _broadcast_report_text(entry)
    try:
        await status_msg.edit_text(report)
        # Remember where this report lives so cb_bc_start_now can keep it
        # live-updated as users tap 🚀 Start Bot, instead of the numbers
        # only ever being a one-time snapshot.
        entry["report_chat_id"] = status_msg.chat_id
        entry["report_message_id"] = status_msg.message_id
    except Exception:
        sent_report = await update.message.reply_text(report)
        entry["report_chat_id"] = sent_report.chat_id
        entry["report_message_id"] = sent_report.message_id
    save_data()
    await log_event(
        context,
        f"📢 Broadcast sent by {update.effective_user.id} — {sent}/{total} delivered "
        f"(blocked {blocked}, invalid {invalid_chat}, other {other_failed})",
    )


# ---- Delete Broadcast (month-wise) -------------------------------------------

def _broadcast_month_key(iso_ts: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_ts)
    except Exception:
        return "unknown"
    return dt.strftime("%B %Y")  # e.g. "September 2026"


async def _render_adm_bc_delmenu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    entries = BOT_DATA["broadcast_log"]
    months = {}
    for idx, e in enumerate(entries):
        key = _broadcast_month_key(e.get("at", ""))
        months.setdefault(key, []).append(idx)

    if not months:
        text = to_small_caps("🗑 delete broadcast") + "\n\n" + to_small_caps("no broadcasts recorded yet.")
        kb = InlineKeyboardMarkup([back_row("adm_broadcast")])
        await query.edit_message_text(text, reply_markup=kb)
        return

    month_keys = list(months.keys())
    rows = []
    for i in range(0, len(month_keys), 2):
        pair = month_keys[i:i + 2]
        rows.append([
            styled_button(f"🗓 {mk} ({len(months[mk])})", callback_data=f"adm_bc_delmonth:{mk}")
            for mk in pair
        ])
    rows.append(back_row("adm_broadcast"))
    rows.append(home_row())
    text = (
        to_small_caps("🗑 delete broadcast") + "\n"
        + to_small_caps("pick a month to see broadcasts sent that month")
    )
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))


async def cb_adm_bc_delmenu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _render_adm_bc_delmenu(update, context)


async def cb_adm_bc_delmonth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    month = query.data.split(":", 1)[1]
    entries = BOT_DATA["broadcast_log"]
    rows = []
    lines = [to_small_caps("🗓 broadcasts in") + f" {month}\n"]
    for idx, e in enumerate(entries):
        if _broadcast_month_key(e.get("at", "")) != month:
            continue
        when = e.get("at", "?")[:16].replace("T", " ")
        lines.append(f"#{idx} — {when} — " + to_small_caps("delivered") + f" {e.get('recipients', 0)}")
        rows.append([styled_button(f"🗑 #{idx} — {when}", callback_data=f"adm_bc_delconfirm:{idx}")])
    rows.append(back_row("adm_bc_delmenu"))
    rows.append(home_row())
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))


async def cb_adm_bc_delconfirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split(":", 1)[1])
    entries = BOT_DATA["broadcast_log"]
    if idx < 0 or idx >= len(entries):
        await query.edit_message_text(
            "❌ " + to_small_caps("that broadcast no longer exists."),
            reply_markup=InlineKeyboardMarkup([back_row("adm_bc_delmenu")]),
        )
        return
    e = entries[idx]
    when = e.get("at", "?")[:16].replace("T", " ")
    recipients = len(e.get("messages", {}))
    text = (
        "⚠️ " + to_small_caps("confirm delete") + "\n\n"
        + to_small_caps("broadcast") + f" #{idx} — {when}\n"
        + to_small_caps("this will remove it from") + f" {recipients} " + to_small_caps("recipient chats.")
        + "\n\n" + to_small_caps("this action cannot be undone.")
    )
    kb = InlineKeyboardMarkup(
        [
            [styled_button("✅ Yes, Delete", callback_data=f"adm_bc_deldo:{idx}"),
             styled_button("❌ Cancel", callback_data="adm_bc_delmenu")],
        ]
    )
    await query.edit_message_text(text, reply_markup=kb)


async def cb_adm_bc_deldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split(":", 1)[1])
    entries = BOT_DATA["broadcast_log"]
    if idx < 0 or idx >= len(entries):
        await query.edit_message_text(
            "❌ " + to_small_caps("that broadcast no longer exists."),
            reply_markup=InlineKeyboardMarkup([back_row("adm_bc_delmenu")]),
        )
        return
    e = entries[idx]
    messages = e.get("messages", {})
    removed = 0
    gone = 0
    for uid, mid in messages.items():
        try:
            await context.bot.delete_message(chat_id=int(uid), message_id=int(mid))
            removed += 1
        except Exception:
            gone += 1
        await asyncio.sleep(BROADCAST_SEND_DELAY)
    entries.pop(idx)
    save_data()
    text = (
        "✅ " + to_small_caps("broadcast deleted") + "\n\n"
        + to_small_caps("removed from chats") + f": {removed}\n"
        + to_small_caps("already gone / could not remove") + f": {gone}"
    )
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([back_row("adm_bc_delmenu"), home_row()]))
    await log_event(context, f"🗑 Broadcast #{idx} deleted by {update.effective_user.id} — {removed} removed")


__all__ = [_n for _n in dir() if not _n.startswith("__")]
