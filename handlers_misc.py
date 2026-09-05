from ig_monitor import *


async def _render_ai_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Owner/admin live control-room dashboard with the bot-wide premium
    typography, pointer + underline convention, and a single Telegram
    blockquote card. Rendering is read-only and never blocks downloading."""
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("🔒 " + to_small_caps("admin only."), show_alert=True)
        return

    now = datetime.utcnow()
    day_ago = now - timedelta(hours=24)
    _ig_monitor_prune(now)
    st = _ig_monitor_state()

    def recent(ts):
        dt = _parse_iso(ts)
        return bool(dt and dt >= day_ago)

    users = BOT_DATA.get("users", {})
    active_24h = sum(1 for u in users.values() if recent(u.get("last_active")))
    new_users_24h = sum(1 for u in users.values() if recent(u.get("joined")))
    events_24h = [e for e in BOT_DATA.get("activity_log", []) if recent(e.get("time"))]
    errors_24h = [e for e in BOT_DATA.get("error_log", []) if recent(e.get("time"))]
    download_errors_24h = [e for e in errors_24h if e.get("kind") in ("download", "ytdlp_no_formats")]

    request_count = len(events_24h)
    monitor_failures = st.get("failures", [])
    monitor_successes = st.get("successes", [])
    systemic = [e for e in monitor_failures if e.get("category") == "instagram_extractor"]
    distinct_failed_users = len({e.get("user_id") for e in systemic if e.get("user_id")})
    total_health_events = len(monitor_failures) + len(monitor_successes)
    health_rate = (len(monitor_successes) / total_health_events * 100) if total_health_events else 100.0

    if st.get("outage_active"):
        status = "🔴 " + to_small_caps("Instagram downloads unstable")
        state_label = "🔴 " + to_small_caps("Critical")
    elif systemic and len(systemic) >= max(1, int(_ig_monitor_cfg("instagram_monitor_threshold", 5)) - 1):
        status = "🟡 " + to_small_caps("Instagram being watched closely")
        state_label = "🟡 " + to_small_caps("Warning")
    else:
        status = "🟢 " + to_small_caps("Instagram downloads operational")
        state_label = "🟢 " + to_small_caps("Operational")

    last_failure = monitor_failures[-1] if monitor_failures else None
    last_error = html.escape(str(st.get("last_error_detail") or "—")[:120])
    last_category = html.escape(str((last_failure or {}).get("category") or "—"))

    def row(icon, label, value):
        return f"{icon} <u>➤ {to_small_caps(label)}</u> : {value}"

    lines = [
        "🤖 " + to_title_small_caps("AI Check"),
        "",
        "<u>📊 " + to_title_small_caps("Admin Dashboard") + "</u>",
        row("📡", "Instagram Status", status),
        row("⏱", "Bot Uptime", html.escape(human_uptime())),
        row("👥", "Total Users", len(users)),
        row("🆕", "New Users · 24h", new_users_24h),
        row("🟢", "Active Users · 24h", active_24h),
        row("🎬", "Reel Requests · 24h", request_count),
        row("❌", "Download Errors · 24h", len(download_errors_24h)),
        row("📈", "Lifetime Reels Delivered", BOT_DATA.get("metrics", {}).get("reels_downloaded", 0)),
        "",
        "<u>🧠 " + to_title_small_caps("Smart Instagram Monitor") + "</u>",
        row("🚦", "State", state_label),
        row("📉", "Failures · Window", len(monitor_failures)),
        row("✓", "Successes · Window", len(monitor_successes)),
        row("🎯", "Failure Threshold", int(_ig_monitor_cfg("instagram_monitor_threshold", 5))),
        row("🕒", "Detection Window", f"{int(_ig_monitor_cfg('instagram_monitor_window_minutes', 10))} min"),
        row("🔁", "Recovery Threshold", f"{int(_ig_monitor_cfg('instagram_monitor_recovery_successes', 3))} successes"),
        row("⏳", "Alert Cooldown", f"{int(_ig_monitor_cfg('instagram_monitor_cooldown_minutes', 60))} min"),
        row("👤", "Affected Users · Extractor", distinct_failed_users),
        row("📊", "Health Rate · Window", f"{health_rate:.0f}%"),
        row("🧩", "Last Error Type", last_category),
        row("📝", "Last Error", last_error),
    ]
    if st.get("last_alert_at"):
        lines.append(row("🚨", "Last Alert", html.escape(str(st.get("last_alert_at")))))
    if st.get("last_recovery_at"):
        lines.append(row("🟢", "Last Recovery", html.escape(str(st.get("last_recovery_at")))))

    # Keep the entire dashboard inside the same native Telegram quote/card,
    # matching the bot's existing premium message convention.
    text = "<blockquote>" + "\n".join(lines) + "</blockquote>"
    kb = InlineKeyboardMarkup([
        [styled_button("🔄 " + to_small_caps("Refresh"), callback_data="ai_check")],
        [styled_button("📊 " + to_small_caps("Statistics"), callback_data="adm_stats"),
         styled_button("📜 " + to_small_caps("Activity Log"), callback_data="adm_activity")],
        back_row(),
        home_row(),
    ])
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)


async def cb_ai_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _render_ai_check(update, context)


# ----------------------------------------------------------------------------
# Support ticket system
# ----------------------------------------------------------------------------


__all__ = [_n for _n in dir() if not _n.startswith("__")]
