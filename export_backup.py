from handlers_admin_text import *


async def cmd_dbstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    col = get_mongo_collection()
    if col is not None:
        text = "✅ MongoDB: connected"
    elif MONGO_URI:
        text = f"❌ MongoDB: not connected\nReason: {_mongo_last_error}"
    else:
        text = "ℹ️ MongoDB not configured — using local JSON file."
    text += f"\n\nUsers: {len(BOT_DATA['users'])} | Groups: {len(BOT_DATA['groups'])} | Admins: {len(BOT_DATA['admins'])}"
    await update.message.reply_text(text)


async def cmd_mongodb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/mongodb — full 🗄 Mongo Plugin status card, admin-only. Same data
    (and same live re-ping) as the admin-panel screen, for a quick check
    straight from the command line without opening the panel."""
    if not is_admin(update.effective_user.id):
        return
    status_msg = await update.message.reply_text("🔎 " + to_small_caps("checking mongodb status..."))
    text, kb = _build_mongo_plugin_view()
    await status_msg.edit_text(text, parse_mode="HTML", reply_markup=kb)


def build_health_text() -> str:
    """Single source of truth for /health, used by both the real command
    and the admin panel's Test Commands screen, so the two never drift out
    of sync. Covers every subsystem the bot actually depends on, not just
    a subset — storage, timing, limits, downloads, premium, and every
    optional dependency that silently degrades instead of crashing."""
    col = get_mongo_collection()
    backend = "MongoDB ✅ connected" if col is not None else (
        f"❌ MongoDB configured but not connected ({_mongo_last_error})" if MONGO_URI
        else "Local JSON file (no MongoDB configured)"
    )
    mem = get_memory_usage_mb()
    s = BOT_DATA["settings"]
    premium_count = sum(1 for uid in BOT_DATA["users"] if is_premium_active(uid))
    recent_errors = [e for e in BOT_DATA.get("error_log", [])
                     if (datetime.utcnow() - datetime.fromisoformat(e["time"])) < timedelta(hours=24)]
    lines = [
        "🩺 " + to_small_caps("health report"),
        "",
        "— " + to_small_caps("system") + " —",
        f"🕒 Server time: {now_ist_str('%d %b %Y, %H:%M:%S')} IST",
        f"⏱ Uptime: {human_uptime()}",
        f"💾 Memory: {mem if mem is not None else 'n/a'} MB",
        f"🐍 python-telegram-bot: {'button-style support ✅' if SUPPORTS_BUTTON_STYLE else 'no button-style support (upgrade to 22.7+)'}",
        f"🎬 ffmpeg: {'✅ ' + FFMPEG_PATH if FFMPEG_AVAILABLE else '⚠️ not found (no-merge fallback in use)'}",
        f"🧾 QR generation: {'✅ styled/local' if QRCODE_STYLED_AVAILABLE else ('✅ plain/local' if QRCODE_AVAILABLE else '⚠️ remote fallback (install qrcode[pil])')}",
        "",
        "— " + to_small_caps("data") + " —",
        f"🗄 Storage: {backend}",
        f"👥 Users: {len(BOT_DATA['users'])} | Groups: {len(BOT_DATA['groups'])} | Admins: {len(BOT_DATA['admins'])}",
        f"💎 Active premium users: {premium_count}",
        f"📢 Broadcasts sent (all-time): {len(BOT_DATA['broadcast_log'])}",
        f"🎫 Open tickets: {sum(1 for t in BOT_DATA.get('tickets', {}).values() if not t.get('closed_at'))}" if isinstance(BOT_DATA.get("tickets"), dict) else "🎫 Open tickets: n/a",
        "",
        "— " + to_small_caps("limits & modes") + " —",
        f"🔒 Maintenance: {'✅ ON' if s.get('maintenance') else '❌ OFF'}",
        f"🎛 Rate limit: {s.get('rate_limit_max')} msgs / {s.get('rate_limit_window_seconds')}s",
        f"📅 Daily free-download limit: {s.get('daily_limit', 20)}",
        "",
        "— " + to_small_caps("last 24h") + " —",
        f"🐞 Errors logged: {len(recent_errors)}" + (" — check 📋 Activity Log" if recent_errors else ""),
    ]
    return "\n".join(lines)


async def cmd_health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(build_health_text())


async def cmd_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    raw = json.dumps(BOT_DATA, ensure_ascii=False, indent=2).encode("utf-8")
    payload, encrypted = encrypt_backup_bytes(raw)
    filename = "bot_data_backup.json.enc" if encrypted else "bot_data_backup.json"
    path = os.path.join(tempfile.gettempdir(), f"bot_data_export_{int(time.time())}_{filename}")
    with open(path, "wb") as f:
        f.write(payload)
    caption = None
    if encrypted:
        caption = to_small_caps("🔒 encrypted with the bot's local backup.key — restore only works on this same bot instance (or copy backup.key to a new one first).")
    with open(path, "rb") as f:
        await update.message.reply_document(document=f, filename=filename, caption=caption)
    os.remove(path)


async def send_update_backup(bot, chat_id):
    """The 📦 Update Backup system. Sends TWO plain (never encrypted) JSON
    files, with fixed names so they can be committed straight into the
    GitHub repo next to bot.py, unchanged:

      • bot_settings_seed.json — everything EXCEPT users (menus, settings,
        admins, groups, tickets, broadcast log, metrics, etc.)
      • bot_users_seed.json    — just the full user list/info.

    Workflow: before pushing a code update, run this (📦 Update Backup in
    the admin panel, or /updatebackup) → download both files → add/commit
    them into the repo with these exact names → push. On the next deploy,
    if the host has no existing data (see _apply_seed_files_if_present in
    load_data()), the bot auto-restores everything from these two files —
    no manual DM-restore step needed."""
    settings_data = {k: v for k, v in BOT_DATA.items() if k != "users"}
    users_data = {"users": BOT_DATA.get("users", {})}

    ts = int(time.time())
    settings_path = os.path.join(tempfile.gettempdir(), f"update_backup_settings_{ts}.json")
    users_path = os.path.join(tempfile.gettempdir(), f"update_backup_users_{ts}.json")
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings_data, f, ensure_ascii=False, indent=2)
    with open(users_path, "w", encoding="utf-8") as f:
        json.dump(users_data, f, ensure_ascii=False, indent=2)

    intro = to_small_caps(
        "📦 update backup — 2 files, exact names required. put both next to "
        "bot.py in your github repo and commit them BEFORE pushing a new "
        f"version:\n\n• {SEED_SETTINGS_FILE}\n• {SEED_USERS_FILE}\n\n"
        "on the next deploy, if the host has no existing data, the bot "
        "auto-loads these back in on startup. no manual restore needed."
    )
    await bot.send_message(chat_id, intro)
    with open(settings_path, "rb") as f:
        await bot.send_document(chat_id, document=f, filename=SEED_SETTINGS_FILE)
    with open(users_path, "rb") as f:
        await bot.send_document(
            chat_id, document=f, filename=SEED_USERS_FILE,
            caption=f"👥 {to_small_caps('users in this file')}: {len(BOT_DATA.get('users', {}))}",
        )
    os.remove(settings_path)
    os.remove(users_path)


async def cmd_updatebackup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    await send_update_backup(context.bot, update.effective_chat.id)


async def cb_adm_update_backup_run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Actually builds and sends the 2 seed-backup files. Split out from
    the screen entry point below (cb_adm_update_backup) so tapping
    '📦 Update Backup' from the Admin Panel now opens a proper screen
    instead of instantly firing off files — every backup/database-related
    action (seed backup, full DB export, restore, Mongo Plugin) now lives
    together on that one screen."""
    query = update.callback_query
    if not is_owner(update.effective_user.id):
        await query.answer("🔒 " + to_small_caps("owner only."), show_alert=True)
        return
    await query.answer("✅ " + to_small_caps("building update backup..."))
    await send_update_backup(context.bot, update.effective_chat.id)


async def cb_adm_export_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Same full-database export as /database, now reachable with a tap
    from the 🍭 Update Backup screen instead of only via command."""
    query = update.callback_query
    if not is_owner(update.effective_user.id):
        await query.answer("🔒 " + to_small_caps("owner only."), show_alert=True)
        return
    await query.answer("✅ " + to_small_caps("preparing full database export..."))
    raw = json.dumps(BOT_DATA, ensure_ascii=False, indent=2).encode("utf-8")
    payload, encrypted = encrypt_backup_bytes(raw)
    filename = "bot_data_backup.json.enc" if encrypted else "bot_data_backup.json"
    path = os.path.join(tempfile.gettempdir(), f"bot_data_export_{int(time.time())}_{filename}")
    with open(path, "wb") as f:
        f.write(payload)
    caption = None
    if encrypted:
        caption = to_small_caps("🔒 encrypted with the bot's local backup.key — restore only works on this same bot instance (or copy backup.key to a new one first).")
    with open(path, "rb") as f:
        await context.bot.send_document(update.effective_chat.id, document=f, filename=filename, caption=caption)
    os.remove(path)


def _build_adm_update_backup_view():
    """🍭 Update Backup — single home for every backup/database-related
    action in the bot, per the request to stop scattering these across
    Settings (Restore Backup used to live there) and Feature Plugins
    (Mongo Plugin used to live there)."""
    text = (
        "🍭 <b>" + to_small_caps("update backup") + "</b>\n\n"
        "<blockquote>"
        + to_small_caps(
            "everything to do with backing up, restoring, or connecting a "
            "live database now lives here, in one place."
        ) + "</blockquote>"
    )
    kb = InlineKeyboardMarkup([
        [styled_button("📦 Run Update Backup Now", callback_data="adm_update_backup_run")],
        [styled_button("🔐 Full Database Export", callback_data="adm_export_database")],
        [styled_button("📥 Restore Backup", callback_data="adm_restore_info")],
        [styled_button("🗄 Mongo Plugin", callback_data="adm_mongo_plugin", style="primary")],
        [styled_button("ℹ️ How Update Backup Works", callback_data="help_update_backup_info")],
        back_row(),
        home_row(),
    ])
    return text, kb


async def _render_adm_update_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    text, kb = _build_adm_update_backup_view()
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)


async def cb_adm_update_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_owner(update.effective_user.id):
        await query.answer("🔒 " + to_small_caps("owner only."), show_alert=True)
        return
    await query.answer()
    await _render_adm_update_backup(update, context)


async def cmd_exportusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """CSV export of users."""
    if not is_owner(update.effective_user.id):
        return
    path = os.path.join(tempfile.gettempdir(), f"users_export_{int(time.time())}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["user_id", "name", "username", "joined", "last_active"])
        for uid, info in BOT_DATA["users"].items():
            writer.writerow([uid, info.get("name"), info.get("username"), info.get("joined"), info.get("last_active")])
    with open(path, "rb") as f:
        await update.message.reply_document(document=f, filename="users_export.csv")
    os.remove(path)


def _parse_iso(s):
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def build_pdf_report_chart_images() -> list:
    """Two matplotlib charts as PNG file paths: (1) new-user growth over
    the last 14 days, built from real per-user 'joined' timestamps —
    there's no separate daily-stats log, so this buckets what's actually
    stored; (2) a bar chart of the lifetime metrics counters. Caller is
    responsible for deleting the returned files."""
    paths = []

    # Chart 1 — daily new users, last 14 days
    days = [(datetime.utcnow().date() - timedelta(days=i)) for i in range(13, -1, -1)]
    counts = {d: 0 for d in days}
    for info in BOT_DATA["users"].values():
        dt = _parse_iso(info.get("joined"))
        if dt and dt.date() in counts:
            counts[dt.date()] += 1
    fig1, ax1 = plt.subplots(figsize=(6, 3))
    ax1.bar([d.strftime("%d %b") for d in days], [counts[d] for d in days], color="#3b82f6")
    ax1.set_title("New Users — Last 14 Days")
    ax1.tick_params(axis="x", rotation=45, labelsize=7)
    fig1.tight_layout()
    p1 = os.path.join(tempfile.gettempdir(), f"chart_growth_{int(time.time())}.png")
    fig1.savefig(p1, dpi=150)
    plt.close(fig1)
    paths.append(p1)

    # Chart 2 — lifetime metrics counters
    metrics = BOT_DATA.get("metrics", {})
    labels = list(metrics.keys())
    values = [metrics[k] for k in labels]
    fig2, ax2 = plt.subplots(figsize=(6, 3))
    ax2.barh(labels, values, color="#10b981")
    ax2.set_title("Lifetime Metrics")
    fig2.tight_layout()
    p2 = os.path.join(tempfile.gettempdir(), f"chart_metrics_{int(time.time())}.png")
    fig2.savefig(p2, dpi=150)
    plt.close(fig2)
    paths.append(p2)

    return paths


def build_pdf_report() -> str:
    """Builds a full PDF report (summary table + the two charts above) and
    returns its file path. Caller deletes the file after sending. Raises
    if PDF_REPORT_AVAILABLE is False — callers should check that first."""
    chart_paths = build_pdf_report_chart_images()
    pdf_path = os.path.join(tempfile.gettempdir(), f"bot_report_{int(time.time())}.pdf")
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Bot Report", styles["Title"]),
        Paragraph(f"Generated {now_ist_str('%d %b %Y, %H:%M:%S')} IST", styles["Normal"]),
        Spacer(1, 0.5 * cm),
    ]

    s = BOT_DATA["settings"]
    metrics = BOT_DATA.get("metrics", {})
    summary_rows = [
        ["Metric", "Value"],
        ["Total Users", str(len(BOT_DATA["users"]))],
        ["Total Groups", str(len(BOT_DATA["groups"]))],
        ["Total Admins", str(len(BOT_DATA["admins"]))],
        ["Reels Downloaded", str(metrics.get("reels_downloaded", 0))],
        ["Start Count", str(metrics.get("start_count", 0))],
        ["Broadcasts Sent", str(metrics.get("broadcasts_sent", 0))],
        ["Maintenance Mode", "ON" if s.get("maintenance") else "OFF"],
    ]
    table = Table(summary_rows, colWidths=[8 * cm, 6 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, rl_colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.whitesmoke, rl_colors.white]),
    ]))
    story.append(table)
    story.append(Spacer(1, 1 * cm))

    for cp in chart_paths:
        story.append(RLImage(cp, width=14 * cm, height=7 * cm))
        story.append(Spacer(1, 0.5 * cm))

    doc.build(story)
    for cp in chart_paths:
        os.remove(cp)
    return pdf_path


async def cmd_exportpdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """📊 PDF report — summary table + charts, generated fresh each time."""
    if not is_owner(update.effective_user.id):
        return
    if not PDF_REPORT_AVAILABLE:
        await update.message.reply_text(
            to_small_caps("❌ pdf report needs matplotlib + reportlab — run `pip install matplotlib reportlab` and try again.")
        )
        return
    status = await update.message.reply_text("📊 " + to_small_caps("building pdf report..."))
    try:
        pdf_path = await asyncio.to_thread(build_pdf_report)
        with open(pdf_path, "rb") as f:
            await update.message.reply_document(document=f, filename="bot_report.pdf")
        os.remove(pdf_path)
        await status.delete()
    except Exception:
        log_error("unhandled", "/exportpdf failed")
        await status.edit_text("❌ " + to_small_caps("pdf report failed — see the activity log for details."))


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Latency check, available to everyone. Admins get the full picture
    (uptime, RAM/CPU/disk load, storage backend, server time in IST) as a
    Telegram quote block; regular users just get the plain pong."""
    t0 = time.monotonic()
    msg = await update.message.reply_text("🏓 Pong!")
    ms = int((time.monotonic() - t0) * 1000)
    if is_admin(update.effective_user.id):
        col = get_mongo_collection()
        backend = "MongoDB ✅" if col is not None else "Local JSON"
        cpu = get_cpu_percent()
        ram = get_ram_percent()
        disk = get_disk_percent()

        lines = [f"↬ {to_title_small_caps('Uptime')} : {human_uptime_full()}"]
        if ram is not None:
            lines.append(f"↬ {to_title_small_caps('RAM')} : {ram:.1f}%")
        if cpu is not None:
            lines.append(f"↬ {to_title_small_caps('CPU')} : {cpu:.1f}%")
        if disk is not None:
            lines.append(f"↬ {to_title_small_caps('Disk')} : {disk:.1f}%")
        lines.append(f"↬ {to_title_small_caps('Storage')} : {to_title_small_caps(backend)}")
        lines.append(f"↬ {to_title_small_caps('Server Time')} : {now_ist_str('%d %b %Y, %H:%M:%S')} IST")

        quote_body = html.escape("\n".join(lines))
        text = f"🏓 <b>{to_title_small_caps('Pong!')}</b> {ms}ms\n\n<blockquote>{quote_body}</blockquote>"
        await msg.edit_text(text, parse_mode="HTML")
    else:
        await msg.edit_text(f"🏓 Pong! {ms}ms")


EXPORT_MAX_BYTES = 49 * 1024 * 1024  # stay under Telegram's ~50MB bot upload cap
EXPORT_EXCLUDE_DIRS = {DOWNLOAD_DIR, BACKUP_DIR, "__pycache__", ".git", ".venv", "venv"}
EXPORT_EXCLUDE_FILES = {DATA_FILE, "backup.key", "mongo_config.json"}


def _build_export_zip(src_dir: str) -> str:
    """Zip the bot's source code only — never the downloads/backups/data
    folders, which is what actually made /export unusable before: those
    directories fill up with downloaded videos and JSON backups over time,
    so the old 'zip literally everything' approach routinely built an
    archive well past Telegram's ~50MB bot upload limit and the send would
    just silently fail with no feedback to the admin."""
    import zipfile

    zip_path = os.path.join(tempfile.gettempdir(), f"bot_export_{int(time.time())}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(src_dir):
            dirs[:] = [d for d in dirs if d not in EXPORT_EXCLUDE_DIRS and not d.startswith(".")]
            for fname in files:
                if fname in EXPORT_EXCLUDE_FILES or fname.endswith((".zip", ".pyc")):
                    continue
                full = os.path.join(root, fname)
                arcname = os.path.relpath(full, src_dir)
                try:
                    zf.write(full, arcname)
                except Exception:
                    continue  # skip any file that vanished/locked mid-walk
    return zip_path


def _scan_export_code_stats(src_dir: str):
    """Walk the same file set /export zips (source .py files only, same
    excludes) and return light stats about the codebase: how many files,
    total lines, a rough function/handler count, and the most recent
    modification time across those files (used as the "code last updated"
    timestamp — more meaningful than the export zip's own mtime, which is
    always "just now" since it's freshly built on every run)."""
    total_files = 0
    total_lines = 0
    total_funcs = 0
    latest_mtime = 0.0
    for root, dirs, files in os.walk(src_dir):
        dirs[:] = [d for d in dirs if d not in EXPORT_EXCLUDE_DIRS and not d.startswith(".")]
        for fname in files:
            if not fname.endswith(".py"):
                continue
            full = os.path.join(root, fname)
            try:
                mtime = os.path.getmtime(full)
                latest_mtime = max(latest_mtime, mtime)
                with open(full, "r", encoding="utf-8", errors="ignore") as fh:
                    lines = fh.readlines()
                total_files += 1
                total_lines += len(lines)
                total_funcs += sum(1 for ln in lines if re.match(r"\s*(async\s+)?def\s+\w+\(", ln))
            except Exception:
                continue
    return {
        "files": total_files,
        "lines": total_lines,
        "funcs": total_funcs,
        "last_updated": to_ist(datetime.utcfromtimestamp(latest_mtime)).strftime("%d %b %Y, %H:%M") if latest_mtime else "?",
    }


async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Owner-only — zips the bot's source code (never user downloads,
    backups, or the live data file) and DMs it to the owner. Wrapped
    end-to-end in error handling so a failure always tells the admin what
    went wrong instead of silently doing nothing.

    After the zip is sent, a small follow-up message is also sent with
    when the code was last modified (based on source file mtimes, not the
    zip's own build time) plus a light summary of the codebase (file/line/
    function counts, export size)."""
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("🚫 " + to_small_caps("owner only."))
        return
    status = await update.message.reply_text("📦 " + to_small_caps("building export..."))
    src_dir = os.path.dirname(os.path.abspath(__file__))
    zip_path = None
    try:
        zip_path = _build_export_zip(src_dir)
        size = os.path.getsize(zip_path)
        if size > EXPORT_MAX_BYTES:
            await status.edit_text(
                "⚠️ " + to_small_caps(f"export is {size / 1024 / 1024:.1f}mb — too large for telegram's ~50mb bot upload limit.")
                + "\n" + to_small_caps("try removing unused files from the project folder and run /export again.")
            )
            return
        with open(zip_path, "rb") as f:
            await context.bot.send_document(chat_id=update.effective_user.id, document=f, filename="bot_source.zip")
        try:
            await status.delete()
        except Exception:
            pass
        if update.effective_chat.id != update.effective_user.id:
            await update.message.reply_text("✅ " + to_small_caps("sent to your dm."))
        # Follow-up: last-updated timestamp + light code details, sent as a
        # separate message right under the exported file.
        try:
            stats = _scan_export_code_stats(src_dir)
            details_text = (
                "🗂 " + to_small_caps("code details") + "\n"
                f"🕒 " + to_small_caps("last updated") + f": {stats['last_updated']} IST\n"
                f"📄 " + to_small_caps("files") + f": {stats['files']}\n"
                f"📃 " + to_small_caps("total lines") + f": {stats['lines']}\n"
                f"⚙️ " + to_small_caps("functions") + f": {stats['funcs']}\n"
                f"📦 " + to_small_caps("export size") + f": {size / 1024:.0f} kb"
            )
            await context.bot.send_message(chat_id=update.effective_user.id, text=details_text)
        except Exception:
            # Purely informational — never let this break the actual export.
            log.warning("Could not send export code-details follow-up message", exc_info=True)
    except Forbidden:
        await status.edit_text(
            "⚠️ " + to_small_caps("couldn't dm you the export — start a private chat with the bot first, then try again.")
        )
    except Exception as e:
        log.exception("Export failed")
        log_error("unhandled", f"/export failed: {e}")
        await status.edit_text("❌ " + to_small_caps("export failed — see the activity log for details."))
    finally:
        if zip_path and os.path.exists(zip_path):
            try:
                os.remove(zip_path)
            except Exception:
                pass


# ----------------------------------------------------------------------------
# PDF #6 — Blocked users list, plus admin-command blocking of links/domains
# ----------------------------------------------------------------------------

async def cmd_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /block <user_id | link | domain>")
        return
    target = context.args[0]
    if target.isdigit():
        uid_int = int(target)
        if uid_int not in BOT_DATA["blocked"]:
            BOT_DATA["blocked"].append(uid_int)
            save_data()
        await update.message.reply_text(f"✅ User {uid_int} blocked.")
        await log_event(context, f"🚫 Admin blocked user {uid_int}")
    elif target.startswith("http://") or target.startswith("https://"):
        if target not in BOT_DATA["blocked_links"]:
            BOT_DATA["blocked_links"].append(target)
            save_data()
        await update.message.reply_text(f"✅ Link blocked: {target}")
        await log_event(context, f"🚫 Admin blocked link {target}")
    else:
        if target not in BOT_DATA["blocked_domains"]:
            BOT_DATA["blocked_domains"].append(target)
            save_data()
        await update.message.reply_text(f"✅ Domain blocked: {target}")
        await log_event(context, f"🚫 Admin blocked domain {target}")


async def cmd_unblock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /unblock <user_id | link | domain>")
        return
    target = context.args[0]
    removed = False
    if target.isdigit() and int(target) in BOT_DATA["blocked"]:
        BOT_DATA["blocked"].remove(int(target))
        removed = True
    if target in BOT_DATA["blocked_links"]:
        BOT_DATA["blocked_links"].remove(target)
        removed = True
    if target in BOT_DATA["blocked_domains"]:
        BOT_DATA["blocked_domains"].remove(target)
        removed = True
    if removed:
        save_data()
        await update.message.reply_text(f"✅ Unblocked: {target}")
        await log_event(context, f"✅ Admin unblocked {target}")
    else:
        await update.message.reply_text("Wasn't on any blocked list.")


async def handle_restore_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_owner(user.id):
        return
    if update.effective_chat.type != "private":
        return
    if context.user_data.get("awaiting") or context.user_data.get("btn_flow"):
        return  # owner mid another flow — don't collide

    doc = update.message.document
    fname = (doc.file_name or "").lower() if doc else ""
    if not doc or not (fname.endswith(".json") or fname.endswith(".json.enc")):
        return

    tg_file = await doc.get_file()
    raw_path = os.path.join(tempfile.gettempdir(), f"incoming_{int(time.time())}_{fname}")
    await tg_file.download_to_drive(raw_path)

    try:
        with open(raw_path, "rb") as f:
            file_bytes = f.read()
        if fname.endswith(".json.enc"):
            try:
                file_bytes = decrypt_backup_bytes(file_bytes)
            except ValueError:
                await update.message.reply_text(
                    to_small_caps("❌ this backup is encrypted but the `cryptography` package isn't installed here — run `pip install cryptography` and try again.")
                )
                os.remove(raw_path)
                return
            except InvalidToken:
                await update.message.reply_text(
                    to_small_caps("❌ couldn't decrypt this backup — it was likely made with a different bot's backup.key. restore cancelled.")
                )
                os.remove(raw_path)
                return
        incoming = json.loads(file_bytes.decode("utf-8"))
    except Exception:
        await update.message.reply_text(to_small_caps("❌ this is not a valid backup file."))
        os.remove(raw_path)
        return

    # 📦 Update Backup split files — sent one at a time, each merges into
    # the CURRENT live data instead of replacing everything (unlike a full
    # combined /database backup, which replaces it all).
    if fname == SEED_SETTINGS_FILE:
        incoming = dict(incoming)
        incoming["users"] = BOT_DATA.get("users", {})
    elif fname == SEED_USERS_FILE:
        merged_incoming = json.loads(json.dumps(BOT_DATA))
        merged_incoming["users"] = incoming.get("users", incoming)
        incoming = merged_incoming

    if not set(DEFAULT_DATA.keys()).issubset(set(incoming.keys())):
        await update.message.reply_text(to_small_caps("❌ this doesn't look like a valid backup file. restore cancelled."))
        os.remove(raw_path)
        return

    context.user_data["pending_restore"] = incoming
    os.remove(raw_path)

    cur_users, new_users = len(BOT_DATA["users"]), len(incoming.get("users", {}))
    cur_admins, new_admins = len(BOT_DATA["admins"]), len(incoming.get("admins", []))
    text = (
        to_small_caps("⚠️ restore confirmation") + "\n\n"
        + f"{to_small_caps('users')}: {cur_users} → {new_users}\n{to_small_caps('admins')}: {cur_admins} → {new_admins}\n\n"
        + to_small_caps("⚠️ this will completely REPLACE the current live data.") + "\n" + to_small_caps("(the current data will be backed up first.)")
    )
    kb = InlineKeyboardMarkup(
        [[styled_button("✅ Confirm Restore", callback_data="restore_confirm"),
          styled_button("❌ Cancel", callback_data="restore_cancel")]]
    )
    await update.message.reply_text(text, reply_markup=kb)


async def cb_restore_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_DATA
    query = update.callback_query
    await query.answer()
    if not is_owner(update.effective_user.id):
        return
    incoming = context.user_data.pop("pending_restore", None)
    if incoming is None:
        await query.edit_message_text(to_small_caps("this has expired — please send the file again."))
        return
    before_path = make_backup_snapshot(reason="pre_restore")
    before_users = len(BOT_DATA["users"])
    BOT_DATA = _deep_merge_defaults(incoming)
    save_data()
    BOT_DATA["restore_log"].append(
        {"by": update.effective_user.id, "at": datetime.utcnow().isoformat(),
         "before_users": before_users, "after_users": len(BOT_DATA["users"])}
    )
    save_data()
    await query.edit_message_text(
        f"✅ Restore complete.\nBefore: {before_users} → After: {len(BOT_DATA['users'])}\n"
        f"Pre-restore snapshot: {os.path.basename(before_path)}\n\nConfirm karne ke liye /dbstatus chalao."
    )


async def cb_restore_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("pending_restore", None)
    await query.edit_message_text(to_small_caps("restore cancelled."))


async def scheduled_backup_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        path = make_backup_snapshot(reason="scheduled")
        if OWNER_ID:
            with open(path, "rb") as f:
                await context.bot.send_document(chat_id=OWNER_ID, document=f, filename=os.path.basename(path), caption="🗄 Scheduled backup snapshot.")
    except Exception:
        log.exception("Scheduled backup failed")


async def inactive_reengage_job(context: ContextTypes.DEFAULT_TYPE):
    """#15 — lightweight re-engagement, reuses render_menu, no new sending logic."""
    days = BOT_DATA["settings"].get("inactive_reengage_days", 0)
    if not days:
        return
    cutoff = datetime.utcnow() - timedelta(days=days)
    for uid, info in BOT_DATA["users"].items():
        try:
            last_active = datetime.fromisoformat(info.get("last_active"))
        except Exception:
            continue
        last_reengaged = info.get("last_reengaged")
        already_today = last_reengaged and (datetime.utcnow() - datetime.fromisoformat(last_reengaged)) < timedelta(days=days)
        if last_active < cutoff and not already_today:
            try:
                await render_menu(context, int(uid), "start")
                info["last_reengaged"] = datetime.utcnow().isoformat()
            except Exception:
                pass
    save_data()


# ----------------------------------------------------------------------------
# App wiring
# ----------------------------------------------------------------------------


__all__ = [_n for _n in dir() if not _n.startswith("__")]
